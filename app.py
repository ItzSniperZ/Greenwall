from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS
import serial
import threading
import json
import time
import os
from datetime import datetime, timedelta
from collections import deque, defaultdict

app = Flask(__name__)
CORS(app)

BOARD_PORTS = {
    1: "/dev/ttyACM1",
    2: "/dev/ttyACM2",
    3: "/dev/ttyACM0",
    4: "/dev/ttyACM3",
}
BAUD_RATE = 9600

SECTION_SOLENOIDS = {
    1: [1, 2, 3, 4, 5, 6],
    2: [1, 2, 5, 6],
    3: [1, 2, 3, 4, 5, 6],
    4: [1, 3, 4, 5, 6],
}

DRY_THRESHOLD          = 215
PRESSURIZE_DELAY       = 120
SOLENOID_DELAY         = 10
OPEN_DURATION          = 300
NIGHTLY_HOUR           = 21
DRY_CHECK_DELAY        = 5
STARTUP_DELAY          = 120
CELL_COOLDOWN          = 3600
DRY_CONFIRM_READINGS   = 3
WALL_FAN_HOT_THRESHOLD = 6
WALL_FAN_TEMP          = 28
STATE_FILE             = os.path.join(os.path.dirname(__file__), "greenwall_state.json")

START_TIME = time.time()
system_mode = "auto"
wall_fan_state = False
wall_fan_lock = threading.Lock()

greenhouse_data = {
    board_id: {
        "board_id":     board_id,
        "cells":        [],
        "light":        0,
        "aqi":          0,
        "pump":         0,
        "online":       False,
        "last_updated": None,
    }
    for board_id in range(1, 5)
}

data_lock      = threading.Lock()
pump_lock      = threading.Lock()
pump_running   = False
dry_queue      = deque()
dry_queue_lock = threading.Lock()
already_queued = set()
last_watered   = {}
dry_counts     = defaultdict(int)

board_serials  = {1: None, 2: None, 3: None, 4: None}
serial_lock    = threading.Lock()

watering_log   = []
log_lock       = threading.Lock()


def load_state():
    global last_watered
    try:
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, 'r') as f:
                data = json.load(f)
                last_watered = {int(k): v for k, v in data.get("last_watered", {}).items()}
                print(f"[State] Loaded last_watered for {len(last_watered)} cells")
    except Exception as e:
        print(f"[State] Failed to load state: {e}")


def save_state():
    try:
        with open(STATE_FILE, 'w') as f:
            json.dump({"last_watered": last_watered, "saved_at": datetime.now().isoformat()}, f)
    except Exception as e:
        print(f"[State] Failed to save state: {e}")


def log_watering(board_id, cell_index, reason):
    entry = {
        "timestamp":  datetime.now().isoformat(),
        "board_id":   board_id,
        "cell":       cell_index + 1,
        "reason":     reason,
    }
    with log_lock:
        watering_log.append(entry)
    print(f"[Log] Watering: {entry}")


def send_command(board_id, cmd):
    with serial_lock:
        ser = board_serials.get(board_id)
        if ser and ser.is_open:
            try:
                ser.write((cmd + "\n").encode())
                print(f"[Board {board_id}] Sent: {cmd}")
                time.sleep(0.2)
            except Exception as e:
                print(f"[Board {board_id}] Send error: {e}")
        else:
            print(f"[Board {board_id}] Not available, dropped: {cmd}")


def send_all(cmd):
    for board_id in BOARD_PORTS:
        send_command(board_id, cmd)


def open_solenoids(board_id, solenoids):
    for sol in solenoids:
        send_command(board_id, f"SOL_ON_{sol}")
        time.sleep(SOLENOID_DELAY)


def close_solenoids(board_id, solenoids):
    for sol in solenoids:
        send_command(board_id, f"SOL_OFF_{sol}")
        time.sleep(SOLENOID_DELAY)


def run_nightly_cycle():
    global pump_running
    print("[Pump] Starting nightly cycle")
    with pump_lock:
        pump_running = True
    try:
        send_command(1, "PUMP_ON")
        print(f"[Pump] Pressurizing for {PRESSURIZE_DELAY}s...")
        time.sleep(PRESSURIZE_DELAY)
        for board_id in [1, 2, 3, 4]:
            solenoids = SECTION_SOLENOIDS[board_id]
            open_solenoids(board_id, solenoids)
            print(f"[Pump] Section {board_id} open, waiting {OPEN_DURATION}s...")
            time.sleep(OPEN_DURATION)
            close_solenoids(board_id, solenoids)
            print(f"[Pump] Section {board_id} closed")
            time.sleep(5)
        send_command(1, "PUMP_OFF")
        print("[Pump] Nightly cycle complete")
        with dry_queue_lock:
            for i in range(24):
                last_watered[i] = time.time()
        save_state()
        log_watering(0, -1, "nightly_cycle")
    except Exception as e:
        print(f"[Pump] Error: {e}")
        for board_id in [1, 2, 3, 4]:
            send_command(board_id, "ALL_SOL_OFF")
        send_command(1, "PUMP_OFF")
    with pump_lock:
        pump_running = False


def run_dry_cell_cycle(board_id, cell_index):
    global pump_running
    sol_num = cell_index + 1
    with pump_lock:
        pump_running = True
    try:
        send_command(1, "PUMP_ON")
        time.sleep(PRESSURIZE_DELAY)
        send_command(board_id, f"SOL_ON_{sol_num}")
        time.sleep(OPEN_DURATION)
        send_command(board_id, f"SOL_OFF_{sol_num}")
        send_command(1, "PUMP_OFF")
        global_idx = (board_id - 1) * 6 + cell_index
        with dry_queue_lock:
            last_watered[global_idx] = time.time()
        save_state()
        log_watering(board_id, cell_index, "dry_trigger")
    except Exception as e:
        print(f"[Pump] Error: {e}")
        send_command(board_id, f"SOL_OFF_{sol_num}")
        send_command(1, "PUMP_OFF")
    with pump_lock:
        pump_running = False
    with dry_queue_lock:
        already_queued.discard((board_id - 1) * 6 + cell_index)


def dry_queue_worker():
    while True:
        time.sleep(DRY_CHECK_DELAY)
        if system_mode != "auto":
            continue
        with pump_lock:
            running = pump_running
        if not running:
            cell = None
            with dry_queue_lock:
                if dry_queue:
                    cell = dry_queue.popleft()
            if cell is not None:
                threading.Thread(target=run_dry_cell_cycle, args=(cell[0], cell[1]), daemon=True).start()
                time.sleep(10)


def queue_dry_cell(board_id, cell_index):
    if system_mode != "auto":
        return
    global_index = (board_id - 1) * 6 + cell_index
    dry_counts[global_index] += 1
    if dry_counts[global_index] < DRY_CONFIRM_READINGS:
        return
    with dry_queue_lock:
        last = last_watered.get(global_index, 0)
        if time.time() - last < CELL_COOLDOWN:
            return
        if global_index not in already_queued:
            already_queued.add(global_index)
            dry_queue.append((board_id, cell_index))
            dry_counts[global_index] = 0
            print(f"[Pump] Queued dry cell board {board_id} cell {cell_index+1}")


def reset_dry_count(board_id, cell_index):
    global_index = (board_id - 1) * 6 + cell_index
    if dry_counts[global_index] > 0:
        dry_counts[global_index] = 0


def nightly_scheduler():
    while True:
        now = datetime.now()
        target = now.replace(hour=NIGHTLY_HOUR, minute=0, second=0, microsecond=0)
        if now >= target:
            target += timedelta(days=1)
        wait = (target - now).total_seconds()
        print(f"[Pump] Next nightly cycle in {wait/3600:.1f} hours")
        time.sleep(wait)
        if system_mode != "auto":
            print("[Pump] Skipped -- MANUAL mode")
            continue
        with pump_lock:
            running = pump_running
        if not running:
            threading.Thread(target=run_nightly_cycle, daemon=True).start()


def check_wall_fans():
    global wall_fan_state
    while True:
        time.sleep(10)
        if system_mode != "auto":
            continue
        try:
            hot_cells = 0
            with data_lock:
                for section in greenhouse_data.values():
                    for cell in section.get("cells", []):
                        if cell.get("temp", 0) > WALL_FAN_TEMP:
                            hot_cells += 1
            with wall_fan_lock:
                if not wall_fan_state and hot_cells > WALL_FAN_HOT_THRESHOLD:
                    wall_fan_state = True
                    send_command(1, "WALL_FAN_ON")
                    print(f"[WallFan] ON -- {hot_cells} hot cells")
                elif wall_fan_state and hot_cells <= WALL_FAN_HOT_THRESHOLD:
                    wall_fan_state = False
                    send_command(1, "WALL_FAN_OFF")
                    print(f"[WallFan] OFF -- {hot_cells} hot cells")
        except Exception as e:
            print(f"[WallFan] Error: {e}")


def read_serial(board_id, port):
    while True:
        try:
            with serial.Serial(port, BAUD_RATE, timeout=2) as ser:
                print(f"[Board {board_id}] Connected on {port}")
                with serial_lock:
                    board_serials[board_id] = ser
                time.sleep(2)
                with data_lock:
                    greenhouse_data[board_id]["online"] = True
                while True:
                    line = ser.readline().decode("utf-8", errors="ignore").strip()
                    if not line:
                        continue
                    try:
                        packet = json.loads(line)
                        with data_lock:
                            greenhouse_data[board_id].update({
                                "cells":        packet.get("cells", []),
                                "light":        packet.get("light", 0),
                                "aqi":          packet.get("aqi", 0),
                                "pump":         packet.get("pump", 0),
                                "online":       True,
                                "last_updated": datetime.now().isoformat(),
                            })
                        if system_mode == "auto" and time.time() - START_TIME > STARTUP_DELAY:
                            for cell in packet.get("cells", []):
                                moist = cell.get("moist", -1)
                                cell_index = (cell["cell"] - 1) % 6
                                if moist != -1 and moist < DRY_THRESHOLD:
                                    queue_dry_cell(board_id, cell_index)
                                else:
                                    reset_dry_count(board_id, cell_index)
                    except json.JSONDecodeError:
                        print(f"[Board {board_id}] Bad JSON: {line}")
        except serial.SerialException as e:
            print(f"[Board {board_id}] Error: {e}. Retrying in 5s...")
            with serial_lock:
                board_serials[board_id] = None
            with data_lock:
                greenhouse_data[board_id]["online"] = False
            time.sleep(5)


# ─── API ROUTES ───

@app.route("/api/data")
def get_all_data():
    with data_lock:
        return jsonify(list(greenhouse_data.values()))

@app.route("/api/data/<int:board_id>")
def get_section(board_id):
    if board_id not in greenhouse_data:
        return jsonify({"error": "Invalid board_id"}), 404
    with data_lock:
        return jsonify(greenhouse_data[board_id])

@app.route("/api/health")
def health():
    online = sum(1 for s in greenhouse_data.values() if s["online"])
    with pump_lock:
        running = pump_running
    with wall_fan_lock:
        wf = wall_fan_state
    with dry_queue_lock:
        cooldowns = {
            str(i+1): max(0, int((CELL_COOLDOWN - (time.time() - t)) / 60))
            for i, t in last_watered.items()
        }
    return jsonify({
        "status": "ok", "mode": system_mode,
        "boards_online": online, "pump_running": running,
        "wall_fan": wf,
        "uptime_seconds": int(time.time() - START_TIME),
        "cell_cooldowns_min": cooldowns,
        "timestamp": datetime.now().isoformat(),
    })

@app.route("/api/watering_log")
def get_watering_log():
    with log_lock:
        return jsonify(list(reversed(watering_log)))

# ─── MODE ───

@app.route("/api/mode/auto", methods=["POST"])
def set_auto():
    global system_mode
    system_mode = "auto"
    send_all("AUTO_MODE")
    return jsonify({"success": True, "mode": "auto"})

@app.route("/api/mode/manual", methods=["POST"])
def set_manual():
    global system_mode
    system_mode = "manual"
    send_command(1, "PUMP_OFF")
    for board_id in [1, 2, 3, 4]:
        send_command(board_id, "ALL_SOL_OFF")
        send_command(board_id, "MANUAL_MODE")
    return jsonify({"success": True, "mode": "manual"})

@app.route("/api/mode")
def get_mode():
    return jsonify({"mode": system_mode})

# ─── PUMP ───

@app.route("/api/pump/trigger", methods=["POST"])
def manual_pump_trigger():
    with pump_lock:
        running = pump_running
    if running:
        return jsonify({"error": "Pump already running"}), 409
    threading.Thread(target=run_nightly_cycle, daemon=True).start()
    return jsonify({"success": True, "message": "Cycle started"})

@app.route("/api/pump/off", methods=["POST"])
def pump_off():
    global pump_running
    send_command(1, "PUMP_OFF")
    for board_id in [1, 2, 3, 4]:
        send_command(board_id, "ALL_SOL_OFF")
    with pump_lock:
        pump_running = False
    return jsonify({"success": True, "message": "Pump off, all solenoids closed"})

# ─── WALL FANS ───

@app.route("/api/wallfan/on", methods=["POST"])
def wall_fan_on():
    global wall_fan_state
    with wall_fan_lock:
        wall_fan_state = True
    send_command(1, "WALL_FAN_ON")
    return jsonify({"success": True, "message": "Wall fans on"})

@app.route("/api/wallfan/off", methods=["POST"])
def wall_fan_off():
    global wall_fan_state
    with wall_fan_lock:
        wall_fan_state = False
    send_command(1, "WALL_FAN_OFF")
    return jsonify({"success": True, "message": "Wall fans off"})

@app.route("/api/wallfan/status")
def wall_fan_status():
    with wall_fan_lock:
        return jsonify({"wall_fan": wall_fan_state})

# ─── FANS ───

@app.route("/api/fan/all/all/on", methods=["POST"])
def fan_all_sections_on():
    send_all("ALL_FAN_ON"); return jsonify({"success": True})

@app.route("/api/fan/all/all/off", methods=["POST"])
def fan_all_sections_off():
    send_all("ALL_FAN_OFF"); return jsonify({"success": True})

@app.route("/api/fan/<int:board_id>/all/on", methods=["POST"])
def fan_all_on(board_id):
    if board_id not in BOARD_PORTS: return jsonify({"error": "Invalid board_id"}), 404
    send_command(board_id, "ALL_FAN_ON"); return jsonify({"success": True})

@app.route("/api/fan/<int:board_id>/all/off", methods=["POST"])
def fan_all_off(board_id):
    if board_id not in BOARD_PORTS: return jsonify({"error": "Invalid board_id"}), 404
    send_command(board_id, "ALL_FAN_OFF"); return jsonify({"success": True})

@app.route("/api/fan/<int:board_id>/<int:cell>/on", methods=["POST"])
def fan_on(board_id, cell):
    if board_id not in BOARD_PORTS: return jsonify({"error": "Invalid board_id"}), 404
    send_command(board_id, f"FAN_ON_{cell}"); return jsonify({"success": True})

@app.route("/api/fan/<int:board_id>/<int:cell>/off", methods=["POST"])
def fan_off(board_id, cell):
    if board_id not in BOARD_PORTS: return jsonify({"error": "Invalid board_id"}), 404
    send_command(board_id, f"FAN_OFF_{cell}"); return jsonify({"success": True})

# ─── LEDs ───

@app.route("/api/led/all/all/<color>", methods=["POST"])
def led_all_sections(color):
    color = color.upper()
    if color not in ["R","G","B","W","OFF"]: return jsonify({"error": "Invalid color"}), 400
    send_all(f"ALL_LED_{color}"); return jsonify({"success": True})

@app.route("/api/led/all/breathe/green", methods=["POST"])
def breathe_green_all():
    send_all("BREATHE_GREEN"); return jsonify({"success": True})

@app.route("/api/led/all/breathe/stop", methods=["POST"])
def breathe_stop_all():
    send_all("BREATHE_STOP"); return jsonify({"success": True})

@app.route("/api/led/<int:board_id>/all/<color>", methods=["POST"])
def led_all(board_id, color):
    if board_id not in BOARD_PORTS: return jsonify({"error": "Invalid board_id"}), 404
    color = color.upper()
    if color not in ["R","G","B","W","OFF"]: return jsonify({"error": "Invalid color"}), 400
    send_command(board_id, f"ALL_LED_{color}"); return jsonify({"success": True})

@app.route("/api/led/<int:board_id>/<int:cell>/<color>", methods=["POST"])
def led_cell(board_id, cell, color):
    if board_id not in BOARD_PORTS: return jsonify({"error": "Invalid board_id"}), 404
    color = color.upper()
    if color not in ["R","G","B","W","OFF"]: return jsonify({"error": "Invalid color"}), 400
    send_command(board_id, f"LED_{color}_{cell}"); return jsonify({"success": True})

@app.route("/api/led/<int:board_id>/breathe/green", methods=["POST"])
def breathe_green(board_id):
    if board_id not in BOARD_PORTS: return jsonify({"error": "Invalid board_id"}), 404
    send_command(board_id, "BREATHE_GREEN"); return jsonify({"success": True})

@app.route("/api/led/<int:board_id>/breathe/stop", methods=["POST"])
def breathe_stop(board_id):
    if board_id not in BOARD_PORTS: return jsonify({"error": "Invalid board_id"}), 404
    send_command(board_id, "BREATHE_STOP"); return jsonify({"success": True})

# ─── SOLENOIDS ───

@app.route("/api/solenoid/<int:board_id>/<int:cell>/on", methods=["POST"])
def solenoid_on(board_id, cell):
    if board_id not in BOARD_PORTS: return jsonify({"error": "Invalid board_id"}), 404
    send_command(board_id, f"SOL_ON_{cell}"); return jsonify({"success": True})

@app.route("/api/solenoid/<int:board_id>/<int:cell>/off", methods=["POST"])
def solenoid_off(board_id, cell):
    if board_id not in BOARD_PORTS: return jsonify({"error": "Invalid board_id"}), 404
    send_command(board_id, f"SOL_OFF_{cell}"); return jsonify({"success": True})

# ─── PAGES ───

@app.route("/")
def dashboard():
    return send_from_directory(os.path.dirname(__file__), "index.html")

@app.route("/control")
def control_panel():
    return send_from_directory(os.path.dirname(__file__), "control_panel.html")


if __name__ == "__main__":
    load_state()

    for board_id, port in BOARD_PORTS.items():
        t = threading.Thread(target=read_serial, args=(board_id, port), daemon=True)
        t.start()
        print(f"[Startup] Board {board_id} on {port}")

    threading.Thread(target=nightly_scheduler, daemon=True).start()
    threading.Thread(target=dry_queue_worker,  daemon=True).start()
    threading.Thread(target=check_wall_fans,   daemon=True).start()
    print("[Startup] Starting in AUTO mode")
    print("\n✅ Greenwall running!")
    print("   Dashboard: http://localhost:5000")
    print("   Controls:  http://localhost:5000/control\n")

    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
