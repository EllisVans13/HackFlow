"""Render entrypoint: migrate, bootstrap once, then supervise web and reminders."""
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time
from urllib.parse import urlsplit

ROOT=Path(__file__).resolve().parent

def configure_environment(env):
    database=env.get('DATABASE_URL','')
    if not database:
        raise ValueError('Render: подключите PostgreSQL через DATABASE_URL.')
    for prefix in ('postgres://','postgresql://'):
        if database.startswith(prefix):
            database='postgresql+psycopg://'+database[len(prefix):]
            break
    env['DATABASE_URL']=database
    public=(env.get('PUBLIC_URL') or env.get('RENDER_EXTERNAL_URL') or '').rstrip('/')
    if not public or urlsplit(public).scheme not in ('http','https') or not urlsplit(public).netloc:
        raise ValueError('Render: не задан публичный адрес RENDER_EXTERNAL_URL или PUBLIC_URL.')
    env['PUBLIC_URL']=public
    env.setdefault('CORS_ORIGINS',public)
    env.setdefault('COOKIE_SECURE','true' if public.startswith('https://') else 'false')
    env.setdefault('RATELIMIT_STORAGE_URI','memory://')
    port=int(env.get('PORT','10000'))
    if not 1<=port<=65535:raise ValueError('PORT должен быть от 1 до 65535.')
    return port

def prepare_database():
    from flask_migrate import upgrade
    from werkzeug.security import generate_password_hash
    from hackflow import create_app
    from hackflow.models import db,User,Hackathon
    app=create_app()
    with app.app_context():
        upgrade(directory=str(ROOT/'migrations'))
        if not User.query.filter_by(role='admin',is_demo=False).first():
            email=os.environ.get('ADMIN_EMAIL','').strip().lower()
            password=os.environ.get('ADMIN_PASSWORD','')
            nickname=os.environ.get('ADMIN_NICKNAME','Администратор').strip()
            if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email) or len(email)>254:
                raise ValueError('Заполните корректный ADMIN_EMAIL в настройках Render.')
            if len(password)<12:raise ValueError('ADMIN_PASSWORD должен содержать минимум 12 символов.')
            if not 1<=len(nickname)<=64:raise ValueError('ADMIN_NICKNAME должен содержать от 1 до 64 символов.')
            if User.query.filter((User.email==email)|(User.nickname==nickname)).first():
                raise ValueError('ADMIN_EMAIL или ADMIN_NICKNAME уже занят другим аккаунтом.')
            db.session.add(User(email=email,nickname=nickname,role='admin',is_owner=True,
                                password_hash=generate_password_hash(password)))
            db.session.commit()
            print('Первый администратор создан. Пароль не выводится в журнал.',flush=True)
        if os.environ.get('SEED_DEMO','false').lower()=='true':
            password=os.environ.get('DEMO_PASSWORD','')
            if len(password)<12:raise ValueError('Для демоданных задайте DEMO_PASSWORD от 12 символов.')
            from hackflow.cli import seed
            from hackflow.demo import enrich
            if not Hackathon.query.first():seed(password)
            enrich(password)
        if os.environ.get('SEED_REVIEW_DEMO','true').lower()=='true':
            from hackflow.review_demo import seed_review_demo
            seed_review_demo()
        db.session.remove();db.engine.dispose()

def server_command(port):
    # One worker keeps the in-memory limiter consistent across request threads.
    return [sys.executable,'-m','gunicorn','--bind',f'0.0.0.0:{port}',
            '--workers','1','--threads','4','--timeout','120','wsgi:app']

def serve(port):
    children=[]
    def stop(*_):raise SystemExit(0)
    signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
    try:
        children.append(subprocess.Popen(server_command(port),cwd=ROOT))
        if os.environ.get('RUN_REMINDERS','true').lower()=='true':
            children.append(subprocess.Popen([sys.executable,'-m','hackflow.worker'],cwd=ROOT))
        while True:
            for child in children:
                code=child.poll()
                if code is not None:return code or 1
            time.sleep(.5)
    finally:
        for child in children:
            if child.poll() is None:child.terminate()
        for child in children:
            try:child.wait(timeout=15)
            except subprocess.TimeoutExpired:child.kill();child.wait()

def main():
    port=configure_environment(os.environ)
    prepare_database()
    print('HackFlow готов. Запускаем сайт и напоминания.',flush=True)
    return serve(port)

if __name__=='__main__':
    sys.exit(main())
