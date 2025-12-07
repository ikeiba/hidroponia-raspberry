from flask import Flask, render_template
from hardware import sensores, actuadores, controlador


app = Flask(__name__)

@app.route('/')
def index():
	estado = "apagado"
	onoff = "off"
	if controlador.get_estado()["led_verde_on"]:
		estado = "encendido"
		onoff = "on"
	return render_template('index.html', estado = estado, onoff = onoff)

@app.route('/toggleLED')
def toggleLED():
	if controlador.get_estado()["led_verde_on"]:
		led.off()
		estado = "apagado"
		onoff = "off"
	else:
		led.on()
		estado = "encendido"
		onoff = "on"
	return render_template('index.html', estado = estado, onoff = onoff)
    
led.on()
if __name__ == '__main__':
	app.run(host='0.0.0.0', port=8000)