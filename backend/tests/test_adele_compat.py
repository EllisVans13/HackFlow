"""The database used when changing branches must not be reset or restamped."""
import os,uuid
from pathlib import Path
import pytest
from sqlalchemy import create_engine,text
from sqlalchemy.engine import make_url
from flask_migrate import upgrade
from hackflow import create_app
from hackflow.models import db

@pytest.mark.parametrize('revision',['55e9b1bb7a5d','adele_awards','a14_team_city','a15_merge_city_awards'])
def test_known_database_histories_preserve_data(revision,tmp_path):
    uri=os.environ.get('TEST_DATABASE_URL')
    if not uri or not uri.startswith('postgresql'):pytest.skip('PostgreSQL required')
    schema='adele_compat_'+uuid.uuid4().hex;engine=create_engine(uri)
    with engine.begin() as c:c.execute(text(f'CREATE SCHEMA {schema}'))
    test_uri=make_url(uri).update_query_dict({'options':f'-csearch_path={schema}'}).render_as_string(hide_password=False)
    app=create_app({'TESTING':True,'SQLALCHEMY_DATABASE_URI':test_uri,'RATELIMIT_ENABLED':False,'UPLOAD_FOLDER':str(tmp_path/'uploads')})
    try:
        with app.app_context():
            directory=str(Path(__file__).resolve().parents[1]/'migrations')
            upgrade(directory=directory,revision=revision)
            db.session.execute(text("INSERT INTO \"user\" (id,email,nickname,password_hash,role,blocked,created_at) VALUES (1,'compat@example.com','Сохранённый','unused','participant',false,now())"))
            db.session.execute(text("INSERT INTO hackathon (id,title,start_at,end_at,registration_deadline,submission_deadline,team_size,closed,status,results_published,peer_published) VALUES (1,'Сохранённый',now(),now(),now(),now(),5,true,'active',false,false)"))
            db.session.execute(text("INSERT INTO team (id,hackathon_id,captain_id,name,code,open,created_at) VALUES (1,1,1,'Команда','saved',true,now())"))
            city=revision in ['a14_team_city','a15_merge_city_awards']
            awards=revision in ['adele_awards','a15_merge_city_awards']
            if city:db.session.execute(text("UPDATE team SET city_style='tower',city_showcase=true WHERE id=1"))
            if awards:db.session.execute(text("INSERT INTO award (id,user_id,hackathon_id,kind,token,recipient,event_title,organizers,issued_at) VALUES (1,1,1,'certificate','saved-token','Сохранённый','Сохранённый','Организатор',now())"))
            db.session.commit()
            upgrade(directory=directory)
            assert db.session.execute(text('SELECT version_num FROM alembic_version')).scalar()=='adele_compat_heads'
            assert db.session.execute(text('SELECT nickname FROM "user" WHERE id=1')).scalar()=='Сохранённый'
            if city:assert db.session.execute(text('SELECT city_style,city_showcase FROM team WHERE id=1')).one()==('tower',True)
            if awards:assert db.session.execute(text('SELECT token FROM award WHERE id=1')).scalar()=='saved-token'
            upgrade(directory=directory)
            db.session.remove();db.engine.dispose()
    finally:
        with engine.begin() as c:c.execute(text(f'DROP SCHEMA {schema} CASCADE'))
        engine.dispose()
