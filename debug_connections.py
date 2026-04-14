import requests
import logging

logging.basicConfig(level=logging.INFO)

def test_ip(ip):
    url = f"http://{ip}/getjp"
    print(f"Testing {url}...")
    try:
        # Mini payload just to see if it responds
        payload = "preval=none;{\"152\":null}"
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        response = requests.post(url, data=payload, headers=headers, timeout=5)
        print(f"✅ {ip} responded with status {response.status_code}")
        return True
    except Exception as e:
        print(f"❌ {ip} failed: {e}")
        return False

print("Check 1: Local IP from screenshot")
test_ip("192.168.1.100")

print("\nCheck 2: Tailscale IP from previous logs")
test_ip("100.116.216.29")

print("\nCheck 3: Possible other Tailscale IP")
test_ip("100.93.13.71")
