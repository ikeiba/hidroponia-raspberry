# hardware/controlador.py
"""
Controlador principal del sistema de hidroponía.

Funcionamiento:
- Botón (GPIO 22):
    * Pulsar cuando sistema inactivo → activa el sistema:
        - Bomba se enciende y permanece encendida.
        - Empiezan las lecturas periódicas de sensores.
    * Pulsar cuando sistema activo → desactiva el sistema:
        - Se apaga la bomba.
        - Servo vuelve a posición cerrada.
        - LEDs se apagan.

- Servo:
    * Si el TDS está por debajo de TDS_MIN, el servo se activa
      puntualmente (abre un momento, luego se cierra) y vuelve a
      su posición original. No afecta a otros actuadores.

- LED rojo:
    * Se enciende si:
        - temperatura < TEMP_MIN, o temperatura > TEMP_MAX, o
        - TDS > TDS_ALERT (por ejemplo 400 ppm).
    * En otro caso se apaga.

- LED verde:
    * Sistema activo y sin alertas → verde encendido.
    * El resto del tiempo (apagado o con alerta) → verde apagado.

- InfluxDB:
    * Cada vez que se leen sensores (con sistema activo), se publica una
      medida llamando a `influx_writer.publicar_medida(medida)` si el
      módulo data.influx_writer está disponible.

Este módulo no sabe nada de Flask. Flask solo usará get_estado()
para mostrar los valores en la web.
"""

import threading
import time
from gpiozero import Button

from . import sensores, actuadores

# Intentamos importar el publicador de MQTT
try:
    from data import mqtt_publicador
except ImportError:
    mqtt_publicador = None
    print("[CONTROLADOR] Aviso: No se encontró data.mqtt_publicador")


# =========================
# CONFIGURACIÓN
# =========================

BUTTON_PIN = 22          # GPIO del botón físico
TIEMPO_LECTURA = 2.0     # segundos entre lecturas de sensores

TEMP_MIN = 10.0          # debajo → alerta temperatura
TEMP_MAX = 30.0          # encima → alerta temperatura

TDS_MIN = 100.0          # por debajo → activar servo
TDS_ALERT = 400.0        # por encima → LED rojo encendido

SERVO_COOLDOWN = 60.0    # segundos entre activaciones del servo


# =========================
# ESTADO GLOBAL
# =========================

estado = {
    "sistema_activo": False,
    "temp": None,          # temperatura ºC
    "tds": None,           # TDS ppm
    "nivel_agua": None,    # de momento sin sensor real

    "bomba_on": False,
    "led_rojo_on": False,
    "led_verde_on": False,

    "servo_count": 0,      # nº total de activaciones del servo
}

_ultima_activacion_servo = 0.0  # para saber cuándo fue la última vez
_servo_count = 0               # contador interno

_lock_estado = threading.Lock()
_stop_event = threading.Event()

boton = Button(BUTTON_PIN, pull_up=True, bounce_time=0.05)

_ultima_activacion_servo = 0.0  # para no machacar el servo


# =========================
# ACCESO AL ESTADO
# =========================

def _set_estado(clave, valor):
    with _lock_estado:
        estado[clave] = valor


def get_estado():
    """
    Devuelve una copia del estado actual (para Flask).
    """
    with _lock_estado:
        return dict(estado)


# =========================
# LÓGICA DEL BOTÓN
# =========================

def _callback_boton():
    """
    Alterna el estado del sistema al pulsar el botón.
    """
    with _lock_estado:
        activo = not estado["sistema_activo"]
        estado["sistema_activo"] = activo

    print(f"[CONTROLADOR] Botón pulsado. Sistema activo: {activo}")

    if activo:
        # Sistema se activa → bomba siempre encendida
        actuadores.encender_bomba()
        # LEDs se gestionan en el hilo de control
    else:
        # Sistema se desactiva → apagamos todo
        actuadores.apagar_bomba()
        actuadores.servo_cerrar()
        actuadores.led_verde_off()
        actuadores.led_rojo_off()


def _hilo_boton():
    """
    Hilo que asocia el callback al botón y se mantiene vivo.
    """
    boton.when_pressed = _callback_boton
    print("[CONTROLADOR] Hilo del botón iniciado.")
    while not _stop_event.is_set():
        time.sleep(0.5)


# =========================
# HILO: LECTURA DE SENSORES
# =========================

def _hilo_lectura_sensores():
    """
    Lee los sensores periódicamente cuando el sistema está activo.
    Actualiza el estado y publica en InfluxDB si está disponible.
    """
    print("[CONTROLADOR] Hilo de lectura de sensores iniciado.")

    while not _stop_event.is_set():
        with _lock_estado:
            activo = estado["sistema_activo"]

        if activo:
            temp = sensores.leer_temperatura()
            tds_ppm = sensores.leer_tds_ppm()
            nivel = sensores.leer_nivel_agua()

            _set_estado("temp", temp)
            _set_estado("tds", tds_ppm)
            _set_estado("nivel_agua", nivel)

            print(f"[CONTROLADOR] Sensores → temp={temp}ºC, TDS={tds_ppm}ppm, nivel={nivel}")

            # Publicar vía MQTT
            if mqtt_publicador is not None:
                # Preparamos el diccionario con TODO lo que espera tu base de datos
                estado_actual = {
                    "temperatura": temp if temp is not None else 0.0,
                    "tds": tds_ppm if tds_ppm is not None else 0,
                    "voltaje": 0.0, # Si no tienes sensor de voltaje real, pon 0 o simúlalo
                    "bomba": estado["sistema_activo"],  # La bomba va con el sistema
                    "led_accion": False, # Tendrías que leer el estado real si quieres
                    "led_alerta": estado["led_rojo_on"]
                }
                mqtt_publicador.publicar_telemetria(estado_actual)

        time.sleep(TIEMPO_LECTURA)


# =========================
# HILO: CONTROL DE ACTUADORES
# =========================

def _hilo_control_actuadores():
    """
    Control de bomba, servo y LEDs según:
      - sistema_activo
      - temperatura
      - TDS
    """
    global _ultima_activacion_servo
    print("[CONTROLADOR] Hilo de control de actuadores iniciado.")

    while not _stop_event.is_set():
        with _lock_estado:
            activo = estado["sistema_activo"]
            temp = estado["temp"]
            tds_ppm = estado["tds"]

        if activo:
            # La bomba debe estar encendida SIEMPRE mientras el sistema esté activo
            actuadores.encender_bomba()

            # --- Lógica del servo (solo por TDS bajo) ---
            if tds_ppm is not None and tds_ppm < TDS_MIN:
                ahora = time.time()
                if ahora - _ultima_activacion_servo > SERVO_COOLDOWN:
                    print("[CONTROLADOR] TDS bajo → activando servo (abre/cierra).")
                    _ultima_activacion_servo = ahora

                    actuadores.servo_abrir()
                    time.sleep(0.5)   # tiempo de apertura (ajusta según montaje)
                    actuadores.servo_cerrar()

            # --- Lógica de LEDs (alertas de temp y TDS) ---
            alerta_temp = (
                temp is not None and (temp < TEMP_MIN or temp > TEMP_MAX)
            )

            alerta_tds = (
                tds_ppm is not None and tds_ppm > TDS_ALERT
            )

            if alerta_temp or alerta_tds:
                # Hay alguna alerta → LED rojo ON, verde OFF
                actuadores.led_rojo_on()
                actuadores.led_verde_off()
            else:
                # Sin alerta → rojo OFF, verde ON (sistema OK)
                actuadores.led_rojo_off()
                actuadores.led_verde_on()

        else:
            # Sistema inactivo → todo apagado
            actuadores.apagar_bomba()
            actuadores.servo_cerrar()
            actuadores.led_verde_off()
            actuadores.led_rojo_off()

        time.sleep(0.5)


# =========================
# API PÚBLICA
# =========================

def iniciar():
    """
    Inicia los hilos de:
      - botón
      - lectura de sensores
      - control de actuadores
      - escritor InfluxDB (si existe)
    """
    print("[CONTROLADOR] Iniciando controlador...")

    # Estado inicial: sistema apagado y actuadores off
    actuadores.apagar_bomba()
    actuadores.servo_cerrar()
    actuadores.led_verde_off()
    actuadores.led_rojo_off()

    # Iniciar Influx si existe
    if mqtt_publicador is not None:
        mqtt_publicador.iniciar()

    # Hilo botón
    threading.Thread(target=_hilo_boton, daemon=True).start()

    # Hilo sensores
    threading.Thread(target=_hilo_lectura_sensores, daemon=True).start()

    # Hilo actuadores
    threading.Thread(target=_hilo_control_actuadores, daemon=True).start()

    print("[CONTROLADOR] Todos los hilos iniciados.")


def detener():
    """
    Señala a los hilos que deben detenerse y apaga todo.
    """
    print("[CONTROLADOR] Deteniendo controlador...")
    _stop_event.set()
    actuadores.apagar_bomba()
    actuadores.servo_cerrar()
    actuadores.led_verde_off()
    actuadores.led_rojo_off()
