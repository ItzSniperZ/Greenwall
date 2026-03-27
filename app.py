"""
Greenwall - Self-Monitoring Hydroponic Wall
=========================================
Unified Flask server for Raspberry Pi.

- Reads JSON data from 4 Arduino Megas over USB serial (/dev/ttyACM0-3)
- Stores latest data in memory
- Serves the dashboard at http://<pi-ip>:5000/
- Exposes API at http://<pi-ip>:5000/api/data
- Accessible from any device on the same network

Usage:
    python app.py

Install deps:
    pip install flask flask-cors pyserial
"""

from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS
import serial
import threading
import json
import time
import os
from datetime import datetime

app = Flask(__name__)
CORS(app)

# ─────────────────────────────────────────────────────
# SERIAL PORT CONFIG
# Update these if your Pi assigns different ports.
# Run `ls /dev/ttyACM*` to check.
# ─────────────────────────────────────────────────────
BOARD_PORTS = {
    1: "/dev/ttyACM0",
    2: "/dev/ttyACM1",
    3: "/dev/ttyACM2",
    4: "/dev/ttyACM3",
}
BAUD_RATE = 9600

# ─────────────────────────────────────────────────────
# IN-MEMORY DATA STORE
# Keyed by board_id (1-4), matches the JSON packet format
# the Arduinos send.
# ─────────────────────────────────────────────────────
greenhouse_data = {
    board_id: {
        "board_id": board_id,
        "cells": [],
        "light": 0,
        "aqi": 0,
        "pump": 0,
        "online": False,
        "last_updated": None,
    }
    for board_id in range(1, 5)
}

data_lock = threading.Lock()


# ─────────────────────────────────────────────────────
# SERIAL READER
# One thread per Arduino. Reconnects automatically if
# the cable is unplugged or the board resets.
# ─────────────────────────────────────────────────────
def read_serial(board_id, port):
    """Continuously read JSON packets from one Arduino."""
    while True:
        try:
            with serial.Serial(port, BAUD_RATE, timeout=2) as ser:
                print(f"[Board {board_id}] Connected on {port}")
                time.sleep(2)  # Wait for Arduino to finish booting
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
                    except json.JSONDecodeError:
                        print(f"[Board {board_id}] Bad JSON: {line}")

        except serial.SerialException as e:
            print(f"[Board {board_id}] Serial error on {port}: {e}. Retrying in 5s...")
            with data_lock:
                greenhouse_data[board_id]["online"] = False
            time.sleep(5)


# ─────────────────────────────────────────────────────
# API ROUTES
# ─────────────────────────────────────────────────────

@app.route("/api/data")
def get_all_data():
    """All 4 sections — polled by the dashboard every 3s."""
    with data_lock:
        return jsonify(list(greenhouse_data.values()))


@app.route("/api/data/<int:board_id>")
def get_section(board_id):
    """Single section by board_id (1-4)."""
    if board_id not in greenhouse_data:
        return jsonify({"error": "Invalid board_id"}), 404
    with data_lock:
        return jsonify(greenhouse_data[board_id])


@app.route("/api/health")
def health():
    online = sum(1 for s in greenhouse_data.values() if s["online"])
    return jsonify({
        "status": "ok",
        "boards_online": online,
        "timestamp": datetime.now().isoformat(),
    })


# ─────────────────────────────────────────────────────
# SERVE THE DASHBOARD
# Flask serves index.html so any browser on the network
# can open http://<pi-ip>:5000/ — no CORS issues.
# index.html must be in the same folder as this file.
# ─────────────────────────────────────────────────────

@app.route("/")
def dashboard():
    return send_from_directory(os.path.dirname(__file__), "index.html")


# ─────────────────────────────────────────────────────
# STARTUP
# ─────────────────────────────────────────────────────
if __name__ == "__main__":
    # Start one reader thread per Arduino board
    for board_id, port in BOARD_PORTS.items():
        t = threading.Thread(target=read_serial, args=(board_id, port), daemon=True)
        t.start()
        print(f"[Startup] Listening for Board {board_id} on {port}")

    print("\n✅ Greenwall server running!")
    print("   Local:   http://localhost:5000")
    print("   Network: http://<your-pi-ip>:5000")
    print("   Find your IP with: hostname -I\n")

    # host="0.0.0.0" makes it reachable on the whole LAN
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
