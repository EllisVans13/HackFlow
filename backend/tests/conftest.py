import os
import pytest
from hackflow import create_app
from hackflow.models import db, User
from hackflow.cli import seed
from werkzeug.security import generate_password_hash

@pytest.fixture()
def app(tmp_path):
    app=create_app({'TESTING':True,'SQLALCHEMY_DATABASE_URI':os.environ.get('TEST_DATABASE_URL','sqlite://'),'SESSION_COOKIE_SECURE':False,'WTF_CSRF_ENABLED':False,'RATELIMIT_ENABLED':False,'UPLOAD_FOLDER':str(tmp_path/'uploads')})
    with app.app_context():
        db.create_all(); seed('DemoPass2026!')
        db.session.add(User(email='admin@hackflow.test',nickname='Admin',role='admin',password_hash=generate_password_hash('DemoPass2026!')))
        db.session.commit()
    yield app
    with app.app_context():
        db.session.remove(); db.drop_all()

@pytest.fixture()
def client(app): return app.test_client()

def login(client,name):
    r=client.post('/api/auth/login',json={'email':name+'@hackflow.test','password':'DemoPass2026!'})
    assert r.status_code==200,r.json
    return r.json['user']
