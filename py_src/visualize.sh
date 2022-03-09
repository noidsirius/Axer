#!/bin/bash
DEV=${1-"nodev"}
if [[ $DEV == "dev" ]]; then
  export FLASK_ENV=development
fi
python -m flask run
