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
    "TDS_MIN": 70,         # Mínimo para dosificar (Servo)
    "TDS_ALERT": 400,       # <--- NUEVO: Máximo para avisar (Led Rojo)
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
                # Intentamos convertir al tipo correcto (float/int)
                tipo_dato = type(configuracion[clave])
                configuracion[clave] = tipo_dato(valor)
            except ValueError: pass

def _set_emergencia(valor):
    with _lock_estado: estado["modo_emergencia"] = valor

# =========================
# LÓGICA DEL BOTÓN
# =========================
def _callback_boton():
    global _ultimo_rebote_boton
    ahora = time.time()
    
    if ahora - _ultimo_rebote_boton < 0.5: return
    _ultimo_rebote_boton = ahora

    with _lock_estado:
        emergencia = estado["modo_emergencia"]
        activo = estado["sistema_activo"]
        
        # RESET DE EMERGENCIA
        if emergencia:
            logger.info("[BOTÓN] Reseteando EMERGENCIA. Sistema en espera.")
            estado["modo_emergencia"] = False
            estado["sistema_activo"] = False
            actuadores.led_rojo_off()
            actuadores.led_verde_off()
            return

        # TOGGLE NORMAL
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
    time.sleep(2.0)
    boton.when_pressed = _callback_boton
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

        # 1. MODO EMERGENCIA (Prioridad máxima)
        if emergencia:
            actuadores.apagar_bomba()
            actuadores.led_rojo_on(); actuadores.led_verde_on()
            time.sleep(0.5)
            actuadores.led_rojo_off(); actuadores.led_verde_off()
            time.sleep(0.5)
            continue

        # 2. SISTEMA PAUSADO
        if not activo:
            time.sleep(0.5)
            continue

        # 3. SISTEMA ACTIVO - LEER
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

        # --- A. Chequeo Crítico (Emergencia) ---
        limit_emergencia = configuracion.get("TEMP_EMERGENCIA", 30.0)
        if temp >= limit_emergencia:
            logger.warning(f"!!! EMERGENCIA: {temp}ºC !!!")
            _set_emergencia(True)
            continue

        # --- B. Lógica LED ROJO (Alertas Temp O Alerta TDS) ---
        # Ahora el rojo se enciende si la temperatura falla O si el TDS es muy alto
        t_min, t_max = configuracion["TEMP_MIN"], configuracion["TEMP_MAX"]
        tds_alert_high = configuracion.get("TDS_ALERT", 800) # Valor por defecto seguro

        alerta_temp = (temp < t_min or temp > t_max)
        alerta_tds_alta = (tds > tds_alert_high) # <--- NUEVA CONDICIÓN

        if alerta_temp or alerta_tds_alta:
            actuadores.led_rojo_on()
            led_rojo_state = True
            if alerta_tds_alta:
                logger.warning(f"Alerta TDS Alto: {tds} > {tds_alert_high}")
        else:
            actuadores.led_rojo_off()
            led_rojo_state = False

        with _lock_estado: estado["led_rojo_on"] = led_rojo_state

        # --- C. Lógica LED VERDE + SERVO (Dosificación) ---
        tds_min = configuracion["TDS_MIN"]
        led_verde_state = False
        
        if tds < tds_min:
            actuadores.led_verde_on()
            led_verde_state = True
            
            # Servo
            ahora = time.time()
            if ahora - _ultima_activacion_servo > configuracion["SERVO_COOLDOWN"]:
                logger.info("[ACCIÓN] TDS Bajo -> Activando Servo.")
                actuadores.servo_abrir()
                time.sleep(1.0) # Tiempo vertiendo
                actuadores.servo_cerrar()
                
                with _lock_estado: estado["servo_count"] += 1
                _ultima_activacion_servo = time.time()
        else:
            actuadores.led_verde_off()

        with _lock_estado: estado["led_verde_on"] = led_verde_state

        # 4. PUBLICAR
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