import sqlite3
from flask import Flask, render_template, request, redirect, flash, url_for
from datetime import datetime
import re, os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


app = Flask(__name__)
app.secret_key = os.urandom(24)

DB_FILE = "datos.db"

def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS registros (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sic TEXT NOT NULL,
            fecha TEXT NOT NULL,
            oc_cliente TEXT NOT NULL,
            cliente TEXT NOT NULL,
            descripcion TEXT NOT NULL,
            cantidad TEXT
        )
        """)
    print("DB inicializada")

def generar_sic():
    ahora = datetime.now()
    fecha_display = ahora.strftime("%d/%m/%Y")
    fecha_id = ahora.strftime("%Y%m%d")

    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM registros WHERE fecha = ?", (fecha_display,))
        contador = c.fetchone()[0] + 1

    sic = f"{fecha_id}-{contador:03d}"
    return fecha_display, sic

def parse_linea_material(linea):
    linea = linea.strip()
    if not linea:
        return None, None
    partes = re.split(r'[\t;]+|\s{2,}', linea)
    if len(partes) >= 2:
        return partes[0].strip(), partes[1].strip()
    partes = linea.rsplit(" ", 1)
    if len(partes) == 2:
        return partes[0].strip(), partes[1].strip()
    return linea, ""

@app.route('/')
def index():
    fecha, sic = generar_sic()
    return render_template("form.html", fecha=fecha, sic=sic)

@app.route('/guardar', methods=['POST'])
def guardar():
    oc_cliente = request.form.get('oc_cliente', '').strip()
    cliente = request.form.get('cliente', '').strip()
    materiales_texto = request.form.get('materiales', '').strip()

    if not oc_cliente or not cliente:
        flash("OC Cliente y Cliente son obligatorios.", "error")
        return redirect(url_for('index'))

    fecha, sic = generar_sic()
    materiales = []
    for linea in materiales_texto.splitlines():
        desc, cant = parse_linea_material(linea)
        if desc and (desc.strip() or cant.strip()):
            materiales.append((desc, cant))

    if not materiales:
        flash("No se detectaron materiales válidos.", "error")
        return redirect(url_for('index'))

    with sqlite3.connect(DB_FILE) as conn:
        for desc, cant in materiales:
            conn.execute("""
                INSERT INTO registros (sic, fecha, oc_cliente, cliente, descripcion, cantidad)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (sic, fecha, oc_cliente, cliente, desc, cant))
        conn.commit()

    # Enviar correo con los datos guardados
    enviar_correo(sic, oc_cliente, cliente, materiales)


    flash(f"Guardado correctamente. SIC: {sic}. Filas añadidas: {len(materiales)}", "success")
    return redirect(url_for('index'))

def enviar_correo(sic, oc_cliente, cliente, materiales):
    """
    Envía un correo con el SIC en el asunto y una tabla HTML de materiales.
    materiales: lista de tuplas (descripcion, cantidad)
    """
    remitente = "flix.federico@gmail.com"
    destinatario = "abastecimiento@flix-instrumentacion.com"
    asunto = f"Nuevo registro SIC {sic}"

    # Construir tabla HTML
    filas = "".join([f"<tr><td>{desc}</td><td>{cant}</td></tr>" for desc, cant in materiales])
    tabla_html = f"""
    <html>
      <body>
        <p><strong>OC Cliente:</strong> {oc_cliente}<br>
        <strong>Cliente:</strong> {cliente}<br>
        <strong>SIC:</strong> {sic}</p>
        <table border="1" cellspacing="0" cellpadding="4">
          <tr><th>Descripción</th><th>Cantidad</th></tr>
          {filas}
        </table>
      </body>
    </html>
    """

    msg = MIMEMultipart("alternative")
    msg["From"] = remitente
    msg["To"] = destinatario
    msg["Subject"] = asunto
    msg.attach(MIMEText(tabla_html, "html"))

    try:
        # ⚠️ IMPORTANTE: necesitarás una "App Password" de Gmail (no la contraseña normal)
        smtp_server = smtplib.SMTP("smtp.gmail.com", 587)
        smtp_server.starttls()
        smtp_server.login(remitente, "tcci cuvq opal ifgq")
        smtp_server.sendmail(remitente, destinatario, msg.as_string())
        smtp_server.quit()
        print(f"Correo enviado a {destinatario} con SIC {sic}")
    except Exception as e:
        print("Error al enviar correo:", e)




if __name__ == "__main__":
    init_db()
    app.run(debug=True)
