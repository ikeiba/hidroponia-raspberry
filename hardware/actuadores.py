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
SERVO_PIN = 18       # Pin GPIO para el servo (PWM)
PUMP_PIN = 27        # Pin GPIO para el relé de la bomba
LED_VERDE_PIN = 24   
LED_ROJO_PIN = 23    

# INSTANCIAS DE DISPOSITIVOS

# Servo: AngularServo trabaja en grados (min_angle / max_angle)         # 0.5 ms                # 2.4 ms
# --- CORRECCIÓN SERVO ---
# Añadimos min_pulse_width y max_pulse_width. 
# Valores típicos para SG90: 0.0005 (0.5ms) a 0.0024 (2.4ms)
servo = AngularServo(
    SERVO_PIN, 
    min_angle=-90, 
    max_angle=90, 
    min_pulse_width=0.0005, 
    max_pulse_width=0.0024
)

# Bomba: muchos relés se activan con nivel BAJO → active_high=False
bomba = OutputDevice( PUMP_PIN, active_high=True, initial_value=False)

led_verde = LED(LED_VERDE_PIN)
led_rojo = LED(LED_ROJO_PIN)

# FUNCIONES PARA EL SERVO

# Ajusta estos ángulos a tu montaje físico
ANGULO_CERRADO = -90
ANGULO_ABIERTO = 90

def servo_abrir():
    """
    Abre, espera a que llegue y corta la señal para evitar ruido.
    """
    servo.angle = ANGULO_ABIERTO
    sleep(0.5)      # Damos tiempo al motor para llegar
    servo.detach()  # <--- TRUCO: Corta la señal PWM. El servo se relaja y deja de sonar.

def servo_cerrar():
    """
    Cierra, espera a que llegue y corta la señal.
    """
    servo.angle = ANGULO_CERRADO
    sleep(0.5)
    servo.detach()  # <--- TRUCO

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
