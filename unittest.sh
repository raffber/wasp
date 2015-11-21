#!/bin/bash

curdir=$(dirname $0)
PYTHONPATH=$PYTHONPATH:"$curdir/src"
py.test tests
