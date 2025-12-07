import time
import json
import paho.mqtt.client as mqtt
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS

# --- CONFIGURACIÓN MQTT ---
MQTT_BROKER = "localhost"  # O la IP de la Raspberry si lo ejecutas desde otro PC
MQTT_PORT = 1883
MQTT_TOPIC = "hidroponia/telemetria"

# --- CONFIGURACIÓN INFLUXDB ---
# Estos datos te los da InfluxDB cuando creas el 'Bucket'
INFLUX_URL = "http://localhost:8086"
INFLUX_TOKEN = "TU_TOKEN_LARGO_DE_INFLUXDB_AQUI" 
INFLUX_ORG = "tu_organizacion"   # El nombre de organización que pusiste al instalar
INFLUX_BUCKET = "hidroponia_db"  # El nombre del bucket donde guardarás los datos

# --- INICIALIZACIÓN DE CLIENTE INFLUXDB ---
client_db = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
write_api = client_db.write_api(write_options=SYNCHRONOUS)

def on_connect(client, userdata, flags, rc):
    """ Se ejecuta cuando nos conectamos correctamente al broker MQTT """
    if rc == 0:
        print("✅ Conectado al Broker MQTT!")
        # Nos suscribimos al tópico donde publica el script principal
        client.subscribe(MQTT_TOPIC)
    else:
        print(f"❌ Error de conexión MQTT. Código: {rc}")

def on_message(client, userdata, msg):
    """ Se ejecuta CADA VEZ que llega un mensaje nuevo """
    try:
        # 1. Decodificar el mensaje recibido (de bytes a string y luego a JSON)
        payload = msg.payload.decode("utf-8")
        datos = json.loads(payload)
        
        print(f"📩 Dato recibido: {datos}")

        # 2. Crear el punto de datos para InfluxDB
        # Estructura: Measurement -> Tags -> Fields -> Time (automático si no se pone)
        point = Point("estado_hidroponia") \
            .tag("dispositivo", "raspberry_pi_5") \
            .field("temperatura", float(datos["temperatura"])) \
            .field("tds", float(datos["tds"])) \
            .field("voltaje", float(datos["voltaje"])) \
            .field("bomba_activa", bool(datos["bomba"])) \
            .field("led_accion", bool(datos["led_accion"])) \
            .field("led_alerta", bool(datos["led_alerta"]))

        # 3. Escribir en la base de datos
        write_api.write(bucket=INFLUX_BUCKET, org=INFLUX_ORG, record=point)
        print("💾 Guardado en InfluxDB correctamente")

    except json.JSONDecodeError:
        print("⚠️ Error: El mensaje recibido no es un JSON válido")
    except KeyError as e:
        print(f"⚠️ Error: Falta un campo en el JSON recibido: {e}")
    except Exception as e:
        print(f"❌ Error desconocido al guardar: {e}")

# --- CONFIGURACIÓN CLIENTE MQTT ---
client_mqtt = mqtt.Client()
client_mqtt.on_connect = on_connect
client_mqtt.on_message = on_message

# Conexión inicial
print("⏳ Conectando al sistema...")
try:
    client_mqtt.connect(MQTT_BROKER, MQTT_PORT, 60)
except ConnectionRefusedError:
    print("❌ No se puede conectar al Broker. ¿Está 'mosquitto' corriendo?")
    exit()

# Bucle infinito para mantener el script escuchando
try:
    client_mqtt.loop_forever()
except KeyboardInterrupt:
    print("\n🛑 Deteniendo suscriptor...")
    client_mqtt.disconnect()
    client_db.close()