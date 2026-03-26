import serial
import threading
import json
import time

PORTS = [
    "/dev/ttyACM0",
    "/dev/ttyACM1",
    "/dev/ttyACM2",
    "/dev/ttyACM3",
]

BAUD = 9600

latest_cells = {}
lock = threading.Lock()

def read_port(port):
    while True:
        try:
            with serial.Serial(port, BAUD, timeout=1) as ser:
                print(f"Connected {port}")
                time.sleep(2)

                while True:
                    line = ser.readline().decode().strip()
                    if not line:
                        continue

                    try:
                        data = json.loads(line)
                        with lock:
                            for cell in data["cells"]:
                                latest_cells[cell["cell"]] = cell
                        print(f"{port} OK")
                    except:
                        print(f"Bad data: {line}")

        except Exception as e:
            print(f"{port} error: {e}")
            time.sleep(2)

def print_all():
    while True:
        time.sleep(5)
        with lock:
            print("\n==== ALL 24 CELLS ====")
            for c in sorted(latest_cells):
                d = latest_cells[c]
                print(f"Cell {c}: T={d['temp']} H={d['hum']} M={d['moist']}")
            print("======================\n")

if __name__ == "__main__":
    for p in PORTS:
        threading.Thread(target=read_port, args=(p,), daemon=True).start()

    threading.Thread(target=print_all, daemon=True).start()

    while True:
        time.sleep(1)
