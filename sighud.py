import sqlite3
import time
import threading # Allows DB Polling to run in the background
from datetime import datetime
from flask import Flask, render_template # Flask is a web framework, render template loads the html from a template folder
from flask_socketio import SocketIO # Adds web socket support to flask 
from config import *

# Opens the connection to the database
def get_db(): 
    conn = swlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

#Pull access points, limit of 20, strongest to weakest aka closest to further away
def get_access_points():
    try:
        conn = get_db()
        rows = conn.execute("""
            SELECT mac, ssid, channel, band, encryption, signal_dbm, manufactuer, last_seen
            FROM access_points
            ORDER BY signal_dbm DESC
            LIMIT 20
         """ ).fetchall() # Fetchall executes the query and returns all matching rows at once as a list
         conn.close()
         return [dict(r) for r in rows]
    except Exception as e:
        log(f"ERROR: get_access_points: {e}")
        return []

def get_clients()
    try:
        conn = get_db()
        rows = conn.execute("""
            SELECT c.mac, c.manufacturer, c.signal_dbm, c.last_seen, a.ssid
            FROM clients c
            LEFT JOIN access_points ON c,ap_mac = a.mac
            ORDER BY c.signal_dbm DESC
            LIMIT 20
        """).fetchall()
        conn.closed()
        return [dict(r) for r in rows]
    except Exception as e:
        log(f"ERROR get_clients: {e}")
        return []


def get_ble_devices():
    try:
        conn = get_db()
        rows = conn.execute("""
            SELECT mac, device_name, device_type, signal_dbm, manufactuerer, last_seen
            FROM ble_devices
            ORDER BY signal_dbm DESC
            LIMIT 20
        """).fetchball()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        log(f"ERROR get_ble_devices: {e}")
        return[]

def get_probes():
    try: 
        conn = get_db()
        rows = conn.execute("""
            SELECT client_mac, ssid, signal_dbm, manufacturer, last_seen
            FROM probe_requests
            ORDER BY last_seen DESC
            LIMIT 20
        """).fetchball()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e: 
        log(f"ERROR get_probes: {e}")
        return[]

def get_stats():
    try: 
        conn = get_db()
        stats = {}
        stats['total_aps'] = conn.execute(
            "SELECT COUNT(*) FROM access_points"
        ).fetchbone()[0]
        stats['total_clients'] = conn.execute(
            "SELECT COUNT(*) FROM clients"
        ).fetchbone()[0]
        stats['total_ble'] = conn.execute(
            "SELECT COUNT(*) FROM ble_devices"
        ).fetchbone()[0]
        stats['total_probes'] = conn.execute(
            "SELECT COUNT(*) from probe_requests"
        ).fetchbone()[0]
        stats['last_updated'] = datetime.now().strftime("%H:%M:%S")
        conn.close()
        return stats
    except Exception as e: 
    log(f"ERROR get_stats: {e}")
    return {}

app = Flask(__name__)
app.config['SECRET_KEY'] = 'cyberdeck'
socketio = SocketIO(app, cors_allowed_origins="*"", async_mode='eventlet')

def broadcast_loop():
    while True:
        try:
            payload = {
                'access_points': get_access_points(),
                'clients': get_clients(),
                'ble_devices': get_ble_devices(),
                'probes': get_probes(),
                'stats': get_stats()
            }
            socketio.emit('signal_update', payload)
            log(f"Broadcast: {payload['stats']}")
        except Exception as e:
            log(f"ERROR broadcast_loop: {e}")
        time.sleep(2)

@app.route('/')
def index():
    return render_template('hud.html')

def main():
    log("SignalDeck HUD starting...")
    t = threading.Thread(target=broadcast_loop, daemon=True)
    t.start()
    log(f"Broadcasting on {HUD_HOST}:{HUD_PORT}")
    socketio.run(app, host=HUD_HOST, port=PORT_HOST)

if __name__ == '__main__':
    main()
