#!/bin/bash

# initialize virtualenv or reuese existing one. Use python3
# use whatever version, wasp should be compatible with all of them
virtualenv --no-site-packages --python /usr/bin/python3 env || exit 1
# activate it
source env/bin/activate || exit 1
# install dependencies (only useful for unittesting, otherwise, there are none...
pip install --download-cache=$DLC -e . || exit 1
