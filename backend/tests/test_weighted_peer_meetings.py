import io
from pathlib import Path
import pytest
from pypdf import PdfReader
from conftest import login,TEST_PASSWORD
from hackflow.models import db,User,Hackathon,Submission,Team,PeerAssignment,PeerReview,PersonalResult,AwardCertificate,Upload
from hackflow.review_demo import seed_review_demo,DEMO_PASSWORD,project_pdf


def demo_login(client,name):
    result=client.post('/api/auth/login',json={'email':name+'@demo.hackflow.test','password':DEMO_PASSWORD})
    assert result.status_code==200,result.json
    return result.json['user']


@pytest.fixture()
def scenario(app):
    with app.app_context():
        h=seed_review_demo();return {'id':h.id,'submissions':[s.id for s in Submission.query.join(Team).filter(Team.hackathon_id==h.id).order_by(Submission.id)],'criteria':{str(c.id):c.maximum for c in __import__('hackflow.models',fromlist=['Criterion']).Criterion.query.filter_by(hackathon_id=h.id)}}


def test_demo_seed_has_four_anonymous_teams_and_is_repeatable(app,client,scenario):
    with app.app_context():
        counts=(User.query.count(),Team.query.count(),Submission.query.count(),Upload.query.count(),PeerAssignment.query.count())
        assert PeerAssignment.query.filter(PeerAssignment.submission_id.in_(scenario['submissions'])).count()==12
        first=User.query.filter_by(email='captain@demo.hackflow.test').one();password=first.password_hash
        s=db.session.get(Submission,scenario['submissions'][0]);file=db.session.get(Upload,s.anonymous_file_id)
        Path(app.config['UPLOAD_FOLDER'],file.storage_name).unlink()
        seed_review_demo()
        assert counts==(User.query.count(),Team.query.count(),Submission.query.count(),Upload.query.count(),PeerAssignment.query.count())
        assert first.password_hash==password and Path(app.config['UPLOAD_FOLDER'],file.storage_name).is_file()
    for name in ['captain','review2','review3','review4']:
        user=demo_login(client,name)
        data=client.get(f"/api/hackathons/{scenario['id']}/peer").json
        assert len(data['items'])==3
        for work in data['items']:
            assert set(work)=={'id','code','text','reviewed','material_url'}
            assert work['material_url']
            response=client.get(work['material_url']);assert response.status_code==200
            reader=PdfReader(io.BytesIO(response.data))
            assert 'Демонстрационный' in reader.pages[0].extract_text()
            assert not reader.metadata.get('/Author')
            assert user['nickname'] not in reader.pages[0].extract_text()


def test_weighted_scores_wait_for_three_teams_and_issue_diplomas(app,client,scenario):
    hid=scenario['id'];demo_login(client,'organizer')
    assert client.post(f'/api/hackathons/{hid}/publish',json={}).status_code==409
    for name in ['captain','review2','review3','review4']:
        demo_login(client,name)
        data=client.get(f'/api/hackathons/{hid}/peer').json
        scores={k:v*.8 for k,v in scenario['criteria'].items()}
        for work in data['items']:
            assert client.post(f"/api/peer/{work['id']}",json={'scores':scores,'comment':'Демонстрационная рецензия: основные функции работают.'}).status_code==201
        assert client.post(f"/api/peer/{data['items'][0]['id']}",json={'scores':scores,'comment':'Повтор'}).status_code==409
    demo_login(client,'organizer')
    result=client.post(f'/api/hackathons/{hid}/publish',json={})
    assert result.status_code==200,result.json
    rows=result.json['items'];assert [r['score'] for r in rows]==[88,84,80,76]
    assert rows[0]['jury_component']==72 and rows[0]['peer_component']==16 and rows[0]['peer_score']==80
    with app.app_context():
        assert AwardCertificate.query.filter_by(hackathon_id=hid,revoked_at=None).count()==3
        assert sorted(r.score for r in PersonalResult.query.filter_by(hackathon_id=hid))==[76,80,84,88]
    assert client.post(f'/api/hackathons/{hid}/publish',json={}).status_code==200
    with app.app_context():assert AwardCertificate.query.filter_by(hackathon_id=hid).count()==3
    demo_login(client,'captain')
    assert client.get('/api/profile').json['level']['xp']==132
    client.post('/api/auth/logout')
    public=client.get(f'/api/public/hackathons/{hid}/results').json
    assert public['items'][0]['score']==88 and public['items'][0]['peer_count']==3


def test_peer_files_do_not_open_own_or_original_uploads(client,app,scenario):
    demo_login(client,'captain')
    with app.app_context():
        uid=User.query.filter_by(email='captain@demo.hackflow.test').one().id
        own=Submission.query.join(Team).filter(Team.captain_id==uid).one()
        own_id=own.id
        foreign=Submission.query.filter(Submission.id.in_(scenario['submissions']),Submission.id!=own_id).first()
        foreign_upload=foreign.presentation_id
    assert client.get(f'/api/peer/{own_id}/material').status_code==403
    assert client.get(f'/api/uploads/{foreign_upload}').status_code==403
    client.post('/api/auth/logout')
    assert client.get(f"/api/peer/{scenario['submissions'][1]}/material").status_code==401


def test_public_demo_admin_cannot_manage_real_accounts_or_events(client,scenario):
    user=demo_login(client,'admin');assert user['is_demo'] is True
    users=client.get('/api/admin/users').json['items']
    assert len(users)==10 and all(u['is_demo'] for u in users)
    assert client.patch('/api/admin/users/1',json={'blocked':True}).status_code==403
    assert client.patch('/api/admin/hackathons/1',json={'approval':'approved'}).status_code==403
    assert client.patch('/api/hackathons/1',json={'title':'Нельзя'}).status_code==403
    assert client.post('/api/admin/ownership',json={'user_id':user['id']}).status_code==403


def test_demo_expert_gives_feedback_but_cannot_participate(client,scenario):
    demo_login(client,'expert')
    assert len(client.get('/api/expert/assignments').json['items'])==4
    assert client.post(f"/api/submissions/{scenario['submissions'][0]}/feedback",json={'text':'Добавьте проверку пользовательского сценария.'}).status_code==200
    assert client.post(f"/api/hackathons/{scenario['id']}/register",json={}).status_code==403
    assert client.get('/api/admin/users').status_code==403
    assert client.get('/api/profile').json['staff'] is True


def test_meetings_preserve_timezone_duration_and_validate_provider(client):
    login(client,'organizer')
    base={'title':'Созвон','description':'Разбор вопросов','starts_at':'2026-11-20T15:00:00+05:00','duration_minutes':45,'provider':'yandex','url':'https://telemost.yandex.ru/j/1234567890','kind':'consultation','speaker':'Ментор'}
    result=client.post('/api/hackathons/1/schedule',json=base);assert result.status_code==201,result.json
    sid=result.json['id'];event=next(e for e in client.get('/api/hackathons/1/schedule').json['items'] if e['id']==sid)
    assert event['starts_at']=='2026-11-20T10:00:00Z' and event['duration_minutes']==45 and event['provider']=='yandex'
    assert client.patch(f'/api/schedule/{sid}',json={'duration_minutes':90,'provider':'zoom','url':'https://us02web.zoom.us/j/123456789'}).status_code==200
    for fields in [{'duration_minutes':1},{'duration_minutes':1441},{'provider':'yandex','url':'https://telemost.yandex.ru/'},{'provider':'zoom','url':'https://zoom.us/'},{'provider':'zoom','url':'https://evilzoom.us/j/123'}]:
        assert client.post('/api/hackathons/1/schedule',json={**base,**fields}).status_code==400
    login(client,'captain')
    assert client.post('/api/hackathons/1/schedule',json=base).status_code==403


def test_anonymous_pdf_requires_confirmation_and_cleans_metadata(client,app,scenario):
    demo_login(client,'organizer');sid=scenario['submissions'][0]
    with app.app_context():
        from hackflow.models import JuryScore
        JuryScore.query.filter_by(submission_id=sid).delete();db.session.commit()
    pdf=project_pdf('SAFE-CODE',0)
    assert client.post(f'/api/submissions/{sid}/anonymous-file',data={'file':(io.BytesIO(pdf),'PRIVATE_AUTHOR.pdf')}).status_code==400
    response=client.post(f'/api/submissions/{sid}/anonymous-file',data={'file':(io.BytesIO(pdf),'PRIVATE_AUTHOR.pdf'),'confirmed':'true'})
    assert response.status_code==200,response.json
    result=client.get(f'/api/peer/{sid}/material');reader=PdfReader(io.BytesIO(result.data))
    assert not reader.metadata.get('/Author') and 'PRIVATE_AUTHOR' not in result.headers['Content-Disposition']
    demo_login(client,'jury')
    assert client.get(f'/api/jury/{sid}/material').status_code==200


def test_distribution_is_idempotent_and_self_review_forbidden(client,app,scenario):
    demo_login(client,'organizer')
    result=client.post(f"/api/hackathons/{scenario['id']}/peer/distribute",json={})
    assert result.status_code==200 and result.json['added']==0
    demo_login(client,'captain')
    with app.app_context():
        uid=User.query.filter_by(email='captain@demo.hackflow.test').one().id
        own=Submission.query.join(Team).filter(Team.captain_id==uid).one().id
    assert client.post(f'/api/peer/{own}',json={'scores':scenario['criteria'],'comment':'Себя нельзя'}).status_code==403
    demo_login(client,'participant')
    assert client.post(f"/api/peer/{scenario['submissions'][0]}",json={'scores':scenario['criteria'],'comment':'Без команды'}).status_code==403


def test_cross_event_assignments_and_demo_staff_cannot_see_real_projects(client,scenario):
    demo_login(client,'organizer')
    assert client.post(f"/api/hackathons/{scenario['id']}/peer",json={'team_id':1,'submission_id':scenario['submissions'][0]}).status_code==400
    demo_login(client,'admin')
    users=client.get('/api/admin/users').json['items'];expert=next(u for u in users if u['role']=='expert')
    login(client,'organizer')
    assert client.post('/api/teams/1/consultation/assign',json={'user_id':expert['id']}).status_code==403


def test_anonymous_file_cannot_change_after_scoring(client,scenario):
    demo_login(client,'organizer');sid=scenario['submissions'][0]
    assert client.post(f'/api/submissions/{sid}/anonymous-file',data={'file':(io.BytesIO(project_pdf('SAFE',0)),'new.pdf'),'confirmed':'true'}).status_code==409
    assert client.patch(f'/api/submissions/{sid}/anonymous',json={'text':'Новая версия','confirmed':True}).status_code==409


def test_distribution_needs_four_projects_and_manual_assignments_stop_at_three(client,app,scenario,monkeypatch):
    import hackflow.peer_assessment as module
    demo_login(client,'organizer')
    original=module.projects
    monkeypatch.setattr(module,'projects',lambda hid:original(hid)[:3])
    assert client.post(f"/api/hackathons/{scenario['id']}/peer/distribute",json={}).status_code==409
    monkeypatch.setattr(module,'projects',original)
    with app.app_context():
        s=db.session.get(Submission,scenario['submissions'][0])
        reviewer=Team.query.filter(Team.hackathon_id==scenario['id'],Team.id!=s.team_id).first().id
    assert client.post(f"/api/hackathons/{scenario['id']}/peer",json={'team_id':reviewer,'submission_id':scenario['submissions'][0]}).status_code==409


def test_all_public_demo_logins_are_documented_and_work(client,scenario):
    from hackflow.review_demo import ACCOUNTS
    readme=Path(__file__).resolve().parents[2].joinpath('README.md').read_text()
    assert DEMO_PASSWORD in readme
    for name,nickname,role in ACCOUNTS:
        assert name+'@demo.hackflow.test' in readme
        user=demo_login(client,name)
        assert user['role']==role and user['is_demo'] is True
        assert client.get('/api/auth/me').status_code==200


def test_online_meeting_requires_join_url_and_closed_peer_rejects_assignments(client,app,scenario):
    login(client,'organizer')
    assert client.post('/api/hackathons/1/schedule',json={'title':'Встреча','starts_at':'2026-11-20T10:00:00Z','provider':'link','url':''}).status_code==400
    demo_login(client,'organizer')
    with app.app_context():
        h=db.session.get(Hackathon,scenario['id']);h.peer_published=True;db.session.commit()
    assert client.post(f"/api/hackathons/{scenario['id']}/peer",json={'team_id':1,'submission_id':scenario['submissions'][0]}).status_code==409
