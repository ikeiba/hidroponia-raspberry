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
from data import logger_web as logger  # <--- IMPORTAR EL LOGGER NUEVO

# Intentamos importar el publicador de MQTT
try:
    from data import mqtt_publicador
except ImportError:
    mqtt_publicador = None
    logger.info("[CONTROLADOR] Aviso: No se encontró data.mqtt_publicador")


# =========================
# CONFIGURACIÓN
# =========================

BUTTON_PIN = 22          # GPIO del botón físico

configuracion = {
    "TEMP_MIN": 10.0,
    "TEMP_MAX": 30.0,
    "TDS_MIN": 70,
    "TDS_ALERT": 400.0,
    "SERVO_COOLDOWN": 60.0,
    "TIEMPO_LECTURA": 2.0  # <--- NUEVA VARIABLE
}


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
# NUEVAS FUNCIONES DE CONFIG
# =========================

def get_config():
    """Devuelve la configuración actual."""
    return dict(configuracion) # Copia de seguridad

def update_config(nueva_conf):
    """Actualiza los valores de configuración."""
    global configuracion
    # Actualizamos solo las claves que nos lleguen
    for clave, valor in nueva_conf.items():
        if clave in configuracion:
            # Intentamos convertir a float/int según el tipo original
            tipo_orig = type(configuracion[clave])
            try:
                configuracion[clave] = tipo_orig(valor)
            except ValueError:
                pass # Si falla la conversión, ignoramos


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

    logger.info(f"[CONTROLADOR] Botón pulsado. Sistema activo: {activo}")

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
    logger.info("[CONTROLADOR] Hilo del botón iniciado.")
    while not _stop_event.is_set():
        time.sleep(0.5)


# =========================
# HILO: LECTURA DE SENSORES
# =========================

def _hilo_lectura_sensores():
    logger.info("[CONTROLADOR] Hilo de lectura de sensores iniciado.")

    while not _stop_event.is_set():
        # 1. Leemos la configuración actual para saber cuánto dormir luego
        # Lo hacemos al principio o al final del bucle, da igual
        tiempo_espera = configuracion["TIEMPO_LECTURA"]

        with _lock_estado:
            activo = estado["sistema_activo"]

        if activo:
            # ... (Lectura de sensores y publicación MQTT igual que antes) ...
            temp = sensores.leer_temperatura()
            tds_ppm = sensores.leer_tds_ppm()
            nivel = sensores.leer_nivel_agua()

            _set_estado("temp", temp)
            _set_estado("tds", tds_ppm)
            _set_estado("nivel_agua", nivel)

            logger.info(f"[CONTROLADOR] Sensores → temp={temp}ºC, TDS={tds_ppm}ppm, nivel={nivel}")

            if mqtt_publicador is not None:
                # ... (publicar_telemetria igual que antes) ...
                pass

        # 2. Usamos la variable dinámica en lugar de la constante
        time.sleep(tiempo_espera)


# =========================
# HILO: CONTROL DE ACTUADORES
# =========================

# =========================
# ACTUALIZAR HILO DE ACTUADORES
# =========================
# Tienes que buscar la función _hilo_control_actuadores y 
# cambiar las variables constantes por configuracion["CLAVE"]

def _hilo_control_actuadores():
    global _ultima_activacion_servo
    logger.info("[CONTROLADOR] Hilo de control de actuadores iniciado.")

    while not _stop_event.is_set():
        with _lock_estado:
            activo = estado["sistema_activo"]
            temp = estado["temp"]
            tds_ppm = estado["tds"]
        
        # --- USAMOS LA CONFIGURACIÓN DINÁMICA ---
        cfg_tds_min = configuracion["TDS_MIN"]
        cfg_servo_cd = configuracion["SERVO_COOLDOWN"]
        cfg_temp_min = configuracion["TEMP_MIN"]
        cfg_temp_max = configuracion["TEMP_MAX"]
        cfg_tds_alert = configuracion["TDS_ALERT"]

        if activo:
            actuadores.encender_bomba()

            # Servo
            if tds_ppm is not None and tds_ppm < cfg_tds_min:
                ahora = time.time()
                if ahora - _ultima_activacion_servo > cfg_servo_cd:
                    logger.info("[CONTROLADOR] TDS bajo -> Dosificando.")
                    _ultima_activacion_servo = ahora
                    actuadores.servo_abrir()
                    time.sleep(0.5)
                    actuadores.servo_cerrar()

            # LEDs (Alertas)
            alerta_temp = (temp is not None and (temp < cfg_temp_min or temp > cfg_temp_max))
            alerta_tds = (tds_ppm is not None and tds_ppm > cfg_tds_alert)

            if alerta_temp or alerta_tds:
                actuadores.led_rojo_on()
                actuadores.led_verde_off()
            else:
                actuadores.led_rojo_off()
                actuadores.led_verde_on()
        else:
            # ... (Apagado igual que antes) ...
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
    logger.info("[CONTROLADOR] Iniciando controlador...")

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

    logger.info("[CONTROLADOR] Todos los hilos iniciados.")


def detener():
    """
    Señala a los hilos que deben detenerse y apaga todo.
    """
    logger.info("[CONTROLADOR] Deteniendo controlador...")
    _stop_event.set()
    actuadores.apagar_bomba()
    actuadores.servo_cerrar()
    actuadores.led_verde_off()
    actuadores.led_rojo_off()
