from flask import Flask, render_template, request, redirect, url_for
import sqlite3
from datetime import datetime
# ¡Aquí está la librería del bot!
from twilio.twiml.messaging_response import MessagingResponse

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
        folio_id = busqueda.upper().replace("CH-00", "").replace("CH-0", "").replace("CH-", "")
        
        conn = get_db_connection()
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

# --- RUTA PARA EL RECIBO Y GARANTÍA ---

@app.route("/recibo/<int:id>")
def recibo(id):
    conn = get_db_connection()
    equipo = conn.execute('SELECT * FROM diagnosticos WHERE id = ?', (id,)).fetchone()
    conn.close()
    
    if not equipo:
        return "Recibo no encontrado", 404
        
    fecha_hoy = datetime.now().strftime("%d/%m/%Y")
        
    return render_template("recibo.html", equipo=equipo, fecha_hoy=fecha_hoy)

# --- RUTA PARA EL BOT DE WHATSAPP ---
@app.route("/whatsapp", methods=["POST"])
def whatsapp_bot():
    # Capturamos el mensaje del cliente
    mensaje_cliente = request.values.get('Body', '').strip().lower()
    
    # Preparamos la respuesta de WhatsApp
    resp = MessagingResponse()
    
    if mensaje_cliente in ['hola', 'buenas', 'buen dia', 'buenas tardes']:
        resp.message("¡Hola! Bienvenido a Reparaciones El Chicken 🐔.\n\nEscribe tu *número de folio* (ej. 1 o CH-1) o tu *número de teléfono* para consultar el estado de tu equipo.")
    else:
        # Limpiamos el texto por si escriben "CH-1" para que solo quede el número "1"
        busqueda = mensaje_cliente.upper().replace("CH-00", "").replace("CH-0", "").replace("CH-", "")
        
        # Buscamos en la base de datos
        conn = get_db_connection()
        equipo = conn.execute(
            'SELECT * FROM diagnosticos WHERE id = ? OR telefono = ?', 
            (busqueda, mensaje_cliente)
        ).fetchone()
        conn.close()
        
        # Si encontramos el equipo, le armamos un mensaje bonito
        if equipo:
            msg = f"📱 *Equipo:* {equipo['marca']} {equipo['modelo']}\n🛠️ *Falla:* {equipo['falla']}\n📊 *Estado actual:* {equipo['estado']}"
            resp.message(msg)
        else:
            resp.message("No encontré ningún equipo con ese dato 🤔. Verifica tu folio o número e intenta de nuevo.")
            
    return str(resp)

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)