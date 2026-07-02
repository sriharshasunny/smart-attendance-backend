import urllib.request
import time

url = "https://smart-attendance-backend-2fo9.onrender.com/health"
print(f"Fetching {url}...")
start = time.time()
try:
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    response = urllib.request.urlopen(req, timeout=120)
    print(f"Success! Status: {response.getcode()}")
    print(f"Response: {response.read().decode('utf-8')}")
except Exception as e:
    print(f"Error: {e}")
print(f"Time taken: {time.time() - start:.2f}s")
