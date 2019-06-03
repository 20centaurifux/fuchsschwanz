#!/bin/sh

RUNTIME_DIR=$(pwd)/runtime

mkdir -p $RUNTIME_DIR

if [ ! -f "$RUNTIME_DIR/selfsigned.key" ] || [ ! -f "$RUNTIME_DIR/selfsigned.cert"  ]; then
	openssl req -new -newkey rsa:4096 -x509 -sha256 -days 365 -nodes -out "$RUNTIME_DIR/selfsigned.cert" -keyout "$RUNTIME_DIR/selfsigned.key"
fi

python3.7 icbd/icbd.py --config=./config.json --data-dir="$(pwd)/data"
