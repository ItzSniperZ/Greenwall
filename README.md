# Greenwall — Self-Watering Hydroponic Wall

A living plant wall built at the BSU Think Tank that monitors and waters itself. Sensors track soil moisture, temperature, and humidity across 24 individual plant cells. When a cell gets dry, the system waters it automatically. LEDs on each cell reflect plant health in real time.

---

## How It Works

The wall is split into 4 sections of 6 hexagonal cells each. Each section has its own Arduino Mega that reads sensors and controls the hardware. A Raspberry Pi 5 sits at the center -- it collects data from all 4 Arduinos over USB serial, runs the watering logic, serves the dashboard, and pushes data to the cloud.

```
Plants -> Sensors -> Arduinos -> Raspberry Pi -> Dashboard / Wix CMS
                                      |
                                Pump + Solenoids
```

---

## Moisture States

| State | Range | LED Color |
|-------|-------|-----------|
| Dry | below 25% | Red |
| Optimal | 25 to 85% | Green |
| Wet | above 85% | Blue |
| Unplugged | -- | Off |

---

## Watering Logic

The Pi coordinates all watering since the Arduinos don't communicate with each other.

**Nightly cycle (9PM, AUTO mode only)**

The pump turns on and pressurizes, then each section's solenoids open one section at a time. Each section holds for 5 minutes then closes before moving to the next. The pump turns off when all sections are done.

**Dry cell trigger (AUTO mode only)**

A cell must read dry for 3 consecutive readings before anything happens. Once confirmed, the Pi queues it, runs the pump, opens that cell's solenoid for 5 minutes, then closes it. Each cell has a 1 hour cooldown after watering. Cooldowns are saved to disk so a reboot doesn't reset them.

---

## AUTO vs MANUAL Mode

The system has two modes toggled from the control panel or via the API.

**AUTO** -- sensors control everything. LEDs reflect moisture, fans respond to temperature, and watering runs on schedule and on demand.

**MANUAL** -- full manual control from the Pi. Sensor-driven behavior is paused on all Arduinos. You control LEDs, fans, and solenoids directly. The nightly cycle is disabled.

---

## Software

**Arduino Sketches (x4)**

Each Arduino reads its sensors and sends a JSON packet to the Pi every 3 seconds. It also listens for serial commands to control outputs. In AUTO mode the Arduino handles fan and LED logic on its own. In MANUAL mode that logic is paused and the Pi takes over.

**Flask Backend (app.py)**

Runs on the Pi and handles everything -- reading serial data from all 4 Arduinos, coordinating watering, serving the dashboard and control panel, and exposing a REST API.

**Dashboard (index.html)**

Live sensor display at `http://<pi-ip>:5000`. Shows all 4 sections with per-cell temperature, humidity, and moisture. Cells are clickable for more detail. Alerts appear at the top for dry, wet, or high-temp conditions.

**Control Panel (control_panel.html)**

Available at `http://<pi-ip>:5000/control`. Lets you toggle AUTO/MANUAL mode, control LEDs and fans per section or per cell, open and close solenoids, and select specific cells by clicking the hex grid to apply commands to just those cells.

**Logger (logger.py)**

Runs as a background service. Pushes sensor readings to Wix CMS every hour and watering events within 30 seconds of them happening.

---

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/data` | All sensor data |
| GET | `/api/health` | System status and mode |
| GET | `/api/mode` | Current mode |
| POST | `/api/mode/auto` | Switch to AUTO |
| POST | `/api/mode/manual` | Switch to MANUAL |
| POST | `/api/pump/trigger` | Manually run the watering cycle |
| POST | `/api/fan/{board}/all/on` | All fans on for a section |
| POST | `/api/fan/{board}/{cell}/on` | Single fan on |
| POST | `/api/led/{board}/all/{color}` | All LEDs a color (R/G/B/W/OFF) |
| POST | `/api/led/{board}/{cell}/{color}` | Single cell LED |
| POST | `/api/led/all/breathe/green` | Breathe animation on all sections |
| POST | `/api/solenoid/{board}/{cell}/on` | Open a solenoid |
| GET | `/api/watering_log` | Watering event history |

---

## Services

Both services run on boot and restart automatically on failure.

```bash
sudo systemctl status greenwall
sudo systemctl status greenwall-logger
```

The dashboard also launches automatically in fullscreen on the wall's monitor at startup.

---

## Wix CMS

Sensor and watering data is pushed to two collections on bsuthinktank.com:

- **SensorReadings** -- temperature, humidity, and moisture per cell, logged hourly
- **WateringLog** -- timestamp, section, cell, and reason for each watering event

---

## File Structure

```
greenwall/
├── app.py                  # Flask backend
├── logger.py               # Wix CMS logger
├── index.html              # Monitoring dashboard
├── control_panel.html      # Control panel UI
├── greenwall_state.json    # Persisted watering state (auto-generated)
├── mega1_sender.ino        # Arduino sketch -- Section 1
├── mega2_sender.ino        # Arduino sketch -- Section 2
├── mega3_sender.ino        # Arduino sketch -- Section 3
└── mega4_sender.ino        # Arduino sketch -- Section 4
```

---

Built at BSU Think Tank
