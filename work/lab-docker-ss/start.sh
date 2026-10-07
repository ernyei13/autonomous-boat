#!/bin/bash
wait_for_host() {
  while ! nc -z $1 $2; do sleep 1; done;
}

echo "Waiting for vehicles..."
wait_for_host ardupilot-sitl-1 5760
wait_for_host ardupilot-sitl-2 5770

echo "Starting Dedicated Proxies..."
mavproxy.py --master=tcp:ardupilot-sitl-1:5760 --out=tcpin:0.0.0.0:16001 --out=udp:127.0.0.1:14560  --out=tcpin:0.0.0.0:16010 --state-basedir=/tmp --daemon --non-interactive &
mavproxy.py --master=tcp:ardupilot-sitl-2:5770 --out=tcpin:0.0.0.0:16002 --out=udp:127.0.0.1:14570  --out=tcpin:0.0.0.0:16011 --state-basedir=/tmp --daemon --non-interactive &

sleep 5

echo "Starting Swarm Aggregator (Port 16000)..."
exec mavproxy.py --master=tcp:localhost:16001 --master=tcp:localhost:16002 --out=tcpin:0.0.0.0:16000 --out=udpbcast:0.0.0.0:14550 --aircraft=SwarmController --state-basedir=/tmp
