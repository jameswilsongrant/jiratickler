#!/bin/bash
# A very dumb wrapper to make jiratickler run forever
while [ true ]; do
    ./jiratickler.py
    sleep 60
done
