from gpiozero import Servo
from time import sleep

# Servo en GPIO17
servo = Servo(17, min_pulse_width=0.0005, max_pulse_width=0.0024)

MAX_ANGLE = 270  # si tu servo es de 180º, pon 180 aquí

def set_angle(angle_deg):
    """
    Mueve el servo a un ángulo entre 0º y MAX_ANGLE.
    Mapear: 0º -> -1 (min), MAX_ANGLE -> 1 (max).
    """
    # Limitar por seguridad
    angle_deg = max(0, min(MAX_ANGLE, angle_deg))
    value = (angle_deg / MAX_ANGLE) * 2 - 1   # [0..MAX] -> [-1..1]
    servo.value = value

# Ir al inicio (0º)
set_angle(0)
sleep(1)

while True:
    for angle in range(30, 271, 30):  # 30, 60, 90, ..., 270
        print(f"Giro a {angle} grados")
        set_angle(angle)
        sleep(1)

        print("Volver al inicio (0 grados)")
        set_angle(0)
        sleep(1)
