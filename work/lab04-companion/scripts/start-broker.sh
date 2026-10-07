#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/env.sh"

exec /opt/homebrew/sbin/mosquitto -c "$LAB04_ROOT/mosquitto.conf"
