# 🌿 Sistema Automatizado de Hidroponía con Raspberry Pi

[![Python](https://img.shields.io/badge/Python-3.9+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Raspberry Pi](https://img.shields.io/badge/Raspberry%20Pi-5-C51A4A?style=for-the-badge&logo=raspberry-pi&logoColor=white)](https://www.raspberrypi.com/)
[![Flask](https://img.shields.io/badge/Flask-Web%20Dashboard-000000?style=for-the-badge&logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![MQTT](https://img.shields.io/badge/MQTT-Mosquitto-660066?style=for-the-badge&logo=eclipse-mosquitto&logoColor=white)](https://mosquitto.org/)
[![InfluxDB](https://img.shields.io/badge/InfluxDB-Time--Series%20v2-22ADF6?style=for-the-badge&logo=influxdb&logoColor=white)](https://www.influxdata.com/)

> **Language / Idioma:**  
> [🇬🇧 Read in English](README.md) | **🇪🇸 Español**

---

## 📖 Tabla de Contenidos
- [Descripción del Proyecto](#-descripción-del-proyecto)
- [Características Principales](#-características-principales)
- [Arquitectura del Sistema](#-arquitectura-del-sistema)
- [Hardware y Asignación de Pines (Pinout)](#-hardware-y-asignación-de-pines-pinout)
- [Componentes de Software](#-componentes-de-software)
- [Lo que hemos hecho (Evolución del Desarrollo)](#-lo-que-hemos-hecho-evolución-del-desarrollo)
- [Estructura del Repositorio](#-estructura-del-repositorio)
- [Instalación y Puesta en Marcha](#-instalación-y-puesta-en-marcha)
- [Configuración de InfluxDB y Credenciales](#-configuración-de-influxdb-y-credenciales)
- [Autores y Contexto Académico](#-autores-y-contexto-académico)

---

## 🔬 Descripción del Proyecto

Este proyecto consiste en un **Sistema IoT de Monitorización y Control Automatizado para Cultivo Hidropónico**, desarrollado e implementado en una **Raspberry Pi 5** para la asignatura de **Arquitectura de Computadores** (3.er curso del Grado en Ingeniería Informática).

El objetivo es automatizar de forma integral y en bucle cerrado las condiciones del agua del cultivo:
1. **Circulación de la solución nutritiva** mediante una bomba de agua sumergible controlada por relé.
2. **Monitorización continua de la temperatura del agua** para evitar estrés radicular o proliferación de patógenos.
3. **Medición de Sólidos Disueltos Totales (TDS)** a través de conductividad eléctrica para conocer la concentración de nutrientes en partes por millón (ppm).
4. **Dosificación automática de sales/nutrientes** mediante un servomotor SG90 cuando el nivel de TDS desciende por debajo del límite deseado.
5. **Parada y alerta de emergencia crítica** ante temperaturas anormalmente altas o concentraciones excesivas de sales.
6. **Almacenamiento de telemetría temporal en InfluxDB** a través de un bus de mensajería **MQTT (Mosquitto)** desacoplado.
7. **Panel de control web en Flask** accesible desde red local, con indicadores tipo reloj interactivos (Google Charts), gráficas históricas (Chart.js), visualizador de registros/logs en vivo, diagnóstico de salud de la Raspberry Pi, configuración de umbrales en caliente y exportación de datos a CSV.

---

## ✨ Características Principales

- **Control Autónomo Multihilo (Multithreading)**: Hilos independientes en segundo plano (*daemon threads*) dedicados a la lectura periódica de sensores, gestión de eventos del botón físico con anti-rebote, activación del servo y mecanismos de seguridad concurrentes protegidos por cerrojos (`threading.Lock`).
- **Encendido/Apagado Sincronizado (Físico y Web)**: Conmutación de estado del sistema indistintamente desde un pulsador físico o desde un botón virtual en la interfaz web.
- **Cálculo de TDS con Compensación de Temperatura**: La señal analógica del sensor TDS se muestrea mediante un conversor analógico-digital (ADC) ADS1115 de 16 bits por I2C. El voltaje leído se normaliza a 25 °C y se convierte a ppm mediante un ajuste polinómico de tercer grado.
- **Dosificación Inteligente por Servomotor**: Calibración precisa de ancho de pulso PWM (0.5 ms a 2.4 ms) con desconexión activa del pulso (`servo.detach()`), eliminando vibraciones, sobrecalentamiento y ruidos mecánicos parásitos cuando el servo está en reposo.
- **Sistema de Alertas Visuales Multinivel**:
  - *Aviso Térmico (LED Rojo)*: Se enciende de forma fija si la temperatura del agua sale del rango óptimo `[TEMP_MIN, TEMP_MAX]`.
  - *Acción de Dosificación (LED Verde)*: Se ilumina mientras el sistema detecta TDS bajo y activa la dosificación.
  - *Modo de Emergencia*: Si se sobrepasa `TEMP_EMERGENCIA` o el nivel crítico de TDS (`TDS_ALERT`), se apaga la bomba de inmediato y ambos LEDs parpadean alternativamente (0.5 s) requiriendo intervención y reinicio manual.
- **Telemetría del Host (Raspberry Pi)**: Lectura continua de la temperatura de la CPU y uso de memoria RAM con barras de estado de color dinámico (verde, amarillo, rojo).
- **Canal de Datos IoT con MQTT e InfluxDB**: Desacoplamiento entre la captura de datos y la persistencia en base de datos mediante publicación/suscripción en el tópico `hidroponia/telemetria`.
- **Panel Web Moderno y Responsivo**:
  - Relojes *Gauge* con transiciones de color calculadas dinámicamente según los umbrales configurados.
  - Gráficas históricas con Chart.js para 1 hora, 24 horas y 7 días, usando reducción de resolución temporal (*downsampling*) con Flux en InfluxDB.
  - Consola web en tiempo real con búfer circular en memoria para las últimas 50 líneas de log.
  - Formulario de configuración con validación tanto en cliente (JavaScript) como en servidor (Flask).
  - Descarga directa de datos históricos en formato CSV.

---

## 🏛 Arquitectura del Sistema

Flujo de datos entre las capas de hardware, backend, base de datos e interfaz de usuario:

```
+--------------------------------------------------------------------------------+
|                               CAPA DE HARDWARE                                 |
|                                                                                |
|  [DS18B20 Temp]   [Sensor TDS]   [Pulsador]      [Relé / Bomba] [Servo SG90]  |
|     (1-Wire)       (Analógico)    (GPIO 22)         (GPIO 27)     (GPIO 18)    |
|        |                |              |                ^             ^        |
|        |           [ADS1115]           |                |             |        |
|        |             (I2C)             |                |             |        |
+--------|---------------|---------------|----------------|-------------|--------+
         |               |               |                |             |
+--------v---------------v---------------v----------------|-------------|--------+
|                        RASPBERRY PI 5 - CONTROLADOR     |             |        |
|                                                         |             |        |
|   hardware/sensores.py       hardware/controlador.py ---+-------------+        |
|   (DS18B20, ADS1115, psutil)  - Sincronización concurrente (_lock_estado)      |
|                               - Máquina de estados y disparos de emergencia    |
|                               - Accionamiento de actuadores (actuadores.py)    |
+--------------------------------------|-----------------------------------------+
                                       |
                   +-------------------+-------------------+
                   |                                       |
                   v                                       v
         [data/mqtt_publicador.py]               [Servidor Web Flask (app.py)]
                   |                                       |
         (MQTT: 1883 / Mosquitto)                (HTTP: 8000 / API REST)
                   |                                       |
                   v                                       +---> Panel (index.html)
         [data/mqtt_suscriptor.py]                         +---> Histórico (graficas.html)
                   |                                       +---> Configuración (config.html)
                   v                                       +---> Terminal Logs (logs.html)
         [InfluxDB v2 (Puerto 8086)] <---------------------+---> Exportar CSV (/exportar_csv)
             (Bucket: hidroponia_db)   (data/influx_reader.py)
```

---

## 🔌 Hardware y Asignación de Pines (Pinout)

### Lista de Componentes
| Componente | Tipo / Interfaz | Función |
| :--- | :--- | :--- |
| **Raspberry Pi 5** | SBC / Placa principal | Cerebro del sistema, lectura GPIO, servidor web y base de datos |
| **DS18B20** | Digital 1-Wire (3.3V) | Sensor sumergible de temperatura del agua |
| **Sensor TDS Analógico** | Analógico (3.3V / 5V) | Medición de conductividad eléctrica (nutrientes) |
| **ADS1115** | I2C (ADC 16 bits) | Digitalizador de la señal analógica del sensor TDS |
| **Bomba de Agua Sumergible** | Digital vía Relé (5V VCC, 3.3V señal) | Recirculación de la solución hidropónica |
| **Servomotor SG90** | PWM (5V VCC, 3.3V señal) | Dosificador de sales/nutrientes |
| **LED Rojo** | Digital con resistencia 330Ω | Aviso de temperatura fuera de rango |
| **LED Verde** | Digital con resistencia 330Ω | Indicador de acción de dosificación |
| **Pulsador Físico** | Digital (Pull-up interno) | Conmutador ON/OFF y rearme de emergencias |

### Tabla de Conexiones GPIO (BCM)
| Pin GPIO (BCM) | Pin Físico | Dispositivo Conectado | Modo / Función |
| :---: | :---: | :--- | :--- |
| **GPIO 2** | Pin 3 | ADS1115 (SDA) | Línea de datos I2C |
| **GPIO 3** | Pin 5 | ADS1115 (SCL) | Línea de reloj I2C |
| **GPIO 4** | Pin 7 | DS18B20 Datos | Bus 1-Wire (con resistencia pull-up de 4.7kΩ a 3.3V) |
| **GPIO 18** | Pin 12 | Servomotor SG90 | Línea de señal PWM |
| **GPIO 22** | Pin 15 | Pulsador | Entrada digital con pull-up (cierra a GND) |
| **GPIO 23** | Pin 16 | LED Rojo | Salida digital (Alerta de temperatura) |
| **GPIO 24** | Pin 18 | LED Verde | Salida digital (Dosificación activa) |
| **GPIO 27** | Pin 13 | Relé de la Bomba | Salida digital de control del relé |
| **ADS1115 A0** | Canal A0 | Salida Sensor TDS | Voltaje analógico proporcional al TDS |

---

## 💻 Componentes de Software

### 1. Control de Hardware y Lógica (`hardware/`)
- **`sensores.py`**:
  - Control del bus 1-Wire mediante `w1thermsensor`.
  - Lectura del canal `A0` del ADS1115 usando CircuitPython (`adafruit_ads1x15`).
  - Conversión de tensión a TDS con compensación de temperatura:
    $$\text{Factor de Compensación} = 1.0 + 0.02 \times (T_{\text{agua}} - 25.0)$$
    $$V_{\text{comp}} = \frac{V_{\text{leído}}}{\text{Factor de Compensación}}$$
    $$\text{TDS (ppm)} = \left( 133.42 \times V_{\text{comp}}^3 - 255.86 \times V_{\text{comp}}^2 + 857.39 \times V_{\text{comp}} \right) \times 0.5$$
  - Métricas internas del sistema mediante `psutil.virtual_memory()` y `CPUTemperature()`.
- **`actuadores.py`**:
  - Control de `gpiozero.AngularServo`, relé de bomba y LEDs.
  - Implementación del corte de señal (`servo.detach()`) para eliminar ruidos indeseados en el servomotor.
- **`controlador.py`**:
  - Núcleo del sistema: orquesta la máquina de estados con hilos en segundo plano (`_hilo_boton` y `_hilo_maestro`).
  - Lógica de seguridad y parada de emergencia inmediata (`_set_emergencia`).
  - Control del tiempo de enfriamiento del servo (`SERVO_COOLDOWN`) para evitar sobre-dosificaciones.
  - Despacho de paquetes JSON al publicador MQTT.

### 2. Capa de Datos y Comunicaciones (`data/`)
- **`mqtt_publicador.py`**: Publica datos de sensores y eventos en el tópico `hidroponia/telemetria` en un hilo no bloqueante (`loop_start()`).
- **`mqtt_suscriptor.py`**: Demonio en segundo plano suscrito al bróker MQTT; recibe los JSONs, los transforma en puntos de InfluxDB (`Point`) y los escribe en el bucket `hidroponia_db`.
- **`influx_reader.py`**: Consulta InfluxDB v2 mediante Flux aplicando agregaciones temporales (`aggregateWindow`) según el intervalo solicitado (`1h` -> `30s`, `24h` -> `10m`, `7d` -> `1h`).
- **`logger_web.py`**: Handler personalizado de logging que redirige los mensajes tanto a la consola estándar como a un búfer circular en memoria (`collections.deque(maxlen=50)`).

### 3. Aplicación Web Flask (`app.py`, `templates/`, `static/`)
- **`/` (Dashboard Principal)**: Tarjetas con datos en tiempo real, relojes medidores de Google Charts, estado de salud de la Raspberry Pi y botón de encendido virtual.
- **`/api/estado`**: Endpoint JSON consultado asíncronamente mediante `fetch` cada 2 segundos para actualizar la web sin parpadeo.
- **`/graficas` y `/api/historial`**: Interfaz interactiva basada en Chart.js para seleccionar métricas (`temperatura`, `tds`, `cpu_temp`, `ram_usage`) y rangos temporales.
- **`/config`**: Formulario interactivo con validación de rangos numéricos tanto en JavaScript como en Flask (evita, por ejemplo, que $T_{\text{min}} \ge T_{\text{max}}$).
- **`/logs` y `/api/logs`**: Consola web que simula un terminal Linux, actualizándose periódicamente con auto-desplazamiento vertical.
- **`/exportar_csv`**: Generación y descarga dinámica de archivos CSV con los datos de las series temporales.

---

## 🚀 Lo que hemos hecho (Evolución del Desarrollo)

A lo largo del historial del repositorio se refleja el proceso de ingeniería aplicado:

1. **Validación y Pruebas Unitarias de Hardware (`pruebas/`)**:
   - Creación de scripts aislados para validar cada componente de forma individual:
     - `test_ads.py`: Muestreo de los 4 canales analógicos del ADS1115 vía I2C.
     - `prueba_temperatura.py`: Validación de lectura del sensor DS18B20 en hilo independiente.
     - `prueba_tds.py`: Calibración de la fórmula polinómica de TDS y compensación térmica.
     - `prueba_bomba.py`: Comprobación de la activación del relé y compatibilidad eléctrica.
     - `prueba_servo.py`: Ajuste de recorrido angular y oscilación del SG90.
2. **Prototipo Monolítico Inicial (`hidro_final.py`)**:
   - Integración funcional de todos los periféricos en un único script con arquitectura de colas (`queue.Queue`) y trabajadores concurrentes.
3. **Refactorización Modular de la Arquitectura**:
   - Separación ordenada del código en módulos especializados: capa de hardware (`hardware/`), capa de datos (`data/`) e interfaz web (`templates/`, `static/`).
4. **Implementación de Arquitectura IoT (MQTT + InfluxDB)**:
   - Desacoplamiento del muestreo de sensores y la persistencia en base de datos mediante el bróker Mosquitto.
   - Configuración de InfluxDB v2 para almacenamiento de series temporales con consultas Flux optimizadas.
5. **Desarrollo del Panel Web Completo en Flask**:
   - Dashboard interactivo con Google Charts y actualización asíncrona sin recarga de página.
   - Visualización de datos históricos con Chart.js y agregación temporal automática.
   - Consola de logs en vivo en memoria accesible desde el navegador.
   - Panel de configuración con validación en doble capa (cliente y servidor).
   - Exportador de datos a archivos CSV descargables.
6. **Mecanismos de Seguridad y Pulido del Sistema**:
   - Implementación del modo de emergencia crítica ante anomalías térmicas o químicas severas.
   - Incorporación de métricas de diagnóstico del hardware (temperatura de CPU y RAM de la Raspberry Pi).
   - Solución del zumbido y calentamiento del servomotor desconectando la señal PWM tras cada movimiento (`detach()`).
   - Sincronización bidireccional limpia entre el botón físico y el botón virtual de la web.

---

## 📁 Estructura del Repositorio

```
hidroponia-raspberry/
│
├── app.py                      # Servidor Flask y endpoints de la API REST
├── README.md                   # Documentación del proyecto (Inglés)
├── README_es.md                # Documentación del proyecto (Español)
│
├── hardware/                   # Capa de abstracción y control de hardware
│   ├── __init__.py
│   ├── actuadores.py           # Controladores de bomba, servo y LEDs (gpiozero)
│   ├── controlador.py          # Máquina de estados, lógica de control e hilos de ejecución
│   └── sensores.py             # Lecturas DS18B20, ADS1115, cálculo de TDS y métricas RPi
│
├── data/                       # Capa de comunicaciones y base de datos
│   ├── __init__.py
│   ├── influx_reader.py        # Consultas Flux a InfluxDB con reducción de resolución
│   ├── logger_web.py           # Búfer circular en memoria para la consola web
│   ├── mqtt_publicador.py      # Publicador de telemetría por MQTT (Paho MQTT)
│   └── mqtt_suscriptor.py      # Servicio suscriptor MQTT que escribe en InfluxDB
│
├── templates/                  # Plantillas HTML con Jinja2
│   ├── index.html              # Panel principal con relojes medidores y estado
│   ├── graficas.html           # Vista de gráficas históricas con Chart.js
│   ├── config.html             # Formulario de parámetros operativos y umbrales
│   └── logs.html               # Terminal de logs en tiempo real
│
├── static/                     # Archivos estáticos
│   └── main.css                # Hoja de estilos CSS (tema oscuro responsivo)
│
└── pruebas/                    # Scripts de prueba y calibración unitaria de componentes
    ├── borrado_influx.py       # Limpieza de mediciones de prueba en InfluxDB
    ├── hidro_final.py          # Prototipo inicial monolítico basado en colas
    ├── prueba_bomba.py         # Prueba unitaria del relé de la bomba
    ├── prueba_influx.py        # Verificación de conexión y escritura en InfluxDB
    ├── prueba_servo.py         # Calibración del recorrido angular del servo SG90
    ├── prueba_tds.py           # Prueba de lectura y conversión analógica de TDS
    ├── prueba_temperatura.py   # Prueba de lectura del sensor DS18B20 por 1-Wire
    └── test_ads.py             # Lectura de los 4 canales analógicos del ADS1115
```

---

## 🛠 Instalación y Puesta en Marcha

### 1. Requisitos previos en Raspberry Pi OS
Habilitar los buses **1-Wire** e **I2C**:
```bash
sudo raspi-config
# Entrar en: Interfacing Options -> I2C -> Habilitar
# Entrar en: Interfacing Options -> 1-Wire -> Habilitar
sudo reboot
```

Instalar e iniciar el bróker MQTT Mosquitto:
```bash
sudo apt update
sudo apt install -y mosquitto mosquitto-clients
sudo systemctl enable mosquitto
sudo systemctl start mosquitto
```

### 2. Clonar el Repositorio e Instalar Dependencias
```bash
git clone https://github.com/ikeiba/hidroponia-raspberry.git
cd hidroponia-raspberry

# Instalar los paquetes Python necesarios
pip install flask gpiozero w1thermsensor adafruit-circuitpython-ads1x15 adafruit-blinka psutil paho-mqtt influxdb-client
```

---

## ⚙️ Configuración de InfluxDB y Credenciales

### Credenciales por Defecto de InfluxDB v2
El sistema está configurado para conectarse a una instancia local de InfluxDB:
- **URL**: `http://localhost:8086`
- **Organización**: `proyecto_hidroponia`
- **Bucket**: `hidroponia_db`
- **Token**: `Aq38n8SaWh7iGjRC8u9Peb0mmkwfxu-TWOqXWBZF0amtG04swNbuUxE6U-XL1CGGWt5sA2hjpQ4dSw_BrEPdAg==`

> [!NOTE]  
> Si se crea un nuevo bucket o se regenera el token en InfluxDB, actualizar estos valores en `data/mqtt_suscriptor.py`, `data/influx_reader.py` y en los scripts correspondientes de `pruebas/`.

### Ejecución del Sistema
Para el correcto funcionamiento, abrir dos terminales en la Raspberry Pi:

**Terminal 1 — Iniciar el servicio suscriptor MQTT a InfluxDB:**
```bash
python3 -m data.mqtt_suscriptor
```

**Terminal 2 — Iniciar la aplicación web Flask y el controlador:**
```bash
python3 app.py
```

El sistema comenzará a muestrear los sensores, procesará la máquina de estados, publicará la telemetría por MQTT y habilitará el servidor web en:
```
http://<ip_de_la_raspberry>:8000
```

---

## 👥 Autores y Contexto Académico

- **Asignatura**: Arquitectura de Computadores
- **Curso**: 3.º Grado en Ingeniería Informática (1.er Semestre)
- **Plataforma Hardware**: Raspberry Pi 5

