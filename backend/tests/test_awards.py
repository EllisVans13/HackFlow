from datetime import timedelta
from unittest.mock import patch
from conftest import login
from test_flows import submit,prepare,score
from hackflow.models import *
from hackflow.awards import issue_awards,award_data

def publish_example(client):
    sid=submit(client);prepare(client,sid);score(client,sid)
    login(client,'organizer')
    r=client.post('/api/hackathons/1/publish',json={});assert r.status_code==200,r.json
    return sid

def test_public_results_require_publication_not_account(client):
    guest=client.application.test_client()
    assert guest.get('/api/public/hackathons/1/results').status_code==404
    assert guest.get('/api/hackathons/1/ranking').json['items']==[]
    publish_example(client)
    d=guest.get('/api/public/hackathons/1/results')
    assert d.status_code==200 and d.json['items'][0]['place']==1
    assert guest.get('/api/hackathons/1/ranking').json['published'] is True
    assert guest.get('/api/public/results').json['items'][0]['id']==1
    raw=str(d.json)
    for key in ['password','email','github','presentation_id','user_id','anonymous_text']:assert key not in raw

def test_awards_pdf_qr_access_and_duplicate_publication(client,app):
    publish_example(client);login(client,'captain')
    awards=client.get('/api/profile/awards').json['items']
    assert {a['kind'] for a in awards}=={'diploma','certificate'}
    diploma=next(a for a in awards if a['kind']=='diploma')
    assert diploma['place']==1 and diploma['recipient']=='Мария Волкова'
    assert 'Анна Смирнова' in diploma['organizers']
    assert '/results/1?award=' in diploma['verification_url']
    token=diploma['verification_url'].split('award=')[1]
    guest=app.test_client()
    assert guest.get('/api/public/awards/'+token).json['verified'] is True
    with patch('hackflow.awards.qrcode.make',wraps=__import__('qrcode').make) as qr:
        r=client.get(f"/api/profile/awards/{diploma['id']}/pdf")
        assert r.status_code==200 and r.mimetype=='application/pdf' and r.data.startswith(b'%PDF')
        assert len(r.data)>10000
        qr.assert_called_once_with(diploma['verification_url'])
    assert guest.get(f"/api/profile/awards/{diploma['id']}/pdf").status_code==401
    login(client,'participant')
    assert client.get(f"/api/profile/awards/{diploma['id']}/pdf").status_code==403
    # Registered users without prize results still receive participation certificates.
    assert {a['kind'] for a in client.get('/api/profile/awards').json['items']}=={'certificate'}
    login(client,'organizer');assert client.post('/api/hackathons/1/publish',json={}).status_code==200
    with app.app_context():
        a=db.session.get(Award,diploma['id']);assert a.token==token
        assert Award.query.count()==3

def test_degrees_and_reissue_after_result_change(app):
    with app.app_context():
        h=db.session.get(Hackathon,1);h.results_published=True;h.status='completed'
        # Four genuine participant records; judge and organiser must not get awards.
        ids=[1,2]
        for n in [3,4]:
            u=User(email=f'award{n}@example.com',nickname=f'Участник {n}',password_hash='unused-hash',role='participant');db.session.add(u);db.session.flush()
            ids.append(u.id);db.session.add(Admission(hackathon_id=1,email=u.email))
        for place,uid in enumerate(ids,1):db.session.add(PersonalResult(user_id=uid,hackathon_id=1,team_name=f'Команда {place}',score=100-place,place=place))
        db.session.flush();issue_awards(h);db.session.commit()
        assert sorted(a.place for a in Award.query.filter_by(kind='diploma'))==[1,2,3]
        assert Award.query.filter_by(kind='certificate').count()==4
        old=Award.query.filter_by(user_id=1,kind='diploma').one();token=old.token
        result=PersonalResult.query.filter_by(user_id=1,hackathon_id=1).one();result.place=2
        db.session.flush();issue_awards(h);db.session.commit()
        assert old.token!=token and old.place==2
        assert Award.query.filter_by(token=token).first() is None
        result.place=4;db.session.flush();issue_awards(h);db.session.commit()
        assert Award.query.filter_by(user_id=1,kind='diploma').count()==0
        assert Award.query.filter_by(user_id=1,kind='certificate').count()==1

def test_own_document_section_is_accessible_for_every_role(client):
    for role in ['participant','captain','organizer','jury','admin']:
        login(client,role)
        r=client.get('/api/profile/awards')
        assert r.status_code==200,r.json
        assert isinstance(r.json['items'],list)
