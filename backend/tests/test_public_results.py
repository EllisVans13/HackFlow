from datetime import timedelta
import pytest
from werkzeug.security import generate_password_hash
from conftest import TEST_PASSWORD,login
from hackflow.models import db,User,Hackathon,Team,Upload,Submission,Criterion,JuryScore,now


@pytest.fixture()
def published_results(app):
    with app.app_context():
        h=db.session.get(Hackathon,1);h.status='completed';h.results_published=True
        criteria=Criterion.query.filter_by(hackathon_id=1).all()
        for index,total in enumerate([95,95,80]):
            if index==0: t=db.session.get(Team,1)
            else:
                t=Team(hackathon_id=1,captain_id=1,name=f'Команда {index+1}',code=f'SECRET-CODE-{index}')
                db.session.add(t);db.session.flush()
            f=Upload(team_id=t.id,owner_id=t.captain_id,storage_name=f'private-{index}.pdf',filename='private-presentation.pdf',purpose='presentation',size=100)
            db.session.add(f);db.session.flush()
            s=Submission(team_id=t.id,title=f'Проект {index+1}',description='PRIVATE DESCRIPTION',code=f'ANON-{index}',presentation_id=f.id,github='https://github.com/private/repository',demo='https://private.example.com',submitted_at=now()-timedelta(hours=3-index))
            db.session.add(s);db.session.flush()
            db.session.add(JuryScore(submission_id=s.id,user_id=4,total=total,scores={str(c.id):c.maximum*total/100 for c in criteria},comment='PRIVATE JURY COMMENT'))
        ids=[]
        for title,status,published,approval in [('Без результатов','completed',False,'approved'),('Идёт проверка','review',True,'approved'),('Отклонён','completed',True,'rejected')]:
            event=Hackathon(title=title,status=status,results_published=published,approval=approval,start_at=now()-timedelta(days=4),end_at=now(),registration_deadline=now()-timedelta(days=3),submission_deadline=now()-timedelta(days=1))
            db.session.add(event);db.session.flush();ids.append(event.id)
        for name,role in [('mentor','mentor'),('outsider','participant')]:
            db.session.add(User(email=name+'@hackflow.test',nickname=name,role=role,password_hash=generate_password_hash(TEST_PASSWORD)))
        db.session.commit()
        return ids


@pytest.mark.parametrize('account',[None,'participant','captain','organizer','jury','admin','mentor','outsider'])
def test_public_archive_and_places_available_to_every_role_without_admission(client,published_results,account):
    if account: login(client,account)
    archive=client.get('/api/public/results')
    assert archive.status_code==200
    assert {h['id'] for h in archive.json['items']}=={1,published_results[0]}
    assert next(h for h in archive.json['items'] if h['id']==published_results[0])['results_published'] is False
    result=client.get('/api/public/hackathons/1/results')
    assert result.status_code==200,result.json
    rows=result.json['items']
    assert [r['place'] for r in rows]==[1,2,3]
    assert [r['score'] for r in rows]==[95,95,80]
    assert rows[0]['team']=='Код будущего'
    assert all(set(r)=={'place','team','title','score','criteria','jury_score','peer_score','jury_component','peer_component','peer_count','peer_enabled'} for r in rows)
    for secret in ['PRIVATE','private-presentation','SECRET-CODE','ANON-','@hackflow.test','user_id','presentation_id','github','submitted_at']:
        assert secret not in result.get_data(as_text=True)


def test_unpublished_unapproved_and_incomplete_results_remain_private(client,published_results):
    for hid in published_results+[999999]:
        assert client.get(f'/api/public/hackathons/{hid}/results').status_code==404
    login(client,'organizer')
    assert client.get(f'/api/public/hackathons/{published_results[0]}/results').status_code==404


def test_public_ranking_does_not_grant_access_to_closed_hackathon_or_team(client,published_results):
    assert client.get('/api/public/hackathons/1/results').status_code==200
    assert client.get('/api/teams/1/messages').status_code==401
    login(client,'outsider')
    for path in ['/hackathons/1/materials','/hackathons/1/schedule','/teams/1/tasks','/teams/1/messages']:
        assert client.get('/api'+path).status_code==403
