#!/bin/sh

CONFIG=$(pwd)/config.json

python3.7 icbd/sendmails.py --config=$CONFIG
