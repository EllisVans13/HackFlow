"""Exercise the actual launcher database path, not db.create_all()."""
import importlib.util
from pathlib import Path
import pytest
from sqlalchemy.exc import IntegrityError

@pytest.fixture()
def launcher(tmp_path, monkeypatch):
    root=Path(__file__).resolve().parents[2]
    spec=importlib.util.spec_from_file_location('local_launcher',root/'scripts/start_local.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    monkeypatch.setattr(module,'DATA',tmp_path/'local')
    # A user's Docker env must not determine the local database or cookie settings.
    monkeypatch.setenv('DATABASE_URL','postgresql://not-a-local-database/production')
    monkeypatch.setenv('SECRET_KEY','existing-production-secret')
    monkeypatch.setenv('COOKIE_SECURE','true')
    monkeypatch.setenv('MAIL_PORT','587')
    monkeypatch.setenv('CORS_ORIGINS','https://production.example')
    return module

def test_fresh_sqlite_migrations_seed_and_restart(launcher):
    from hackflow.models import db, User, Hackathon, Message
    app, config=launcher.prepare_app(8000)
    assert app.config['SESSION_COOKIE_SECURE'] is False
    assert app.config['RATELIMIT_STORAGE_URI']=='memory://'
    assert app.config['MAIL_SERVER'] is None
    with app.app_context():
        assert db.engine.dialect.name=='sqlite'
        assert db.session.execute(db.text('PRAGMA foreign_keys')).scalar()==1
        assert db.session.execute(db.text('select version_num from alembic_version')).scalar()=='a13_platform_owner'
        count=Hackathon.query.count();users=User.query.count()
        assert count>0 and users>=5
        assert User.query.filter_by(email='admin@hackflow.test').one().is_owner
        original_message=Message.query.first().text
        h=Hackathon.query.first();h.team_size=0
        with pytest.raises(IntegrityError):db.session.commit()
        db.session.rollback()
    client=app.test_client()
    token=client.get('/api/auth/csrf').json['token']
    login=client.post('/api/auth/login',json={'email':'captain@hackflow.test','password':config['demo_password']},headers={'X-CSRFToken':token})
    assert login.status_code==200,login.json
    assert client.get('/api/health').json=={'status':'ok','database':'sqlite'}
    app2,config2=launcher.prepare_app(8000)
    assert config2==config
    with app2.app_context():
        assert Hackathon.query.count()==count and User.query.count()==users
        assert Message.query.first().text==original_message
        # Local SQLite must enforce the database's role/owner rules as well.
        owner=User.query.filter_by(is_owner=True).one();owner.role='participant'
        with pytest.raises(IntegrityError):db.session.commit()
        db.session.rollback()

def test_settings_are_persistent_and_private(launcher):
    one=launcher.settings();assert launcher.settings()==one
    assert len(one['secret'])>=64 and len(one['demo_password'])>=12
    if __import__('os').name!='nt':
        assert (launcher.DATA/'settings.json').stat().st_mode & 0o077==0
