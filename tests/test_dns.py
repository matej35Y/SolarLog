import requests
import socket

target_host = "desktop-l3cv8h8"
target_port = 8085

try:
    ip = socket.gethostbyname(target_host)
    print(f"Host '{target_host}' resolved to: {ip}")
    
    # Try a quick request to the specified port
    url = f"http://{target_host}:{target_port}/getjp"
    print(f"Trying to connect to: {url}")
    
    payload = 'preval=none;{"141":{"32000":{"108":None}},"776":{"0":None}}'
    headers = {
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "X-Requested-With": "XMLHttpRequest"
    }
    
    r = requests.post(url, data=payload, headers=headers, timeout=10)
    print(f"Response status: {r.status_code}")
    print(f"Response body snippet: {r.text[:200]}")
    
except Exception as e:
    print(f"Error connecting to host: {e}")

try:
    # Try with .local suffix for mDNS if direct fails
    local_host = f"{target_host}.local"
    ip_local = socket.gethostbyname(local_host)
    print(f"Host '{local_host}' resolved to: {ip_local}")
    
    url_local = f"http://{local_host}:{target_port}/getjp"
    print(f"Trying to connect to: {url_local}")
    r = requests.post(url_local, data=payload, headers=headers, timeout=10)
    print(f"Response status (local): {r.status_code}")
    print(f"Response body snippet (local): {r.text[:200]}")
except Exception as e:
    print(f"Error with .local suffix: {e}")
