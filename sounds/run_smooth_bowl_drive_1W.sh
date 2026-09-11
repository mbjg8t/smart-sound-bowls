#!/bin/bash

cd "$(dirname "$0")/.."

AMPLITUDE="${1:-0.5}"
CHANNEL="${2:-left}"
FREQUENCY="${3:-528.7}"

echo
echo "============================================================"
echo " 1W EXCITER - SMOOTH BOWL DRIVE"
echo "============================================================"
echo "Frequency : ${FREQUENCY} Hz"
echo "Amplitude : ${AMPLITUDE}"
echo "Channel   : ${CHANNEL}"
echo "============================================================"
echo

python3 tools/smooth_bowl_drive.py \
    --device hw:3,1 \
    --channel "$CHANNEL" \
    --frequency "$FREQUENCY" \
    --amplitude "$AMPLITUDE" \
    --attack 3 \
    --hold 4 \
    --release 5

echo
echo "Done."
