"""Exercise real upgrades from every migration history shipped to users."""
import os
from pathlib import Path
from uuid import uuid4

import pytest
import sqlalchemy as sa
from flask_migrate import upgrade

from hackflow import create_app
from hackflow.models import db


MIGRATIONS = str(Path(__file__).resolve().parents[1] / 'migrations')


@pytest.mark.parametrize('revision', [
    'base', '55e9b1bb7a5d', 'a14_team_city', 'a14_awards',
    'a15_merge_city_awards', 'adele_awards', 'adele_compat_heads',
    'a15_award_certificates', 'a16_merge_legacy_histories',
])
def test_upgrade_preserves_existing_database(tmp_path, revision):
    url = os.environ.get('MIGRATION_TEST_DATABASE_URL')
    schema = 'migration_test_' + uuid4().hex
    admin_engine = sa.create_engine(url) if url else None
    if admin_engine:
        with admin_engine.begin() as conn:
            conn.execute(sa.text(f'CREATE SCHEMA {schema}'))
    config = {
        'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': url or 'sqlite:///' + str(tmp_path / 'migration.db'),
        'RATELIMIT_ENABLED': False,
        'UPLOAD_FOLDER': str(tmp_path / 'uploads'),
    }
    if url:
        config['SQLALCHEMY_ENGINE_OPTIONS'] = {
            'connect_args': {'options': f'-csearch_path={schema}'},
        }
    app = create_app(config)
    try:
        with app.app_context():
            upgrade(directory=MIGRATIONS, revision=revision)
            if revision == 'base':
                upgrade(directory=MIGRATIONS, revision='55e9b1bb7a5d')
            db.session.execute(sa.text('''INSERT INTO "user"
                (id,email,nickname,password_hash,role,blocked,created_at)
                VALUES (901,'preserved@example.test','Preserved','existing-hash',
                'participant',false,CURRENT_TIMESTAMP)'''))
            db.session.commit()
            legacy = sa.inspect(db.engine).has_table('award')
            if legacy:
                db.session.execute(sa.text('''INSERT INTO hackathon
                    (id,title,start_at,end_at,registration_deadline,submission_deadline,
                     team_size,closed,status,results_published,peer_published)
                    VALUES (901,'Preserved event',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP,
                    CURRENT_TIMESTAMP,CURRENT_TIMESTAMP,5,false,'completed',true,false)'''))
                db.session.execute(sa.text('''INSERT INTO award
                    (user_id,hackathon_id,kind,token,recipient,event_title,organizers,issued_at)
                    VALUES (901,901,'certificate','preserved-token','Preserved',
                    'Preserved event','Organizer',CURRENT_TIMESTAMP)'''))
                db.session.commit()
            upgrade(directory=MIGRATIONS)
            upgrade(directory=MIGRATIONS)
            assert db.session.execute(sa.text(
                'SELECT version_num FROM alembic_version'
            )).scalars().all() == ['a17_mentors_learning']
            assert db.session.execute(sa.text(
                'SELECT password_hash FROM "user" WHERE id=901'
            )).scalar_one() == 'existing-hash'
            assert sa.inspect(db.engine).has_table('award_certificate')
            if legacy:
                assert db.session.execute(sa.text(
                    'SELECT token FROM award WHERE user_id=901'
                )).scalar_one() == 'preserved-token'
    finally:
        with app.app_context():
            db.session.remove()
            db.engine.dispose()
        if admin_engine:
            with admin_engine.begin() as conn:
                conn.execute(sa.text(f'DROP SCHEMA {schema} CASCADE'))
            admin_engine.dispose()
