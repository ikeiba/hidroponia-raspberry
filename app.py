# app.py (Versión actualizada)
import os
from flask import Flask, render_template, request, jsonify, redirect, url_for, make_response
from hardware import controlador
from data import influx_reader  # <--- IMPORTAR EL NUEVO MODULO
from data.logger_web import logger, log_buffer # Importamos la lista de memoria
import csv
import io

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, "templates"),
    static_folder=os.path.join(BASE_DIR, "static"),
)

# --- RUTAS DE VISTAS ---

@app.route("/")
def index():
    # 1. Obtenemos el ESTADO (sensores actuales)
    try:
        estado = controlador.get_estado()
    except Exception:
        estado = {}
    if not isinstance(estado, dict): estado = {}

    # 2. Obtenemos la CONFIGURACIÓN (límites)
    try:
        conf = controlador.get_config()
    except Exception:
        conf = {}

    # 3. Preparamos el contexto mezclando ambos
    contexto = {
        # Datos en tiempo real
        "temp":         estado.get("temp"),
        "tds":          estado.get("tds"),
        "bomba_on":     estado.get("bomba_on", False),
        "led_rojo_on":  estado.get("led_rojo_on", False),
        "led_verde_on": estado.get("led_verde_on", False),
        "servo_count":  estado.get("servo_count", 0),
        "ultimo_servo_time": estado.get("ultimo_servo_time", "--:--:--"),
        "cpu_temp":     estado.get("cpu_temp", 0),
        "ram_usage":    estado.get("ram_usage", 0),
        
        # Datos de configuración (límites)
        "CFG_TEMP_MIN": conf.get("TEMP_MIN", 15),
        "CFG_TEMP_MAX": conf.get("TEMP_MAX", 25),
        "CFG_TEMP_EMG": conf.get("TEMP_EMERGENCIA", 30),
        "CFG_TDS_MIN":  conf.get("TDS_MIN", 500),
        "CFG_TDS_ALERT":conf.get("TDS_ALERT", 800)
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


# --- API JSON (Para evitar el parpadeo) ---

@app.route("/api/estado")
def api_estado():
    # Devuelve el estado actual en formato JSON puro
    try:
        data = controlador.get_estado()
        # Aseguramos que data es serializable
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)})

# --- CONFIGURACIÓN ---
@app.route("/config", methods=["GET", "POST"])
def config():
    error_msg = None # Variable para mensajes de error

    if request.method == "POST":
        try:
            # 1. Recogemos y convertimos los datos para poder compararlos
            t_min = float(request.form.get("temp_min"))
            t_max = float(request.form.get("temp_max"))
            tds_min = int(request.form.get("tds_min"))
            tds_alert = int(request.form.get("tds_alert"))
            
            # 2. Validaciones Lógicas (Reglas de Negocio)
            errores = []
            
            if t_min >= t_max:
                errores.append(f"Error Temp: Mínima ({t_min}) >= Máxima ({t_max})")
            
            if tds_min >= tds_alert:
                errores.append(f"Error TDS: Mínimo ({tds_min}) >= Alerta ({tds_alert})")
            
            # 3. Decisión
            if errores:
                # Si hay errores, NO guardamos. Mostramos la web con el aviso.
                cfg_actual = controlador.get_config()
                return render_template("config.html", **cfg_actual, error_msg=" | ".join(errores))

            # 4. Si todo está OK, guardamos
            nueva_conf = {
                "TEMP_MIN": t_min,
                "TEMP_MAX": t_max,
                "TDS_MIN": tds_min,
                "TDS_ALERT": tds_alert,
                "SERVO_COOLDOWN": request.form.get("servo_cd"),
                "TIEMPO_LECTURA": request.form.get("reading_time"),
            }
            controlador.update_config(nueva_conf)
            return redirect(url_for('config'))

        except ValueError:
            cfg_actual = controlador.get_config()
            return render_template("config.html", **cfg_actual, error_msg="Error: Introduce valores numéricos válidos.")

    # Petición GET normal
    cfg_actual = controlador.get_config()
    return render_template("config.html", **cfg_actual)

# --- LOGS ---
@app.route("/logs")
def ver_logs():
    """Renderiza la página de consola visual"""
    return render_template("logs.html")

@app.route("/api/logs")
def api_logs():
    """Devuelve la lista de logs en formato JSON"""
    # Convertimos el deque a lista para que sea serializable
    return jsonify(list(log_buffer))

# --- NUEVA RUTA PARA EL BOTÓN WEB ---
@app.route("/action/toggle", methods=["POST"])
def action_toggle():
    """
    Simula pulsar el botón físico desde la web.
    """
    try:
        controlador.toggle_sistema(origen="WEB")
        return jsonify({"status": "ok", "mensaje": "Sistema conmutado"})
    except Exception as e:
        return jsonify({"status": "error", "mensaje": str(e)}), 500

# --- NUEVA RUTA PARA CSV ---
@app.route("/exportar_csv")
def exportar_csv():
    """
    Genera y descarga un archivo CSV con los datos actuales.
    Usa los mismos parámetros que la gráfica (sensor y rango).
    """
    sensor = request.args.get("sensor", "temperatura")
    rango = request.args.get("rango", "24h")
    
    # 1. Obtenemos los datos de InfluxDB (Reutilizamos tu función existente)
    datos = influx_reader.obtener_historial(sensor, rango)
    
    # 2. Creamos el CSV en memoria
    si = io.StringIO()
    writer = csv.writer(si)
    
    # Cabecera
    writer.writerow(["Fecha (UTC)", f"Valor ({sensor})"])
    
    # Datos
    for fila in datos:
        writer.writerow([fila["time"], fila["value"]])
    
    # 3. Preparamos la respuesta como archivo descargable
    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = f"attachment; filename={sensor}_{rango}.csv"
    output.headers["Content-type"] = "text/csv"
    return output

if __name__ == "__main__":
    print("🚀 Iniciando Flask + Controlador...")
    controlador.iniciar() # <--- MOVIDO AQUÍ PARA SEGURIDAD
    app.run(host="0.0.0.0", port=8000, debug=True, use_reloader=False)