#!/bin/bash
cd -- "$(dirname -- "$0")" || exit 1
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
PYTHON=""
for candidate in python3.12 python3.13 python3.14 python3; do
  if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import sys; sys.exit(sys.version_info < (3, 12))' 2>/dev/null; then
    PYTHON="$candidate"
    break
  fi
done
if [ -z "$PYTHON" ]; then
  echo 'Установите Python 3.12 или новее с https://www.python.org/downloads/ и откройте файл снова.'
else
  "$PYTHON" scripts/start_local.py
fi
read -r -p 'Нажмите Enter для закрытия…'
