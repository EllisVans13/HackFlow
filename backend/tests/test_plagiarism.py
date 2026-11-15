import io
import zipfile
from datetime import timedelta
import pytest
from werkzeug.security import generate_password_hash
from conftest import login,TEST_PASSWORD
from hackflow.models import db,User,Hackathon,Team,Upload,Submission,EventRole,CodeReport,Notification,now
from test_flows import submit,prepare


def source(name='original',offset=0,files=1):
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,'w') as archive:
        for f in range(files):
            code='\n'.join(f'def {name}_{i}(value):\n    label = "PRIVATE_AUTHOR_EMAIL"\n    if value > {i+offset}:\n        return value * {2+offset}\n    return label\n' for i in range(12))
            archive.writestr(f'PRIVATE_FILENAME_{f}.py',code)
    stream.seek(0)
    return stream


def second_submission(client,archive):
    login(client,'participant')
    team=client.post('/api/hackathons/1/teams',json={'name':'PRIVATE_TEAM'}).json['team']['id']
    assert client.patch(f'/api/teams/{team}',json={'case_id':1}).status_code==200
    assert client.post(f'/api/teams/{team}/uploads',data={'file':(archive,'PRIVATE_SOURCE.zip'),'purpose':'source'}).status_code==201
    pdf=client.post(f'/api/teams/{team}/uploads',data={'file':(io.BytesIO(b'%PDF-1.4'),'private.pdf'),'purpose':'presentation'}).json['id']
    result=client.post(f'/api/teams/{team}/submission',json={'title':'PRIVATE_TITLE','description':'PRIVATE_DESCRIPTION','github':'https://github.com/pallets/flask','demo':'https://example.com','presentation_id':pdf})
    assert result.status_code==201,result.json
    return result.json['id']


def test_assignment_runs_real_check_notifies_jury_and_preserves_anonymity(client,app):
    sid=submit(client,source())
    second=second_submission(client,source('renamed',99))
    prepare(client,sid)  # Assigning jury automatically computes the report.
    with app.app_context():
        report=CodeReport.query.filter_by(submission_id=sid).one()
        assert report.status=='completed' and report.report['max_similarity']==100
        assert report.report['compared_projects']==1
        assert Notification.query.filter(Notification.event_key.like(f'codecheck:{sid}:%')).count()==1
    login(client,'jury')
    result=client.get(f'/api/jury/{sid}')
    assert result.status_code==200 and result.json['codecheck']['report']['matches'][0]['fragments']
    text=result.get_data(as_text=True)
    for secret in ['PRIVATE_AUTHOR','PRIVATE_FILENAME','PRIVATE_TEAM','PRIVATE_TITLE','@hackflow.test','corpus_signature','github','storage_name']:
        assert secret not in text
    assert client.post(f'/api/jury/{sid}/codecheck',json={'force':True}).json['report']['max_similarity']==100
    with app.app_context():
        assert Notification.query.filter(Notification.event_key.like(f'codecheck:{sid}:%')).count()==1


def test_no_source_or_no_other_zip_is_not_originality_confirmation(client):
    sid=submit(client)
    prepare(client,sid)
    login(client,'jury')
    report=client.get(f'/api/jury/{sid}').json['codecheck']
    assert report['status']=='unavailable' and 'matches' not in report['report']


def test_only_one_source_has_insufficient_data_status(client):
    sid=submit(client,source())
    prepare(client,sid);login(client,'jury')
    report=client.get(f'/api/jury/{sid}').json['codecheck']
    assert report['status']=='insufficient_data'
    assert report['report']['max_similarity'] is None and report['report']['compared_projects']==0


def test_new_submitted_source_invalidates_old_report_and_assigned_jury_refreshes(client):
    sid=submit(client,source());prepare(client,sid)
    second_submission(client,source('changed',55))
    login(client,'jury')
    old=client.get(f'/api/jury/{sid}').json['codecheck']
    assert old['status']=='stale' and old['stale'] is True
    fresh=client.post(f'/api/jury/{sid}/codecheck',json={})
    assert fresh.status_code==200 and fresh.json['status']=='completed'
    assert fresh.json['report']['max_similarity']==100
    assert client.post(f'/api/jury/{sid}/codecheck',json={'force':'yes'}).status_code==400


def test_report_is_available_only_to_assigned_jury_and_staff(client,app):
    sid=submit(client,source());prepare(client,sid)
    with app.app_context():
        u=User(email='unassigned@hackflow.test',nickname='unassigned',role='jury',password_hash=generate_password_hash(TEST_PASSWORD))
        db.session.add(u);db.session.flush();db.session.add(EventRole(user_id=u.id,hackathon_id=1,role='jury'));db.session.commit()
    login(client,'unassigned')
    assert client.get(f'/api/jury/{sid}').status_code==403
    assert client.post(f'/api/jury/{sid}/codecheck',json={}).status_code==403
    assert client.get(f'/api/submissions/{sid}/codecheck').status_code==403
    client.post('/api/auth/logout')
    assert client.get(f'/api/submissions/{sid}/codecheck').status_code==401


def test_missing_archive_is_explicit_error_not_fake_zero(client,app):
    sid=submit(client,source())
    with app.app_context():
        from pathlib import Path
        s=db.session.get(Submission,sid);upload=db.session.get(Upload,s.source_id)
        Path(app.config['UPLOAD_FOLDER'],upload.storage_name).unlink()
    prepare(client,sid);login(client,'jury')
    result=client.get(f'/api/jury/{sid}').json['codecheck']
    assert result['status']=='error' and 'max_similarity' not in result['report']


def test_comparison_ignores_sources_from_another_hackathon(client,app):
    sid=submit(client,source())
    with app.app_context():
        from pathlib import Path
        h=Hackathon(title='Другой хакатон',start_at=now(),end_at=now()+timedelta(days=10),registration_deadline=now()+timedelta(days=2),submission_deadline=now()+timedelta(days=9))
        db.session.add(h);db.session.flush()
        t=Team(hackathon_id=h.id,captain_id=1,name='Другие',code='ANOTHER-EVENT')
        db.session.add(t);db.session.flush()
        Path(app.config['UPLOAD_FOLDER'],'other.zip').write_bytes(source().getvalue())
        f=Upload(team_id=t.id,owner_id=1,storage_name='other.zip',filename='other.zip',purpose='source',size=100)
        db.session.add(f);db.session.flush()
        db.session.add(Submission(team_id=t.id,code='OTHER_EVENT',title='Другой проект',description='Другой',presentation_id=f.id,source_id=f.id,github='https://github.com/pallets/flask',demo='https://example.com'))
        db.session.commit()
    prepare(client,sid);login(client,'jury')
    result=client.get(f'/api/jury/{sid}').json['codecheck']
    assert result['status']=='insufficient_data' and result['report']['compared_projects']==0
    assert 'OTHER_EVENT' not in str(result)


def test_analysis_limits_are_visible_not_claimed_as_complete(client,monkeypatch):
    import hackflow.plagiarism as module
    sid=submit(client,source(files=2));second_submission(client,source('copy',5,files=2))
    monkeypatch.setattr(module,'MAX_FILES',1)
    login(client,'organizer')
    result=client.post(f'/api/submissions/{sid}/codecheck',json={})
    assert result.status_code==200 and result.json['status']=='partial'
    assert result.json['report']['files_analyzed']==1 and result.json['report']['files_total']==2


def test_time_budget_does_not_report_zero_similarity_as_originality(client,monkeypatch):
    import hackflow.plagiarism as module
    sid=submit(client,source());second_submission(client,source('copy'))
    monkeypatch.setattr(module,'TIME_BUDGET',0)
    login(client,'organizer')
    report=client.post(f'/api/submissions/{sid}/codecheck',json={}).json
    assert report['status']=='partial' and report['report']['max_similarity'] is None
    assert report['report']['comparisons']==0


def test_file_limit_before_supported_code_is_partial_not_no_code(client):
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,'w') as archive:
        for i in range(8):archive.writestr(f'empty_{i}.py','pass')
        archive.writestr('later.py','\n'.join(f'def work_{i}(value):\n    return value * 2\n' for i in range(20)))
    stream.seek(0)
    sid=submit(client,stream);login(client,'organizer')
    report=client.post(f'/api/submissions/{sid}/codecheck',json={}).json
    assert report['status']=='partial' and report['report']['max_similarity'] is None
    assert report['report']['files_total']==9 and report['report']['files_analyzed']==0
