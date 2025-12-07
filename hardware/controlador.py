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
    "TDS_MIN": 70,         # Mínimo -> Dosificar Sal
    "TDS_ALERT": 400,       # Máximo -> Alerta contaminación
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
# LÓGICA DE CONTROL (COMPARTIDA)
# =========================

def toggle_sistema(origen="WEB"):
    """
    Función única para encender/apagar, llamada por botón físico o web.
    """
    with _lock_estado:
        emergencia = estado["modo_emergencia"]
        activo = estado["sistema_activo"]
        
        # 1. SI ESTAMOS EN EMERGENCIA -> RESET
        if emergencia:
            logger.info(f"[{origen}] Reseteando EMERGENCIA. Sistema en espera.")
            estado["modo_emergencia"] = False
            estado["sistema_activo"] = False
            actuadores.led_rojo_off()
            actuadores.led_verde_off()
            return

        # 2. TOGGLE NORMAL
        nuevo_estado = not activo
        estado["sistema_activo"] = nuevo_estado
    
    if nuevo_estado:
        logger.info(f"[{origen}] Sistema ACTIVADO. Iniciando...")
        actuadores.encender_bomba()
    else:
        logger.info(f"[{origen}] Sistema PAUSADO.")
        actuadores.apagar_bomba()
        actuadores.servo_cerrar()
        actuadores.led_rojo_off()
        actuadores.led_verde_off()

# =========================
# CALLBACK BOTÓN FÍSICO
# =========================
def _callback_boton_fisico():
    global _ultimo_rebote_boton
    ahora = time.time()
    
    # Filtro anti-rebote (0.5s)
    if ahora - _ultimo_rebote_boton < 0.5: return
    _ultimo_rebote_boton = ahora

    # Llamamos a la lógica compartida
    toggle_sistema(origen="BOTÓN FÍSICO")

def _hilo_boton():
    time.sleep(2.0) # Espera inicial
    boton.when_pressed = _callback_boton_fisico
    while not _stop_event.is_set():
        time.sleep(0.1)

# =========================
# HILO MAESTRO
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
            # Parpadeo de AMBOS LEDs en emergencia crítica
            actuadores.led_rojo_on(); actuadores.led_verde_on()
            time.sleep(0.5)
            actuadores.led_rojo_off(); actuadores.led_verde_off()
            time.sleep(0.5)
            continue

        # --- SISTEMA PAUSADO ---
        if not activo:
            time.sleep(0.5)
            continue

        # --- SISTEMA ACTIVO ---
        
        # 1. Leer Sensores
        temp = sensores.leer_temperatura()
        if temp is None: temp = 25.0
        
        tds = sensores.leer_tds_ppm()
        if tds is None: tds = 600

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

        # ==========================================
        # NUEVA LÓGICA DE LEDS (SEPARADA POR TIPO)
        # ==========================================

        # --- ROJO: Solo ALERTAS DE TEMPERATURA ---
        t_min, t_max = configuracion["TEMP_MIN"], configuracion["TEMP_MAX"]
        
        if temp < t_min or temp > t_max:
            actuadores.led_rojo_on()
            led_rojo_state = True
        else:
            actuadores.led_rojo_off()
            led_rojo_state = False

        # --- VERDE: Solo ALERTAS DE TDS (Bajo o Alto) ---
        tds_min = configuracion["TDS_MIN"]
        tds_alert_high = configuracion.get("TDS_ALERT", 800)
        led_verde_state = False

        # Caso A: TDS Muy Alto (Alerta)
        if tds > tds_alert_high:
            actuadores.led_verde_on()
            led_verde_state = True
            logger.warning(f"Alerta TDS Alto: {tds} > {tds_alert_high}")

        # Caso B: TDS Bajo (Dosificación)
        elif tds < tds_min:
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
            # TDS Normal
            actuadores.led_verde_off()
            led_verde_state = False

        # Actualizamos estado para la web
        with _lock_estado: 
            estado["led_rojo_on"] = led_rojo_state
            estado["led_verde_on"] = led_verde_state

        # 4. PUBLICAR MQTT
        if mqtt_publicador:
            datos_mqtt = {
                "temperatura": float(temp),
                "tds": int(tds),
                "voltaje": float(voltaje),
                "bomba": True,
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
    actuadores.apagar_bomba()
    actuadores.servo_cerrar()
    actuadores.led_rojo_off()
    actuadores.led_verde_off()
    
    if mqtt_publicador: mqtt_publicador.iniciar()

    threading.Thread(target=_hilo_boton, daemon=True).start()
    threading.Thread(target=_hilo_maestro, daemon=True).start()

def detener():
    _stop_event.set()
    actuadores.apagar_bomba()