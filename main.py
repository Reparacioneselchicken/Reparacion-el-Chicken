from flask import Flask, render_template, request, redirect, url_for
import sqlite3

app = Flask(__name__)

def get_db_connection():
    conn = sqlite3.connect('taller.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    # Tabla de diagnósticos
    conn.execute('''
        CREATE TABLE IF NOT EXISTS diagnosticos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente TEXT NOT NULL,
            telefono TEXT NOT NULL,
            marca TEXT NOT NULL,
            modelo TEXT NOT NULL,
            falla TEXT NOT NULL,
            estado TEXT NOT NULL
        )
    ''')
    # Tabla de inventario
    conn.execute('''
        CREATE TABLE IF NOT EXISTS inventario (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            repuesto TEXT NOT NULL,
            compatible TEXT NOT NULL,
            precio_compra REAL NOT NULL,
            precio_venta REAL NOT NULL,
            cantidad INTEGER NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

init_db()

@app.route("/")
def inicio():
    conn = get_db_connection()
    reparaciones = conn.execute('SELECT * FROM diagnosticos ORDER BY id DESC LIMIT 5').fetchall()
    totales = conn.execute('SELECT COUNT(*) FROM diagnosticos').fetchone()[0]
    pendientes = conn.execute("SELECT COUNT(*) FROM diagnosticos WHERE estado != 'Terminado'").fetchone()[0]
    terminadas = conn.execute("SELECT COUNT(*) FROM diagnosticos WHERE estado = 'Terminado'").fetchone()[0]
    clientes_unicos = conn.execute('SELECT COUNT(DISTINCT cliente) FROM diagnosticos').fetchone()[0]
    conn.close()
    
    return render_template(
        "index.html", 
        reparaciones=reparaciones,
        totales=totales,
        pendientes=pendientes,
        terminadas=terminadas,
        clientes_unicos=clientes_unicos
    )

@app.route("/diagnostico", methods=["GET", "POST"])
def diagnostico():
    if request.method == "POST":
        cliente = request.form['cliente']
        telefono = request.form['telefono']
        marca = request.form['marca']
        modelo = request.form['modelo']
        falla = request.form['falla']
        estado = request.form['estado']

        conn = get_db_connection()
        conn.execute('''
            INSERT INTO diagnosticos (cliente, telefono, marca, modelo, falla, estado)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (cliente, telefono, marca, modelo, falla, estado))
        conn.commit()
        conn.close()
        return redirect(url_for('inicio'))

    return render_template("diagnostico.html")

@app.route("/reparaciones")
def reparaciones():
    conn = get_db_connection()
    lista = conn.execute('SELECT * FROM diagnosticos ORDER BY id DESC').fetchall()
    conn.close()
    return render_template("reparaciones.html", reparaciones=lista)

@app.route("/cambiar_estado/<int:id>", methods=["POST"])
def cambiar_estado(id):
    nuevo_estado = request.form['nuevo_estado']
    conn = get_db_connection()
    conn.execute('UPDATE diagnosticos SET estado = ? WHERE id = ?', (nuevo_estado, id))
    conn.commit()
    conn.close()
    return redirect(url_for('reparaciones'))

@app.route("/eliminar/<int:id>", methods=["POST"])
def eliminar(id):
    conn = get_db_connection()
    conn.execute('DELETE FROM diagnosticos WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('reparaciones'))

@app.route("/clientes")
def clientes():
    conn = get_db_connection()
    lista_clientes = conn.execute('''
        SELECT 
            cliente, 
            telefono, 
            COUNT(id) as total_equipos 
        FROM diagnosticos 
        GROUP BY cliente, telefono 
        ORDER BY total_equipos DESC
    ''').fetchall()
    conn.close()
    return render_template("clientes.html", clientes=lista_clientes)

# --- RUTAS DE INVENTARIO ---

@app.route("/inventario", methods=["GET", "POST"])
def inventario():
    conn = get_db_connection()
    if request.method == "POST":
        repuesto = request.form['repuesto']
        compatible = request.form['compatible']
        precio_compra = request.form['precio_compra']
        precio_venta = request.form['precio_venta']
        cantidad = request.form['cantidad']

        conn.execute('''
            INSERT INTO inventario (repuesto, compatible, precio_compra, precio_venta, cantidad)
            VALUES (?, ?, ?, ?, ?)
        ''', (repuesto, compatible, precio_compra, precio_venta, cantidad))
        conn.commit()
        conn.close()
        return redirect(url_for('inventario'))

    items = conn.execute('SELECT * FROM inventario ORDER BY id DESC').fetchall()
    conn.close()
    return render_template("inventario.html", inventario=items)

@app.route("/eliminar_repuesto/<int:id>", methods=["POST"])
def eliminar_repuesto(id):
    conn = get_db_connection()
    conn.execute('DELETE FROM inventario WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('inventario'))

@app.route("/historial")
def historial():
    conn = get_db_connection()
    # Trae solo los trabajos con estado 'Terminado'
    terminados = conn.execute("SELECT * FROM diagnosticos WHERE estado = 'Terminado' ORDER BY id DESC").fetchall()
    total_terminados = len(terminados)
    conn.close()
    return render_template("historial.html", reparaciones=terminados, total=total_terminados)

# --- RUTA PÚBLICA PARA CLIENTES ---

@app.route("/consultar", methods=["GET", "POST"])
def consultar():
    equipo = None
    error = None
    
    if request.method == "POST":
        busqueda = request.form.get('busqueda', '').strip()
        
        # Limpiamos si el cliente escribió "CH-001" o solo "1"
        folio_id = busqueda.upper().replace("CH-00", "").replace("CH-0", "").replace("CH-", "")
        
        conn = get_db_connection()
        # Busca por ID de folio o por número de teléfono
        equipo = conn.execute(
            'SELECT * FROM diagnosticos WHERE id = ? OR telefono = ?', 
            (folio_id, busqueda)
        ).fetchone()
        conn.close()
        
        if not equipo:
            error = "No encontramos ningún registro con ese Folio o Teléfono. Verifica los datos."

    return render_template("consulta_cliente.html", equipo=equipo, error=error)

# --- RUTA DE COTIZACIONES ---

@app.route("/cotizacion", methods=["GET", "POST"])
def cotizacion():
    resultado = None
    if request.method == "POST":
        repuesto_costo = float(request.form.get('repuesto_costo', 0))
        mano_obra = float(request.form.get('mano_obra', 0))
        resultado = repuesto_costo + mano_obra
        
    return render_template("cotizacion.html", resultado=resultado)

from twilio.twml.messaging_response import MessagingResponse

# --- RUTA PARA EL BOT DE WHATSAPP ---

@app.route("/whatsapp", methods=["POST"])
def whatsapp_bot():
    mensaje_cliente = request.values.get('Body', '').strip().lower()
    numero_cliente = request.values.get('From', '').replace('whatsapp:', '').strip()
    
    resp = MessagingResponse()
    msg = resp.message()

    # Opción 1 o consulta directa por Folio/Teléfono
    if mensaje_cliente == '1':
        conn = get_db_connection()
        equipo = conn.execute(
            'SELECT * FROM diagnosticos WHERE telefono = ? ORDER BY id DESC LIMIT 1', 
            (numero_cliente,)
        ).fetchone()
        conn.close()

        if equipo:
            msg.body(f"📱 *Estado de tu equipo (Folio CH-{equipo['id']}):*\n"
                     f"• Marca/Modelo: {equipo['marca']} {equipo['modelo']}\n"
                     f"• Estado actual: *{equipo['estado']}*\n\n"
                     f"Para más detalles entra a: https://chickenreparacion3292.pythonanywhere.com/consultar")
        else:
            msg.body("No encontramos ninguna reparación vinculada a tu número de WhatsApp. "
                     "Si tienes un número de folio, escríbelo directamente (ejemplo: 5 o CH-5).")

    # Opción 2: Horarios y Ubicación
    elif mensaje_cliente == '2':
        msg.body("📍 *Ubicación y Horarios - El Chicken*\n\n"
                 "⏰ Lunes a Sábado: 9:00 AM - 7:00 PM\n"
                 "📍 Dirección: [Escribe aquí tu dirección completa]\n"
                 "📞 Teléfono del taller: [Escribe tu número principal]")

    # Opción 3: Enlace directo
    elif mensaje_cliente == '3':
        msg.body("Consulta el estado detallado de tu teléfono ingresando aquí:\n"
                 "https://chickenreparacion3292.pythonanywhere.com/consultar")

    # Menú Principal (Si escribe hola o cualquier otra cosa)
    else:
        msg.body("¡Hola! 🐔 Bienvenido a *Reparaciones El Chicken*.\n\n"
                 "¿En qué te podemos ayudar? Responde con el número de opción:\n\n"
                 "1️⃣ Consultar estado de mi equipo\n"
                 "2️⃣ Ver horarios y ubicación del taller\n"
                 "3️⃣ Ver enlace de consulta pública\n\n"
                 "_Escribe 1, 2 o 3 para seleccionar._")

    return str(resp)

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)