import os
import time
import json
import requests
import subprocess
import tempfile

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(BASE_DIR, "config.json"), "r", encoding="utf-8") as f:
    config = json.load(f)

SERVER_URL = config["server_url"].rstrip("/")
TOKEN = config["agent_token"]
PRINTER = config["printer_name"]
SUMATRA = os.path.join(BASE_DIR, "printer", "SumatraPDF.exe")
HEADERS = {"X-Agent-Token": TOKEN}

def get_job():
    try:
        response = requests.get(SERVER_URL + "/agent/jobs", headers=HEADERS, timeout=20)
        response.raise_for_status()
        return response.json().get("job")
    except Exception as e:
        print("Server connection error:", e)
        return None

def update_job(job_id, status):
    try:
        requests.post(SERVER_URL + f"/agent/jobs/{job_id}", headers=HEADERS, json={"status": status}, timeout=20)
    except Exception as e:
        print("Status update error:", e)

def download_file(url):
    temp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    temp.close()
    response = requests.get(url, timeout=120)
    response.raise_for_status()
    with open(temp.name, "wb") as f:
        f.write(response.content)
    return temp.name

def print_pdf(filename, copies):
    command = [SUMATRA, "-print-to", PRINTER, "-silent", "-print-settings", f"{copies}x", filename]
    print("Printing:", filename)
    print("Printer:", PRINTER)
    subprocess.run(command, check=True)

def process_job(job):
    job_id = job["id"]
    local_file = None
    try:
        print("\nNew print job:", job_id)
        local_file = download_file(job["url"])
        print_pdf(local_file, job["copies"])
        update_job(job_id, "completed")
        print("Print completed.")
    except Exception as e:
        print("PRINT ERROR:", e)
        update_job(job_id, "failed")
    finally:
        if local_file:
            try:
                os.remove(local_file)
            except OSError:
                pass

def main():
    print("QR Print Agent started.")
    print("Printer:", PRINTER)
    while True:
        job = get_job()
        if job:
            process_job(job)
        time.sleep(3)

if __name__ == "__main__":
    main()
