from gpiozero import AngularServo
from time import sleep

# Define el pin GPIO. Usamos el pin físico 12, que corresponde a GPIO 18 (BCM).
# Los valores min_angle y max_angle se establecen por defecto en -90 y 90 grados.
# Puedes ajustarlos si tu servo tiene un rango diferente.
servo = AngularServo(18) 

# --- Rutina de prueba ---

def mover_servo():
    print("Moviendo el servo a diferentes ángulos...")

    # 1. Posición central (0 grados)
    print(" -> 0 grados (Centro)")
    servo.angle = 0
    sleep(1)

    # 2. Posición máxima positiva (+90 grados)
    print(" -> +90 grados (Máximo)")
    servo.angle = 90
    sleep(1)

    # 3. Posición central (0 grados)
    print(" -> 0 grados (Centro)")
    servo.angle = 0
    sleep(1)
    
    # 4. Posición máxima negativa (-90 grados)
    print(" -> -90 grados (Mínimo)")
    servo.angle = -90
    sleep(1)

    # 5. Posición central (0 grados)
    print(" -> 0 grados (Centro)")
    servo.angle = 0
    sleep(1)

    print("--- Ciclo de oscilación (Wiggle) ---")
    # Haz que el servo oscile entre los límites
    for _ in range(5):
        servo.min()  # Mueve al ángulo mínimo (-90)
        sleep(0.5)
        servo.max()  # Mueve al ángulo máximo (+90)
        sleep(0.5)

    # Detiene el servo en la posición central
    servo.angle = 0
    sleep(1)
    print("Servo detenido en 0 grados.")

# Ejecutar la función
try:
    mover_servo()
except KeyboardInterrupt:
    print("\nPrograma detenido por el usuario.")
finally:
    servo.close() # Libera el pin GPIO