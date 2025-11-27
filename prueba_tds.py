#! ANALOGICO // 5V
import time
import threading
import queue

import board
import busio  # <- importante con Blinka

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
        # En Raspberry Pi: SCL = GPIO3 (pin 5), SDA = GPIO2 (pin 3)
        i2c = busio.I2C(board.SCL, board.SDA)
        ads = ADS.ADS1115(i2c)

        # Ganancia: rango ±4.096 V
        ads.gain = 1

        # Canal analógico en A0
        canal_tds = AnalogIn(ads, ADS.P0)

        # 2. Configurar Sensor de Temperatura
        sensor_temp = W1ThermSensor()

        print("Hardware inicializado: ADS1115 y DS18B20 encontrados.")

        while True:
            # --- Lectura de Temperatura ---
            try:
                temp_c = sensor_temp.get_temperature()
            except Exception:
                temp_c = 25.0  # Valor de seguridad

            # --- Lectura de Voltaje TDS ---
            voltaje = canal_tds.voltage  # en Voltios

            # --- Compensación y Cálculo ---
            coeficiente_compensacion = 1.0 + 0.02 * (temp_c - 25.0)
            voltaje_compensado = voltaje / coeficiente_compensacion

            tds_value = (133.42 * voltaje_compensado**3 -
                         255.86 * voltaje_compensado**2 +
                         857.39 * voltaje_compensado) * 0.5

            datos = {
                "temp": round(temp_c, 2),
                "tds": int(tds_value),
                "volts": round(voltaje, 4),
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
                print(f"T: {lectura['temp']}°C | TDS: {lectura['tds']} ppm | V: {lectura['volts']} V")
            except queue.Empty:
                pass
    except KeyboardInterrupt:
        print("\nSaliendo...")
