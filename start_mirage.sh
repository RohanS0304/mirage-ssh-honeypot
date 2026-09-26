#!/bin/bash

cd ~/mirage-honeypot
source .env

echo "[*] Starting Mirage Honeypot..."
python3 ssh_honeypot.py > logs/honeypot_runtime.log 2>&1 &
HONEYPOT_PID=$!

sleep 2

echo "[*] Starting Mirage Dashboard..."
python3 dashboard.py

kill $HONEYPOT_PID 2>/dev/null
