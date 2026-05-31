#!/bin/bash
#Quick note to future me. I have sleeps in between commands cause I am paranoid
#Also don't judge my formatting. This is my script damnit 

#Kill any old TCPDUMP instances
pkill -e -f "tcpdump"
echo "TCPDUMP Jobs Killed"

echo "Removing Old Fifo Files"
# Remove and Create new fifo files
# Without removal old fifo files get corrupted and kill kismet ingest
rm -f /tmp/wndr.fifo /tmp/wndr5.fifo

echo "Creating New Fifo Files"
mkfifo /tmp/wndr.fifo
mkfifo /tmp/wndr5.fifo

echo "Launching mon0 and mon1"
# Establish Data Streams
# 2.4GHz
ssh root@192.168.1.1 "tcpdump -i mon0 -U -w -" > /tmp/wndr.fifo &
# 5GHz 
ssh root@192.168.1.1 "tcpdump -i mon1 -U -w -" > /tmp/wndr5.fifo &

# Stop BlueZ so kismet can take control of hci0
sudo systemctl stop bluetooth
echo "BlueZ Stopped - hci0 released to kismet"
sleep 2

echo "Data Streams Live"
sleep 15
#Buffer here to make sure the data pipes are up before kismet starts pulling on them.

echo "Launching Localhost" 
xdg-open http://localhost:2501

# Launches the sources for Kismet. Currently Mon0, Mon1, and BLE

echo "Launching Kismet"
sleep 5
sudo kismet -c /tmp/wndr.fifo:type=pcapfile,name=2.4GHz -c /tmp/wndr5.fifo:type=pcapfile,name=5GHz -c hci0:type=linuxbluetooth,name=BLE
