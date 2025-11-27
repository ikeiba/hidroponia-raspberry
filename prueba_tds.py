#! ANALOGICO // 5V
import time
import board
import threading
import queue

# Librerías específicas del hardware
import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn
from w1thermsensor import W1ThermSensor

# --- CONFIGURACIÓN ---
data_queue = queue.Queue()

def leer_sensores_agua(out_queue):
    """
    Hilo encargado de leer Temperatura (1-Wire) y TDS (I2C/ADS1115).
    """
    try:
        # 1. Configurar I2C y ADS1115
        i2c = board.I2C()  # Usa los pines SDA/SCL por defecto de la Pi
        ads = ADS.ADS1115(i2c)
        
        # IMPORTANTE: Configurar ganancia. 
        # Gain=1 significa que el rango de lectura es +/- 4.096V.
        # Como alimentamos con 3.3V, esto cubre todo nuestro rango de forma segura.
        ads.gain = 1 
        
        # Creamos el canal analógico en el pin A0
        canal_tds = AnalogIn(ads, ADS.P0)

        # 2. Configurar Sensor de Temperatura
        sensor_temp = W1ThermSensor()
        
        print("Hardware inicializado: ADS1115 y DS18B20 encontrados.")

        while True:
            # --- Lectura de Temperatura ---
            try:
                temp_c = sensor_temp.get_temperature()
            except:
                temp_c = 25.0 # Valor por defecto si falla la lectura para no romper la fórmula
            
            # --- Lectura de Voltaje TDS ---
            # La librería de Adafruit nos da el voltaje directamente. ¡Muy cómodo!
            voltaje = canal_tds.voltage
            
            # --- Compensación y Cálculo (Misma matemática que antes) ---
            coeficiente_compensacion = 1.0 + 0.02 * (temp_c - 25.0)
            voltaje_compensado = voltaje / coeficiente_compensacion
            
            # Fórmula TDS (Aproximación estándar para sensores tipo Gravity)
            tds_value = (133.42 * voltaje_compensado**3 - 
                         255.86 * voltaje_compensado**2 + 
                         857.39 * voltaje_compensado) * 0.5
            
            # Empaquetamos datos
            datos = {
                "temp": round(temp_c, 2),
                "tds": int(tds_value),
                "volts": round(voltaje, 4) # 4 decimales porque el ADS1115 es muy preciso
            }
            
            out_queue.put(datos)
            time.sleep(1)

    except Exception as e:
        print(f"Error CRÍTICO en hilo de sensores: {e}")

# --- PROGRAMA PRINCIPAL ---

if __name__ == "__main__":
    hilo = threading.Thread(target=leer_sensores_agua, args=(data_queue,), daemon=True)
    hilo.start()
    
    print("Monitor TDS con ADS1115 Iniciado...")

    try:
        while True:
            try:
                lectura = data_queue.get(timeout=0.5)
                
                print(f"T: {lectura['temp']}°C | TDS: {lectura['tds']} ppm | V: {lectura['volts']}v")
                
                # Ejemplo: Encender un LED (usando gpiozero en el hilo principal)
                # if lectura['tds'] > 600:
                #    led_rojo.on()
                
            except queue.Empty:
                pass
                
    except KeyboardInterrupt:
        print("\nSaliendo...")