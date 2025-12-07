# app.py
import os
from flask import Flask, render_template
from hardware import controlador  # necesita hardware/__init__.py

# Ruta base del proyecto
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, "templates"),
    static_folder=os.path.join(BASE_DIR, "static"),
)

print("🚀 Iniciando Flask + Controlador...")

# Iniciar hilos del controlador (sensores, actuadores, MQTT, Influx…)
controlador.iniciar()


@app.route("/")
def index():
    # Intentamos leer el estado de forma segura
    try:
        estado = controlador.get_estado()
    except Exception as e:
        print("❌ Error al obtener estado del controlador:", e)
        estado = {}

    # Si por lo que sea estado no es un dict, lo forzamos a dict vacío
    if not isinstance(estado, dict):
        print("⚠️ Estado no es un dict, valor real:", estado)
        estado = {}

    contexto = {
        "temp":         estado.get("temp"),
        "tds":          estado.get("tds"),
        "bomba_on":     estado.get("bomba_on", False),
        "led_rojo_on":  estado.get("led_rojo_on", False),
        "led_verde_on": estado.get("led_verde_on", False),
        "servo_count":  estado.get("servo_count", 0),
    }

    return render_template("index.html", **contexto)


if __name__ == "__main__":
    # debug=True para ver el error bonito en el navegador
    # use_reloader=False para que NO haga el segundo proceso que nos liaba el servo
    app.run(host="0.0.0.0", port=8000, debug=True, use_reloader=False)
