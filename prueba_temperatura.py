import time
import threading
import queue
from w1thermsensor import W1ThermSensor, Unit

# Configuración de Colas y Eventos
data_queue = queue.Queue()

def leer_temperatura(out_queue):
    """
    Hilo dedicado a leer el sensor cada X segundos.
    La lectura del sensor 1-Wire puede tardar hasta 750ms,
    por eso es GENIAL que lo hagas en un hilo aparte.
    """
    try:
        # Detecta automáticamente el sensor conectado
        sensor = W1ThermSensor() 
        print(f"Sensor encontrado: {sensor.id}")
        
        while True:
            # Leemos la temperatura en Celsius
            temp_c = sensor.get_temperature(Unit.DEGREES_C)
            
            # Ponemos el dato en la cola para que el hilo principal lo use
            out_queue.put({"tipo": "temp", "valor": temp_c})
            
            time.sleep(2) # Leer cada 2 segundos
            
    except Exception as e:
        print(f"Error en el sensor: {e}")

# --- Bloque Principal ---

if __name__ == "__main__":
    # Iniciamos el hilo del sensor
    hilo_sensor = threading.Thread(target=leer_temperatura, args=(data_queue,), daemon=True)
    hilo_sensor.start()

    print("Programa iniciado. Presiona Ctrl+C para salir.")

    try:
        while True:
            # El bucle principal procesa los datos sin bloquearse esperando al sensor
            try:
                # Esperamos datos de la cola (con timeout para no bloquear eternamente)
                evento = data_queue.get(timeout=0.1)
                
                if evento["tipo"] == "temp":
                    print(f"Lectura Recibida -> Temperatura: {evento['valor']:.2f}°C")
                    
                    # AQUÍ podrías añadir lógica:
                    # if evento['valor'] > 30:
                    #     led_alerta.on()
                
            except queue.Empty:
                pass # La cola está vacía, seguimos haciendo otras cosas
                
    except KeyboardInterrupt:
        print("\nSaliendo...")