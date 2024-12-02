#!/bin/bash

RUNTIME_DIR=$(pwd)/runtime

mkdir -p $RUNTIME_DIR

if [ ! -f "$RUNTIME_DIR/selfsigned.key" ] || [ ! -f "$RUNTIME_DIR/selfsigned.cert"  ]; then
	openssl req -new -newkey rsa:4096 -x509 -sha256 -days 365 -nodes -out "$RUNTIME_DIR/selfsigned.cert" -keyout "$RUNTIME_DIR/selfsigned.key"
fi

CONFIG=$(pwd)/config.json

if [ ! -f "$CONFIG" ]; then
	CONFIG=$(pwd)/config.minimal.json
fi

DATA_DIR=$(pwd)/data

OPTS=("--config" "$CONFIG" --data-dir "$DATA_DIR")

if [ "$AUTO_RESPAWN" == "1" ]; then
	OPTS+=("--auto-respawn")
fi

PYTHON3=""

for PYTHON in "python3.13" "python3.12" "python3.11" "python3.10" "python3.9" "python3.8" "python3.7"; do
	PYTHON3=$(command -v $PYTHON 1)

	if [ $? == 0 ]; then
		break
	fi
done

if [ -z "$PYTHON3" ]; then
	echo "No supported python version found."
	exit 1
fi

$PYTHON3 icbd/icbd.py ${OPTS[*]}
