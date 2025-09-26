#!/bin/bash
cp -nr /oopt-gnpy/gnpy/example-data /shared

python oopt-gnpy/gnpy/tools/flaskrun.py
exec "$@"
