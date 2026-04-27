from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS
import serial
import threading
import json
import time
import os
from datetime import datetime, timedelta
from collections import deque

app = Flask(__name__)
CORS(app)

BOARD_PORTS = {
    1: "/dev/ttyACM0",
    2: "/dev/ttyACM1",
    3: "/dev/ttyACM2",
    4: "/dev/ttyACM3",
}
BAUD_RATE = 9600

PUMP_BOARD_PORT    = "/dev/ttyACM0"
DRY_THRESHOLD      = 200
PRESSURIZE_DELAY   = 120
SOLENOID_DELAY     = 10
OPEN_DURATION      = 300
NIGHTLY_HOUR       = 21
DRY_CHECK_DELAY    = 5
STARTUP_DELAY      = 120
CELL_COOLDOWN      = 3600  # 1 hour cooldown per cell after watering

START_TIME = time.time()

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
pump_serial    = None
dry_queue      = deque()
dry_queue_lock = threading.Lock()
already_queued = set()
last_watered   = {}  # cell_index -> timestamp of last watering


def send_command(cmd):
    global pump_serial
    if pump_serial and pump_serial.is_open:
        try:
            pump_serial.write((cmd + "\n").encode())
            print(f"[Pump] Sent: {cmd}")
            time.sleep(0.2)
        except Exception as e:
            print(f"[Pump] Send error: {e}")
    else:
        print(f"[Pump] Serial not available, command dropped: {cmd}")


def run_nightly_cycle():
    global pump_running
    print("[Pump] Starting nightly cycle")
    with pump_lock:
        pump_running = True
    try:
        send_command("PUMP_ON")
        print(f"[Pump] Pressurizing for {PRESSURIZE_DELAY}s...")
        time.sleep(PRESSURIZE_DELAY)
        for i in range(1, 7):
            send_command(f"SOL_ON_{i}")
            print(f"[Pump] Opened solenoid {i}")
            time.sleep(SOLENOID_DELAY)
        print(f"[Pump] All solenoids open, waiting {OPEN_DURATION}s...")
        time.sleep(OPEN_DURATION)
        for i in range(1, 7):
            send_command(f"SOL_OFF_{i}")
            print(f"[Pump] Closed solenoid {i}")
            time.sleep(SOLENOID_DELAY)
        send_command("PUMP_OFF")
        print("[Pump] Nightly cycle complete")
        # Mark all cells as watered after nightly cycle
        with dry_queue_lock:
            for i in range(6):
                last_watered[i] = time.time()
    except Exception as e:
        print(f"[Pump] Error during nightly cycle: {e}")
        send_command("ALL_SOL_OFF")
        send_command("PUMP_OFF")
    with pump_lock:
        pump_running = False


def run_dry_cell_cycle(cell_index):
    global pump_running
    sol_num = cell_index + 1
    print(f"[Pump] Dry trigger — running solenoid {sol_num}")
    with pump_lock:
        pump_running = True
    try:
        send_command("PUMP_ON")
        print(f"[Pump] Pressurizing for {PRESSURIZE_DELAY}s...")
        time.sleep(PRESSURIZE_DELAY)
        send_command(f"SOL_ON_{sol_num}")
        print(f"[Pump] Solenoid {sol_num} open, waiting {OPEN_DURATION}s...")
        time.sleep(OPEN_DURATION)
        send_command(f"SOL_OFF_{sol_num}")
        send_command("PUMP_OFF")
        print(f"[Pump] Dry cycle complete for cell {sol_num}")
        # Record watering time for this cell
        with dry_queue_lock:
            last_watered[cell_index] = time.time()
    except Exception as e:
        print(f"[Pump] Error during dry cycle: {e}")
        send_command(f"SOL_OFF_{sol_num}")
        send_command("PUMP_OFF")
    with pump_lock:
        pump_running = False
    with dry_queue_lock:
        already_queued.discard(cell_index)


def dry_queue_worker():
    while True:
        time.sleep(DRY_CHECK_DELAY)
        with pump_lock:
            running = pump_running
        if not running:
            cell = None
            with dry_queue_lock:
                if dry_queue:
                    cell = dry_queue.popleft()
            if cell is not None:
                threading.Thread(
                    target=run_dry_cell_cycle, args=(cell,), daemon=True
                ).start()
                time.sleep(10)


def queue_dry_cell(cell_index):
    with dry_queue_lock:
        # Check cooldown
        last = last_watered.get(cell_index, 0)
        if time.time() - last < CELL_COOLDOWN:
            remaining = int((CELL_COOLDOWN - (time.time() - last)) / 60)
            print(f"[Pump] Cell {cell_index + 1} in cooldown, {remaining}min remaining")
            return
        if cell_index not in already_queued:
            already_queued.add(cell_index)
            dry_queue.append(cell_index)
            print(f"[Pump] Queued dry cell {cell_index + 1}")


def nightly_scheduler():
    while True:
        now = datetime.now()
        target = now.replace(hour=NIGHTLY_HOUR, minute=0, second=0, microsecond=0)
        if now >= target:
            target += timedelta(days=1)
        wait = (target - now).total_seconds()
        print(f"[Pump] Next nightly cycle in {wait/3600:.1f} hours at {target.strftime('%H:%M')}")
        time.sleep(wait)
        with pump_lock:
            running = pump_running
        if not running:
            threading.Thread(target=run_nightly_cycle, daemon=True).start()
        else:
            print("[Pump] Nightly cycle skipped — pump already running")


def read_serial(board_id, port):
    global pump_serial
    while True:
        try:
            with serial.Serial(port, BAUD_RATE, timeout=2) as ser:
                print(f"[Board {board_id}] Connected on {port}")
                if board_id == 1:
                    pump_serial = ser
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
                        if time.time() - START_TIME > STARTUP_DELAY:
                            for cell in packet.get("cells", []):
                                moist = cell.get("moist", -1)
                                if moist > 10 and moist < DRY_THRESHOLD:
                                    queue_dry_cell(cell["cell"] - 1)
                    except json.JSONDecodeError:
                        print(f"[Board {board_id}] Bad JSON: {line}")
        except serial.SerialException as e:
            print(f"[Board {board_id}] Serial error on {port}: {e}. Retrying in 5s...")
            if board_id == 1:
                pump_serial = None
            with data_lock:
                greenhouse_data[board_id]["online"] = False
            time.sleep(5)


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
    uptime = int(time.time() - START_TIME)
    with dry_queue_lock:
        cooldowns = {
            str(i + 1): max(0, int((CELL_COOLDOWN - (time.time() - t)) / 60))
            for i, t in last_watered.items()
        }
    return jsonify({
        "status":               "ok",
        "boards_online":        online,
        "pump_running":         running,
        "uptime_seconds":       uptime,
        "startup_delay_active": uptime < STARTUP_DELAY,
        "cell_cooldowns_min":   cooldowns,
        "timestamp":            datetime.now().isoformat(),
    })


@app.route("/api/pump/trigger", methods=["POST"])
def manual_pump_trigger():
    with pump_lock:
        running = pump_running
    if running:
        return jsonify({"error": "Pump already running"}), 409
    threading.Thread(target=run_nightly_cycle, daemon=True).start()
    return jsonify({"success": True, "message": "Nightly cycle started manually"})


@app.route("/")
def dashboard():
    return send_from_directory(os.path.dirname(__file__), "index.html")


if __name__ == "__main__":
    for board_id, port in BOARD_PORTS.items():
        t = threading.Thread(target=read_serial, args=(board_id, port), daemon=True)
        t.start()
        print(f"[Startup] Listening for Board {board_id} on {port}")

    threading.Thread(target=nightly_scheduler, daemon=True).start()
    threading.Thread(target=dry_queue_worker,  daemon=True).start()
    print("[Startup] Pump controller started, nightly cycle at 9PM")
    print(f"[Startup] Dry cell checks will begin in {STARTUP_DELAY}s")

    print("\n✅ Greenwall server running!")
    print("   Local:   http://localhost:5000")
    print("   Network: http://<your-pi-ip>:5000")
    print("   Find your IP with: hostname -I\n")

    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
