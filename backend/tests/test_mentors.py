import secrets
from datetime import timedelta
import pytest
from werkzeug.security import generate_password_hash
from conftest import login, TEST_PASSWORD
from hackflow.models import (db,User,Team,Hackathon,EventRole,Admission,Upload,Submission,now)


@pytest.fixture()
def mentors(app):
    with app.app_context():
        people=[]
        for name in ['mentor','mentor.other','mentor.blocked']:
            u=User(email=name+'@hackflow.test',nickname=name,role='mentor',
                   mentor_skills='Python, React',mentor_bio='Помогаю с архитектурой.',
                   blocked=name.endswith('blocked'),password_hash=generate_password_hash(TEST_PASSWORD))
            db.session.add(u);db.session.flush();people.append(u.id)
        h=Hackathon(title='Другой хакатон',start_at=now(),end_at=now()+timedelta(days=10),
                    registration_deadline=now()+timedelta(days=2),submission_deadline=now()+timedelta(days=8))
        db.session.add(h);db.session.flush()
        other=Team(hackathon_id=h.id,captain_id=2,name='Чужая команда',code=secrets.token_hex(8))
        db.session.add(other);db.session.flush()
        foreign=User(email='foreign@hackflow.test',nickname='foreign',role='organizer',password_hash=generate_password_hash(TEST_PASSWORD))
        db.session.add(foreign);db.session.flush();db.session.add(EventRole(user_id=foreign.id,hackathon_id=h.id,role='organizer'))
        f=Upload(team_id=1,owner_id=2,storage_name='mentor-test.pdf',filename='project.pdf',size=9,purpose='presentation')
        db.session.add(f);db.session.flush()
        from pathlib import Path
        Path(app.config['UPLOAD_FOLDER'],'mentor-test.pdf').write_bytes(b'%PDF-test')
        s=Submission(team_id=1,title='Проект',description='Описание проекта',code='MENTOR1',
                     github='https://github.com/pallets/flask',demo='https://example.com',presentation_id=f.id)
        db.session.add(s);db.session.commit()
        return {'first':people[0],'second':people[1],'blocked':people[2],'event':h.id,'team':other.id,'file':f.id,'submission':s.id}


def assign(client,uid):
    login(client,'captain')
    r=client.put('/api/teams/1/mentor',json={'user_id':uid})
    assert r.status_code==200,r.json
    return r


def test_captain_selects_active_mentor_and_permissions_are_scoped(client,mentors):
    login(client,'captain')
    rows=client.get('/api/hackathons/1/mentors').json['items']
    assert {r['id'] for r in rows}=={mentors['first'],mentors['second']}
    assert not any('email' in r or 'xp' in r for r in rows)
    assert client.put('/api/teams/1/mentor',json={'user_id':mentors['blocked']}).status_code==409
    assert client.put('/api/teams/1/mentor',json={'user_id':1}).status_code==409
    assign(client,mentors['first'])
    login(client,'mentor')
    assert len(client.get('/api/mentor/teams').json['items'])==1
    workspace=client.get('/api/mentor/teams/1')
    assert workspace.status_code==200 and workspace.json['tasks'] and workspace.json['case']
    assert 'code' not in workspace.json['team']
    assert client.get('/api/teams/1/tasks').status_code==200
    assert client.get('/api/teams/1/messages').status_code==200
    assert client.get('/api/teams/1/messages?channel=organizer').status_code==403
    assert client.get(f"/api/uploads/{mentors['file']}").data==b'%PDF-test'
    assert client.get('/api/hackathons/1/materials').status_code==200
    assert client.get('/api/hackathons/1/schedule').status_code==200
    assert client.get(f"/api/hackathons/{mentors['event']}/schedule").status_code==403
    assert client.get(f"/api/mentor/teams/{mentors['team']}").status_code==403
    assert client.get(f"/api/teams/{mentors['team']}/tasks").status_code==403
    assert client.get('/api/profile').json['staff'] is True
    assert 'level' not in client.get('/api/profile').json
    assert client.post('/api/teams/1/consultation',json={'text':'Проверьте сценарий входа.'}).status_code==200
    assert client.post(f"/api/submissions/{mentors['submission']}/feedback",json={'text':'Добавьте обработку ошибок.'}).status_code==200
    login(client,'captain')
    assert client.get('/api/teams/1/consultation').json['items'][0]['text'].startswith('Проверьте')


@pytest.mark.parametrize('method,path,data',[
    ('post','/hackathons/1/register',{}),('post','/hackathons/1/teams',{'name':'Нельзя'}),
    ('post','/hackathons/1/join',{'code':'HACKFLOW26'}),
    ('post','/teams/1/tasks',{'title':'Нельзя'}),('patch','/tasks/1',{'status':'done'}),
    ('post','/teams/1/messages',{'text':'Нельзя'}),('post','/teams/1/submission',{}),
    ('post','/hackathons',{}),('get','/admin/users',None),('post','/jury/1/score',{}),
    ('put','/teams/1/mentor',{'user_id':1}),('post','/materials/1/complete',{}),
])
def test_mentor_cannot_use_participant_or_staff_actions(client,mentors,method,path,data):
    assign(client,mentors['first']);login(client,'mentor')
    assert getattr(client,method)('/api'+path,json=data).status_code==403


def test_organizer_assigns_only_own_team_and_revocation_is_immediate(client,app,mentors):
    login(client,'organizer')
    assert client.put('/api/teams/1/mentor',json={'user_id':mentors['first']}).status_code==200
    assert client.put(f"/api/teams/{mentors['team']}/mentor",json={'user_id':mentors['first']}).status_code==403
    login(client,'participant')
    assert client.put('/api/teams/1/mentor',json={'user_id':mentors['second']}).status_code==403
    login(client,'organizer')
    assert client.put('/api/teams/1/mentor',json={'user_id':mentors['second']}).status_code==200
    # A legacy admission must not grant a former mentor residual event access.
    with app.app_context():
        db.session.add(Admission(hackathon_id=1,email='mentor@hackflow.test'));db.session.commit()
    login(client,'mentor')
    for path in ['/mentor/teams/1','/teams/1/tasks','/teams/1/messages','/teams/1/consultation',
                 '/hackathons/1/schedule',f"/uploads/{mentors['file']}",f"/submissions/{mentors['submission']}/feedback"]:
        assert client.get('/api'+path).status_code==403,path
    assert client.get('/api/mentor/teams').json['items']==[]
    login(client,'organizer')
    assert client.delete('/api/teams/1/mentor').status_code==200
    login(client,'mentor.other')
    assert client.get('/api/mentor/teams/1').status_code==403


def test_admin_assigns_mentor_role_and_changing_role_revokes_assignments(client,mentors):
    login(client,'admin')
    # Existing captain cannot simultaneously become mentor of active teams.
    assert client.patch('/api/admin/users/2',json={'role':'mentor'}).status_code==409
    # An unassigned mentor can switch to participant and back through admin controls.
    uid=mentors['first']
    assert client.patch(f'/api/admin/users/{uid}',json={'role':'participant'}).status_code==200
    assert client.patch(f'/api/admin/users/{uid}',json={'role':'mentor'}).status_code==200
    assign(client,uid)
    login(client,'admin')
    assert client.patch(f'/api/admin/users/{uid}',json={'role':'participant'}).status_code==200
    login(client,'captain')
    assert client.get('/api/teams/1').json['team']['mentor'] is None


def test_mentor_updates_professional_profile_without_changing_role(client,mentors):
    login(client,'mentor')
    r=client.patch('/api/profile',json={'mentor_bio':'Помогаю с SQL','mentor_skills':'PostgreSQL','role':'admin'})
    assert r.status_code==200 and r.json['user']['role']=='mentor'
    assert r.json['user']['mentor_skills']=='PostgreSQL'
    login(client,'captain')
    assert client.patch('/api/profile',json={'mentor_bio':'Поддельный ментор'}).status_code==403


def test_former_mentor_cannot_anonymously_judge_known_project(client,mentors):
    assign(client,mentors['first'])
    login(client,'admin')
    uid=mentors['first']
    assert client.patch(f'/api/admin/users/{uid}',json={'role':'jury'}).status_code==200
    assert client.patch(f'/api/admin/users/{uid}',json={'hackathon_id':1,'event_role':'jury'}).status_code==200
    login(client,'organizer')
    assert client.post(f"/api/submissions/{mentors['submission']}/assign",json={'user_id':uid,'kind':'jury'}).status_code==403
