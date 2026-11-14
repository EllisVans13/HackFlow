import pytest
import json
from conftest import login, TEST_PASSWORD
from hackflow.models import db,Team,Task,Message,Hackathon,User,Upload,Submission

def row(client,tid=1):
    response=client.get('/api/hackathons/1/city')
    assert response.status_code==200,response.json
    return next(t for t in response.json['items'] if t['id']==tid)

def test_city_tracks_actual_progress_and_stages(app,client):
    login(client,'captain')
    with app.app_context():
        Task.query.filter_by(team_id=1).delete()
        t=db.session.get(Team,1);case=t.case_id;t.case_id=None;db.session.commit()
    assert row(client)['stage']=='plot'
    client.patch('/api/teams/1',json={'case_id':case})
    assert row(client)['stage']=='foundation'
    client.post('/api/teams/1/tasks',json={'title':'Не раскрывать эту задачу'})
    assert row(client)['stage']=='building' and row(client)['floors']==1
    tasks=client.get('/api/teams/1/tasks').json['items']
    client.patch(f"/api/tasks/{tasks[0]['id']}",json={'status':'done'})
    built=row(client)
    assert built['progress']==100 and built['floors']==5 and built['done']==1
    payload=client.get('/api/hackathons/1/city').get_data(as_text=True)
    for key in ['Не раскрывать эту задачу','HACKFLOW26','password_hash','storage_name','@hackflow.test']:
        assert key not in payload
    assert 'requests' not in built and 'messages' not in built

def test_city_settings_captain_only_and_persisted(app,client):
    login(client,'participant')
    assert client.patch('/api/teams/1/city',json={'style':'tower'}).status_code==403
    assert not row(client)['can_customize']
    login(client,'captain')
    assert client.patch('/api/teams/1/city',json={'style':'castle'}).status_code==400
    assert client.patch('/api/teams/1/city',json={'showcase':'true'}).status_code==400
    assert client.patch('/api/teams/1/city',json={'style':'lab','showcase':True}).status_code==200
    assert row(client)['style']=='lab' and row(client)['showcase'] is True
    client.post('/api/auth/logout')
    login(client,'captain');assert row(client)['style']=='lab'
    with app.app_context():assert db.session.get(Team,1).city_showcase

def test_city_requires_admission_and_protects_judging(client):
    assert client.get('/api/hackathons/1/city').status_code==401
    client.post('/api/auth/register',json={'email':'outsider@example.com','nickname':'Без допуска','password':TEST_PASSWORD})
    assert client.get('/api/hackathons/1/city').status_code==403
    login(client,'jury');assert client.get('/api/hackathons/1/city').status_code==403
    login(client,'organizer');assert client.get('/api/hackathons/1/city').status_code==200

def test_project_exhibition_requires_results_and_captain_consent(app,client):
    login(client,'captain')
    with app.app_context():
        team=db.session.get(Team,1)
        f=Upload(team_id=1,owner_id=team.captain_id,storage_name='city-private.pdf',filename='private.pdf',size=10,purpose='presentation')
        db.session.add(f);db.session.flush()
        db.session.add(Submission(team_id=1,code='CITY-PRIVATE',title='Секретный проект',description='Закрытое описание',github='https://github.com/private/repo',demo='https://example.com/city-demo',presentation_id=f.id))
        db.session.commit()
    assert row(client)['stage']=='submitted' and row(client)['project'] is None
    client.patch('/api/teams/1/city',json={'showcase':True})
    assert row(client)['project'] is None
    with app.app_context():db.session.get(Hackathon,1).results_published=True;db.session.commit()
    project=row(client)['project']
    assert project['title']=='Секретный проект' and project['demo']=='https://example.com/city-demo'
    assert 'github' not in project and 'presentation_id' not in project
    client.patch('/api/teams/1/city',json={'showcase':False})
    assert row(client)['project'] is None


@pytest.mark.parametrize('style',['aframe','treehouse'])
def test_new_cabin_styles_persist_without_changing_team_work(app,client,style):
    login(client,'captain')
    original=row(client)
    with app.app_context():count=Task.query.filter_by(team_id=1).count()
    assert client.patch('/api/teams/1/city',json={'style':style}).status_code==200
    client.post('/api/auth/logout');login(client,'captain')
    updated=row(client)
    assert updated['style']==style
    assert updated['progress']==original['progress'] and updated['stage']==original['stage']
    with app.app_context():
        assert db.session.get(Team,1).city_style==style
        assert Task.query.filter_by(team_id=1).count()==count
