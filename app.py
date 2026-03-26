"""
Greenwall - Greenhouse Monitoring System
Flask Backend API for Raspberry Pi
Aggregates data from 4 Arduino Mega boards over USB serial
"""

from flask import Flask, jsonify
from flask_cors import CORS
import json
import threading
import time
import random  # Remove when using real serial data
from datetime import datetime

# Uncomment for real serial communication:
# import serial
# import serial.tools.list_ports

app = Flask(__name__)
CORS(app)  # Allow cross-origin requests from the React frontend

# ─────────────────────────────────────────────
# In-memory store for all section data
# Structure mirrors the JSON packets from Arduinos
# ─────────────────────────────────────────────
greenhouse_data = {
    1: {"board_id": 1, "cells": [], "light": 0, "aqi": 0, "pump": 0, "online": False, "last_updated": None},
    2: {"board_id": 2, "cells": [], "light": 0, "aqi": 0, "pump": 0, "online": False, "last_updated": None},
    3: {"board_id": 3, "cells": [], "light": 0, "aqi": 0, "pump": 0, "online": False, "last_updated": None},
    4: {"board_id": 4, "cells": [], "light": 0, "aqi": 0, "pump": 0, "online": False, "last_updated": None},
}

data_lock = threading.Lock()

# ─────────────────────────────────────────────
# Serial Reader Thread
# Listens to all 4 Arduinos over USB
# ─────────────────────────────────────────────

# Map board_id → serial port (update these to match your Pi's /dev/ttyUSB* paths)
SERIAL_PORTS = {
    1: "/dev/ttyUSB0",
    2: "/dev/ttyUSB1",
    3: "/dev/ttyUSB2",
    4: "/dev/ttyUSB3",
}
BAUD_RATE = 9600


def read_serial_port(board_id, port_path):
    """
    Continuously reads JSON packets from a single Arduino over serial.
    Runs in its own thread per board.
    """
    # Uncomment below for real hardware:
    # while True:
    #     try:
    #         with serial.Serial(port_path, BAUD_RATE, timeout=2) as ser:
    #             print(f"[Board {board_id}] Connected on {port_path}")
    #             with data_lock:
    #                 greenhouse_data[board_id]["online"] = True
    #             while True:
    #                 line = ser.readline().decode("utf-8").strip()
    #                 if line:
    #                     try:
    #                         packet = json.loads(line)
    #                         update_board_data(packet)
    #                     except json.JSONDecodeError:
    #                         pass  # Ignore malformed packets
    #     except serial.SerialException as e:
    #         print(f"[Board {board_id}] Serial error: {e}. Retrying in 5s...")
    #         with data_lock:
    #             greenhouse_data[board_id]["online"] = False
    #         time.sleep(5)
    pass


def update_board_data(packet):
    """Update in-memory store from a parsed Arduino JSON packet."""
    board_id = packet.get("board_id")
    if board_id not in greenhouse_data:
        return
    with data_lock:
        greenhouse_data[board_id].update({
            "cells": packet.get("cells", []),
            "light": packet.get("light", 0),
            "aqi": packet.get("aqi", 0),
            "pump": packet.get("pump", 0),
            "online": True,
            "last_updated": datetime.now().isoformat(),
        })


# ─────────────────────────────────────────────
# Demo Data Generator (remove for production)
# Simulates realistic sensor readings
# ─────────────────────────────────────────────

def generate_demo_data():
    """Produces realistic fake sensor data for UI development."""
    while True:
        for board_id in range(1, 5):
            cells = []
            for cell_num in range(1, 7):
                cells.append({
                    "cell": cell_num,
                    "temp": round(random.uniform(20, 30), 1),
                    "hum": round(random.uniform(40, 80), 1),
                    "moist": random.randint(300, 900),  # Raw analog: ~300=wet, ~900=dry
                })
            packet = {
                "board_id": board_id,
                "cells": cells,
                "light": round(random.uniform(30, 95), 1),
                "aqi": round(random.uniform(10, 80), 1),
                "pump": random.choice([0, 0, 0, 1]),  # Mostly off
            }
            update_board_data(packet)
        time.sleep(3)  # Refresh every 3 seconds


# ─────────────────────────────────────────────
# API Routes
# ─────────────────────────────────────────────

@app.route("/api/data", methods=["GET"])
def get_all_data():
    """Returns the full current state of all 4 sections."""
    with data_lock:
        return jsonify(list(greenhouse_data.values()))


@app.route("/api/data/<int:board_id>", methods=["GET"])
def get_section_data(board_id):
    """Returns data for a single section by board_id (1–4)."""
    if board_id not in greenhouse_data:
        return jsonify({"error": "Invalid board_id"}), 404
    with data_lock:
        return jsonify(greenhouse_data[board_id])


@app.route("/api/health", methods=["GET"])
def health():
    """Simple health check endpoint."""
    return jsonify({"status": "ok", "timestamp": datetime.now().isoformat()})


# ─────────────────────────────────────────────
# Startup
# ─────────────────────────────────────────────

if __name__ == "__main__":
    # Start demo data thread (replace with real serial threads for hardware)
    demo_thread = threading.Thread(target=generate_demo_data, daemon=True)
    demo_thread.start()

    # For real hardware, start one thread per Arduino:
    # for board_id, port in SERIAL_PORTS.items():
    #     t = threading.Thread(target=read_serial_port, args=(board_id, port), daemon=True)
    #     t.start()

    # Run Flask — accessible on the local network
    app.run(host="0.0.0.0", port=5000, debug=False)
