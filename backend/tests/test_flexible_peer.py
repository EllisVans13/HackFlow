from datetime import timedelta
from pathlib import Path
import pytest
from hackflow.models import db,User,Hackathon,EventRole,Criterion,Team,Membership,Admission,Submission,Upload,ReviewAssignment,JuryScore,PeerAssignment,PersonalResult,now
from hackflow.review_demo import seed_review_demo,project_pdf,DEMO_PASSWORD


def login_demo(client,name):
    result=client.post('/api/auth/login',json={'email':name+'@demo.hackflow.test','password':DEMO_PASSWORD})
    assert result.status_code==200,result.json


def prepare(app,count):
    with app.app_context():
        seed_review_demo()
        h=Hackathon(title=f'Гибкий Peer Review {count}',demo_key=f'flexible-{count}',difficulty='medium',peer_enabled=True,status='active',start_at=now()-timedelta(days=5),end_at=now()+timedelta(days=3),registration_deadline=now()-timedelta(days=3),submission_deadline=now()-timedelta(days=1))
        db.session.add(h);db.session.flush()
        organizer=User.query.filter_by(email='organizer@demo.hackflow.test').one();jury=User.query.filter_by(email='jury@demo.hackflow.test').one()
        db.session.add_all([EventRole(user_id=organizer.id,hackathon_id=h.id,role='organizer'),EventRole(user_id=jury.id,hackathon_id=h.id,role='jury')])
        criterion=Criterion(hackathon_id=h.id,title='Результат',maximum=100);db.session.add(criterion);db.session.flush()
        names=['captain','review2','review3','review4','participant'][:count];sids=[];tids=[]
        for i,name in enumerate(names):
            user=User.query.filter_by(email=name+'@demo.hackflow.test').one()
            t=Team(hackathon_id=h.id,captain_id=user.id,name=f'Команда {i}',code=f'FLEX-{h.id}-{i}')
            db.session.add(t);db.session.flush()
            db.session.add_all([Membership(user_id=user.id,team_id=t.id,hackathon_id=h.id),Admission(hackathon_id=h.id,email=user.email)])
            filename=f'flex-{h.id}-{i}.pdf';data=project_pdf(f'FLEX-{i}',i%4);Path(app.config['UPLOAD_FOLDER'],filename).write_bytes(data)
            upload=Upload(team_id=t.id,owner_id=user.id,storage_name=filename,filename=filename,purpose='anonymous',size=len(data));db.session.add(upload);db.session.flush()
            s=Submission(team_id=t.id,code=f'FX{h.id}-{i}',title=f'Проект {i}',description='Демо',github='https://github.com/pallets/flask',demo='https://example.com',presentation_id=upload.id,anonymous_file_id=upload.id,anonymous_ready=True,anonymous_text='Проверенные материалы',submitted_at=h.submission_deadline-timedelta(hours=count-i))
            db.session.add(s);db.session.flush()
            db.session.add_all([ReviewAssignment(user_id=jury.id,submission_id=s.id,kind='jury'),JuryScore(user_id=jury.id,submission_id=s.id,scores={str(criterion.id):90},total=90,comment='Проверка жюри')])
            sids.append(s.id);tids.append(t.id)
        db.session.commit();return h.id,criterion.id,names,sids,tids


@pytest.mark.parametrize('count,required',[(2,1),(3,2),(4,3),(5,3)])
def test_possible_review_counts_keep_weighted_scores_and_levels(app,client,count,required):
    hid,cid,names,sids,tids=prepare(app,count);login_demo(client,'organizer')
    response=client.post(f'/api/hackathons/{hid}/review-assignments',json={'team_id':tids[1],'submission_id':sids[0]})
    assert response.status_code==200,response.json
    assert response.json['required']==required
    assert response.json['added']==count*required
    assert client.post(f'/api/hackathons/{hid}/review-assignments',json={}).json['added']==0
    assert client.post(f'/api/hackathons/{hid}/publish',json={}).status_code==409
    with app.app_context():
        for tid,sid in zip(tids,sids):
            assert PeerAssignment.query.filter_by(team_id=tid).count()==required
            assert PeerAssignment.query.filter_by(submission_id=sid).count()==required
            assert not PeerAssignment.query.filter_by(team_id=tid,submission_id=sid).first()
    for i,name in enumerate(names):
        login_demo(client,name)
        response=client.get(f'/api/hackathons/{hid}/peer');assert response.status_code==200
        assert response.json['required']==required and len(response.json['items'])==required
        assert client.post(f'/api/peer/{sids[i]}',json={'scores':{str(cid):80},'comment':'Собственный проект'}).status_code==403
        for work in response.json['items']:
            assert client.get(work['material_url']).status_code==200
            assert client.post(f"/api/peer/{work['id']}",json={'scores':{str(cid):80},'comment':'Работа проверена'}).status_code==201
        if i==0:
            login_demo(client,'organizer')
            assert client.post(f'/api/hackathons/{hid}/publish',json={}).status_code==409
    login_demo(client,'organizer');result=client.post(f'/api/hackathons/{hid}/publish',json={})
    assert result.status_code==200,result.json
    assert all(row['score']==88 and row['criteria'][str(cid)]==88 and row['peer_component']==16 and row['peer_count']==required for row in result.json['items'])
    with app.app_context():assert PersonalResult.query.filter_by(hackathon_id=hid).count()==count
    login_demo(client,'captain');xp=client.get('/api/profile').json['level']['earned']
    assert next(x for x in xp if x['hackathon_id']==hid)['xp']==132


def test_one_project_cannot_review_itself_and_keeps_stage_unchanged(app,client):
    hid,cid,names,sids,tids=prepare(app,1);login_demo(client,'organizer')
    response=client.post(f'/api/hackathons/{hid}/review-assignments',json={})
    assert response.status_code==409 and 'две команды' in response.json['error']
    assert client.post(f'/api/hackathons/{hid}/publish',json={}).status_code==409
    with app.app_context():
        assert db.session.get(Hackathon,hid).status=='active'
        assert PeerAssignment.query.filter_by(submission_id=sids[0]).count()==0
