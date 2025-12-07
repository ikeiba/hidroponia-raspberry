from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS

# --- TUS DATOS (Rellena esto) ---
url = "http://localhost:8086"
token = "Aq38n8SaWh7iGjRC8u9Peb0mmkwfxu-TWOqXWBZF0amtG04swNbuUxE6U-XL1CGGWt5sA2hjpQ4dSw_BrEPdAg=="
org = "proyecto_hidroponia"
bucket = "hidroponia_db"
# -------------------------------

def probar_conexion():
    client = InfluxDBClient(url=url, token=token, org=org)
    
    try:
        # 1. ESCRITURA
        write_api = client.write_api(write_options=SYNCHRONOUS)
        
        # Creamos un punto: Medición "hidroponia_test", tag "sensor=ph", valor=7.2
        point = Point("hidroponia_test").tag("sensor", "ph").field("valor", 7.2)
        
        print(f"> Intentando escribir: {point.to_line_protocol()}")
        write_api.write(bucket=bucket, org=org, record=point)
        print("✅ Escritura completada sin errores.")

        # 2. LECTURA (Verificación)
        print("> Verificando lectura (Query)...")
        query_api = client.query_api()
        
        # Consulta en lenguaje Flux: Dame los datos de 'hidroponia_test' del último minuto
        query = f'from(bucket: "{bucket}") |> range(start: -1m) |> filter(fn: (r) => r._measurement == "hidroponia_test")'
        
        tables = query_api.query(query)

        # Procesar resultados
        encontrado = False
        for table in tables:
            for record in table.records:
                print(f"✅ DATO ENCONTRADO EN DB: Tiempo={record.get_time()}, Valor={record.get_value()}")
                encontrado = True
        
        if not encontrado:
            print("⚠️ El comando funcionó, pero la consulta no devolvió datos (revisa el reloj del sistema).")

    except Exception as e:
        print(f"❌ ERROR: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    probar_conexion()