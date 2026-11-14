"""Start HackFlow on localhost using Docker Desktop. No ChatGPT account required."""
import json
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
DEMO_PASSWORD = 'HackFlowDemo2026!'

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
        command('docker', 'compose', 'exec', '-T', 'app', 'flask', '--app', 'wsgi', 'seed-demo', '--password', DEMO_PASSWORD)
    print('\nHackFlow запущен: ' + URL)
    print('Участник: participant@hackflow.test')
    print('Капитан: captain@hackflow.test')
    print('Организатор: organizer@hackflow.test')
    print('Жюри: jury@hackflow.test')
    if empty:
        print('Пароль демоаккаунтов: ' + DEMO_PASSWORD)
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
