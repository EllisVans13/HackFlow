#!/bin/bash
cd -- "$(dirname -- "$0")"
python3 scripts/start_local.py
read -r -p 'Нажмите Enter для закрытия…'
