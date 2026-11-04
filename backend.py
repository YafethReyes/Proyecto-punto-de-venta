import mysql.connector
import os
from decimal import Decimal, ROUND_HALF_UP
from dotenv import load_dotenv

# Lee los datos de conexión del archivo .env
load_dotenv()

IVA = Decimal("0.16")  # 16% de IVA


def conectar():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", 3306)),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", "root"),
        database=os.getenv("DB_NAME", "punto_venta")
    )


def redondear(valor):
    # 2 decimales
    return Decimal(valor).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


# ---------- PRODUCTOS ----------

def buscar_producto(codigo_barras):
    conexion = conectar()
    try:
        cursor = conexion.cursor(dictionary=True)
        cursor.execute("""SELECT ID_PRODUCTO, CODIGO_BARRAS, DESCRIPCION, PRECIO, STOCK
                          FROM PRODUCTOS WHERE CODIGO_BARRAS = %s""", (codigo_barras.strip(),))
        return cursor.fetchone()
    finally:
        conexion.close()


def obtener_productos():
    conexion = conectar()
    try:
        cursor = conexion.cursor(dictionary=True)
        cursor.execute("SELECT ID_PRODUCTO, CODIGO_BARRAS, DESCRIPCION, PRECIO, STOCK FROM PRODUCTOS")
        return cursor.fetchall()
    finally:
        conexion.close()


def agregar_producto(codigo_barras, descripcion, precio, stock):
    codigo_barras = codigo_barras.strip()
    if codigo_barras == "" or descripcion.strip() == "":
        return "Escribe el código y la descripción."
    try:
        precio = redondear(precio)
        stock = int(stock)
    except Exception:
        return "El precio y el stock deben ser números."
    if precio < 0 or stock < 0:
        return "El precio y el stock no pueden ser negativos."

    conexion = conectar()
    try:
        cursor = conexion.cursor()
        cursor.execute("""INSERT INTO PRODUCTOS (CODIGO_BARRAS, DESCRIPCION, PRECIO, STOCK)
                          VALUES (%s, %s, %s, %s)""", (codigo_barras, descripcion.strip(), precio, stock))
        conexion.commit()
        return None
    except mysql.connector.IntegrityError:
        return "Ya existe un producto con ese código de barras."
    finally:
        conexion.close()


def editar_producto(id_producto, descripcion, precio, stock):
    if descripcion.strip() == "":
        return "Escribe la descripción."
    try:
        precio = redondear(precio)
        stock = int(stock)
    except Exception:
        return "El precio y el stock deben ser números."
    if precio < 0 or stock < 0:
        return "El precio y el stock no pueden ser negativos."

    conexion = conectar()
    try:
        cursor = conexion.cursor()
        cursor.execute("UPDATE PRODUCTOS SET DESCRIPCION = %s, PRECIO = %s, STOCK = %s WHERE ID_PRODUCTO = %s",
                       (descripcion.strip(), precio, stock, id_producto))
        conexion.commit()
        return None
    finally:
        conexion.close()


def surtir_stock(codigo_barras, cantidad):
    if cantidad < 1:
        return "La cantidad debe ser mayor a 0."
    conexion = conectar()
    try:
        cursor = conexion.cursor()
        cursor.execute("UPDATE PRODUCTOS SET STOCK = STOCK + %s WHERE CODIGO_BARRAS = %s",
                       (cantidad, codigo_barras.strip()))
        conexion.commit()
        if cursor.rowcount == 0:
            return "Producto no encontrado."
        return None
    finally:
        conexion.close()


def eliminar_producto(id_producto):
                                                # Regresa False si el producto ya aparece en ventas no se puede borrar
    conexion = conectar()
    try:
        cursor = conexion.cursor()
        cursor.execute("DELETE FROM PRODUCTOS WHERE ID_PRODUCTO = %s", (id_producto,))
        conexion.commit()
        return True
    except mysql.connector.IntegrityError:
        return False  # ya tiene ventas
    finally:
        conexion.close()


# ---------- Venta que se está capturando) ----------

def agregar_al_carrito(carrito, codigo_barras, cantidad=1):
    """Agrega un producto al carrito. Si ya estaba, le suma la cantidad.
    Regresa un mensaje de error (texto) o None si todo salió bien."""
    if cantidad < 1:
        return "La cantidad debe ser mayor a 0."

    producto = buscar_producto(codigo_barras)
    if producto is None:
        return "Producto no encontrado."

    # Si ya está en el carrito, sumamos a lo que ya llevaba
    for item in carrito:
        if item["ID_PRODUCTO"] == producto["ID_PRODUCTO"]:
            if item["CANTIDAD"] + cantidad > producto["STOCK"]:
                return "Stock insuficiente. Solo hay " + str(producto["STOCK"]) + " piezas."
            item["CANTIDAD"] += cantidad
            item["IMPORTE"] = redondear(item["PRECIO"] * item["CANTIDAD"])
            return None

    if cantidad > producto["STOCK"]:
        return "Stock insuficiente. Solo hay " + str(producto["STOCK"]) + " piezas."

    carrito.append({
        "ID_PRODUCTO": producto["ID_PRODUCTO"],
        "CODIGO_BARRAS": producto["CODIGO_BARRAS"],
        "DESCRIPCION": producto["DESCRIPCION"],
        "PRECIO": producto["PRECIO"],
        "CANTIDAD": cantidad,
        "IMPORTE": redondear(producto["PRECIO"] * cantidad)})
    return None


def quitar_del_carrito(carrito, id_producto):
    for item in carrito:
        if item["ID_PRODUCTO"] == id_producto:
            carrito.remove(item)
            return


def calcular_totales(carrito):
    """Calcula subtotal, iva y total. Se llama cada vez que se captura un producto."""
    subtotal = Decimal("0")
    for item in carrito:
        subtotal += item["IMPORTE"]
    subtotal = redondear(subtotal)
    iva = redondear(subtotal * IVA)
    total = subtotal + iva
    return subtotal, iva, total


# ---------- VENTA ----------

def guardar_venta(carrito):
    """Guarda la venta completa en una sola transacción:
       1) inserta en VENTAS
       2) por cada producto: actualiza el stock en PRODUCTOS
       3) por cada producto: inserta en DETALLES_VENTA
    Si algo falla, se hace ROLLBACK y no se guarda nada.
    Regresa el ID de la venta."""
    if len(carrito) == 0:
        raise ValueError("El carrito está vacío.")

    subtotal, iva, total = calcular_totales(carrito)

    conexion = conectar()
    cursor = conexion.cursor()
    try:
        conexion.start_transaction()

        # 1) La venta
        cursor.execute("INSERT INTO VENTAS (SUBTOTAL, IVA, TOTAL) VALUES (%s, %s, %s)",
                       (subtotal, iva, total))
        id_venta = cursor.lastrowid

        for item in carrito:
            # 2) Descontar el stock (solo si alcanza, así evitamos stock negativo)
            cursor.execute("""UPDATE PRODUCTOS SET STOCK = STOCK - %s
                              WHERE ID_PRODUCTO = %s AND STOCK >= %s""",
                           (item["CANTIDAD"], item["ID_PRODUCTO"], item["CANTIDAD"]))
            if cursor.rowcount == 0:
                raise ValueError("Stock insuficiente para: " + item["DESCRIPCION"])

            # 3) El detalle
            cursor.execute("""INSERT INTO DETALLES_VENTA (ID_VENTA, ID_PRODUCTO, CANTIDAD, PRECIO, IMPORTE)
                              VALUES (%s, %s, %s, %s, %s)""",
                           (id_venta, item["ID_PRODUCTO"], item["CANTIDAD"], item["PRECIO"], item["IMPORTE"]))

        conexion.commit()
        return id_venta

    except Exception:
        conexion.rollback()  # se deshace todo
        raise                
    finally:
        conexion.close()


def obtener_ventas():
    conexion = conectar()
    try:
        cursor = conexion.cursor(dictionary=True)
        cursor.execute("SELECT ID_VENTA, FECHA, SUBTOTAL, IVA, TOTAL FROM VENTAS ORDER BY ID_VENTA DESC")
        return cursor.fetchall()
    finally:
        conexion.close()


def obtener_detalles(id_venta):
    conexion = conectar()
    try:
        cursor = conexion.cursor(dictionary=True)
        cursor.execute("""SELECT P.CODIGO_BARRAS, P.DESCRIPCION, D.CANTIDAD, D.PRECIO, D.IMPORTE
                          FROM DETALLES_VENTA D
                          JOIN PRODUCTOS P ON P.ID_PRODUCTO = D.ID_PRODUCTO
                          WHERE D.ID_VENTA = %s""", (id_venta,))
        return cursor.fetchall()
    finally:
        conexion.close()

# Ejecuta:  python backend.py
if __name__ == "__main__":
    carrito = []
    for codigo, cant in [("7501000000011", 2), ("7501000000042", 1), ("7501000000011", 1)]:
        error = agregar_al_carrito(carrito, codigo, cant)
        if error:
            print("Error:", error)
        subtotal, iva, total = calcular_totales(carrito)
        print("Subtotal:", subtotal, "| IVA:", iva, "| Total:", total)

    id_venta = guardar_venta(carrito)
    print("Venta guardada con ID:", id_venta)
    for d in obtener_detalles(id_venta):
        print(d)
