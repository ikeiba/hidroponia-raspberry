# hardware/sensores.py
"""
Módulo de sensores para el sistema de hidroponía.

Incluye:
- Sensor de temperatura DS18B20 (1-Wire).
- Sensor de TDS usando ADS1115 (canal A0 / P0).
- Placeholder para sensor de nivel de agua.

Dependencias:
    pip install w1thermsensor adafruit-circuitpython-ads1x15

Asegúrate de tener activado:
    - 1-Wire en raspi-config para el DS18B20
    - I2C para el ADS1115
"""

import time

from w1thermsensor import W1ThermSensor, Unit

import busio  # <- importante con Blinka
import board
import adafruit_ads1x15.ads1115 as ADS1115_mod
import adafruit_ads1x15.ads1x15 as ADS_CFG
from adafruit_ads1x15.analog_in import AnalogIn

import psutil
from gpiozero import CPUTemperature

# TEMPERATURA (DS18B20)

# Si solo tienes un DS18B20, esto lo detecta automáticamente
try:
    sensor_temp = W1ThermSensor()
except Exception as e:
    print("Aviso: no se ha podido inicializar el DS18B20:", e)
    sensor_temp = None


def leer_temperatura():
    """
    Lee la temperatura del agua en ºC.
    Devuelve:
        float → temperatura en ºC
        None  → si hay error o no hay sensor
    """
    if sensor_temp is None:
        return None

    try:
        temp_c = sensor_temp.get_temperature(Unit.DEGREES_C)
        return float(temp_c)
    except Exception as e:
        print("Error leyendo temperatura:", e)
        return None


# TDS (ADS1115)

# Configuración I2C + ADS1115
try:
    i2c = busio.I2C(board.SCL, board.SDA)
    ads = ADS1115_mod.ADS1115(i2c)
    ads.gain = 1             # rango ±4.096 V (seguro para 3.3V)
    canal_tds = AnalogIn(ads, 0)  # canal A0 del ADS1115
except Exception as e:
    print("Aviso: no se ha podido inicializar el ADS1115:", e)
    ads = None
    canal_tds = None

# Constantes para conversión aproximada a ppm
# Estas constantes DEBÉIS AJUSTARLAS con calibración real.
VREF = 3.3       # tensión de referencia del divisor (por ejemplo 3.3V)
K_TDS = 500.0    # factor de conversión a ppm aproximado (placeholder)


def leer_tds_voltage():
    """
    Lee el voltaje del canal TDS (en V).
    Devuelve:
        float → voltios
        None  → si hay error o no hay ADS
    """
    if canal_tds is None:
        return None

    try:
        return float(canal_tds.voltage)
    except Exception as e:
        print("Error leyendo TDS (voltaje):", e)
        return None


def leer_tds_ppm():
    """
    Convierte el voltaje leído a una estimación de TDS (ppm).

    IMPORTANTE:
        - Esta fórmula es solo un EJEMPLO.
        - Necesitáis calibrar con soluciones conocidas para obtener
          una relación voltaje → ppm adecuada.
    """
    v = leer_tds_voltage()
    if v is None:
        return None

    try:
        # Normalización a 0–1 respecto a VREF
        ratio = max(0.0, min(v / VREF, 1.0))
        # Conversión simplificada a ppm (ajustar K_TDS con calibración)
        ppm = ratio * K_TDS
        return float(ppm)
    except Exception as e:
        print("Error calculando TDS (ppm):", e)
        return None


# NIVEL DE AGUA (PLACEHOLDER) en proceso de implementación

def leer_nivel_agua():
    """
    Placeholder para el sensor de nivel de agua.

    Cuando tengáis el sensor, aquí iría la lógica real, por ejemplo:
        - Lectura digital (flotador): True/False
        - Lectura analógica/ultrasónica: distancia o porcentaje

    De momento:
        - Devuelve None para indicar "sin sensor / sin implementar".
    """
    return None

# ================================
# NUEVO: SENSORES DE SISTEMA (RPi)
# ================================

def leer_cpu_temp():
    """
    Lee la temperatura de la CPU de la Raspberry Pi.
    Retorna float (grados C) o 0.0 si falla.
    """
    try:
        cpu = CPUTemperature()
        return round(cpu.temperature, 1)
    except Exception:
        return 0.0

def leer_ram_usage():
    """
    Lee el porcentaje de uso de la memoria RAM.
    Retorna float (0-100).
    """
    try:
        # psutil.virtual_memory() devuelve un objeto con varios datos
        # .percent nos da el % usado directamente.
        return psutil.virtual_memory().percent
    except Exception:
        return 0.0