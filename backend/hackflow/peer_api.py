from pathlib import Path
import secrets
from flask import Blueprint,request,jsonify,abort,current_app,send_from_directory
from flask_login import current_user,login_required
from .models import db,Hackathon,Submission,Team,Upload,PeerAssignment,PeerReview,JuryScore
from .api import get,require_organizer,require_admission,member_team,audit,commit,require_jury_submission,require_participant
from .anonymous_files import sanitize_pdf

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
