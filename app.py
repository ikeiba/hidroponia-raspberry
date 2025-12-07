# app.py (Versión actualizada)
import os
from flask import Flask, render_template, request, jsonify
from hardware import controlador
from data import influx_reader  # <--- IMPORTAR EL NUEVO MODULO

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, "templates"),
    static_folder=os.path.join(BASE_DIR, "static"),
)

# --- RUTAS DE VISTAS ---

@app.route("/")
def index():
    # ... (Tu código existente del index se mantiene igual) ...
    # Solo asegúrate de añadir un enlace en index.html para ir a /graficas
    try:
        estado = controlador.get_estado()
    except Exception:
        estado = {}
    
    if not isinstance(estado, dict): estado = {}

    contexto = {
        "temp":         estado.get("temp"),
        "tds":          estado.get("tds"),
        "bomba_on":     estado.get("bomba_on", False),
        "led_rojo_on":  estado.get("led_rojo_on", False),
        "led_verde_on": estado.get("led_verde_on", False),
        "servo_count":  estado.get("servo_count", 0),
    }
    return render_template("index.html", **contexto)

@app.route("/graficas")
def pagina_graficas():
    """ Renderiza la página visual de gráficas """
    return render_template("graficas.html")

# --- API ENDPOINTS (JSON) ---

@app.route("/api/historial")
def api_historial():
    """
    Endpoint llamado por JS.
    Ejemplo: /api/historial?sensor=temperatura&rango=24h
    """
    sensor = request.args.get("sensor", "temperatura")
    rango = request.args.get("rango", "1h")
    
    datos = influx_reader.obtener_historial(sensor, rango)
    return jsonify(datos)


if __name__ == "__main__":
    print("🚀 Iniciando Flask + Controlador...")
    controlador.iniciar() # <--- MOVIDO AQUÍ PARA SEGURIDAD
    app.run(host="0.0.0.0", port=8000, debug=True, use_reloader=False)