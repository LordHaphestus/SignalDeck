# config.example.py - copy to config.py and fill in real values
KISMET_URL = "http://localhost:2501"
KISMET_USER = "Kismet Username"
KISMET_PASS = "Kismet Password"

DB_PATH = "/mnt/cyberdeck-db/signals.db"
PID_FILE_DB = "/tmp/db_daemon.pid"
PID_FILE_MONITOR = "/tmp/monitor_daemon.pid"

POLL_INTERVAL_DB = 30
POLL_INTERVAL_MONITOR = 15
FAILURE_THRESHOLD = 3

HUD_HOST = "0.0.0.0"
HUD_PORT = 5000
