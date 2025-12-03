from gpiozero import Servo
from time import sleep

# Servo en GPIO17 (pin físico 11)
servo = Servo(17, min_pulse_width=0.0005, max_pulse_width=0.0024)

MAX_ANGLE = 180  # servo de 180 grados

def set_angle_from_min(angle_deg):
    """
    Mapea un ángulo desde el mínimo (izquierda) hasta el máximo (derecha).

    0º   -> servo.min()  (value = -1)
    180º -> servo.max()  (value = 1)
    """
    # Limitar por seguridad
    angle_deg = max(0, min(MAX_ANGLE, angle_deg))

    # 0º -> -1, 180º -> 1
    frac = angle_deg / MAX_ANGLE      # 0..1
    value = -1 + frac * 2             # -1..1
    servo.value = value

# Ir al inicio (0º, tope izquierda) al arrancar
print("Ir a inicio: 0° (izquierda)")
servo.min()
sleep(3)

while True:
    for angle in range(30, MAX_ANGLE + 1, 30):  # 30, 60, 90, 120, 150, 180
        print(f"Giro hasta {angle}° desde la izquierda")
        set_angle_from_min(angle)
        sleep(1)

        print("Volver al inicio: 0° (izquierda)")
        servo.min()   # siempre vuelve al mismo valor (-1)
        sleep(1)
