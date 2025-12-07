import json
import paho.mqtt.client as mqtt

# --- CONFIGURACIÓN ---
MQTT_BROKER = "localhost"
MQTT_PORT = 1883

# Tópicos
TOPIC_TELEMETRIA = "hidroponia/telemetria"  # Para enviar datos (sensores)
TOPIC_EVENTOS    = "hidroponia/eventos"     # Para avisos (emergencia, inicio...)
TOPIC_COMANDOS   = "hidroponia/comandos"    # Para recibir órdenes (desde Flask)

# Instancia del cliente
client = mqtt.Client()

# --- CALLBACKS ---

def _on_connect(client, userdata, flags, rc):
    """Se ejecuta automáticamente al conectar."""
    if rc == 0:
        print(f"[MQTT] Conectado al Broker (Código: {rc})")
        # Nos suscribimos a comandos por si la web nos quiere decir algo
        client.subscribe(TOPIC_COMANDOS)
    else:
        print(f"[MQTT] Error de conexión. Código: {rc}")

def _on_message(client, userdata, msg):
    """Se ejecuta si recibimos una orden desde la web (Flask)."""
    try:
        mensaje = msg.payload.decode("utf-8")
        print(f"[MQTT] Comando recibido en {msg.topic}: {mensaje}")
        
        # Aquí podrías conectar una función del controlador para reaccionar
        # Por ejemplo: if mensaje == "TOGGLE": toggle_sistema()
        
    except Exception as e:
        print(f"[MQTT] Error procesando mensaje: {e}")

# Asignamos los callbacks
client.on_connect = _on_connect
client.on_message = _on_message

# --- FUNCIONES PÚBLICAS ---

def iniciar():
    """
    Inicia la conexión MQTT y el hilo en segundo plano.
    Llamar a esta función al arrancar el controlador.
    """
    try:
        print("[MQTT] Iniciando cliente...")
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        # loop_start() crea un hilo propio para gestionar la red.
        # Esto evita que se bloquee tu programa principal.
        client.loop_start() 
    except Exception as e:
        print(f"[MQTT] Error fatal al conectar: {e}")

def detener():
    """Detiene la conexión limpiamente."""
    client.loop_stop()
    client.disconnect()
    print("[MQTT] Cliente detenido.")

def publicar_telemetria(datos_dict):
    """
    Envía los datos de los sensores al Broker.
    Recibe: Un diccionario (ej. {'temp': 24, 'tds': 500, ...})
    """
    try:
        # Convertimos el diccionario de Python a texto JSON
        payload = json.dumps(datos_dict)
        client.publish(TOPIC_TELEMETRIA, payload)
        # print(f"[MQTT] Telemetría enviada: {payload}") # Descomentar para debug
    except Exception as e:
        print(f"[MQTT] Error publicando telemetría: {e}")

def publicar_evento(tipo, mensaje):
    """
    Envía una alerta o evento (ej. "EMERGENCIA_TEMP").
    """
    try:
        payload = json.dumps({"tipo": tipo, "mensaje": mensaje})
        client.publish(TOPIC_EVENTOS, payload)
        print(f"[MQTT] Evento enviado: {tipo}")
    except Exception as e:
        print(f"[MQTT] Error publicando evento: {e}")