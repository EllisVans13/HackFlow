"""One-click local demo: isolated SQLite, automatic setup, one localhost server."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.request
import venv
import webbrowser

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / '.local-data'
ENV = ROOT / '.venv-local'

def run(*args, cwd=ROOT):
    subprocess.run([str(x) for x in args], cwd=cwd, check=True)

def fingerprint(paths):
    digest = hashlib.sha256()
    for path in sorted(paths):
        digest.update(str(path.relative_to(ROOT)).encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()

def settings():
    DATA.mkdir(parents=True, exist_ok=True)
    path = DATA / 'settings.json'
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        return json.loads(path.read_text(encoding='utf-8'))
    values = {'secret': secrets.token_hex(32), 'demo_password': secrets.token_urlsafe(15)}
    with os.fdopen(fd, 'w', encoding='utf-8') as handle:
        json.dump(values, handle)
    return values

def setup_environment():
    python = ENV / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    if not python.exists():
        print('1/4 Создаём Python-окружение…', flush=True)
        venv.EnvBuilder(with_pip=True).create(ENV)
    if Path(sys.prefix).resolve() != ENV.resolve():
        os.execv(str(python), [str(python), str(Path(__file__).resolve()), *sys.argv[1:]])
    inputs = fingerprint([ROOT / 'backend/requirements.txt'])
    marker = ENV / 'hackflow-requirements.sha256'
    if not marker.exists() or marker.read_text() != inputs:
        print('1/4 Устанавливаем Python-зависимости (первый запуск может занять несколько минут)…', flush=True)
        run(sys.executable, '-m', 'pip', 'install', '-r', ROOT / 'backend/requirements.txt')
        marker.write_text(inputs)

def build_frontend():
    frontend = ROOT / 'frontend'
    DATA.mkdir(parents=True, exist_ok=True)
    os.environ['npm_config_cache'] = str(DATA / 'npm-cache')
    # Homebrew's versioned Node distributions are not on PATH in Finder sessions.
    for directory in ('/opt/homebrew/opt/node@22/bin', '/usr/local/opt/node@22/bin',
                      '/opt/homebrew/bin', '/usr/local/bin'):
        if Path(directory, 'node').is_file():
            os.environ['PATH'] = directory + os.pathsep + os.environ.get('PATH', '')
    npm = shutil.which('npm')
    if not npm or not shutil.which('node'):
        raise RuntimeError('Нужен Node.js 22 LTS или новее. Установите его с https://nodejs.org и запустите файл снова.')
    node = shutil.which('node')
    version = subprocess.check_output([node, '-p', 'process.versions.node'], text=True).strip()
    if int(version.split('.')[0]) < 22:
        raise RuntimeError('Обновите Node.js до версии 22 LTS или новее: https://nodejs.org')
    deps = fingerprint([frontend / 'package.json', frontend / 'package-lock.json'])
    marker = DATA / 'node-dependencies.sha256'
    if not (frontend / 'node_modules').exists() or not marker.exists() or marker.read_text() != deps:
        print('2/4 Устанавливаем зависимости интерфейса…', flush=True)
        run(npm, 'ci', cwd=frontend)
        marker.write_text(deps)
    sources = [frontend / 'package.json', frontend / 'package-lock.json',
               frontend / 'index.html', frontend / 'vite.config.js']
    for directory in ('src', 'public'):
        sources.extend(path for path in (frontend / directory).rglob('*') if path.is_file())
    source_hash = fingerprint(sources)
    marker = DATA / 'frontend-build.sha256'
    if not (frontend / 'dist/index.html').exists() or not marker.exists() or marker.read_text() != source_hash:
        print('2/4 Собираем интерфейс…', flush=True)
        run(npm, 'run', 'build', cwd=frontend)
        marker.write_text(source_hash)

def prepare_app(port):
    values = settings()
    # Deliberately isolate local SQLite mode from any existing Docker/production .env.
    os.environ['SECRET_KEY'] = values['secret']
    os.environ['COOKIE_SECURE'] = 'false'
    os.environ['CORS_ORIGINS'] = f'http://localhost:{port}'
    os.environ['MAIL_PORT'] = '587'
    sys.path.insert(0, str(ROOT / 'backend'))
    from hackflow import create_app
    from hackflow.models import db
    from flask_migrate import upgrade
    from sqlalchemy import event
    app = create_app({
        'SECRET_KEY': values['secret'],
        'SQLALCHEMY_DATABASE_URI': 'sqlite:///' + (DATA / 'hackflow.sqlite3').as_posix(),
        'SQLALCHEMY_ENGINE_OPTIONS': {'connect_args': {'timeout': 30}},
        'SESSION_COOKIE_SECURE': False,
        'UPLOAD_FOLDER': str(DATA / 'uploads'),
        'FRONTEND_DIST': str(ROOT / 'frontend/dist'),
        'RATELIMIT_STORAGE_URI': 'memory://',
        'PUBLIC_URL': f'http://localhost:{port}',
        'MAIL_SERVER': None,
    })
    with app.app_context():
        print('3/4 Проверяем локальную базу…', flush=True)
        upgrade(directory=str(ROOT / 'backend/migrations'))
        # Batch migrations rebuild tables. Enforce foreign keys on subsequent connections.
        def foreign_keys(connection, _):
            connection.execute('PRAGMA foreign_keys=ON')
        event.listen(db.engine, 'connect', foreign_keys)
        db.engine.dispose()
        result = app.test_cli_runner().invoke(args=['seed-demo', '--password', values['demo_password']])
        if result.exit_code:
            raise RuntimeError('Не удалось добавить демоданные: ' + result.output + str(result.exception or ''))
        result=app.test_cli_runner().invoke(args=['seed-review-demo'])
        if result.exit_code:raise RuntimeError('Ошибка демоданных Peer Review: '+result.output+str(result.exception or ''))
    return app, values

def open_when_ready(url):
    for _ in range(60):
        try:
            with urllib.request.urlopen(url + '/api/health', timeout=1) as response:
                if json.load(response).get('status') == 'ok':
                    webbrowser.open(url)
                    return
        except (OSError, ValueError):
            pass
        time.sleep(0.5)

def reminders(app, stop):
    from hackflow.models import db
    from hackflow.services import dispatch_reminders
    while not stop.is_set():
        with app.app_context():
            try:
                dispatch_reminders()
            except Exception:
                db.session.rollback()
                app.logger.exception('Ошибка локальных напоминаний')
        stop.wait(60)

def main():
    parser = argparse.ArgumentParser(description='HackFlow без Docker и PostgreSQL')
    parser.add_argument('--port', type=int, default=8000)
    parser.add_argument('--no-browser', action='store_true')
    args = parser.parse_args()
    if sys.version_info < (3, 12):
        raise RuntimeError('Нужен Python 3.12 или новее: https://www.python.org/downloads/')
    if not 1 <= args.port <= 65535:
        raise RuntimeError('Порт должен быть от 1 до 65535.')
    with socket.socket() as probe:
        try:
            probe.bind(('127.0.0.1', args.port))
        except OSError:
            raise RuntimeError(f'Порт {args.port} занят. Закройте предыдущий запуск или выполните python3 scripts/start_local.py --port 8001.')
    setup_environment()
    build_frontend()
    app, values = prepare_app(args.port)
    url = f'http://localhost:{args.port}'
    print('\n4/4 Готово! Откройте ' + url, flush=True)
    print('Капитан: captain@hackflow.test', flush=True)
    print('Организатор: organizer@hackflow.test', flush=True)
    print('Администратор: admin@hackflow.test (при первоначальном создании демобазы)', flush=True)
    print('Пароль демоаккаунтов: ' + values['demo_password'], flush=True)
    print('Данные сохраняются в .local-data. Для остановки нажмите Ctrl+C.\n', flush=True)
    if not args.no_browser:
        threading.Thread(target=open_when_ready, args=(url,), daemon=True).start()
    stop = threading.Event()
    worker = threading.Thread(target=reminders, args=(app, stop), daemon=True)
    worker.start()
    try:
        app.run(host='127.0.0.1', port=args.port, debug=False, use_reloader=False)
    finally:
        stop.set()
        worker.join(timeout=2)

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('\nHackFlow остановлен. Данные сохранены.')
    except (RuntimeError, OSError, ValueError, subprocess.CalledProcessError) as error:
        print('\nОшибка запуска: ' + str(error), file=sys.stderr)
        sys.exit(1)
