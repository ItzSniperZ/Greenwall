import requests
import time

PI_API = "http://localhost:5000/api/data"
WIX_ENDPOINT = "https://www.bsuthinktank.com/_functions/sensorData"
INTERVAL = 3600  # 1 hour

def log_to_wix():
    while True:
        try:
            data = requests.get(PI_API, timeout=5).json()
            res = requests.post(WIX_ENDPOINT, json=data, timeout=10)
            print(f"Logged to Wix: {res.status_code} — {res.text}")
        except Exception as e:
            print(f"Logger error: {e}")
        time.sleep(INTERVAL)

if __name__ == "__main__":
    print("Logger started, first push in 1 hour...")
    log_to_wix()
