#! DIGITAL // 5V

from gpiozero import Servo
from time import sleep
from gpiozero.pins.pigpio import PiGPIOFactory

# Usar pigpio para mejor precisión PWM
factory = PiGPIOFactory()

servo = Servo(18, min_pulse_width=0.0005, max_pulse_width=0.0024, pin_factory=factory)

while True:
    print("Centro")
    servo.mid()
    sleep(1)

    print("Izquierda")
    servo.min()
    sleep(1)

    print("Derecha")
    servo.max()
    sleep(1)
