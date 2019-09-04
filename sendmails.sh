#!/bin/sh

CONFIG=$(pwd)/config.json

if [ ! -f "$CONFIG" ]; then
	CONFIG=$(pwd)/config.minimal.json
fi

python3.7 icbd/sendmails.py --config=$CONFIG
