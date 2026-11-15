"""Start HackFlow on localhost using Docker Desktop. No ChatGPT account required."""
import json
import os
import getpass
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
URL = 'http://localhost:8000'
DEMO_PASSWORD = os.environ.get('DEMO_PASSWORD')

def command(*args):
    subprocess.run(args, cwd=ROOT, check=True)

def main():
    if not shutil.which('docker'):
        raise RuntimeError('Установите и запустите Docker Desktop, затем повторите запуск.')
    subprocess.run(['docker', 'info'], cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
    if not (ROOT / '.env').exists():
        command(sys.executable, str(ROOT / 'scripts' / 'configure.py'))
    command('docker', 'compose', 'up', '--build', '-d')
    print('Ожидаем запуска приложения на localhost…', flush=True)
    deadline = time.monotonic() + 180
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(URL + '/api/health', timeout=3) as response:
                if json.load(response).get('status') == 'ok':
                    break
        except (OSError, ValueError, urllib.error.URLError):
            time.sleep(2)
    else:
        raise RuntimeError('Сервис не запустился. Выполните docker compose logs app migrate db.')
    with urllib.request.urlopen(URL + '/api/hackathons', timeout=10) as response:
        empty = not json.load(response)['items']
    if empty:
        password = DEMO_PASSWORD or getpass.getpass('Задайте пароль демоаккаунтов (минимум 12 символов): ')
        if len(password) < 12: raise RuntimeError('Пароль должен содержать минимум 12 символов.')
        command('docker', 'compose', 'exec', '-T', 'app', 'flask', '--app', 'wsgi', 'seed-demo', '--password', password)
    print('\nHackFlow запущен: ' + URL)
    print('Участник: participant@hackflow.test')
    print('Капитан: captain@hackflow.test')
    print('Организатор: organizer@hackflow.test')
    print('Жюри: jury@hackflow.test')
    print('Главный администратор: admin@hackflow.test (если первый админ создан демоскриптом)')
    if empty:
        print('Используйте пароль, заданный при заполнении базы.')
    else:
        print('Используйте пароль, заданный при первоначальном заполнении демобазы.')
    print('Вход через ChatGPT не нужен. Код команды: HACKFLOW26')
    print('Остановка: docker compose down (данные сохраняются).')
    webbrowser.open(URL)

if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, subprocess.CalledProcessError, OSError, ValueError) as error:
        print('\nОшибка запуска: ' + str(error), file=sys.stderr)
        sys.exit(1)
