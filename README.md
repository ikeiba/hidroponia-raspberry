# 🌿 Hydroponics Automation System with Raspberry Pi

[![Python](https://img.shields.io/badge/Python-3.9+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Raspberry Pi](https://img.shields.io/badge/Raspberry%20Pi-5-C51A4A?style=for-the-badge&logo=raspberry-pi&logoColor=white)](https://www.raspberrypi.com/)
[![Flask](https://img.shields.io/badge/Flask-Web%20Dashboard-000000?style=for-the-badge&logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![MQTT](https://img.shields.io/badge/MQTT-Mosquitto-660066?style=for-the-badge&logo=eclipse-mosquitto&logoColor=white)](https://mosquitto.org/)
[![InfluxDB](https://img.shields.io/badge/InfluxDB-Time--Series%20v2-22ADF6?style=for-the-badge&logo=influxdb&logoColor=white)](https://www.influxdata.com/)

> **Language / Idioma:**  
> **🇬🇧 English** | [🇪🇸 Leer en Español](README_es.md)

---

## 📖 Table of Contents
- [Project Overview](#-project-overview)
- [Key Features](#-key-features)
- [System Architecture](#-system-architecture)
- [Hardware & Pinout](#-hardware--pinout)
- [Software Components](#-software-components)
- [What We Have Built (Development Journey)](#-what-we-have-built-development-journey)
- [Repository Structure](#-repository-structure)
- [Installation & Getting Started](#-installation--getting-started)
- [Configuration & InfluxDB Setup](#-configuration--influxdb-setup)
- [Authors & Course Context](#-authors--course-context)

---

## 🔬 Project Overview

This project is an **IoT Automated Hydroponics Monitoring and Control System** designed and executed for the **Computer Architecture** course (3rd Year, Computer Engineering). 

The goal of the system is to automate the life cycle of a hydroponic crop through closed-loop control:
1. **Circulating nutrient solution** using an electrically controlled submersible pump.
2. **Monitoring water temperature** to prevent root damage or fungal growth.
3. **Measuring Total Dissolved Solids (TDS)** via electrical conductivity to evaluate nutrient concentration in parts per million (ppm).
4. **Automating nutrient dosing** using an SG90 servomotor dispenser whenever TDS drops below optimal levels.
5. **Protecting crops with critical emergency triggers** when temperatures or salinity spike dangerously.
6. **Logging telemetry into a time-series database (InfluxDB)** through an **MQTT publish/subscribe broker**.
7. **Serving an interactive Flask web dashboard** with real-time Google Charts gauges, historical trend curves (Chart.js), live system terminal logs, Raspberry Pi hardware diagnostics, dynamic threshold configuration, and CSV report export.

---

## ✨ Key Features

- **Autonomous Multithreaded Control**: Separate background worker threads manage physical button inputs, sensor polling, actuator pulses, and safety shutdowns concurrently without blocking.
- **Physical & Web Synchronized Power**: System start/stop can be triggered interchangeably from a physical pushbutton with software debounce or through the web dashboard.
- **Temperature-Compensated TDS Calculation**: Raw analog voltage from the TDS sensor is read via a 16-bit ADS1115 ADC over I2C and mathematically normalized to 25 °C using a 3rd-degree polynomial equation before computing PPM.
- **Automated Nutrient Dispenser**: High-precision servo motor routine with custom pulse width configuration (0.5 ms – 2.4 ms) and PWM signal detachment (`detach()`) to prevent idle motor hum and chatter.
- **Two-Tier Alert & Safety System**:
  - *Thermal Warning*: Dedicated Red LED alerts if water temperature falls outside `[TEMP_MIN, TEMP_MAX]`.
  - *Nutrient Action*: Dedicated Green LED turns ON while salt/nutrients are needed and dosed.
  - *Emergency Lockdown Mode*: If water temperature reaches `TEMP_EMERGENCIA` or TDS exceeds `TDS_ALERT`, the system immediately cuts the pump, halts the servo, and triggers alternating LED strobe patterns until manual reset.
- **Raspberry Pi Host Telemetry**: Monitored CPU temperature and RAM usage percentages rendered with progressive safety color bars.
- **IoT Message Broker Pipeline**: Telemetry publisher pushes JSON packets to `hidroponia/telemetria` over MQTT; an independent subscriber persists points asynchronously to InfluxDB.
- **Interactive Web Interface**:
  - Live animated Google Gauges with color zones derived dynamically from the active configuration.
  - Multi-range historical graphs (1 hour, 24 hours, 7 days) powered by Chart.js with downsampled Flux queries.
  - Real-time in-memory rolling terminal displaying the last 50 system logs.
  - Configuration panel with client and server validations (preventing invalid threshold definitions).
  - One-click CSV export of historical sensor datasets.

---

## 🏛 System Architecture

The following diagram illustrates the hardware and software data flow:

```
+--------------------------------------------------------------------------------+
|                                HARDWARE LAYER                                  |
|                                                                                |
|  [DS18B20 Temp]   [TDS Sensor]   [Pushbutton]    [Relay/Pump]  [SG90 Servo]   |
|     (1-Wire)       (Analog)       (GPIO 22)       (GPIO 27)     (GPIO 18)      |
|        |                |              |              ^             ^          |
|        |           [ADS1115]           |              |             |          |
|        |             (I2C)             |              |             |          |
+--------|---------------|---------------|--------------|-------------|----------+
         |               |               |              |             |
+--------v---------------v---------------v--------------|-------------|----------+
|                        RASPBERRY PI 5 - CONTROLLER    |             |          |
|                                                       |             |          |
|   hardware/sensores.py       hardware/controlador.py -+-------------+          |
|   (DS18B20, ADS1115, psutil)  - Thread safety (_lock_estado)                   |
|                               - State machine & Emergency trips                |
|                               - Actuator drivers (hardware/actuadores.py)      |
+--------------------------------------|-----------------------------------------+
                                       |
                   +-------------------+-------------------+
                   |                                       |
                   v                                       v
         [data/mqtt_publicador.py]               [Flask Web Server (app.py)]
                   |                                       |
         (MQTT: 1883 / Mosquitto)                (HTTP: 8000 / REST API)
                   |                                       |
                   v                                       +---> Dashboard (index.html)
         [data/mqtt_suscriptor.py]                         +---> History (graficas.html)
                   |                                       +---> Settings (config.html)
                   v                                       +---> Terminal Logs (logs.html)
         [InfluxDB v2 (Port 8086)] <-----------------------+---> CSV Export (/exportar_csv)
             (Bucket: hidroponia_db)   (data/influx_reader.py)
```

---

## 🔌 Hardware & Pinout

### Components Bill of Materials
| Component | Interface / Type | Purpose |
| :--- | :--- | :--- |
| **Raspberry Pi 5** | SBC / Host | Core processing unit, GPIO controller, web server |
| **DS18B20** | 1-Wire Digital (3.3V) | Water temperature measurement (waterproof probe) |
| **Analog TDS Sensor** | Analog Voltage (3.3V / 5V) | Total dissolved solids / electrical conductivity |
| **ADS1115** | I2C (16-bit ADC) | Analog-to-digital conversion for the TDS sensor |
| **Submersible Water Pump** | Digital Relay (5V VCC, 3.3V Logic) | Circulates hydroponic nutrient solution |
| **SG90 Servomotor** | PWM (5V VCC, 3.3V Logic) | Automated mechanical nutrient / salt dispenser |
| **Red LED** | Digital Output (330Ω Resistor) | Cold/heat warning indicator |
| **Green LED** | Digital Output (330Ω Resistor) | Dosing / nutrient active indicator |
| **Tactile Pushbutton** | Digital Input (Internal Pull-Up) | Physical system ON/OFF & emergency reset |

### GPIO Pin Mapping Table (BCM)
| GPIO Pin (BCM) | Physical Pin | Connected Device | Function / Mode |
| :---: | :---: | :--- | :--- |
| **GPIO 2** | Pin 3 | ADS1115 (SDA) | I2C Data line |
| **GPIO 3** | Pin 5 | ADS1115 (SCL) | I2C Clock line |
| **GPIO 4** | Pin 7 | DS18B20 Data | 1-Wire protocol with 4.7kΩ pull-up resistor |
| **GPIO 18** | Pin 12 | SG90 Servomotor | Hardware PWM signal line |
| **GPIO 22** | Pin 15 | Pushbutton | Input with internal pull-up (GND triggered) |
| **GPIO 23** | Pin 16 | Red LED | Digital Output (Temperature Warning) |
| **GPIO 24** | Pin 18 | Green LED | Digital Output (Nutrient Action) |
| **GPIO 27** | Pin 13 | Water Pump Relay | Digital Output (Relay drive signal) |
| **ADS1115 A0** | Analog Pin 0 | TDS Sensor Output | Analog voltage proportional to EC |

---

## 💻 Software Components

### 1. Hardware Control & Logic (`hardware/`)
- **`sensores.py`**:
  - Implements 1-Wire temperature retrieval using `w1thermsensor`.
  - Reads channel `A0` from the ADS1115 ADC via CircuitPython Blinka (`adafruit_ads1x15`).
  - Converts voltage to TDS using standard temperature compensation:
    $$\text{Compensation Factor} = 1.0 + 0.02 \times (T_{\text{water}} - 25.0)$$
    $$V_{\text{comp}} = \frac{V_{\text{raw}}}{\text{Compensation Factor}}$$
    $$\text{TDS (ppm)} = \left( 133.42 \times V_{\text{comp}}^3 - 255.86 \times V_{\text{comp}}^2 + 857.39 \times V_{\text{comp}} \right) \times 0.5$$
  - Reads host statistics (`psutil.virtual_memory()` and `CPUTemperature()`).
- **`actuadores.py`**:
  - Encapsulates `gpiozero.AngularServo`, `OutputDevice` (Pump Relay), and `LED`.
  - Disconnects PWM signals after movement (`servo.detach()`) to eliminate noise and save power.
- **`controlador.py`**:
  - Central state machine maintaining synchronization via `threading.Lock`.
  - Evaluates emergency criteria (`fail_temp` or `fail_tds`).
  - Enforces a servo cooldown (`SERVO_COOLDOWN`) to avoid over-fertilizing.
  - Dispatches telemetry payloads to the MQTT publisher.

### 2. Data & Telemetry Pipeline (`data/`)
- **`mqtt_publicador.py`**: Asynchronously formats sensor snapshots into JSON and publishes to `hidroponia/telemetria` using `paho-mqtt`.
- **`mqtt_suscriptor.py`**: Background daemon that connects to the Mosquitto broker, unpacks telemetric payloads, builds InfluxDB `Point` entities, and commits them synchronously to bucket `hidroponia_db`.
- **`influx_reader.py`**: Executes Flux queries against InfluxDB v2, applying dynamic aggregation windows (`aggregateWindow`) based on the requested interval (`1h` -> `30s`, `24h` -> `10m`, `7d` -> `1h`).
- **`logger_web.py`**: Custom dual-logging handler directing logs simultaneously to the console and to an in-memory circular buffer (`collections.deque(maxlen=50)`).

### 3. Flask Web Application (`app.py`, `templates/`, `static/`)
- **`/` (Dashboard)**: Real-time status cards, Google Gauges, Raspberry Pi health bars, and master power toggle.
- **`/api/estado`**: JSON endpoint queried via AJAX every 2 seconds to refresh dashboard indicators without reloading.
- **`/graficas` & `/api/historial`**: Interactive Chart.js interface allowing filtering by metric (`temperatura`, `tds`, `cpu_temp`, `ram_usage`) and duration.
- **`/config`**: Form to modify operational thresholds with server-side validation rejecting invalid ranges (e.g., $T_{\text{min}} \ge T_{\text{max}}$).
- **`/logs` & `/api/logs`**: Web terminal updating every 2 seconds with automatic scroll management.
- **`/exportar_csv`**: Generates and downloads on-the-fly CSV files of time-series data.

---

## 🚀 What We Have Built (Development Journey)

Reviewing the commit history of this repository reveals the step-by-step engineering process carried out:

1. **Hardware Validation & Prototyping (`pruebas/`)**:
   - Developed isolated scripts to test individual components:
     - `test_ads.py`: Verified multi-channel analog voltage reads over I2C.
     - `prueba_temperatura.py`: Validated 1-Wire bus timing and DS18B20 resolution.
     - `prueba_tds.py`: Calibrated raw voltage to PPM conversion curve.
     - `prueba_bomba.py`: Tested relay triggering logic (active-high vs. active-low).
     - `prueba_servo.py`: Fine-tuned SG90 angular limits and resolved mechanical jitter.
2. **First Working Prototype (`hidro_final.py`)**:
   - Built a monolithic threaded prototype coordinating queue-based event passing (`queue.Queue`) between buttons, sensors, and actuators.
3. **Architectural Refactoring into Decoupled Packages**:
   - Restructured the codebase into clean modules: `hardware/` (drivers and state coordinator), `data/` (storage and telemetry), `templates/` and `static/` (presentation).
4. **IoT Message Bus & Time-Series Integration**:
   - Integrated Mosquitto MQTT to decouple measurement collection from database insertion.
   - Configured InfluxDB v2 storage with retention policies, Flux querying, and automated downsampling.
5. **Full-Featured Web Application (Flask)**:
   - Built an interactive responsive dashboard with Google Charts gauges and Chart.js historical curves.
   - Added anti-flicker AJAX state polling (`/api/estado`).
   - Implemented an in-memory web log terminal (`logger_web.py`).
   - Created the dynamic threshold configuration interface with validation logic.
   - Built an on-the-fly CSV telemetric export engine.
6. **Robustness, Safety & Diagnostics Polish**:
   - Added host health monitoring (CPU temperature and RAM usage diagnostics).
   - Designed a critical Emergency Stop Mode with alternating LED strobe alerts when extreme conditions occur.
   - Fixed servomotor mechanical stress by detaching PWM signals upon position acquisition.
   - Refined TDS polynomial equations and boundary checks.

---

## 📁 Repository Structure

```
hidroponia-raspberry/
│
├── app.py                      # Flask web server and API endpoints
├── README.md                   # Project documentation (English)
├── README_es.md                # Project documentation (Spanish)
│
├── hardware/                   # Hardware abstraction & control layer
│   ├── __init__.py
│   ├── actuadores.py           # Pump, servo, and LED wrappers (gpiozero)
│   ├── controlador.py          # State machine, thresholds, and master worker threads
│   └── sensores.py             # DS18B20, ADS1115, TDS formulas, and system metrics
│
├── data/                       # Telemetry, communications, and database layer
│   ├── __init__.py
│   ├── influx_reader.py        # InfluxDB Flux reader with downsampling
│   ├── logger_web.py           # Circular memory buffer logger for web terminal
│   ├── mqtt_publicador.py      # MQTT telemetry publisher (Paho MQTT)
│   └── mqtt_suscriptor.py      # MQTT subscriber daemon writing to InfluxDB
│
├── templates/                  # Jinja2 HTML templates
│   ├── index.html              # Main dashboard with live Google gauges
│   ├── graficas.html           # Historical Chart.js time-series view
│   ├── config.html             # Operational parameters configuration form
│   └── logs.html               # Live scrolling web terminal
│
├── static/                     # Web assets
│   └── main.css                # Custom CSS styling (dark modern theme)
│
└── pruebas/                    # Standalone hardware test & verification scripts
    ├── borrado_influx.py       # InfluxDB test record cleanup script
    ├── hidro_final.py          # Initial monolithic threaded prototype
    ├── prueba_bomba.py         # Standalone pump relay test
    ├── prueba_influx.py        # InfluxDB connectivity and write verification
    ├── prueba_servo.py         # SG90 servomotor calibration script
    ├── prueba_tds.py           # TDS sensor voltage-to-ppm script
    ├── prueba_temperatura.py   # DS18B20 1-Wire temperature test
    └── test_ads.py             # 4-channel ADS1115 I2C voltage reader
```

---

## 🛠 Installation & Getting Started

### 1. Prerequisites on Raspberry Pi OS
Enable **1-Wire** and **I2C** interfaces on your Raspberry Pi:
```bash
sudo raspi-config
# Navigate to: Interface Options -> Enable I2C
# Navigate to: Interface Options -> Enable 1-Wire
sudo reboot
```

Install the Mosquitto MQTT broker:
```bash
sudo apt update
sudo apt install -y mosquitto mosquitto-clients
sudo systemctl enable mosquitto
sudo systemctl start mosquitto
```

### 2. Clone the Repository & Install Python Dependencies
```bash
git clone https://github.com/ikeiba/hidroponia-raspberry.git
cd hidroponia-raspberry

# Install required Python packages
pip install flask gpiozero w1thermsensor adafruit-circuitpython-ads1x15 adafruit-blinka psutil paho-mqtt influxdb-client
```

---

## ⚙️ Configuration & InfluxDB Setup

### Default InfluxDB v2 Credentials
The project is configured to communicate with a local InfluxDB instance:
- **URL**: `http://localhost:8086`
- **Organization**: `proyecto_hidroponia`
- **Bucket**: `hidroponia_db`
- **Token**: `Aq38n8SaWh7iGjRC8u9Peb0mmkwfxu-TWOqXWBZF0amtG04swNbuUxE6U-XL1CGGWt5sA2hjpQ4dSw_BrEPdAg==`

> [!NOTE]  
> If you create a new InfluxDB bucket or generate a new token, update these values in `data/mqtt_suscriptor.py`, `data/influx_reader.py`, and test scripts under `pruebas/`.

### Starting the System
Open two terminals on the Raspberry Pi:

**Terminal 1 — Run the MQTT to InfluxDB Subscriber:**
```bash
python3 -m data.mqtt_suscriptor
```

**Terminal 2 — Launch the Main Application & Controller:**
```bash
python3 app.py
```

The system will start reading sensors, running the control thread, publishing telemetric packets over MQTT, and serving the dashboard at:
```
http://<raspberry_pi_ip>:8000
```

---

## 👥 Authors & Course Context

- **Course**: Computer Architecture (*Arquitectura de Computadores*)
- **Academic Year**: 3rd Year, 1st Semester
- **Degree**: Computer Engineering (*Grado en Ingeniería Informática*)
- **Target Platform**: Raspberry Pi 5
