#!/bin/bash
set -e

cd "$(dirname "$0")"

source .venv/bin/activate

echo
echo "============================================================"
echo " 1W EXCITER - SMOOTH BOWL DRIVE TESTS"
echo "============================================================"

echo
echo "TEST 1 - Gentle"
echo "0.07% drive, 8s attack, 4s hold, 10s release"
echo
python tools/smooth_bowl_drive.py \
    --frequency 528.7 \
    --amplitude 0.0007 \
    --attack 8 \
    --hold 4 \
    --release 10

sleep 3

echo
echo "TEST 2 - Faster"
echo "0.07% drive, 3s attack, 4s hold, 5s release"
echo
python tools/smooth_bowl_drive.py \
    --frequency 528.7 \
    --amplitude 0.0007 \
    --attack 3 \
    --hold 4 \
    --release 5

sleep 3

echo
echo "TEST 3 - Slow sound-bath swell"
echo "0.07% drive, 15s attack, 10s hold, 20s release"
echo
python tools/smooth_bowl_drive.py \
    --frequency 528.7 \
    --amplitude 0.0007 \
    --attack 15 \
    --hold 10 \
    --release 20

echo
echo "============================================================"
echo " COMPLETE"
echo "============================================================"
