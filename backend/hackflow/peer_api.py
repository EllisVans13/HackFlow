from pathlib import Path
import secrets
from flask import Blueprint,request,jsonify,abort,current_app,send_from_directory
from flask_login import current_user,login_required
from .models import db,Hackathon,Submission,Team,Upload,PeerAssignment,PeerReview,JuryScore
from .api import get,require_organizer,require_admission,member_team,audit,commit,require_jury_submission,require_participant,body,integer,notify_team,publish
from .anonymous_files import sanitize_pdf
from .peer_assessment import distribute,required_reviewers

peer_api=Blueprint('peer_tools',__name__)


@peer_api.post('/submissions/<int:sid>/anonymous-file')
@login_required
def anonymous_file(sid):
    s=get(Submission,sid);h=get(Hackathon,get(Team,s.team_id).hackathon_id);require_organizer(h.id)
    if h.results_published or PeerReview.query.filter_by(submission_id=sid).first() or JuryScore.query.filter_by(submission_id=sid).first():abort(409,'После оценивания нельзя подменять обезличенный файл.')
    if request.form.get('confirmed')!='true':abort(400,'Подтвердите, что PDF проверен и не содержит авторов/команд/контактов.')
    file=request.files.get('file')
    if not file:abort(400,'Выберите обезличенный PDF.')
    data=sanitize_pdf(file.read(),s.code);name=secrets.token_hex(24)+'.pdf'
    Path(current_app.config['UPLOAD_FOLDER'],name).write_bytes(data)
    upload=Upload(team_id=s.team_id,owner_id=current_user.id,storage_name=name,filename='project-'+s.code+'.pdf',purpose='anonymous',size=len(data))
    db.session.add(upload);db.session.flush();s.anonymous_file_id=upload.id
    audit('submission.anonymous_file',{'id':sid});commit();return jsonify(ok=True)


def file_response(s):
    if not s.anonymous_ready or not s.anonymous_file_id:abort(404,'Обезличенный PDF ещё не подготовлен.')
    file=get(Upload,s.anonymous_file_id)
    if not Path(current_app.config['UPLOAD_FOLDER'],file.storage_name).is_file():abort(404,'Файл отсутствует в хранилище.')
    response=send_from_directory(current_app.config['UPLOAD_FOLDER'],file.storage_name,mimetype='application/pdf',as_attachment=request.args.get('download')=='1',download_name='project-'+s.code+'.pdf')
    response.headers['Cache-Control']='private, no-store';return response


@peer_api.get('/peer/<int:sid>/material')
@login_required
def peer_material(sid):
    require_participant()
    s=get(Submission,sid);h=get(Hackathon,get(Team,s.team_id).hackathon_id)
    require_admission(h);t=member_team(h.id)
    if not t or t.id==s.team_id or not PeerAssignment.query.filter_by(team_id=t.id,submission_id=sid).first():abort(403,'Работа вашей команде не назначена.')
    return file_response(s)


@peer_api.get('/jury/<int:sid>/material')
@login_required
def jury_material(sid):
    s=get(Submission,sid);require_jury_submission(s);return file_response(s)


@peer_api.get('/submissions/<int:sid>/anonymous-file')
@login_required
def organizer_material(sid):
    s=get(Submission,sid);require_organizer(get(Team,s.team_id).hackathon_id)
    return file_response(s)


@peer_api.post('/hackathons/<int:hid>/review-assignments')
@peer_api.post('/hackathons/<int:hid>/peer')
@peer_api.post('/hackathons/<int:hid>/peer/distribute')
@login_required
def assign_projects(hid):
    require_organizer(hid)
    h=Hackathon.query.filter_by(id=hid).with_for_update().populate_existing().first_or_404()
    if h.results_published or h.peer_published:abort(409,'Этап оценивания уже закрыт.')
    d=body();preferred_added=0
    if 'submission_id' in d or 'team_id' in d:
        target=get(Submission,integer(d.get('submission_id')));team=get(Team,integer(d.get('team_id')))
        if team.hackathon_id!=hid or get(Team,target.team_id).hackathon_id!=hid:abort(400,'Команда и проект должны относиться к этому хакатону.')
        if team.id==target.team_id:abort(400,'Нельзя назначить команде собственный проект.')
        if not Submission.query.filter_by(team_id=team.id).first():abort(409,'Команда-рецензент должна сдать собственный проект.')
        if not PeerAssignment.query.filter_by(team_id=team.id,submission_id=target.id).first():
            if PeerAssignment.query.filter_by(team_id=team.id).count()>=required_reviewers(hid) or PeerAssignment.query.filter_by(submission_id=target.id).count()>=required_reviewers(hid):abort(409,'Достигнут лимит доступных проверок для команды или проекта.')
            db.session.add(PeerAssignment(team_id=team.id,submission_id=target.id));db.session.flush();preferred_added=1
    added=distribute(h)+preferred_added
    if added:
        for team in Team.query.filter_by(hackathon_id=hid):notify_team(team,'Назначены проекты для Peer Review','Откройте Peer Review в пространстве хакатона.')
    audit('review.assignments',{'hackathon':hid,'added':added});commit()
    return jsonify(ok=True,added=added,status=h.status,required=required_reviewers(hid))


@peer_api.post('/hackathons/<int:hid>/peer/publish')
@login_required
def legacy_publish(hid):
    # Old open tabs use the same complete official-publication checks.
    return publish(hid)
