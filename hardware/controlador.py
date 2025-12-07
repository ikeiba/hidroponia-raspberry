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

# Intentamos importar el publicador de MQTT (opcional)
try:
    from data import mqtt_publicador
except ImportError:
    mqtt_publicador = None

# =========================
# CONFIGURACIÓN
# =========================
BUTTON_PIN = 22

# Valores por defecto (se pueden cambiar desde la web /config)
configuracion = {
    "TEMP_MIN": 15.0,       # Por debajo: LED Temp ON
    "TEMP_MAX": 25.0,       # Por encima: LED Temp ON
    "TEMP_EMERGENCIA": 30.0,# Por encima: APAGADO TOTAL + BLINK
    "TDS_MIN": 70,         # Por debajo: LED TDS ON + Servo
    "SERVO_COOLDOWN": 60.0, # Tiempo de espera del servo (1 minuto)
    "TIEMPO_LECTURA": 2.5   # Frecuencia de logs en consola
}

# =========================
# ESTADO GLOBAL
# =========================
estado = {
    "sistema_activo": False, # Si está leyendo y funcionando
    "modo_emergencia": False,# Si ha saltado la seguridad por T > 30
    
    "temp": 0.0,
    "tds": 0,
    
    "bomba_on": False,
    "led_rojo_on": False,  # Asociado a Temperatura (GPIO 24)
    "led_verde_on": False, # Asociado a TDS (GPIO 23)
    "servo_count": 0,
}

# Variables internas para temporizadores
_ultima_activacion_servo = 0.0
_ultimo_rebote_boton = 0.0

_lock_estado = threading.Lock()
_stop_event = threading.Event()

# Configuración del botón físico
# bounce_time ayuda, pero añadiremos lógica extra para botones "malos"
boton = Button(BUTTON_PIN, pull_up=True, bounce_time=0.1) 

# =========================
# GESTIÓN DEL ESTADO
# =========================

def get_estado():
    """Devuelve copia del estado para la web"""
    with _lock_estado:
        return dict(estado)

def get_config():
    return dict(configuracion)

def update_config(nueva_conf):
    global configuracion
    for clave, valor in nueva_conf.items():
        if clave in configuracion:
            try:
                tipo = type(configuracion[clave])
                configuracion[clave] = tipo(valor)
            except ValueError:
                pass

def _set_emergencia(valor):
    with _lock_estado:
        estado["modo_emergencia"] = valor

# =========================
# LÓGICA DEL BOTÓN (ON/OFF/RESET)
# =========================
def _callback_boton():
    global _ultimo_rebote_boton
    ahora = time.time()
    
    # 1. Filtro extra de seguridad (0.5s) para botones de mala calidad
    if ahora - _ultimo_rebote_boton < 0.5:
        return
    _ultimo_rebote_boton = ahora

    with _lock_estado:
        emergencia = estado["modo_emergencia"]
        activo_actual = estado["sistema_activo"]
        
        # CASO 1: Estamos en EMERGENCIA -> El botón sirve de RESET
        if emergencia:
            logger.info("[BOTÓN] Reseteando estado de EMERGENCIA. Sistema en espera.")
            estado["modo_emergencia"] = False
            estado["sistema_activo"] = False # Se queda apagado esperando nueva orden
            # Apagamos LEDs de inmediato para quitar el parpadeo
            actuadores.led_rojo_off()
            actuadores.led_verde_off()
            return

        # CASO 2: Funcionamiento normal -> TOGGLE (Encender/Apagar)
        nuevo_estado = not activo_actual
        estado["sistema_activo"] = nuevo_estado
    
    if nuevo_estado:
        logger.info("[BOTÓN] Sistema ACTIVADO. Iniciando bomba y sensores...")
        actuadores.encender_bomba()
    else:
        logger.info("[BOTÓN] Sistema PAUSADO. Apagando actuadores.")
        actuadores.apagar_bomba()
        actuadores.servo_cerrar()
        actuadores.led_rojo_off()   # Temp LED Off
        actuadores.led_verde_off()  # TDS LED Off

def _hilo_boton():
    boton.when_pressed = _callback_boton
    while not _stop_event.is_set():
        time.sleep(0.1)

# =========================
# HILO DE LÓGICA PRINCIPAL
# =========================
# Unificamos sensores y lógica de control para sincronización perfecta
def _hilo_maestro():
    global _ultima_activacion_servo
    logger.info("[CONTROLADOR] Hilo Maestro iniciado.")

    while not _stop_event.is_set():
        
        # Leemos configuración dinámica
        T_LECTURA = configuracion["TIEMPO_LECTURA"]
        
        with _lock_estado:
            activo = estado["sistema_activo"]
            en_emergencia = estado["modo_emergencia"]

        # -------------------------------------------------
        # ESTADO A: MODO EMERGENCIA (T > 30)
        # -------------------------------------------------
        if en_emergencia:
            # Requisito: "Todo apagado excepto LEDs parpadeando"
            actuadores.apagar_bomba() 
            # Parpadeo: encender, esperar 0.5, apagar, esperar 0.5
            actuadores.led_rojo_on()
            actuadores.led_verde_on()
            time.sleep(0.5)
            actuadores.led_rojo_off()
            actuadores.led_verde_off()
            time.sleep(0.5)
            continue # Vuelve al inicio del while, ignorando el resto

        # -------------------------------------------------
        # ESTADO B: SISTEMA INACTIVO (Standby)
        # -------------------------------------------------
        if not activo:
            # Nos aseguramos que todo esté apagado
            time.sleep(0.5)
            continue

        # -------------------------------------------------
        # ESTADO C: SISTEMA ACTIVO (Funcionando)
        # -------------------------------------------------
        
        # 1. Leer Sensores
        temp = sensores.leer_temperatura()
        tds = sensores.leer_tds_ppm()
        
        # Fallback si hay error de lectura (para que no crash)
        if temp is None: temp = 25.0 
        if tds is None: tds = 600

        # Actualizamos estado global para la web
        with _lock_estado:
            estado["temp"] = temp
            estado["tds"] = tds
            estado["bomba_on"] = True # Forzamos visualización on

        # Imprimir por consola (Requisito: cada 2.5s)
        logger.info(f"Estado -> Temp: {temp:.1f}ºC | TDS: {tds} ppm")

        # 2. Comprobar EMERGENCIA (T > 30)
        limit_emergencia = configuracion.get("TEMP_EMERGENCIA", 30.0)
        if temp >= limit_emergencia:
            logger.warning(f"!!! EMERGENCIA DETECTADA: {temp}ºC >= {limit_emergencia}ºC !!!")
            logger.warning("Apagando bomba y sensores. Iniciando parpadeo.")
            _set_emergencia(True)
            # El ciclo 'continue' saltará al bloque de emergencia en la siguiente vuelta
            continue 

        # 3. Lógica de TEMPERATURA (LED GPIO 24 - Rojo)
        # Requisito: Apagado si 15 < T < 25. Encendido si T < 15 o T > 25
        t_min = configuracion["TEMP_MIN"]
        t_max = configuracion["TEMP_MAX"]
        
        if temp < t_min or temp > t_max:
            actuadores.led_rojo_on()
            with _lock_estado: estado["led_rojo_on"] = True
        else:
            actuadores.led_rojo_off()
            with _lock_estado: estado["led_rojo_on"] = False

        # 4. Lógica de TDS y SERVO (LED GPIO 23 - Verde)
        limit_tds = configuracion["TDS_MIN"]
        
        if tds < limit_tds:
            # TDS BAJO: Encender LED y evaluar Servo
            actuadores.led_verde_on()
            with _lock_estado: estado["led_verde_on"] = True
            
            ahora = time.time()
            cooldown = configuracion["SERVO_COOLDOWN"] # 60 segundos
            
            # Requisito: Pausa SOLO afecta al servo
            if ahora - _ultima_activacion_servo > cooldown:
                logger.info("[ACCIÓN] TDS Bajo. Activando Servo (Dosificando sal).")
                
                actuadores.servo_abrir() # 90 grados
                time.sleep(1.0)          # Tiempo vertiendo sal
                actuadores.servo_cerrar()# Vuelta a 0
                
                with _lock_estado: 
                    estado["servo_count"] += 1
                
                _ultima_activacion_servo = time.time()
                logger.info("[ACCIÓN] Servo finalizado. Iniciando espera de 1 min para el servo.")
            else:
                # Estamos en tiempo de espera del servo, no hacemos nada
                # pero el resto del sistema sigue funcionando
                pass

        else:
            # TDS CORRECTO: Apagar LED Verde
            actuadores.led_verde_off()
            with _lock_estado: estado["led_verde_on"] = False

        # 5. Publicar en MQTT (si existe)
        if mqtt_publicador:
            mqtt_publicador.publicar_telemetria({
                "temperatura": temp, "tds": tds, "bomba": True
            })

        # Esperar el tiempo configurado para la siguiente lectura (2.5s)
        time.sleep(T_LECTURA)

# =========================
# API PÚBLICA
# =========================

def iniciar():
    logger.info("[CONTROLADOR] Inicializando sistema...")
    
    # Estado inicial seguro
    actuadores.apagar_bomba()
    actuadores.servo_cerrar()
    actuadores.led_rojo_off()
    actuadores.led_verde_off()
    
    if mqtt_publicador: mqtt_publicador.iniciar()

    # Lanzar hilos
    hilo_btn = threading.Thread(target=_hilo_boton, daemon=True)
    hilo_master = threading.Thread(target=_hilo_maestro, daemon=True)
    
    hilo_btn.start()
    hilo_master.start()

def detener():
    _stop_event.set()
    actuadores.apagar_bomba()