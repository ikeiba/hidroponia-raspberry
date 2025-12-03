import time
import threading
import queue

from gpiozero import Button, LED, OutputDevice, Servo

import board
import busio
import adafruit_ads1x15.ads1115 as ADS1115_mod
from adafruit_ads1x15.analog_in import AnalogIn
from w1thermsensor import W1ThermSensor, Unit

# =======================
# CONFIGURACIÓN DE PINES
# =======================
PUMP_PIN      = 27   # Bomba (relé)
BUTTON_PIN    = 22   # Botón start/stop
LED_TDS_PIN   = 23   # LED TDS bajo
LED_TEMP_PIN  = 24   # LED Temperatura
SERVO_PIN     = 17   # Servo que "echa sal"

# =======================
# PARÁMETROS DEL SISTEMA
# =======================
TDS_MIN          = 500.0      # ppm mínimos deseados (ajusta)
TEMP_LOW         = 15.0       # ºC → por debajo, LED temp ON
TEMP_HIGH        = 25.0       # ºC → por encima, LED temp ON
TEMP_EMERGENCY   = 30.0       # ºC → emergencia

PRINT_INTERVAL   = 2.5        # segundos entre prints cuando sistema activo
SERVO_PAUSE      = 60.0       # pausa tras "echar sal" (segundos)
DEBOUNCE_BUTTON  = 0.3        # anti-rebote del botón
EMERGENCY_BLINK  = 0.5        # periodo de parpadeo leds en emergencia (segundos)

# =========================
# COLAS Y ESTADOS GLOBALES
# =========================
eventos   = queue.Queue()   # cola principal de eventos
servo_cmd = queue.Queue()   # cola específica para el servo

# Eventos:
# ("BUTTON", tiempo)
# ("SENSOR", temp_c, voltaje, tds)
# ("EXIT",)

# Estados globales
system_running   = False      # sistema en marcha
emergency        = False      # emergencia por temperatura
last_print       = 0.0
last_blink       = 0.0

current_temp = None
current_volt = None
current_tds  = None

tds_low_episode = False       # True mientras estemos en "episodio" de TDS bajo
servo_block_until = 0.0       # no se pueden hacer nuevas dosis hasta después de este tiempo


# =======================
# FUNCIONES AUXILIARES
# =======================
def set_angle_from_min(servo, angle_deg, max_angle=180):
    """
    Mapea un ángulo 0-180º al rango value -1..1 del Servo de gpiozero.
    """
    angle_deg = max(0, min(max_angle, angle_deg))
    frac = angle_deg / max_angle          # 0..1
    value = -1 + frac * 2                 # -1..1
    servo.value = value


# =====================
# HILOS / WORKERS
# =====================

def sensor_worker(sensor_temp, canal_tds):
    """
    Hilo que lee periódicamente la temperatura y el TDS
    y manda eventos a la cola principal.
    """
    while True:
        # --- Temperatura ---
        if sensor_temp is not None:
            try:
                temp_c = sensor_temp.get_temperature(Unit.DEGREES_C)
            except Exception:
                temp_c = 25.0
        else:
            temp_c = 25.0  # valor ficticio si falla

        # --- TDS (a partir de voltaje ADS1115) ---
        voltaje = canal_tds.voltage
        coef_comp = 1.0 + 0.02 * (temp_c - 25.0)
        voltaje_comp = voltaje / coef_comp
        tds_value = (133.42 * voltaje_comp**3 -
                     255.86 * voltaje_comp**2 +
                     857.39 * voltaje_comp) * 0.5
        tds_value = float(tds_value)

        eventos.put(("SENSOR", temp_c, voltaje, tds_value))

        time.sleep(0.5)  # frecuencia de lectura


def servo_worker(servo: Servo):
    """
    Hilo que recibe órdenes para girar el servo (dosificar sal) y
    ejecuta el movimiento sin bloquear la lógica principal.
    """
    while True:
        cmd = servo_cmd.get()
        if cmd == "DOSE":
            try:
                # Girar a 90º desde la posición mínima
                set_angle_from_min(servo, 90)
                time.sleep(1.5)    # tiempo para "echar sal"
                servo.min()        # vuelve a la posición inicial
            except Exception as e:
                print(f"[SERVO] Error moviendo el servo: {e}")
        elif cmd == "EXIT":
            break


# =====================
# LÓGICA PRINCIPAL
# =====================

def main():
    global system_running, emergency
    global last_print, last_blink
    global current_temp, current_volt, current_tds
    global tds_low_episode, servo_block_until

    # ---- Inicializar GPIO / dispositivos ----
    pump    = OutputDevice(PUMP_PIN, active_high=False, initial_value=False)
    led_tds = LED(LED_TDS_PIN)
    led_temp= LED(LED_TEMP_PIN)
    button  = Button(BUTTON_PIN, pull_up=True, bounce_time=DEBOUNCE_BUTTON)

    servo = Servo(SERVO_PIN, min_pulse_width=0.0005, max_pulse_width=0.0024)
    servo.min()
    time.sleep(1)

    # Estado inicial muy claro
    pump.off()
    led_tds.off()
    led_temp.off()

    # ---- Inicializar sensores ----
    # ADS1115 para TDS
    i2c = busio.I2C(board.SCL, board.SDA)
    ads = ADS1115_mod.ADS1115(i2c)
    ads.gain = 1
    canal_tds = AnalogIn(ads, 0)  # A0

    # DS18B20
    try:
        sensor_temp = W1ThermSensor()
        print(f"[TEMP] Sensor DS18B20 encontrado: {sensor_temp.id}")
    except Exception as e:
        sensor_temp = None
        print(f"[TEMP] NO se ha encontrado DS18B20, usando 25ºC ficticios. Error: {e}")

    # ---- Callback del botón: mete evento en la cola ----
    def on_button():
        eventos.put(("BUTTON", time.monotonic()))

    button.when_pressed = on_button

    # ---- Lanzar hilos ----
    t_sens = threading.Thread(target=sensor_worker, args=(sensor_temp, canal_tds), daemon=True)
    t_srv  = threading.Thread(target=servo_worker, args=(servo,), daemon=True)

    t_sens.start()
    t_srv.start()

    print("Sistema de hidroponía listo.")
    print("Pulsa el botón (GPIO22) para INICIAR / PARAR el sistema.")

    try:
        while True:
            ev = eventos.get()
            now = time.monotonic()

            # ----------------
            # EVENTO BOTÓN
            # ----------------
            if ev[0] == "BUTTON":
                if emergency:
                    # En emergencia el botón no hace nada
                    print("[BOTÓN] Pulsado, pero en EMERGENCIA. Ignorado.")
                    continue

                system_running = not system_running
                if system_running:
                    print(">>> Sistema ACTIVADO")
                else:
                    print(">>> Sistema PAUSADO")
                    pump.off()
                    led_tds.off()
                    led_temp.off()
                    tds_low_episode = False
                continue

            # ----------------
            # EVENTO SENSOR
            # ----------------
            if ev[0] == "SENSOR":
                temp_c, voltaje, tds_value = ev[1], ev[2], ev[3]
                current_temp = temp_c
                current_volt = voltaje
                current_tds  = tds_value

                # --- Comprobar emergencia ---
                if temp_c >= TEMP_EMERGENCY and not emergency:
                    emergency = True
                    system_running = False
                    pump.off()
                    led_tds.off()
                    print("!!! EMERGENCIA: T >= 30ºC. Sistema apagado, LEDs parpadeando.")

                # --- Comportamiento en EMERGENCIA ---
                if emergency:
                    if now - last_blink >= EMERGENCY_BLINK:
                        led_tds.toggle()
                        led_temp.toggle()
                        last_blink = now
                    continue  # nada más se procesa

                # === SI EL SISTEMA NO ESTÁ ARRANCADO, NO HACEMOS NADA VISIBLE ===
                if not system_running:
                    pump.off()
                    led_tds.off()
                    led_temp.off()
                    continue

                # A partir de aquí: sistema_running == True y no hay emergencia

                # ---------- Bomba ----------
                pump.on()

                # ---------- LED TEMPERATURA ----------
                # Encendido si T < 15 o T > 25
                if temp_c < TEMP_LOW or temp_c > TEMP_HIGH:
                    led_temp.on()
                else:
                    led_temp.off()

                # ---------- Impresión periódica ----------
                if now - last_print >= PRINT_INTERVAL:
                    print(f"T: {temp_c:.2f} °C | V: {voltaje:.4f} V | TDS: {tds_value:.1f} ppm")
                    last_print = now

                # ---------- Lógica TDS + LED + SERVO ----------
                # Episodios de TDS bajo:
                # - cuando baja por primera vez de TDS_MIN -> 1 dosis de sal
                # - no repetimos dosis hasta que vuelva a subir por encima de TDS_MIN
                if tds_value < TDS_MIN:
                    led_tds.on()
                    # si aún no estábamos en episodio de TDS bajo, lo marcamos y dosificamos
                    if not tds_low_episode and now >= servo_block_until:
                        tds_low_episode = True
                        print("[TDS] TDS por debajo del mínimo. Girando servo para 'echar sal'...")
                        servo_cmd.put("DOSE")
                        servo_block_until = now + SERVO_PAUSE
                        print(f"[TDS] Pausa de {SERVO_PAUSE:.0f}s para que se mezcle la 'sal'.")
                else:
                    # TDS ha vuelto a la normalidad -> fin del episodio
                    if tds_low_episode:
                        print("[TDS] TDS ha vuelto al nivel deseado. Apagando LED TDS.")
                    tds_low_episode = False
                    led_tds.off()

    except KeyboardInterrupt:
        print("\n[MAIN] Saliendo, apagando dispositivos...")
    finally:
        # Intento de apagado "limpio"
        pump.off()
        led_tds.off()
        led_temp.off()
        try:
            servo.min()
        except Exception:
            pass
        servo_cmd.put("EXIT")
        time.sleep(0.5)


if __name__ == "__main__":
    main()
