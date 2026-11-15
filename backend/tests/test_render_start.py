import importlib.util
from pathlib import Path
import secrets
import pytest
from werkzeug.security import check_password_hash

@pytest.fixture()
def render_start():
    spec=importlib.util.spec_from_file_location('render_start',Path(__file__).parents[1]/'start_render.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module

@pytest.mark.parametrize('prefix',['postgres://','postgresql://','postgresql+psycopg://'])
def test_render_managed_database_and_public_address(render_start,prefix):
    env={'DATABASE_URL':prefix+'user:encoded%40password@internal/db?sslmode=require',
         'RENDER_EXTERNAL_URL':'https://hackflow-example.onrender.com/','PORT':'10001'}
    assert render_start.configure_environment(env)==10001
    assert env['DATABASE_URL']=='postgresql+psycopg://user:encoded%40password@internal/db?sslmode=require'
    assert env['PUBLIC_URL']=='https://hackflow-example.onrender.com'
    assert env['CORS_ORIGINS']==env['PUBLIC_URL'] and env['COOKIE_SECURE']=='true'
    assert '0.0.0.0:10001' in render_start.server_command(10001)

def test_render_keeps_custom_domain_and_rejects_missing_configuration(render_start):
    env={'DATABASE_URL':'sqlite://','PUBLIC_URL':'https://hackflow.example','RENDER_EXTERNAL_URL':'https://other.onrender.com'}
    render_start.configure_environment(env)
    assert env['PUBLIC_URL']=='https://hackflow.example'
    with pytest.raises(ValueError):render_start.configure_environment({})
    with pytest.raises(ValueError):render_start.configure_environment({'DATABASE_URL':'sqlite://','PUBLIC_URL':'invalid'})
    with pytest.raises(ValueError):render_start.configure_environment({'DATABASE_URL':'sqlite://','PUBLIC_URL':'https://example.com','PORT':'0'})

def test_render_bootstrap_survives_redeploy_without_resetting_accounts(render_start,tmp_path,monkeypatch):
    from hackflow import create_app
    from hackflow.models import db,User,Hackathon,AwardCertificate
    uri='sqlite:///'+str(tmp_path/'render.sqlite3');password=secrets.token_urlsafe(24)
    values={'DATABASE_URL':uri,'SECRET_KEY':secrets.token_hex(32),'UPLOAD_FOLDER':str(tmp_path/'uploads'),
        'ADMIN_EMAIL':'render-owner@example.test','ADMIN_PASSWORD':password,'ADMIN_NICKNAME':'Владелец Render',
        'SEED_DEMO':'true','DEMO_PASSWORD':secrets.token_urlsafe(24),'RATELIMIT_STORAGE_URI':'memory://'}
    for key,value in values.items():monkeypatch.setenv(key,value)
    render_start.prepare_database()
    app=create_app({'TESTING':True})
    with app.app_context():
        owner=User.query.filter_by(email=values['ADMIN_EMAIL']).one()
        assert owner.role=='admin' and owner.is_owner and check_password_hash(owner.password_hash,password)
        counts=(User.query.count(),Hackathon.query.count(),AwardCertificate.query.count())
        assert counts[1]>0 and counts[2]>0
    monkeypatch.setenv('ADMIN_PASSWORD',secrets.token_urlsafe(24))
    render_start.prepare_database()
    with app.app_context():
        assert counts==(User.query.count(),Hackathon.query.count(),AwardCertificate.query.count())
        owner=User.query.filter_by(email=values['ADMIN_EMAIL']).one()
        assert check_password_hash(owner.password_hash,password)
        db.session.remove();db.engine.dispose()
