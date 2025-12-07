# ACTUADORES: Servo motor, Bomba y leds.
# hardware/actuadores.py
"""
Módulo de actuadores para el sistema de hidroponía.

Incluye:
- Servo para dosificación de nutrientes o válvula.
- Bomba de agua (a través de un relé).
- Dos LEDs de estado.

Dependencias:
    pip install gpiozero
"""

from gpiozero import AngularServo, OutputDevice, LED
from time import sleep

# CONFIGURACIÓN DE PINES

# Cambia estos pines según tu montaje real
SERVO_PIN = 17       # Pin GPIO para el servo (PWM)
PUMP_PIN = 27        # Pin GPIO para el relé de la bomba
LED_VERDE_PIN = 23   # LED 1 (por ejemplo: sistema OK)
LED_ROJO_PIN = 24    # LED 2 (por ejemplo: alarma / error)

# INSTANCIAS DE DISPOSITIVOS

# Servo: AngularServo trabaja en grados (min_angle / max_angle)         # 0.5 ms                # 2.4 ms
# Ajustar el ancho de pulso según el modelo (SG90, etc.), porque si no, puede vibrar o no llegar del todo a los extremos.
servo = AngularServo( SERVO_PIN, min_angle=0, max_angle=180, min_pulse_width=0.0005, max_pulse_width=0.0024)

# Bomba: muchos relés se activan con nivel BAJO → active_high=False
bomba = OutputDevice( PUMP_PIN, active_high=True, initial_value=False)

led_verde = LED(LED_VERDE_PIN)
led_rojo = LED(LED_ROJO_PIN)

# FUNCIONES PARA EL SERVO

# Ajusta estos ángulos a tu montaje físico
ANGULO_CERRADO = 0
ANGULO_ABIERTO = 90

def mover_servo_angulo(angulo: float):
    """
    Mueve el servo al ángulo especificado (0–180 grados aprox).
    """
    servo.angle = angulo

def servo_abrir():
    """
    Posición 'abierta' (por ejemplo para dosificar nutrientes).
    """
    servo.angle = ANGULO_ABIERTO

def servo_cerrar():
    """
    Posición 'cerrada'.
    """
    servo.angle = ANGULO_CERRADO

# FUNCIONES PARA LA BOMBA

def encender_bomba():
    """
    Enciende la bomba de agua.
    """
    bomba.on()

def apagar_bomba():
    """
    Apaga la bomba de agua.
    """
    bomba.off()

def pulso_bomba(segundos: float):
    """
    Enciende la bomba durante 'segundos' y luego la apaga.
    Útil para pruebas o dosificaciones cortas.
    """
    encender_bomba()
    sleep(segundos)
    apagar_bomba()

# FUNCIONES PARA LOS LEDS

def led_verde_on():
    led_verde.on()

def led_verde_off():
    led_verde.off()

def led_rojo_on():
    led_rojo.on()

def led_rojo_off():
    led_rojo.off()

# Introducir mas funciones de led como parpadeo.
