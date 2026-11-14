from datetime import timedelta
from conftest import login
from hackflow.models import *
from hackflow.demo import enrich
from hackflow.api import experience

def test_register_two_events_and_transfer(client,app):
    with app.app_context():
        enrich('DemoPass2026!');h=Hackathon.query.filter_by(demo_key='showcase-2').first();hid=h.id
        h2=Hackathon.query.filter_by(demo_key='showcase-3').first();hid2=h2.id
        Admission.query.filter_by(email='participant@hackflow.test',hackathon_id=hid).delete();db.session.commit()
    login(client,'participant')
    assert client.get(f'/api/hackathons/{hid}/schedule').status_code==403
    assert client.post(f'/api/hackathons/{hid}/register',json={}).status_code==200
    assert client.post(f'/api/hackathons/{hid2}/register',json={}).status_code==200
    assert client.get(f'/api/hackathons/{hid}/schedule').status_code==200
    t=client.post(f'/api/hackathons/{hid}/teams',json={'name':'Новая команда'}).json['team'];tid=t['id']
    assert client.post(f'/api/hackathons/{hid2}/teams',json={'name':'Параллельная команда'}).status_code==201
    assert client.post(f'/api/hackathons/{hid}/teams',json={'name':'Дубликат'}).status_code==409
    login(client,'captain')
    # Captain of another team cannot join a second team in the same event.
    assert client.post(f'/api/hackathons/{hid}/join',json={'code':t['code']}).status_code==409
    login(client,'participant');client.post('/api/auth/register',json={'email':'invitee@example.com','nickname':'Приглашённый','password':'DemoPass2026!'})
    assert client.post(f'/api/hackathons/{hid}/join',json={'code':t['code']}).status_code==403
    client.post(f'/api/hackathons/{hid}/register',json={})
    uid=client.get('/api/auth/me').json['user']['id']
    assert client.post(f'/api/hackathons/{hid}/join',json={'code':t['code']}).status_code==200
    login(client,'participant');assert client.patch(f'/api/teams/{tid}',json={'captain_id':uid}).status_code==200
    assert client.patch(f'/api/teams/{tid}',json={'open':False}).status_code==403

def test_staff_and_levels(client,app):
    for who in ['organizer','jury']:
        login(client,who)
        assert client.post('/api/hackathons/1/register',json={}).status_code==403
        assert client.post('/api/hackathons/1/teams',json={'name':'Forbidden'}).status_code==403
        assert client.post('/api/hackathons/1/join',json={'code':'HACKFLOW26'}).status_code==403
        assert client.get('/api/profile').json['staff'] is True
    with app.app_context():
        enrich('DemoPass2026!');before=Hackathon.query.count();xp=experience(1)['xp'];assert xp>0
        enrich('DemoPass2026!');assert Hackathon.query.count()==before;assert experience(1)['xp']==xp
        r=PersonalResult.query.filter_by(user_id=1).first();r.score-=10;db.session.commit();assert experience(1)['xp']==xp-100

def test_admin_user_status_and_event_management(client):
    login(client,'participant')
    assert client.get('/api/admin/users').status_code==403
    assert client.patch('/api/admin/users/2',json={'role':'organizer'}).status_code==403
    admin=login(client,'admin')
    assert client.get('/api/admin/users').json['items']
    assert client.patch('/api/admin/users/1',json={'role':'organizer'}).status_code==200
    assert client.patch('/api/admin/users/1',json={'hackathon_id':1,'assign':True}).status_code==200
    login(client,'participant')
    assert client.get('/api/hackathons/1/analytics').status_code==200
    login(client,'admin')
    assert client.patch('/api/admin/users/1',json={'role':'participant'}).status_code==200
    login(client,'participant')
    assert client.get('/api/hackathons/1/analytics').status_code==403
    login(client,'admin')
    assert client.patch('/api/admin/users/1',json={'blocked':True}).status_code==200
    assert client.post('/api/auth/login',json={'email':'participant@hackflow.test','password':'DemoPass2026!'}).status_code==403
    assert client.patch(f"/api/admin/users/{admin['id']}",json={'role':'participant'}).status_code==403

def test_showcase_creates_first_admin_only(app):
    with app.app_context():
        User.query.filter_by(role='admin').delete();db.session.commit()
        enrich('AdminDemo2026!')
        admin=User.query.filter_by(email='admin@hackflow.test').one()
        assert admin.role=='admin'
        original=admin.password_hash
        enrich('AnotherPass2026!')
        assert User.query.filter_by(role='admin').count()==1
        assert admin.password_hash==original
