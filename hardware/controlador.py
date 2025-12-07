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

# hardware/controlador.py
import threading
import time
from gpiozero import Button
from . import sensores, actuadores
from data.logger_web import logger 

# Intentamos importar el publicador de MQTT
try:
    from data import mqtt_publicador
except ImportError:
    mqtt_publicador = None

# =========================
# CONFIGURACIÓN
# =========================
BUTTON_PIN = 22

configuracion = {
    "TEMP_MIN": 15.0,
    "TEMP_MAX": 25.0,
    "TEMP_EMERGENCIA": 30.0,
    "TDS_MIN": 500,
    "SERVO_COOLDOWN": 60.0,
    "TIEMPO_LECTURA": 2.5
}

# =========================
# ESTADO GLOBAL
# =========================
estado = {
    "sistema_activo": False,
    "modo_emergencia": False,
    "temp": 0.0,
    "tds": 0,
    "bomba_on": False,
    "led_rojo_on": False,
    "led_verde_on": False,
    "servo_count": 0,
}

_ultima_activacion_servo = 0.0
_ultimo_rebote_boton = 0.0
_lock_estado = threading.Lock()
_stop_event = threading.Event()

boton = Button(BUTTON_PIN, pull_up=True, bounce_time=0.1) 

# =========================
# GESTIÓN DEL ESTADO
# =========================

def get_estado():
    with _lock_estado: return dict(estado)

def get_config():
    return dict(configuracion)

def update_config(nueva_conf):
    global configuracion
    for clave, valor in nueva_conf.items():
        if clave in configuracion:
            try:
                configuracion[clave] = type(configuracion[clave])(valor)
            except ValueError: pass

def _set_emergencia(valor):
    with _lock_estado: estado["modo_emergencia"] = valor

# =========================
# LÓGICA DEL BOTÓN
# =========================
def _callback_boton():
    global _ultimo_rebote_boton
    ahora = time.time()
    
    # Filtro anti-rebote (0.5s)
    if ahora - _ultimo_rebote_boton < 0.5: return
    _ultimo_rebote_boton = ahora

    with _lock_estado:
        emergencia = estado["modo_emergencia"]
        activo = estado["sistema_activo"]
        
        # SI ESTAMOS EN EMERGENCIA -> RESET
        if emergencia:
            logger.info("[BOTÓN] Reseteando EMERGENCIA. Sistema en espera.")
            estado["modo_emergencia"] = False
            estado["sistema_activo"] = False
            actuadores.led_rojo_off()
            actuadores.led_verde_off()
            return

        # SI ESTAMOS NORMAL -> ON/OFF
        nuevo_estado = not activo
        estado["sistema_activo"] = nuevo_estado
    
    if nuevo_estado:
        logger.info("[BOTÓN] Sistema ACTIVADO. Iniciando...")
        actuadores.encender_bomba()
    else:
        logger.info("[BOTÓN] Sistema PAUSADO.")
        actuadores.apagar_bomba()
        actuadores.servo_cerrar()
        actuadores.led_rojo_off()
        actuadores.led_verde_off()

def _hilo_boton():
    # Pequeña pausa al arrancar para evitar falsos positivos
    time.sleep(2.0)
    boton.when_pressed = _callback_boton
    while not _stop_event.is_set():
        time.sleep(0.1)

# =========================
# HILO MAESTRO (LÓGICA)
# =========================
def _hilo_maestro():
    global _ultima_activacion_servo
    logger.info("[CONTROLADOR] Hilo Maestro iniciado.")

    while not _stop_event.is_set():
        T_LECTURA = configuracion["TIEMPO_LECTURA"]
        
        with _lock_estado:
            activo = estado["sistema_activo"]
            emergencia = estado["modo_emergencia"]

        # --- MODO EMERGENCIA ---
        if emergencia:
            actuadores.apagar_bomba()
            actuadores.led_rojo_on(); actuadores.led_verde_on()
            time.sleep(0.5)
            actuadores.led_rojo_off(); actuadores.led_verde_off()
            time.sleep(0.5)
            continue

        # --- SISTEMA APAGADO ---
        if not activo:
            time.sleep(0.5)
            continue

        # --- SISTEMA ACTIVO ---
        
        # 1. Leer Sensores
        temp = sensores.leer_temperatura()
        if temp is None: temp = 25.0
        
        tds = sensores.leer_tds_ppm()
        if tds is None: tds = 600

        # CORRECCIÓN JSON: Obtenemos voltaje real o ponemos 0.0 si no hay función
        # (Si tu sensores.py tiene leer_voltaje, úsalo aquí)
        voltaje = 0.0 
        try: voltaje = sensores.leer_tds_voltage() or 0.0
        except: pass

        with _lock_estado:
            estado["temp"] = temp
            estado["tds"] = tds
            estado["bomba_on"] = True

        logger.info(f"Estado -> Temp: {temp:.1f}ºC | TDS: {tds} ppm")

        # 2. Chequeo Emergencia (> 30ºC)
        limit_emergencia = configuracion.get("TEMP_EMERGENCIA", 30.0)
        if temp >= limit_emergencia:
            logger.warning(f"!!! EMERGENCIA: {temp}ºC !!!")
            _set_emergencia(True)
            continue

        # 3. Lógica LEDs
        # ROJO (Temp)
        t_min, t_max = configuracion["TEMP_MIN"], configuracion["TEMP_MAX"]
        led_rojo_state = False
        if temp < t_min or temp > t_max:
            actuadores.led_rojo_on()
            led_rojo_state = True
        else:
            actuadores.led_rojo_off()

        with _lock_estado: estado["led_rojo_on"] = led_rojo_state

        # VERDE (TDS + Servo)
        tds_min = configuracion["TDS_MIN"]
        led_verde_state = False
        if tds < tds_min:
            actuadores.led_verde_on()
            led_verde_state = True
            
            # Lógica Servo
            ahora = time.time()
            if ahora - _ultima_activacion_servo > configuracion["SERVO_COOLDOWN"]:
                logger.info("[ACCIÓN] TDS Bajo -> Activando Servo.")
                actuadores.servo_abrir()
                time.sleep(1.0)
                actuadores.servo_cerrar()
                with _lock_estado: estado["servo_count"] += 1
                _ultima_activacion_servo = time.time()
        else:
            actuadores.led_verde_off()

        with _lock_estado: estado["led_verde_on"] = led_verde_state

        # 4. PUBLICAR MQTT (CORREGIDO: claves exactas)
        if mqtt_publicador:
            datos_mqtt = {
                "temperatura": float(temp),   # Antes era "temp"
                "tds": int(tds),
                "voltaje": float(voltaje),    # Faltaba antes
                "bomba": True,                # Se mapea a 'bomba_activa'
                "led_accion": led_verde_state,
                "led_alerta": led_rojo_state
            }
            mqtt_publicador.publicar_telemetria(datos_mqtt)

        time.sleep(T_LECTURA)

# =========================
# API
# =========================
def iniciar():
    logger.info("[CONTROLADOR] Iniciando...")
    actuadores.apagar_bomba() # Aseguramos estado inicial
    actuadores.servo_cerrar()
    actuadores.led_rojo_off()
    actuadores.led_verde_off()
    
    if mqtt_publicador: mqtt_publicador.iniciar()

    threading.Thread(target=_hilo_boton, daemon=True).start()
    threading.Thread(target=_hilo_maestro, daemon=True).start()

def detener():
    _stop_event.set()
    actuadores.apagar_bomba()