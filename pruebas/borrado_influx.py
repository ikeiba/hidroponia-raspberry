from influxdb_client import InfluxDBClient
from datetime import datetime

# --- TUS DATOS ---
url = "http://localhost:8086"
token = "TU_TOKEN_LARGO_AQUI"
org = "nombre_org"
bucket = "nombre_bucket"
# -----------------

client = InfluxDBClient(url=url, token=token, org=org)
delete_api = client.delete_api()

# Fechas: Desde el principio de los tiempos hasta ahora
start = "1970-01-01T00:00:00Z"
stop = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')

# El predicado es el "WHERE" de SQL. 
# Aquí le decimos: borra todo lo que tenga la etiqueta de medición "hidroponia_test"
predicate = '_measurement="hidroponia_test"'

try:
    print(f"Borrando datos de '{predicate}'...")
    delete_api.delete(start, stop, predicate, bucket=bucket, org=org)
    print("✅ Datos eliminados correctamente.")
except Exception as e:
    print(f"❌ Error al borrar: {e}")
finally:
    client.close()