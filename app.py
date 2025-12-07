# app.py
from flask import Flask, render_template
from hardware import controlador  # asegúrate de tener hardware/__init__.py

app = Flask(__name__)

# Al arrancar Flask ponemos en marcha el controlador (hilos, botón, sensores, Influx…)
controlador.iniciar()


@app.route("/")
def index():
    # Le pedimos al controlador el estado actual
    
    estado = controlador.get_estado()

    # Preparamos el contexto para la plantilla (con valores por defecto por si falta algo)
    contexto = {
        "temp":        estado.get("temp"),
        "tds":         estado.get("tds"),
        "bomba_on":    estado.get("bomba_on", False),
        "led_rojo_on": estado.get("led_rojo_on", False),
        "led_verde_on": estado.get("led_verde_on", False),
        "servo_count": estado.get("servo_count", 0),
    }
	
    return render_template("index.html", )#**contexto)


if __name__ == "__main__":
    # host='0.0.0.0' → accesible desde otros dispositivos de la red
    # port=8000 → abre en el puerto 8000 (http://IP_DE_LA_PI:8000/)
    app.run(host="0.0.0.0", port=8000, debug=True)
