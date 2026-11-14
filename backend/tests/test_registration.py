from conftest import PASSWORD_0, PASSWORD_1, PASSWORD_3, PASSWORD_4, PASSWORD_5, TEST_PASSWORD
from datetime import timedelta
from conftest import login
from hackflow.models import *
from hackflow.demo import enrich
from hackflow.api import experience

def test_register_two_events_and_transfer(client,app):
    with app.app_context():
        enrich(TEST_PASSWORD);h=Hackathon.query.filter_by(demo_key='showcase-2').first();hid=h.id
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
    login(client,'participant');client.post('/api/auth/register',json={'email':'invitee@example.com','nickname':'Приглашённый','password':TEST_PASSWORD})
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
        enrich(TEST_PASSWORD);before=Hackathon.query.count();xp=experience(1)['xp'];assert xp>0
        enrich(TEST_PASSWORD);assert Hackathon.query.count()==before;assert experience(1)['xp']==xp
        r=PersonalResult.query.filter_by(user_id=1).first();r.score-=10;db.session.commit();assert experience(1)['xp']==xp

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
    assert client.post('/api/auth/login',json={'email':'participant@hackflow.test','password':TEST_PASSWORD}).status_code==403
    assert client.patch(f"/api/admin/users/{admin['id']}",json={'role':'participant'}).status_code==403

def test_showcase_creates_first_admin_only(app):
    with app.app_context():
        User.query.filter_by(role='admin').delete();db.session.commit()
        enrich(PASSWORD_0)
        admin=User.query.filter_by(email='admin@hackflow.test').one()
        assert admin.role=='admin'
        original=admin.password_hash
        enrich(PASSWORD_1)
        assert User.query.filter_by(role='admin').count()==1
        assert admin.password_hash==original

def test_captain_invitations(client,app):
    login(client,'captain')
    candidates=client.get('/api/teams/1/candidates').json['items']
    assert any(u['id']==1 and 'level' in u and 'email' not in u for u in candidates)
    invitation=client.post('/api/teams/1/invitations',json={'user_id':1})
    assert invitation.status_code==201
    iid=invitation.json['id']
    assert client.post('/api/teams/1/invitations',json={'user_id':1}).status_code==409
    login(client,'organizer')
    assert client.get('/api/teams/1/candidates').status_code==403
    assert client.post(f'/api/team-invitations/{iid}/respond',json={'accept':True}).status_code==403
    login(client,'participant')
    assert client.get('/api/team-invitations').json['items'][0]['id']==iid
    assert client.post('/api/teams/1/invitations',json={'user_id':2}).status_code==403
    assert client.post(f'/api/team-invitations/{iid}/respond',json={'accept':True}).status_code==200
    assert client.post(f'/api/team-invitations/{iid}/respond',json={'accept':True}).status_code==409
    assert client.get('/api/hackathons/1').json['hackathon']['team_id']==1

def test_invitation_capacity_and_expiry(client,app):
    login(client,'captain');iid=client.post('/api/teams/1/invitations',json={'user_id':1}).json['id']
    with app.app_context():
        db.session.get(Hackathon,1).team_size=1;db.session.commit()
    login(client,'participant')
    assert client.post(f'/api/team-invitations/{iid}/respond',json={'accept':True}).status_code==409
    with app.app_context():
        from hackflow.models import TeamInvitation
        db.session.get(TeamInvitation,iid).expires_at=now()-timedelta(seconds=1);db.session.commit()
    assert client.post(f'/api/team-invitations/{iid}/respond',json={'accept':True}).status_code==409

def test_clear_level_breakdown(app):
    with app.app_context():
        enrich(TEST_PASSWORD);data=experience(1)
        assert data['thresholds'][1]==250
        assert sum(x['xp'] for x in data['earned'])==data['xp']
        assert all(x['xp']=={'easy':70,'medium':150,'hard':240}[x['difficulty']] for x in data['earned'])
        assert data['remaining']==max(0,data['next']-data['xp'])

def test_zero_start_and_level_boundaries(client,app):
    with app.app_context():
        assert experience(1)['level']==0
        for i in range(3):
            h=Hackathon(title=f'Сложный {i}',difficulty='hard',approval='approved',status='completed',results_published=True,start_at=now()-timedelta(days=3),end_at=now()-timedelta(days=1),registration_deadline=now()-timedelta(days=4),submission_deadline=now()-timedelta(days=2))
            db.session.add(h);db.session.flush()
            db.session.add(PersonalResult(user_id=1,hackathon_id=h.id,team_name='Тест',case_title='Тест',score=80,place=1));db.session.commit()
            assert experience(1)['xp']==240*(i+1)
            assert experience(1)['level']==[0,1,2][i]
    login(client,'participant')
    assert client.get('/api/profile').json['level']['level']==2


def test_hackathon_moderation(client,app):
    login(client,'organizer')
    data={'title':'Заявка','description':'Новая идея','rules':'Тестовые правила','difficulty':'medium','start_at':(now()+timedelta(days=1)).isoformat(),'end_at':(now()+timedelta(days=8)).isoformat(),'registration_deadline':(now()+timedelta(days=2)).isoformat(),'submission_deadline':(now()+timedelta(days=6)).isoformat()}
    r=client.post('/api/hackathons',json=data);assert r.status_code==201,r.json
    hid=r.json['hackathon']['id'];assert r.json['hackathon']['approval']=='pending'
    assert client.patch(f'/api/admin/hackathons/{hid}',json={'difficulty':'easy','approval':'approved'}).status_code==403
    assert client.patch(f'/api/hackathons/{hid}',json={'difficulty':'hard'}).status_code==403
    login(client,'participant')
    assert hid not in [h['id'] for h in client.get('/api/hackathons').json['items']]
    assert client.post(f'/api/hackathons/{hid}/register',json={}).status_code==403
    login(client,'admin')
    r=client.patch(f'/api/admin/hackathons/{hid}',json={'difficulty':'easy','approval':'approved'});assert r.status_code==200
    assert r.json['hackathon']['difficulty']=='easy'
    login(client,'participant');assert client.post(f'/api/hackathons/{hid}/register',json={}).status_code==200

def test_owner_transfer_and_admin_role_changes(client,app):
    owner=login(client,'admin')
    assert owner['is_owner'] is True
    assert client.patch('/api/admin/users/1',json={'role':'admin'}).status_code==200
    login(client,'participant')
    assert client.post('/api/admin/ownership',json={'user_id':owner['id']}).status_code==403
    assert client.patch(f"/api/admin/users/{owner['id']}",json={'blocked':True}).status_code==403
    login(client,'admin')
    r=client.post('/api/admin/ownership',json={'user_id':1});assert r.status_code==200,r.json
    assert r.json['user']['role']=='admin' and r.json['user']['is_owner'] is False
    assert client.post('/api/admin/ownership',json={'user_id':1}).status_code==403
    login(client,'participant')
    assert client.get('/api/auth/me').json['user']['is_owner'] is True
    assert client.patch('/api/admin/users/4',json={'role':'organizer'}).status_code==200
    assert client.patch('/api/admin/users/4',json={'role':'jury'}).status_code==200
    assert client.patch('/api/admin/users/4',json={'role':'participant'}).status_code==200
    assert client.patch('/api/admin/users/4',json={'role':'admin'}).status_code==200
    with app.app_context():assert User.query.filter_by(is_owner=True).count()==1

def test_organizer_appoints_jury_only_own_event(client,app):
    client.post('/api/auth/register',json={'email':'expert@example.com','nickname':'Новый эксперт','password':PASSWORD_3})
    uid=client.get('/api/auth/me').json['user']['id']
    assert client.post('/api/hackathons/1/jury-members',json={'email':'expert@example.com'}).status_code==403
    login(client,'organizer')
    assert client.post('/api/hackathons/1/jury-members',json={'email':'expert@example.com'}).status_code==200
    assert client.post('/api/hackathons/1/jury-members',json={'email':'captain@hackflow.test'}).status_code==409
    with app.app_context():
        h=Hackathon(title='Чужое событие',start_at=now(),end_at=now()+timedelta(days=5),registration_deadline=now()+timedelta(days=1),submission_deadline=now()+timedelta(days=4));db.session.add(h);db.session.commit();hid=h.id
        assert EventRole.query.filter_by(user_id=uid,hackathon_id=1,role='jury').count()==1
    assert client.post(f'/api/hackathons/{hid}/jury-members',json={'email':'expert@example.com'}).status_code==403

def test_remove_jury_revokes_access_preserves_scores_and_other_events(client,app):
    from test_flows import submit, prepare, score
    sid=submit(client);prepare(client,sid);score(client,sid)
    with app.app_context():
        enrich(TEST_PASSWORD)
        other=Hackathon.query.filter_by(demo_key='showcase-0').one().id
        scores_before=JuryScore.query.count();history_before=ScoreHistory.query.count()
    login(client,'participant')
    assert client.delete('/api/hackathons/1/jury-members/4').status_code==403
    login(client,'organizer')
    assert client.delete('/api/hackathons/1/jury-members/4').status_code==200
    login(client,'jury')
    assert client.get('/api/hackathons/1/jury').status_code==403
    assert client.get(f'/api/jury/{sid}').status_code==403
    assert client.post(f'/api/jury/{sid}/flag',json={}).status_code==403
    assert client.get(f'/api/hackathons/{other}/jury').status_code==200
    with app.app_context():
        assert JuryScore.query.count()==scores_before
        assert ScoreHistory.query.count()==history_before
        assert ReviewAssignment.query.filter_by(user_id=4,submission_id=sid,kind='jury').count()==0
        assert AuditLog.query.filter_by(action='jury.remove').count()==1

def test_organizer_cannot_remove_jury_from_other_event(client,app):
    with app.app_context():
        h=Hackathon(title='Чужой',start_at=now(),end_at=now()+timedelta(days=5),registration_deadline=now()+timedelta(days=1),submission_deadline=now()+timedelta(days=4));db.session.add(h);db.session.flush()
        hid=h.id;db.session.add(EventRole(user_id=4,hackathon_id=hid,role='jury'));db.session.commit()
    login(client,'organizer')
    assert client.delete(f'/api/hackathons/{hid}/jury-members/4').status_code==403
    with app.app_context():assert EventRole.query.filter_by(hackathon_id=hid,user_id=4,role='jury').count()==1

def test_holiday_default_and_preserved_theme_choice(client):
    r=client.post('/api/auth/register',json={'email':'newtheme@example.com','nickname':'Новая тема','password':TEST_PASSWORD})
    assert r.status_code==201 and r.json['user']['theme']=='holiday'
    assert client.patch('/api/profile',json={'theme':'purple'}).json['user']['theme']=='purple'
    assert client.get('/api/auth/me').json['user']['theme']=='purple'

def test_demo_catalog_refresh_is_named_idempotent_and_preserves_customizations(app):
    from hackflow.demo import refresh_demo_content, SHOWCASE
    with app.app_context():
        enrich(TEST_PASSWORD)
        h=Hackathon.query.filter_by(demo_key='showcase-2').one()
        assert h.title==SHOWCASE[2][0]
        assert User.query.filter(User.email.like('showcase.member.%@hackflow.test')).count()==12
        original_hash=User.query.filter_by(email='captain@hackflow.test').one().password_hash
        counts=[User.query.count(),Team.query.count(),Membership.query.count(),Message.query.count()]
        h.title='Название организатора';db.session.commit()
        refresh_demo_content()
        assert [User.query.count(),Team.query.count(),Membership.query.count(),Message.query.count()]==counts
        assert h.title=='Название организатора'
        assert User.query.filter_by(email='captain@hackflow.test').one().password_hash==original_hash

def test_showcase_covers_are_bundled_and_uploaded_cover_wins(app,client):
    from pathlib import Path
    import xml.etree.ElementTree as ET
    with app.app_context():enrich(TEST_PASSWORD)
    items=client.get('/api/hackathons').json['items']
    covers=[h['cover'] for h in items if h['is_demo']]
    assert len(set(covers))==7
    public=Path(__file__).resolve().parents[2]/'frontend/public'
    for cover in covers:
        path=public/cover.lstrip('/')
        assert path.is_file()
        svg=ET.parse(path).getroot()
        assert svg.tag=='{http://www.w3.org/2000/svg}svg'
        assert not svg.findall('.//{http://www.w3.org/2000/svg}script')
    with app.app_context():
        h=Hackathon.query.filter_by(demo_key='showcase-3').one()
        h.cover='/api/media/organizer-custom-cover';hid=h.id;db.session.commit()
    updated=next(h for h in client.get('/api/hackathons').json['items'] if h['id']==hid)
    assert updated['cover']=='/api/media/organizer-custom-cover'
