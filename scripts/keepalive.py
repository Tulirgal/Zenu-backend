import requests
import time
import os
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Default URL, can be overridden by environment variable
BACKEND_URL = os.environ.get("BACKEND_URL", "https://zenu-backend.onrender.com/api/status")
# Ping every 5 minutes (300 seconds)
INTERVAL_SECONDS = 300

def ping():
    while True:
        try:
            response = requests.get(BACKEND_URL, timeout=10)
            if response.status_code == 200:
                logging.info(f"Successfully pinged backend: {BACKEND_URL}")
            else:
                logging.warning(f"Pinged backend but got status code: {response.status_code}")
        except requests.RequestException as e:
            logging.error(f"Failed to ping backend: {e}")
        
        time.sleep(INTERVAL_SECONDS)

if __name__ == "__main__":
    logging.info(f"Starting keepalive script for {BACKEND_URL} every {INTERVAL_SECONDS}s")
    ping()
