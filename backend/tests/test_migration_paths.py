"""Exercise genuine old Alembic heads in isolated PostgreSQL schemas."""
import os
import uuid
from pathlib import Path
import pytest
from sqlalchemy import create_engine,text
from sqlalchemy.engine import make_url
from flask_migrate import upgrade
from hackflow import create_app
from hackflow.models import db

@pytest.mark.parametrize('starting',['a13_platform_owner','a14_team_city','a14_awards'])
def test_existing_revision_upgrades_without_data_loss(starting,tmp_path):
    uri=os.environ.get('TEST_DATABASE_URL')
    if not uri or not uri.startswith('postgresql'):pytest.skip('Requires isolated PostgreSQL schema')
    schema='migration_'+uuid.uuid4().hex
    admin=create_engine(uri)
    with admin.begin() as c:c.execute(text(f'CREATE SCHEMA {schema}'))
    test_uri=make_url(uri).update_query_dict({'options':f'-csearch_path={schema}'}).render_as_string(hide_password=False)
    app=create_app({'TESTING':True,'SQLALCHEMY_DATABASE_URI':test_uri,'RATELIMIT_ENABLED':False,'UPLOAD_FOLDER':str(tmp_path/'uploads')})
    migrations=str(Path(__file__).resolve().parents[1]/'migrations')
    try:
        with app.app_context():
            upgrade(directory=migrations,revision=starting)
            db.session.execute(text("INSERT INTO \"user\" (id,email,nickname,password_hash,role,blocked,created_at) VALUES (1,'preserved@example.com','Сохранённый','unused','participant',false,now())"))
            db.session.execute(text("INSERT INTO hackathon (id,title,start_at,end_at,registration_deadline,submission_deadline,team_size,closed,status,results_published,peer_published) VALUES (1,'Сохранённый хакатон',now(),now(),now(),now(),5,true,'active',false,false)"))
            db.session.execute(text("INSERT INTO team (id,hackathon_id,captain_id,name,code,open,created_at) VALUES (1,1,1,'Сохранённая команда','preserved',true,now())"))
            if starting=='a14_team_city':db.session.execute(text("UPDATE team SET city_style='tower',city_showcase=true WHERE id=1"))
            if starting=='a14_awards':db.session.execute(text("INSERT INTO award (id,user_id,hackathon_id,kind,token,recipient,event_title,organizers,issued_at) VALUES (1,1,1,'certificate','preserved-award','Сохранённый','Сохранённый хакатон','Организатор',now())"))
            db.session.commit()
            upgrade(directory=migrations)
            assert db.session.execute(text('SELECT version_num FROM alembic_version')).scalar()=='a15_merge_city_awards'
            assert db.session.execute(text('SELECT nickname FROM "user" WHERE id=1')).scalar()=='Сохранённый'
            assert db.session.execute(text('SELECT name FROM team WHERE id=1')).scalar()=='Сохранённая команда'
            assert db.session.execute(text('SELECT count(*) FROM award')).scalar()==(1 if starting=='a14_awards' else 0)
            if starting=='a14_awards':assert db.session.execute(text('SELECT token FROM award WHERE id=1')).scalar()=='preserved-award'
            if starting=='a14_team_city':assert db.session.execute(text('SELECT city_style,city_showcase FROM team WHERE id=1')).one()==('tower',True)
            upgrade(directory=migrations)  # repeated startup must be harmless
            db.session.remove();db.engine.dispose()
    finally:
        with admin.begin() as c:c.execute(text(f'DROP SCHEMA {schema} CASCADE'))
        admin.dispose()
