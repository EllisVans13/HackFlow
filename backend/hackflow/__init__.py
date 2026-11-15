import os
import secrets
from pathlib import Path
from flask import Flask, jsonify, send_from_directory, request
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_cors import CORS
from flask_wtf.csrf import CSRFProtect, CSRFError
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from sqlalchemy.exc import IntegrityError
from dotenv import load_dotenv
from .models import db, User

login = LoginManager()
csrf = CSRFProtect()
limiter = Limiter(key_func=get_remote_address)

def create_app(config=None):
    load_dotenv()
    app = Flask(__name__, static_folder=None)
    secret = os.environ.get('SECRET_KEY')
    if not secret and not (config and config.get('TESTING')):
        raise RuntimeError('Установите SECRET_KEY в .env (минимум 32 случайных символа).')
    app.config.update(SECRET_KEY=secret or secrets.token_hex(32),
        SQLALCHEMY_DATABASE_URI=os.environ.get('DATABASE_URL', 'postgresql+psycopg://hackflow:hackflow@localhost:5432/hackflow'),
        SQLALCHEMY_TRACK_MODIFICATIONS=False, MAX_CONTENT_LENGTH=20*1024*1024,
        SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax',
        SESSION_COOKIE_SECURE=os.environ.get('COOKIE_SECURE','true').lower() == 'true',
        UPLOAD_FOLDER=os.environ.get('UPLOAD_FOLDER',str(Path(app.instance_path)/'uploads')),
        FRONTEND_DIST=os.environ.get('FRONTEND_DIST',str(Path(__file__).resolve().parents[2]/'frontend'/'dist')),
        RATELIMIT_STORAGE_URI=os.environ.get('RATELIMIT_STORAGE_URI','memory://'),
        MAIL_SERVER=os.environ.get('MAIL_SERVER'), MAIL_PORT=int(os.environ.get('MAIL_PORT','587')),
        MAIL_USER=os.environ.get('MAIL_USER'), MAIL_PASSWORD=os.environ.get('MAIL_PASSWORD'),
        MAIL_FROM=os.environ.get('MAIL_FROM','noreply@example.com'), PUBLIC_URL=os.environ.get('PUBLIC_URL','http://localhost:8000'))
    if config: app.config.update(config)
    Path(app.config['UPLOAD_FOLDER']).mkdir(parents=True,exist_ok=True)
    db.init_app(app)
    Migrate(app,db,compare_type=True)
    login.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)
    CORS(app, resources={r'/api/*': {'origins': os.environ.get('CORS_ORIGINS','http://localhost:5173').split(',')}}, supports_credentials=True)
    from .api import api
    from .cli import register_commands
    app.register_blueprint(api,url_prefix='/api')
    from .certificate_api import certificates_api
    app.register_blueprint(certificates_api,url_prefix='/api')
    from .mentors import mentors_api
    app.register_blueprint(mentors_api,url_prefix='/api')
    from .public_results import public_results_api
    app.register_blueprint(public_results_api,url_prefix='/api')
    register_commands(app)

    @login.user_loader
    def load_user(user_id):
        user=db.session.get(User,int(user_id))
        return user if user and not user.blocked else None

    @login.unauthorized_handler
    def unauthorized(): return jsonify(error='Требуется вход'),401

    @app.errorhandler(CSRFError)
    def csrf_error(e): return jsonify(error='Сессия устарела. Обновите страницу.',code='csrf'),400

    @app.errorhandler(IntegrityError)
    def conflict(e):
        db.session.rollback()
        return jsonify(error='Конфликт данных: запись уже существует или нарушено ограничение.'),409

    @app.errorhandler(400)
    @app.errorhandler(403)
    @app.errorhandler(404)
    @app.errorhandler(409)
    @app.errorhandler(413)
    @app.errorhandler(429)
    def http_error(e): return jsonify(error=str(e.description)),e.code

    @app.after_request
    def headers(response):
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['X-Frame-Options']='DENY'
        response.headers['Referrer-Policy']='same-origin'
        response.headers['Content-Security-Policy']="default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'"
        if request.path.startswith('/api/'): response.headers['Cache-Control']='no-store'
        return response

    @app.get('/',defaults={'path':''})
    @app.get('/<path:path>')
    def frontend(path):
        if path.startswith('api/'): return jsonify(error='Маршрут не найден'),404
        root=Path(app.config['FRONTEND_DIST']).resolve()
        if path and (root/path).is_file(): return send_from_directory(root,path)
        if (root/'index.html').exists(): return send_from_directory(root,'index.html')
        return jsonify(service='HackFlow API',frontend='Выполните npm run build в frontend'),200
    return app
