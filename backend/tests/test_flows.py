import io
import zipfile
from datetime import timedelta
import pytest
from sqlalchemy.exc import IntegrityError
from hackflow.models import *
from conftest import login

def join(c):
    login(c,'participant')
    r=c.post('/api/hackathons/1/join',json={'code':'HACKFLOW26'}); assert r.status_code==200,r.json

def submit(c,source=None):
    login(c,'captain')
    if source:
        assert c.post('/api/teams/1/uploads',data={'file':(source,'source.zip'),'purpose':'source'}).status_code==201
    r=c.post('/api/teams/1/uploads',data={'file':(io.BytesIO(b'%PDF-1.4\n%%EOF'),'slides.pdf'),'purpose':'presentation'})
    assert r.status_code==201,r.json
    data={'title':'Продукт','description':'Описание работающего решения','github':'https://github.com/pallets/flask','demo':'https://example.com','presentation_id':r.json['id']}
    r=c.post('/api/teams/1/submission',json=data); assert r.status_code==201,r.json
    return r.json['id']

def prepare(c,sid):
    login(c,'organizer')
    assert c.patch(f'/api/submissions/{sid}/anonymous',json={'text':'Обезличенная архитектура продукта. Компоненты, сценарии, результаты.','confirmed':True}).status_code==200
    assert c.post(f'/api/submissions/{sid}/assign',json={'user_id':4}).status_code==200

def score(c,sid):
    login(c,'jury')
    d=c.get(f'/api/jury/{sid}').json
    values={str(x['id']):x['maximum']*.9 for x in d['criteria']}
    r=c.post(f'/api/jury/{sid}/score',json={'scores':values,'comment':'Полезный продукт, критерии выполнены.'})
    assert r.status_code==200,r.json
    return values

def test_official_scenario(client):
    join(client)
    assert client.get('/api/hackathons/1').json['cases']
    materials=client.get('/api/hackathons/1/materials').json['items']
    assert client.post(f"/api/materials/{materials[0]['id']}/complete",json={}).status_code==200
    assert any(s['url'] for s in client.get('/api/hackathons/1/schedule').json['items'])
    r=client.post('/api/teams/1/tasks',json={'title':'Моя задача','description':'Реальный сценарий','assignee_id':1})
    assert r.status_code==200
    tid=r.json['items'][-1]['id']
    assert client.patch(f'/api/tasks/{tid}',json={'status':'done'}).status_code==200
    assert client.post('/api/teams/1/messages',json={'text':'Всё готово к сдаче'}).status_code==200
    assert client.get('/api/teams/1/messages').json['items'][-1]['text']=='Всё готово к сдаче'
    assert client.post('/api/teams/1/submission',json={}).status_code==403
    sid=submit(client)
    login(client,'organizer')
    rows=client.get('/api/hackathons/1/submissions').json['items']
    assert rows[0]['id']==sid and rows[0]['team']=='Код будущего'
    assert client.get('/api/uploads/'+str(rows[0]['presentation_id'])).status_code==200


def test_closed_access_and_registration(client):
    r=client.post('/api/auth/register',json={'email':'new@example.com','nickname':'Новый','password':'StrongPass2026!'})
    assert r.status_code==201
    assert client.get('/api/hackathons/1').status_code==403
    assert client.get('/api/teams/1/tasks').status_code==403
    assert client.post('/api/hackathons/1/join',json={'code':'HACKFLOW26'}).status_code==403
    assert client.get('/api/admin/users').status_code==403


def test_one_team_database_constraint(client,app):
    join(client)
    assert client.post('/api/hackathons/1/teams',json={'name':'Вторая'}).status_code==409
    with app.app_context():
        other=Team(hackathon_id=1,captain_id=1,name='Другие',code='other'); db.session.add(other); db.session.flush()
        db.session.add(Membership(user_id=1,team_id=other.id,hackathon_id=1))
        with pytest.raises(IntegrityError): db.session.commit()
        db.session.rollback()


def test_other_team_isolation_and_captain_chat(client):
    login(client,'participant')
    r=client.post('/api/hackathons/1/teams',json={'name':'Своя команда'}); assert r.status_code==201
    assert client.get('/api/teams/1').status_code==403
    assert client.get('/api/teams/1/messages').status_code==403
    assert client.patch('/api/tasks/1',json={'status':'done'}).status_code==403
    assert client.get('/api/teams/1/messages?channel=organizer').status_code==403


def test_deletion_lifecycle(client,app):
    login(client,'captain')
    assert client.delete('/api/teams/1').status_code==403
    with app.app_context():
        h=db.session.get(Hackathon,1); h.start_at=now()+timedelta(days=1); db.session.commit()
    assert client.delete('/api/teams/1').status_code==200
    with app.app_context(): assert Membership.query.count()==0


def test_anonymous_evaluation_publish_and_appeal(client,app):
    join(client); sid=submit(client)
    login(client,'jury'); assert client.get(f'/api/jury/{sid}').status_code==403
    prepare(client,sid)
    login(client,'jury'); d=client.get(f'/api/jury/{sid}').json
    raw=str(d)
    for forbidden in ['github.com','captain','team_id','presentation','Код будущего','Мария']: assert forbidden not in raw
    values=score(client,sid)
    login(client,'participant'); assert client.get('/api/hackathons/1/ranking').json['items']==[]
    login(client,'organizer'); r=client.post('/api/hackathons/1/publish',json={}); assert r.status_code==200,r.json
    assert r.json['items'][0]['score']==90
    login(client,'participant'); assert client.get('/api/profile').json['rating']==90
    assert client.post('/api/hackathons/1/appeals',json={'reason':'Проверка','explanation':'Проверьте баллы'}).status_code==403
    login(client,'captain'); r=client.post('/api/hackathons/1/appeals',json={'reason':'Недооценена защита','explanation':'Демонстрация была полной.'}); assert r.status_code==200
    aid=r.json['items'][0]['id']
    login(client,'organizer')
    with app.app_context(): full={str(x.id):x.maximum for x in Criterion.query.filter_by(hackathon_id=1)}
    r=client.patch(f'/api/appeals/{aid}',json={'status':'accepted','response':'Повторная проверка подтвердила выполнение критериев.','jury_id':4,'scores':full,'comment':'Уточнённая оценка'})
    assert r.status_code==200,r.json
    login(client,'participant'); assert client.get('/api/profile').json['rating']==100
    with app.app_context(): assert ScoreHistory.query.count()==2


def test_score_ranges_and_completeness(client):
    sid=submit(client); prepare(client,sid); login(client,'jury')
    d=client.get(f'/api/jury/{sid}').json; values={str(x['id']):x['maximum'] for x in d['criteria']}
    values[next(iter(values))]=101
    assert client.post(f'/api/jury/{sid}/score',json={'scores':values,'comment':'Нет'}).status_code==400
    assert client.post(f'/api/jury/{sid}/score',json={'scores':{},'comment':'Нет'}).status_code==400


def test_deadline_and_file_validation(client,app):
    login(client,'captain')
    assert client.post('/api/teams/1/uploads',data={'file':(io.BytesIO(b'not pdf'),'bad.pdf')}).status_code==400
    with app.app_context():
        db.session.get(Hackathon,1).submission_deadline=now()-timedelta(seconds=1); db.session.commit()
    r=client.post('/api/teams/1/submission',json={'title':'Late','description':'Late','github':'https://github.com/pallets/flask','demo':'https://example.com'})
    assert r.status_code==400
    assert any(x['name']=='deadline' and x['status']=='error' for x in r.json['checks'])


def test_jury_invite_bound_to_email_single_use(client):
    login(client,'organizer'); r=client.post('/api/hackathons/1/jury-invitations',json={'email':'newjury@example.com'}); assert r.status_code==201
    token=r.json['link'].split('invite=')[1]
    login(client,'participant'); assert client.post('/api/jury-invitations/accept',json={'token':token}).status_code==403
    client.post('/api/auth/register',json={'email':'newjury@example.com','nickname':'Новый судья','password':'StrongPass2026!'})
    assert client.post('/api/jury-invitations/accept',json={'token':token}).status_code==200
    assert client.post('/api/jury-invitations/accept',json={'token':token}).status_code==403


def test_csv_admin_and_criteria(client):
    login(client,'participant'); assert client.patch('/api/admin/users/1',json={'role':'organizer'}).status_code==403
    login(client,'admin'); assert client.patch('/api/admin/users/1',json={'role':'organizer'}).status_code==200
    login(client,'organizer')
    r=client.post('/api/hackathons/1/admissions',data={'file':(io.BytesIO(b'email\nhello@example.com\n'),'admissions.csv')}); assert r.json['added']==1
    assert client.put('/api/hackathons/1/criteria',json={'items':[{'title':'Only','maximum':99}]}).status_code==400
    assert client.put('/api/hackathons/1/criteria',json={'items':[{'title':'Only','maximum':100}]}).status_code==200


def test_codecheck_without_source_is_not_fabricated(client):
    sid=submit(client); login(client,'organizer'); r=client.post(f'/api/submissions/{sid}/codecheck',json={})
    assert r.status_code==200 and r.json['status']=='unavailable' and 'matches' not in r.json['report']


def test_codecheck_real_comparison(client,app):
    def archive():
        buf=io.BytesIO()
        with zipfile.ZipFile(buf,'w') as z: z.writestr('main.py','\n'.join(f'def transform_{i}(value):\n    if value > {i}:\n        return value * 2\n    return 0\n' for i in range(12)))
        buf.seek(0); return buf
    sid=submit(client,archive())
    login(client,'participant'); assert client.post('/api/hackathons/1/teams',json={'name':'Вторая команда'}).status_code==201
    r=client.post('/api/teams/2/uploads',data={'file':(archive(),'source.zip'),'purpose':'source'}); assert r.status_code==201
    pdf=client.post('/api/teams/2/uploads',data={'file':(io.BytesIO(b'%PDF-1.4'),'slides.pdf')}).json['id']
    assert client.patch('/api/teams/2',json={'case_id':1}).status_code==200
    r=client.post('/api/teams/2/submission',json={'title':'Another','description':'Another','github':'https://github.com/pallets/flask','demo':'https://example.com','presentation_id':pdf}); assert r.status_code==201,r.json
    login(client,'organizer'); r=client.post(f'/api/submissions/{sid}/codecheck',json={}); assert r.status_code==200,r.json
    assert r.json['status']=='completed' and r.json['report']['matches'][0]['similarity']==100
    assert r.json['report']['matches'][0]['fragments']


def test_ssrf_urls_blocked(client):
    login(client,'organizer')
    for url in ['http://127.0.0.1','https://127.0.0.1','https://169.254.169.254/latest','javascript:alert(1)']:
        assert client.post('/api/hackathons/1/materials',json={'title':'Bad','url':url}).status_code==400


def test_csrf_required(app):
    app.config['WTF_CSRF_ENABLED']=True
    c=app.test_client()
    assert c.post('/api/auth/login',json={'email':'captain@hackflow.test','password':'DemoPass2026!'}).status_code==400
    token=c.get('/api/auth/csrf').json['token']
    assert c.post('/api/auth/login',json={'email':'captain@hackflow.test','password':'DemoPass2026!'},headers={'X-CSRFToken':token}).status_code==200


def test_submitted_materials_are_immutable(client):
    sid=submit(client)
    r=client.post('/api/teams/1/uploads',data={'file':(io.BytesIO(b'%PDF-1.4'),'changed.pdf')})
    assert r.status_code==403
    assert client.post('/api/teams/1/submission',json={}).status_code==409


def test_consultation_before_submission_and_jury_conflict(client):
    login(client,'organizer')
    assert client.post('/api/teams/1/consultation/assign',json={'user_id':4}).status_code==403
    assert client.post('/api/teams/1/consultation/assign',json={'user_id':5}).status_code==200
    login(client,'admin')
    assert client.post('/api/teams/1/consultation',json={'text':'Сначала проверьте основной пользовательский путь.'}).status_code==200
    login(client,'captain')
    assert client.get('/api/teams/1/consultation').json['items'][0]['text'].startswith('Сначала')
    assert client.post('/api/teams/1/consultation',json={'text':'Поддельный эксперт'}).status_code==403


def test_reminders_are_idempotent(app):
    from hackflow.services import dispatch_reminders
    with app.app_context():
        h=db.session.get(Hackathon,1); h.submission_deadline=now()+timedelta(hours=12); db.session.commit()
        assert dispatch_reminders()==2
        assert dispatch_reminders()==0


def test_peer_review_self_assignment_and_official_rating_independent(client,app):
    sid=submit(client); prepare(client,sid)
    login(client,'participant'); assert client.post('/api/hackathons/1/teams',json={'name':'Рецензенты'}).status_code==201
    login(client,'organizer')
    assert client.post('/api/hackathons/1/peer',json={'team_id':1,'submission_id':sid}).status_code==400
    assert client.post('/api/hackathons/1/peer',json={'team_id':2,'submission_id':sid}).status_code==200
    login(client,'participant')
    with app.app_context(): values={str(x.id):x.maximum for x in Criterion.query.filter_by(hackathon_id=1)}
    assert client.post(f'/api/peer/{sid}',json={'scores':values,'comment':'Отличная работа'}).status_code==201
    assert client.post(f'/api/peer/{sid}',json={'scores':values,'comment':'Второй отзыв'}).status_code==409
    assert client.get('/api/hackathons/1/peer').json['results']==[]
    assert client.get('/api/profile').json['rating']==0
    login(client,'organizer'); assert client.post('/api/hackathons/1/peer/publish',json={}).status_code==200
    login(client,'participant'); assert client.get('/api/hackathons/1/peer').json['results'][0]['score']==100


def test_password_reset_single_use(client,app):
    from hackflow.services import digest
    with app.app_context():
        db.session.add(PasswordReset(user_id=1,token_hash=digest('test-token'),expires_at=now()+timedelta(minutes=30))); db.session.commit()
    assert client.post('/api/auth/reset',json={'token':'test-token','password':'NewPassword2026!'}).status_code==200
    assert client.post('/api/auth/reset',json={'token':'test-token','password':'AnotherPass2026!'}).status_code==403
    assert client.post('/api/auth/login',json={'email':'participant@hackflow.test','password':'NewPassword2026!'}).status_code==200


def test_profile_image_and_cover_validation(client):
    from PIL import Image
    login(client,'captain')
    buf=io.BytesIO(); Image.new('RGB',(32,32),'red').save(buf,format='PNG'); image=buf.getvalue()
    r=client.post('/api/profile/avatar',data={'file':(io.BytesIO(image),'avatar.png')}); assert r.status_code==200,r.json
    path=r.json['user']['avatar']; assert client.get(path).mimetype=='image/jpeg'
    assert client.post('/api/profile/avatar',data={'file':(io.BytesIO(b'<script/>'),'bad.png')}).status_code==400
    assert client.post('/api/hackathons/1/cover',data={'file':(io.BytesIO(image),'cover.png')}).status_code==403
    login(client,'organizer'); assert client.post('/api/hackathons/1/cover',data={'file':(io.BytesIO(image),'cover.png')}).status_code==200
    assert client.get('/api/hackathons').json['items'][0]['cover']


def test_learning_analytics(client):
    join(client); assert client.post('/api/materials/1/complete',json={}).status_code==200
    login(client,'organizer'); d=client.get('/api/hackathons/1/learning-analytics').json
    assert d['items'][0]['completed']==1
