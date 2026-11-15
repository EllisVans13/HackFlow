from datetime import timedelta
from types import SimpleNamespace
import pytest
from werkzeug.security import generate_password_hash
from conftest import login, TEST_PASSWORD
from hackflow.models import (db,User,Team,Membership,Upload,Submission,ReviewAssignment,JuryScore,
    Criterion,Hackathon,AwardCertificate,Notification,Appeal,now)
from hackflow.certificate_pdf import certificate_pdf

@pytest.fixture()
def competition(app):
    with app.app_context():
        db.session.add(Membership(user_id=1,team_id=1,hackathon_id=1))
        teams=[db.session.get(Team,1)]
        for index in range(2,5):
            user=User(email=f'winner{index}@example.test',nickname=f'Участник {index}',
                      password_hash=generate_password_hash(TEST_PASSWORD))
            db.session.add(user);db.session.flush()
            team=Team(hackathon_id=1,captain_id=user.id,name=f'Команда {index}',code=f'AWARD-{index}')
            db.session.add(team);db.session.flush();teams.append(team)
            db.session.add(Membership(user_id=user.id,team_id=team.id,hackathon_id=1))
        submissions=[];criteria=Criterion.query.filter_by(hackathon_id=1).all()
        for index,team in enumerate(teams):
            upload=Upload(team_id=team.id,owner_id=team.captain_id,storage_name=f'award-{index}.pdf',
                          filename='slides.pdf',size=10,purpose='presentation')
            db.session.add(upload);db.session.flush()
            submission=Submission(team_id=team.id,code=f'AWARD-{index}',title=f'Проект {index}',description='Описание',
                github='https://github.com/pallets/flask',demo='https://example.com',presentation_id=upload.id,
                submitted_at=now()+timedelta(seconds=index))
            db.session.add(submission);db.session.flush();submissions.append(submission.id)
            total=90-index*10
            db.session.add(ReviewAssignment(submission_id=submission.id,user_id=4,kind='jury'))
            db.session.add(JuryScore(submission_id=submission.id,user_id=4,total=total,
                scores={str(c.id):c.maximum*total/100 for c in criteria},comment='Оценка жюри'))
        db.session.commit()
        return {'submissions':submissions,'users':[t.captain_id for t in teams]}

def publish(client):
    login(client,'organizer')
    response=client.post('/api/hackathons/1/publish',json={})
    assert response.status_code==200,response.json

def test_automatic_awards_only_after_publication_and_for_every_podium_member(app,client,competition):
    login(client,'organizer')
    assert client.patch('/api/hackathons/1',json={'status':'completed'}).status_code==200
    with app.app_context():assert AwardCertificate.query.count()==0
    publish(client)
    with app.app_context():
        awards=AwardCertificate.query.filter_by(revoked_at=None).all()
        assert len(awards)==4
        assert sorted(c.place for c in awards)==[1,1,2,3]
        assert competition['users'][3] not in {c.user_id for c in awards}
        assert Notification.query.filter(Notification.event_key.like('certificate:%')).count()==4
    publish(client)
    with app.app_context():
        assert AwardCertificate.query.count()==4
        assert Notification.query.filter(Notification.event_key.like('certificate:%')).count()==4
    login(client,'participant')
    items=client.get('/api/profile/certificates').json['items']
    assert len(items)==1 and items[0]['recipient_name']=='Александр' and items[0]['place']==1
    assert client.get('/api/profile/certificates?hackathon_id=99').json['items']==[]
    assert client.get('/api/profile/certificates?hackathon_id=bad').status_code==400

def test_certificate_download_permissions_pdf_fonts_and_public_verification(app,client,competition):
    publish(client);login(client,'participant')
    item=client.get('/api/profile/certificates').json['items'][0]
    response=client.get(item['download_url'])
    assert response.status_code==200 and response.mimetype=='application/pdf'
    assert response.data.startswith(b'%PDF-') and b'/FontFile2' in response.data and b'/Count 1' in response.data
    assert 'attachment;' in response.headers['Content-Disposition']
    assert 'no-store' in response.headers['Cache-Control']
    assert client.get(item['preview_url']).headers['Content-Disposition'].startswith('inline;')
    login(client,'jury');assert client.get(item['download_url']).status_code==403
    login(client,'organizer');assert client.get(item['download_url']).status_code==200
    client.post('/api/auth/logout')
    assert client.get(item['download_url']).status_code==401
    html=client.get('/api/certificates/'+item['id']+'/verify')
    assert html.status_code==200 and 'Диплом подтверждён' in html.get_data(as_text=True)
    assert '@hackflow.test' not in html.get_data(as_text=True)
    assert client.get('/api/certificates/'+('0'*32)+'/verify').status_code==404

def test_accepted_appeal_revokes_old_documents_and_reissues_new_places(app,client,competition):
    publish(client)
    with app.app_context():
        old={c.user_id:c.public_id for c in AwardCertificate.query.all()}
        appeal=Appeal(submission_id=competition['submissions'][3],reason='Пересмотр',explanation='Дополнительные материалы')
        db.session.add(appeal);db.session.commit();aid=appeal.id
        scores={str(c.id):c.maximum*.95 for c in Criterion.query.filter_by(hackathon_id=1)}
    response=client.patch(f'/api/appeals/{aid}',json={'status':'accepted','response':'Оценка пересмотрена',
        'jury_id':4,'scores':scores,'comment':'Уточнённая оценка'})
    assert response.status_code==200,response.json
    with app.app_context():
        active=AwardCertificate.query.filter_by(revoked_at=None).all()
        assert len(active)==4
        assert next(c for c in active if c.user_id==competition['users'][3]).place==1
        assert next(c for c in active if c.user_id==1).place==2
        assert competition['users'][2] not in {c.user_id for c in active}
        assert AwardCertificate.query.filter(AwardCertificate.revoked_at.is_not(None)).count()==4
    token=old[1]
    assert client.get('/api/certificates/'+token+'/download').status_code==409
    assert 'Диплом недействителен' in client.get('/api/certificates/'+token+'/verify').get_data(as_text=True)
    login(client,'participant');assert client.get('/api/profile/certificates').json['items'][0]['place']==2

def test_unpublished_or_reopened_results_hide_awards_and_verification_escapes_names(app,client,competition):
    publish(client);login(client,'participant')
    item=client.get('/api/profile/certificates').json['items'][0]
    with app.app_context():
        h=db.session.get(Hackathon,1);h.status='review';db.session.commit()
    assert client.get('/api/profile/certificates').json['items']==[]
    assert client.get(item['download_url']).status_code==409
    with app.app_context():
        h=db.session.get(Hackathon,1);h.status='completed';h.results_published=False;db.session.commit()
    assert client.get('/api/profile/certificates').json['items']==[]
    with app.app_context():
        h=db.session.get(Hackathon,1);h.results_published=True
        cert=AwardCertificate.query.filter_by(public_id=item['id']).one();cert.recipient_name='<script>alert(1)</script>'
        db.session.commit()
    html=client.get('/api/certificates/'+item['id']+'/verify').get_data(as_text=True)
    assert '<script>' not in html and '&lt;script&gt;' in html

@pytest.mark.parametrize('place',[1,2,3])
def test_long_cyrillic_awards_render_as_one_page_with_embedded_fonts(place):
    cert=SimpleNamespace(id=123,recipient_name='Широкова-Константинопольская Александра Максимилиановна',
        team_name='Очень длинное название команды разработчиков интеллектуальных цифровых сервисов',
        event_title='Международный хакатон интеллектуальных технологий и цифровой трансформации городской инфраструктуры',
        organizer_name='Ассоциация организаторов студенческих технологических соревнований',place=place,is_demo=False,issued_at=now())
    pdf=certificate_pdf(cert,'https://hackflow.example/api/certificates/'+('a'*32)+'/verify')
    assert pdf.startswith(b'%PDF-') and b'/Count 1' in pdf and b'/FontFile2' in pdf


def test_pdf_qr_leads_to_public_results_with_specific_certificate(app,client,competition,monkeypatch):
    from urllib.parse import urlsplit,parse_qs
    import hackflow.certificate_api as certificate_api
    publish(client);login(client,'participant')
    app.config['PUBLIC_URL']='https://hackflow.example'
    item=client.get('/api/profile/certificates').json['items'][0]
    parsed=urlsplit(item['verify_url'])
    assert parsed.netloc=='hackflow.example' and parsed.path=='/results/1'
    assert parse_qs(parsed.query)=={'certificate':[item['id']]}
    captured=[]
    monkeypatch.setattr(certificate_api,'certificate_pdf',lambda cert,url:(captured.append(url) or b'%PDF-test'))
    assert client.get(item['download_url']).status_code==200
    assert captured==[item['verify_url']]
    client.post('/api/auth/logout')
    result=client.get('/api/public/hackathons/1/results?'+parsed.query)
    assert result.status_code==200 and result.json['certificate']['valid'] is True
    assert result.json['certificate']['recipient_name']=='Александр'
    assert result.json['items'][0]['place']==1
    assert '@hackflow.test' not in result.get_data(as_text=True)
    legacy=client.get('/api/certificates/'+item['id']+'/verify').get_data(as_text=True)
    assert 'href="/results/1"' in legacy and 'Все хакатоны' in legacy


def test_qr_validation_rejects_revoked_wrong_event_and_unknown_tokens(app,client,competition):
    publish(client);login(client,'participant')
    token=client.get('/api/profile/certificates').json['items'][0]['id']
    with app.app_context():
        other=Hackathon(title='Другие результаты',status='completed',results_published=True,
            start_at=now(),end_at=now()+timedelta(days=3),registration_deadline=now(),submission_deadline=now()+timedelta(days=2))
        db.session.add(other);db.session.flush();hid=other.id
        cert=AwardCertificate.query.filter_by(public_id=token).one();cert.revoked_at=now();db.session.commit()
    client.post('/api/auth/logout')
    for event,query in [(1,token),(hid,token),(1,'0'*32),(1,'not-a-token')]:
        response=client.get(f'/api/public/hackathons/{event}/results?certificate={query}')
        assert response.status_code==200 and response.json['certificate']=={'valid':False}
        assert 'recipient_name' not in response.get_data(as_text=True)


def test_render_external_url_prevents_localhost_qr_on_cloud(app,client,competition,monkeypatch):
    publish(client);login(client,'participant')
    app.config['PUBLIC_URL']='http://localhost:8000'
    monkeypatch.setenv('RENDER_EXTERNAL_URL','https://hackflow-test.onrender.com')
    item=client.get('/api/profile/certificates').json['items'][0]
    assert item['verify_url'].startswith('https://hackflow-test.onrender.com/results/1?certificate=')
