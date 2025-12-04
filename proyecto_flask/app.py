from gpiozero import LED
from flask import Flask, render_template

LED_PIN = 17
led = LED(LED_PIN)

app = Flask(__name__)

@app.route('/')
def index():
	estado = "apagado"
	onoff = "off"
	if led.is_lit:
		estado = "encendido"
		onoff = "on"
	return render_template('index.html', estado = estado, onoff = onoff)

@app.route('/toggleLED')
def toggleLED():
	if led.is_lit:
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