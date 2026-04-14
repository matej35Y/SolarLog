import requests
import socket

def test():
    print("Testing 192.168.1.100 with 30s timeout...")
    try:
        # Use a session to perhaps keep connection open
        s = requests.Session()
        r = s.get("http://192.168.1.100/getjp", timeout=30)
        print(f"Success! Status: {r.status_code}")
        print(f"Content: {r.text[:100]}")
    except Exception as e:
        print(f"Failed IP: {e}")

    print("\nTesting solar-log-4296 with 30s timeout...")
    try:
        r = requests.get("http://solar-log-4296/getjp", timeout=30)
        print(f"Success Host! Status: {r.status_code}")
    except Exception as e:
        print(f"Failed Host: {e}")

if __name__ == "__main__":
    test()
