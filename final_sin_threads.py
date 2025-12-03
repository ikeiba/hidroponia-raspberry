from gpiozero import OutputDevice, LED, Button, Servo
import time
import board
import busio
import adafruit_ads1x15.ads1115 as ADS1115_mod
from adafruit_ads1x15.analog_in import AnalogIn
from w1thermsensor import W1ThermSensor, Unit

# --- CONFIGURACIÓN DE PINES ---
PUMP_PIN = 27          # Relé de la bomba (como en tu prueba) :contentReference[oaicite:0]{index=0}
BUTTON_PIN = 22        # Botón de inicio/parada
LED_TDS_PIN = 23       # LED aviso TDS bajo
LED_TEMP_PIN = 24      # LED aviso temperatura fuera de rango
SERVO_PIN = 17         # Servo para "echar sal" (como en tu prueba) :contentReference[oaicite:1]{index=1}

# --- PARÁMETROS DEL SISTEMA ---
TDS_MIN = 500          # ppm mínimos deseados (AJUSTA A TU GUSTO)
TEMP_LOW = 15.0        # ºC → por debajo de esto se enciende LED temp
TEMP_HIGH = 25.0       # ºC → por encima de esto se enciende LED temp
TEMP_EMERGENCY = 30.0  # ºC → emergencia, se apaga todo menos LEDs

PRINT_INTERVAL = 2.5   # segundos entre impresiones por consola cuando el sistema está funcionando
SERVO_COOLDOWN = 60.0  # segundos de pausa tras dosificar sal (lo que pedías)
DEBOUNCE_SECONDS = 0.3 # anti-rebote extra para el botón (además del de gpiozero)

def set_angle_from_min(servo, angle_deg, max_angle=180):
    """
    0º   -> servo.min()  (value = -1)
    180º -> servo.max()  (value = 1)
    """
    angle_deg = max(0, min(max_angle, angle_deg))
    frac = angle_deg / max_angle      # 0..1
    value = -1 + frac * 2             # -1..1
    servo.value = value

def main():
    # --- INICIALIZAR HARDWARE DIGITAL ---
    pump = OutputDevice(PUMP_PIN, active_high=False, initial_value=False)  # como en tu script :contentReference[oaicite:2]{index=2}
    led_tds = LED(LED_TDS_PIN)
    led_temp = LED(LED_TEMP_PIN)
    button = Button(BUTTON_PIN, pull_up=True)
    servo = Servo(SERVO_PIN, min_pulse_width=0.0005, max_pulse_width=0.0024)  # como en tu prueba de servo :contentReference[oaicite:3]{index=3}

    # Servo en posición inicial (0°)
    servo.min()
    time.sleep(1)

    # --- INICIALIZAR SENSORES ANALÓGICOS / 1-WIRE ---
    # ADS1115 (TDS) – basado en tu prueba de TDS :contentReference[oaicite:4]{index=4}
    i2c = busio.I2C(board.SCL, board.SDA)
    ads = ADS1115_mod.ADS1115(i2c)
    ads.gain = 1
    canal_tds = AnalogIn(ads, 0)  # A0

    # DS18B20 – basado en tu script de temperatura :contentReference[oaicite:5]{index=5}
    try:
        sensor_temp = W1ThermSensor()
        print(f"Sensor de temperatura encontrado: {sensor_temp.id}")
    except Exception as e:
        sensor_temp = None
        print(f"NO se ha encontrado DS18B20, usando 25ºC ficticios. Error: {e}")

    # --- ESTADO DEL SISTEMA ---
    system_running = False    # solo cuando está True la bomba y la lógica TDS están activas
    emergency = False         # si la T >= 30ºC
    last_button_press = 0.0
    last_print = 0.0
    last_servo_action = 0.0

    # --- GESTIÓN DEL BOTÓN CON ANTI-REBOTE EXTRA ---
    def button_pressed():
        nonlocal system_running, emergency, last_button_press
        now = time.monotonic()
        # anti-rebote extra (por si el botón es malillo)
        if now - last_button_press < DEBOUNCE_SECONDS:
            return
        last_button_press = now

        if emergency:
            print("Botón pulsado, pero el sistema está en EMERGENCIA (T >= 30ºC). Ignorando.")
            return

        system_running = not system_running
        if system_running:
            print(">>> Sistema ACTIVADO")
        else:
            print(">>> Sistema PAUSADO")
            pump.off()

    button.when_pressed = button_pressed

    print("Sistema de hidroponía listo. Pulsa el botón (GPIO22) para iniciar/parar.")

    try:
        while True:
            # --- LECTURA DE SENSORES ---
            # Temperatura
            if sensor_temp is not None:
                try:
                    temp_c = sensor_temp.get_temperature(Unit.DEGREES_C)
                except Exception as e:
                    print(f"Error leyendo temperatura, usando 25ºC: {e}")
                    temp_c = 25.0
            else:
                temp_c = 25.0

            # Voltaje y TDS (fórmula como en tu script de prueba) :contentReference[oaicite:6]{index=6}
            voltaje = canal_tds.voltage
            coef_comp = 1.0 + 0.02 * (temp_c - 25.0)
            voltaje_comp = voltaje / coef_comp
            tds_value = (133.42 * voltaje_comp**3 -
                         255.86 * voltaje_comp**2 +
                         857.39 * voltaje_comp) * 0.5
            tds_value = int(tds_value)

            now = time.monotonic()

            # --- EMERGENCIA POR TEMPERATURA ---
            if temp_c >= TEMP_EMERGENCY and not emergency:
                emergency = True
                system_running = False
                pump.off()
                try:
                    servo.min()
                except Exception:
                    pass
                print("!!! EMERGENCIA: T >= 30ºC. Sistema apagado. LEDs parpadeando.")

            # --- MODO EMERGENCIA: solo parpadean los LEDs ---
            if emergency:
                led_tds.toggle()
                led_temp.toggle()
                # En emergencia ignoramos el resto de la lógica (bomba, servo, etc.)
                time.sleep(0.5)
                continue

            # --- LED TEMPERATURA (aviso si T < 15 o T > 25) ---
            if temp_c < TEMP_LOW or temp_c > TEMP_HIGH:
                led_temp.on()
            else:
                led_temp.off()

            # --- LÓGICA PRINCIPAL SOLO CUANDO EL SISTEMA ESTÁ "FUNCIONANDO" ---
            if system_running:
                # Bomba encendida mientras el sistema está activo
                pump.on()

                # Impresión periódica por consola (cada 2.5 s)
                if now - last_print >= PRINT_INTERVAL:
                    print(f"T: {temp_c:.2f}°C | V: {voltaje:.4f} V | TDS: {tds_value} ppm")
                    last_print = now

                # LED TDS + SERVO
                if tds_value < TDS_MIN:
                    led_tds.on()
                    # Solo giramos el servo si ha pasado al menos 1 minuto desde la última "dosis"
                    if now - last_servo_action >= SERVO_COOLDOWN:
                        print("TDS por debajo del mínimo. Girando servo 90° para 'echar sal'...")
                        try:
                            # Giro 90° respecto a la posición mínima
                            set_angle_from_min(servo, 90)
                            time.sleep(1.5)  # tiempo para "echar sal"
                            servo.min()      # volvemos a la posición de inicio
                        except Exception as e:
                            print(f"Error moviendo el servo: {e}")
                        last_servo_action = time.monotonic()
                        print("Pausa de 60s para que se mezcle la 'sal'...")
                        time.sleep(SERVO_COOLDOWN)
                else:
                    led_tds.off()
            else:
                # Sistema pausado → bomba apagada, LED TDS apagado
                pump.off()
                led_tds.off()

            # Pequeña espera para no saturar CPU
            time.sleep(0.1)

    except KeyboardInterrupt:
        print("\nSaliendo... apagando dispositivos.")
    finally:
        pump.off()
        led_tds.off()
        led_temp.off()
        try:
            servo.min()
        except Exception:
            pass

if __name__ == "__main__":
    main()
