import requests
import time

PI_API            = "http://localhost:5000/api/data"
WIX_SENSOR        = "https://www.bsuthinktank.com/_functions/sensorData"
WIX_WATERING      = "https://www.bsuthinktank.com/_functions/wateringLog"
SENSOR_INTERVAL   = 3600  # 1 hour
WATERING_INTERVAL = 30    # check for new watering events every 30 seconds

last_seen_watering = set()  # track already-pushed watering events

def push_sensor_data():
    try:
        data = requests.get(PI_API, timeout=5).json()
        res = requests.post(WIX_SENSOR, json=data, timeout=10)
        print(f"[Sensor] Logged to Wix: {res.status_code}")
    except Exception as e:
        print(f"[Sensor] Error: {e}")

def push_watering_events():
    try:
        res = requests.get("http://localhost:5000/api/watering_log", timeout=5)
        events = res.json()
        for event in events:
            key = f"{event['timestamp']}_{event['board_id']}_{event['cell']}"
            if key not in last_seen_watering:
                last_seen_watering.add(key)
                try:
                    r = requests.post(WIX_WATERING, json=event, timeout=10)
                    print(f"[Watering] Logged to Wix: {r.status_code} — board {event['board_id']} cell {event['cell']} ({event['reason']})")
                except Exception as e:
                    print(f"[Watering] Push error: {e}")
    except Exception as e:
        print(f"[Watering] Fetch error: {e}")

def run():
    last_sensor_push = 0
    last_watering_check = 0

    print("Logger started...")

    while True:
        now = time.time()

        if now - last_sensor_push >= SENSOR_INTERVAL:
            push_sensor_data()
            last_sensor_push = now

        if now - last_watering_check >= WATERING_INTERVAL:
            push_watering_events()
            last_watering_check = now

        time.sleep(10)

if __name__ == "__main__":
    run()
