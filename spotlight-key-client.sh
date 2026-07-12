#!/bin/bash
SOCK="${XDG_RUNTIME_DIR:-/tmp/spotlight-key-$(id -u)}/spotlight-key.sock"
if [ ! -S "$SOCK" ]; then
    notify-send "Spotlight-Key" "El daemon no está corriendo" 2>/dev/null
    exit 1
fi
echo "$*" | socat - UNIX-CONNECT:"$SOCK"
