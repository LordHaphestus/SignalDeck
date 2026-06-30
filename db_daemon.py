import os
import requests
import sqlite3
import time
import json
from datetime import datetime
from config import *

# Configuration now handeled in config.py

# Database connection Helper


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# Write PID to file


def write_pid():
    with open(PID_FILE, 'w') as f:
        f.write(str(os.getpid()))
    log(f"PID {os.getpid()} written to {PID_FILE}")

# Kismet API Call


def get_kismet_devices():
    try:
        response = requests.post(
            f"{KISMET_URL}/devices/last-time/-60/devices.json",
            auth=(KISMET_USER, KISMET_PASS),
            timeout=5
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.ConnectionError:
        log("ERROR: Cannot connect to Kismet. Is it running?")
        return []
    except requests.exceptions.HTTPError as e:
        log(f"ERROR: Kismet API returned error: {e}")
        return []
    except Exception as e:
        log(f"ERROR: Unexpected error fetching devices: {e}")
        return []

# Sets device type so we know which table to put the data in


def get_device_type(device):
    phyname = device.get("kismet.device.base.phyname", "")
    if phyname == "Bluetooth":
        return "ble"
    type_set = device.get("kismet.device.base.basic_type_set", 0)
    if type_set == 1:
        return "ap"
    elif type_set == 2:
        return "client"
    else:
        return "Unknown"

# upsert Access Points


def upsert_ap(conn, device):
    mac = device.get("kismet.device.base.macaddr", "")
    if not mac:
        return

    ssid_list = device.get("dot11.device", {}).get(
        "dot11.device.advertised_ssid_map", [])
    ssid = ssid_list[0].get("dot11.advertisedssid.ssid",
                            "") if ssid_list else ""

    encryption = device.get("kismet.device.base.crypt", "")
    channel = device.get("kismet.device.base.channel", "")
    frequency = device.get("kismet.device.base.frequency", 0)
    band = "2.4GHz" if frequency < 3000000 else "5GHz"
    signal_dbm = device.get("kismet.device.base.signal", {}).get(
        "kismet.common.signal.last_signal", 0)
    manufacturer = device.get("kismet.device.base.manuf", "")
    first_seen = device.get("kismet.device.base.first_time", 0)
    last_seen = device.get("kismet.device.base.last_time", 0)

    conn.execute("""
		INSERT INTO access_points
			(mac, ssid, encryption, channel, band, signal_dbm, manufacturer, first_seen, last_seen)
		VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
		ON CONFLICT(mac) DO UPDATE SET
			last_seen = excluded.last_seen,
			signal_dbm = excluded.signal_dbm,
			ssid = CASE WHEN excluded.ssid != '' THEN excluded.ssid ELSE access_points.ssid END
	""", (mac, ssid, encryption, channel, band, signal_dbm, manufacturer, first_seen, last_seen))
    conn.commit()

# Upsert Clients


def upsert_clients(conn, device):
    mac = device.get("kismet.device.base.macaddr", "")
    if not mac:
        return
    manufacturer = device.get("kismet.device.base.manuf", "")
    signal_dbm = device.get("kismet.device.base.signal", {}).get(
        "kismet.common.signal.last_signal", 0)
    first_seen = device.get("kismet.device.base.first_time", 0)
    last_seen = device.get("kismet.device.base.last_time", 0)

    conn.execute("""
        INSERT INTO clients
            (mac, manufacturer, signal_dbm, first_seen, last_seen)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(mac) DO UPDATE SET
            last_seen = excluded.last_seen,
            signal_dbm = excluded.signal_dbm
    """, (mac, manufacturer, signal_dbm, first_seen, last_seen))
    conn.commit()

# Upsert Bluetooth Devices


def upsert_ble(conn, device):
    mac = device.get("kismet.device.base.macaddr", "")
    if not mac:
        return

    manufacturer = device.get("kismet.device.base.manuf", "")
    signal_dbm = device.get("kismet.device.base.signal", {}).get(
        "kismet.common.signal.last_signal", 0)
    first_seen = device.get("kismet.device.base.first_time", 0)
    last_seen = device.get("kismet.device.base.last_time", 0)

    bt = device.get("bluetooth.device", {})
    device_type = bt.get("bluetooth.device.type", 0)
    major_class = bt.get("bluetooth.device.major_class", "")
    minor_class = bt.get("bluetooth.device.minor_class", "")
    tx_power = bt.get("bluetooth.device.txpower", 0)

    conn.execute("""
        INSERT INTO ble_devices
            (mac, manufacturer, device_type, major_class, minor_class, tx_power, signal_dbm, first_seen, last_seen)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(mac) DO UPDATE SET
            last_seen = excluded.last_seen,
            signal_dbm = excluded.signal_dbm,
            major_class = CASE WHEN excluded.major_class != '' THEN excluded.major_class ELSE ble_devices.major_class END,
            minor_class = CASE WHEN excluded.minor_class != '' THEN excluded.minor_class ELSE ble_devices.minor_class END
    """, (mac, manufacturer, device_type, major_class, minor_class, tx_power, signal_dbm, first_seen, last_seen))
    conn.commit()

# Upsert AP Clients


def upsert_ap_clients(conn, device):
    ap_mac = device.get("kismet.device.base.macaddr", "")
    if not ap_mac:
        return

    first_seen = device.get("kismet.device.base.first_time", 0)
    last_seen = device.get("kismet.device.base.last_time", 0)

    client_map = device.get("dot11.device", {}).get(
        "dot11.device.associated_client_map", {})

    for client_mac in client_map.keys():
        conn.execute("""
            INSERT INTO ap_clients
                (client_mac, ap_mac, first_seen, last_seen)
            VALUES(?, ?, ?, ?)
            ON CONFLICT(client_mac, ap_mac) DO UPDATE SET
                last_seen = excluded.last_seen
        """, (client_mac, ap_mac, first_seen, last_seen))
    conn.commit()

# Upsert Probes


def upsert_probes(conn, device):
    client_mac = device.get("kismet.device.base.macaddr", "")
    if not client_mac:
        return

    probed_ssid_map = device.get("dot11.device", {}).get(
        "dot11.device.probed_ssid_map", [])

    for probe in probed_ssid_map:
        probed_ssid = probe.get("dot11.probedssid.ssid", "")
        first_seen = probe.get("dot11.probedssid.first_time", 0)
        last_seen = probe.get("dot11.probedssid.last_time", 0)

        conn.execute("""
            INSERT INTO probes
                (client_mac, probed_ssid, first_seen, last_seen)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(client_mac, probed_ssid) DO UPDATE SET
                last_seen = excluded.last_seen
            """, (client_mac, probed_ssid, first_seen, last_seen))
    conn.commit()

# Polling portion, where it all comes together


def poll_kismet():
    write_pid()
    log("Starting DB Daemon")
    conn = get_db()

    while True:
        try:
            devices = get_kismet_devices()
            log(f"Fetched {len(devices)} devices from Kismet")

            for device in devices:
                device_type = get_device_type(device)
#                log(f"Device {device.get('kismet.device.base.macaddr', 'unknown')} type: {device_type}")
#                log(f" basic_type_set: {device.get('kismet.device.base.basic_type_set', 'MISSING')} ")
#                log(f" phyname: {device.get('kismet.device.base.phyname', 'MISSING')} ")

                if device_type == "ap":
                    upsert_ap(conn, device)
                    upsert_ap_clients(conn, device)

                elif device_type == "client":
                    upsert_clients(conn, device)
                    upsert_probes(conn, device)

                elif device_type == "ble":
                    upsert_ble(conn, device)

                else:
                    pass
        except Exception as e:
            log(f"ERROR in poll loop: {e}")

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    poll_kismet()
