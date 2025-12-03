from gpiozero import Servo
from time import sleep

servo = Servo(17, min_pulse_width=0.0005, max_pulse_width=0.0024)

while True:

    print("Izquierda")
    servo.min()
    sleep(1)

    print("Derecha")
    servo.max()
    sleep(1)
