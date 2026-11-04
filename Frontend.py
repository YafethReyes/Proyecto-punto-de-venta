import customtkinter as ctk
from tkinter import ttk, messagebox
import backend

ctk.set_appearance_mode("light")
ctk.set_default_color_theme("green")

app = ctk.CTk()
app.title("Punto de Venta")
app.geometry("1000x650")

# El carrito es la lista que maneja el backend
carrito = []


# ---------- funciones ----------

def agregar_producto():
    codigo = entry_codigo.get().strip()

    if codigo == "":
        return

    try:
        error = backend.agregar_al_carrito(carrito, codigo, 1)
    except Exception as e:
        messagebox.showerror("Error", f"No se pudo conectar a la base de datos:\n{e}")
        return

    if error:
        messagebox.showwarning("Aviso", error)

    entry_codigo.delete(0, "end")
    actualizar_tabla()
    entry_codigo.focus()


def eliminar_producto():
    seleccion = tabla.selection()

    if not seleccion:
        messagebox.showwarning("Aviso", "Selecciona un producto.")
        return

    # El iid de cada fila es el ID_PRODUCTO
    id_producto = int(seleccion[0])
    backend.quitar_del_carrito(carrito, id_producto)
    actualizar_tabla()


def actualizar_tabla():
    for fila in tabla.get_children():
        tabla.delete(fila)

    for p in carrito:
        tabla.insert("", "end", iid=str(p["ID_PRODUCTO"]), values=(
            p["CODIGO_BARRAS"],
            p["DESCRIPCION"],
            p["CANTIDAD"],
            f"${p['PRECIO']:.2f}",
            f"${p['IMPORTE']:.2f}"
        ))

    subtotal, iva, total = backend.calcular_totales(carrito)

    lbl_subtotal.configure(text=f"Subtotal: ${subtotal:.2f}")
    lbl_iva.configure(text=f"IVA: ${iva:.2f}")
    lbl_total.configure(text=f"TOTAL: ${total:.2f}")


def limpiar_venta():
    carrito.clear()
    actualizar_tabla()
    entry_codigo.focus()


def guardar_venta():
    if not carrito:
        messagebox.showwarning("Aviso", "No hay productos.")
        return

    try:
        id_venta = backend.guardar_venta(carrito)
    except Exception as error:
        messagebox.showerror("Error", str(error))
        return

    messagebox.showinfo("Éxito", f"Venta #{id_venta} guardada.")
    carrito.clear()
    actualizar_tabla()
    entry_codigo.focus()


# ---------- interfaz ----------

# encabezado

frame_header = ctk.CTkFrame(app, fg_color="#245743")
frame_header.pack(fill="x")

ctk.CTkLabel(
    frame_header,
    text="🛒 PUNTO DE VENTA",
    font=("Arial", 25, "bold"),
    text_color="white"
).pack(pady=20)


# código de barras

frame_codigo = ctk.CTkFrame(app)
frame_codigo.pack(fill="x", padx=20, pady=15)

ctk.CTkLabel(
    frame_codigo,
    text="Código de barras:"
).pack(side="left", padx=10)

entry_codigo = ctk.CTkEntry(
    frame_codigo,
    placeholder_text="Escanear o escribir código...",
    width=300
)
entry_codigo.pack(side="left", padx=10, pady=15)

entry_codigo.bind("<Return>", lambda event: agregar_producto())

ctk.CTkButton(
    frame_codigo,
    text="Agregar",
    command=agregar_producto
).pack(side="left", padx=10)


# tabla de productos

ctk.CTkLabel(
    app,
    text="Productos de la venta",
    font=("Arial", 20, "bold"),
    text_color="#245743"
).pack(pady=10)

columnas = ("Código", "Descripción", "Cantidad", "Precio", "Importe")

tabla = ttk.Treeview(
    app,
    columns=columnas,
    show="headings",
    height=10
)

for col in columnas:
    tabla.heading(col, text=col)
    tabla.column(col, width=170, anchor="center")

tabla.pack(fill="both", expand=True, padx=20, pady=10)


# botones y totales

frame_inferior = ctk.CTkFrame(app, fg_color="transparent")
frame_inferior.pack(fill="x", padx=20, pady=15)

ctk.CTkButton(
    frame_inferior,
    text="Eliminar producto",
    command=eliminar_producto,
    fg_color="#C84B48"
).pack(side="left", padx=5)

ctk.CTkButton(
    frame_inferior,
    text="Limpiar venta",
    command=limpiar_venta,
    fg_color="gray"
).pack(side="left", padx=5)

frame_totales = ctk.CTkFrame(frame_inferior)
frame_totales.pack(side="right", padx=10)

lbl_subtotal = ctk.CTkLabel(frame_totales, text="Subtotal: $0.00")
lbl_subtotal.pack(pady=5)

lbl_iva = ctk.CTkLabel(frame_totales, text="IVA: $0.00")
lbl_iva.pack(pady=5)

lbl_total = ctk.CTkLabel(
    frame_totales,
    text="TOTAL: $0.00",
    font=("Arial", 20, "bold"),
    text_color="#245743"
)
lbl_total.pack(pady=5)

ctk.CTkButton(
    frame_totales,
    text="GUARDAR VENTA",
    command=guardar_venta,
    height=40
).pack(padx=15, pady=10)


# ---------- iniciar ----------

actualizar_tabla()
entry_codigo.focus()

app.mainloop()
