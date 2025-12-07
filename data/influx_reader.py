# data/influx_reader.py
from influxdb_client import InfluxDBClient

# Configuración (Idealmente esto iría en un config.py compartido)
URL = "http://localhost:8086"
TOKEN = "Aq38n8SaWh7iGjRC8u9Peb0mmkwfxu-TWOqXWBZF0amtG04swNbuUxE6U-XL1CGGWt5sA2hjpQ4dSw_BrEPdAg=="
ORG = "proyecto_hidroponia"
BUCKET = "hidroponia_db"

client = InfluxDBClient(url=URL, token=TOKEN, org=ORG)
query_api = client.query_api()

def obtener_historial(medida, periodo):
    """
    medida: "temperatura" o "tds"
    periodo: "1h", "24h", "7d"
    """
    
    # Ajustamos la ventana de agregación según el periodo para no saturar
    # Si pedimos 1 hora, agrupa cada 10s. Si pedimos 7 dias, cada 1 hora.
    if periodo == "1h":
        range_start = "-1h"
        window_period = "30s" 
    elif periodo == "24h":
        range_start = "-24h"
        window_period = "10m"
    elif periodo == "7d":
        range_start = "-7d"
        window_period = "1h"
    else:
        # Default o "Live" (último minuto)
        range_start = "-5m"
        window_period = "5s"

    # Query Flux:
    # 1. Filtra por range
    # 2. Filtra por measurement (estado_hidroponia) y field (temperatura/tds)
    # 3. aggregateWindow: Calcula la MEDIA en ventanas de tiempo (downsampling)
    query = f'''
    from(bucket: "{BUCKET}")
      |> range(start: {range_start})
      |> filter(fn: (r) => r["_measurement"] == "estado_hidroponia")
      |> filter(fn: (r) => r["_field"] == "{medida}")
      |> aggregateWindow(every: {window_period}, fn: mean, createEmpty: false)
      |> yield(name: "mean")
    '''

    try:
        result = query_api.query(query)
        datos = []
        for table in result:
            for record in table.records:
                # Convertimos a formato lista de dicts para JSON
                datos.append({
                    "time": record.get_time().isoformat(),
                    "value": record.get_value()
                })
        return datos
    except Exception as e:
        print(f"❌ Error leyendo Influx: {e}")
        return []