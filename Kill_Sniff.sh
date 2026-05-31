#!/bin/bash
pkill -e -f "tcpdump"
echo "TCPDUMP Jobs Killed"

sudo systemctl start bluetooth
echo "BlueZ restarted"
