#! DIGITAL // 5V

from gpiozero import OutputDevice
from time import sleep

# Pin GPIO donde está conectado el relé
bomba = OutputDevice(17, active_high=False)  
# active_high=False se usa si el relé se activa con 0 lógico (muy común)

print("Prueba de la bomba...")

while True:
    print("Encendiendo bomba...")
    bomba.on()
    sleep(2)

    print("Apagando bomba...")
    bomba.off()
    sleep(2)
