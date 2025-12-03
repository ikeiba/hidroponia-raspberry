from gpiozero import Servo
from time import sleep

# Servo en GPIO17
servo = Servo(17, min_pulse_width=0.0005, max_pulse_width=0.0024)

def set_angle(angle_deg):
    """
    Mueve el servo a un ángulo aproximado.
    Suponemos que -90º -> -1, 0º -> 0, 90º -> 1.
    """
    value = angle_deg / 90.0  # mapeo lineal
    # Limitar por si acaso
    value = max(-1, min(1, value))
    servo.value = value

# Aseguramos que empieza en el centro (inicio)
set_angle(0)
sleep(1)

while True:
    for angle in [30, 60, 90]:
        print(f"Giro a {angle} grados")
        set_angle(angle)
        sleep(1)      # tiempo en esa posición

        print("Volver al inicio (0 grados)")
        set_angle(0)
        sleep(1)      # tiempo en la posición inicial
