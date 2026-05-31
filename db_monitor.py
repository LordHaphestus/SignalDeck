import requests
import time
import os
import signal
from datetime import datetime
from config import *

# Configuration pulled from config.py


def write_pid():
    with open(PID_FILE_MONITOR, "w") as f:
        f.write(str(os.getpid()))

def log(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}")


def cleanup(signum, frame):
    log("Monitor Daemon shutting down - cleaning up PID file")
    if os.path.exists(PID_FILE_MONITOR):
        os.remove(PID_FILE_MONITOR)
    exit(0)


def get_datasource_status():
    try:
        response = requests.get(
            f"{KISMET_URL}/datasource/all_sources.json",
            auth=(KISMET_USER, KISMET_PASS),
            timeout=5
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.ConnectionError:
        log("ERROR: Cannot connect to Kismet. Is it Running?")
        return None
    except requests.exceptions.HTTPError as e:
        log(f"ERROR: Kismet API returned error: {e}")
        return None
    except Exception as e:
        log(F"ERROR: Unexpected error fetching datasource status: {e}")
        return None


def check_sources_healthy(sources):
    all_healthy = True
    for source in sources:
        running = source.get("kismet.datasource.running", False)
        error = source.get("kismet.datasource.error", "")
        name = source.get("kismet.datasource.name", "unkonwn")
        if not running or error:
            log(f"WARNING: Source '{name}' unhealthy - running={running}, error='{error}'")
            all_healthy = False
    return all_healthy


def main():
    write_pid()
    signal.signal(signal.SIGTERM, cleanup)
    signal.signal(signal.SIGINT, cleanup)
    log("Monitor Daemon started")

    failure_count = 0

    while True:
        sources = get_datasource_status()
        if sources is None:
            log("Kismet Unreachable - skipping health check")
            failure_count = 0
        elif len(sources) == 0:
            log("WARNING: Kismet running but no capture source configured")
            failure_count = 0
        elif check_sources_healthy(sources):
            if failure_count > 0:
                log("Sources recovered - resetting failure counter")
            failure_count = 0
        else:
            failure_count += 1
            log(f"Source failure detected ({failure_count}/{FAILURE_THRESHOLD})")
            if failure_count >= FAILURE_THRESHOLD:
                log("ALERT: FIFO pipe failure confirmed - capture pipeline down")
                # V2: Send SIGSUR1 to DB Daemon
                # V3: Buzz Arduino
                failure_count = 0

        time.sleep(POLL_INTERVAL_MONITOR)


if __name__ == "__main__":
    main()
