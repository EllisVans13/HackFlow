"""Mentor selection and the mentor's read-only team workspace."""
from flask import Blueprint, abort, jsonify, request
from flask_login import current_user, login_required
from .models import db, User, Team, Case, Task, Submission, EventRole, Membership
from .mentoring import assigned_mentor, mentor_data
from .api import (get, body, integer, require_admission, require_participant,
                  organizer, captain, team_data, serialize, notify, notify_team,
                  audit, commit)
from .models import Hackathon

mentors_api=Blueprint('mentors',__name__)


@mentors_api.get('/hackathons/<int:hid>/mentors')
@login_required
def mentor_catalog(hid):
    h=get(Hackathon,hid)
    if not organizer(hid):
        require_participant()
        require_admission(h)
    # Public professional profiles only. Never expose account email/password/XP.
    unavailable=db.select(EventRole.user_id).where(
        EventRole.hackathon_id==hid,EventRole.role.in_(['jury','organizer']))
    members=db.select(Membership.user_id).where(Membership.hackathon_id==hid)
    users=User.query.filter(User.role=='mentor',User.blocked.is_(False),
                            User.id.not_in(unavailable),User.id.not_in(members)).order_by(User.nickname)
    return jsonify(items=[mentor_data(u) for u in users])


@mentors_api.route('/teams/<int:tid>/mentor',methods=['PUT','DELETE'])
@login_required
def select_mentor(tid):
    team=Team.query.filter_by(id=tid).with_for_update().first_or_404()
    if not organizer(team.hackathon_id):
        captain(team)
    previous=team.mentor_id
    if get(Hackathon,team.hackathon_id).status=='completed':
        abort(409,'У завершённого хакатона нельзя менять ментора.')
    if request.method=='PUT':
        body_id=integer(body().get('user_id'))
        user=User.query.filter_by(id=body_id).with_for_update().first_or_404()
        if user.role!='mentor' or user.blocked:
            abort(409,'Выберите активный аккаунт ментора.')
        if EventRole.query.filter(EventRole.user_id==user.id,EventRole.hackathon_id==team.hackathon_id,
                                  EventRole.role.in_(['organizer','jury'])).first() or Membership.query.filter_by(user_id=user.id,hackathon_id=team.hackathon_id).first():
            abort(409,'Ментор не может быть участником или жюри этого хакатона.')
        team.mentor_id=user.id
    else:
        team.mentor_id=None
    if previous!=team.mentor_id:
        if previous: notify(previous,'Назначение ментора завершено',team.name)
        if team.mentor_id: notify(team.mentor_id,'Вы назначены ментором команды',team.name)
        notify_team(team,'Ментор команды изменён',mentor_data(user)['nickname'] if team.mentor_id else 'Ментор снят')
        audit('mentor.assign',{'team':team.id,'previous':previous,'mentor':team.mentor_id})
    commit()
    return jsonify(mentor=mentor_data(db.session.get(User,team.mentor_id)) if team.mentor_id else None)


@mentors_api.get('/mentor/teams')
@login_required
def my_teams():
    if current_user.role!='mentor': abort(403,'Кабинет доступен только ментору.')
    items=[]
    for team in Team.query.filter_by(mentor_id=current_user.id).order_by(Team.id):
        h=get(Hackathon,team.hackathon_id)
        items.append(dict(team_data(team),hackathon_title=h.title,status=h.status))
    return jsonify(items=items)


@mentors_api.get('/mentor/teams/<int:tid>')
@login_required
def workspace(tid):
    team=get(Team,tid)
    if not assigned_mentor(team): abort(403,'Эта команда вам не назначена.')
    h=get(Hackathon,team.hackathon_id)
    case=get(Case,team.case_id) if team.case_id else None
    submission=Submission.query.filter_by(team_id=tid).first()
    return jsonify(team=team_data(team),hackathon={'id':h.id,'title':h.title,'status':h.status},
                   case=serialize(case,'id title description requirements expected') if case else None,
                   tasks=[serialize(t,'id title description status assignee_id deadline') for t in Task.query.filter_by(team_id=tid)],
                   submission=serialize(submission,'id title description github demo presentation_id submitted_at') if submission else None)


@mentors_api.before_app_request
def restrict_mentor_api():
    """Dedicated mentors cannot inherit participant/jury/admin APIs from old rows."""
    if not request.path.startswith('/api/') or not current_user.is_authenticated or current_user.role!='mentor':
        return
    read_only={'api.health','api.me','api.csrf_token','api.profile','api.media_download',
               'api.hackathons','api.hackathon','api.teams','api.team_detail','api.tasks',
               'api.messages','api.materials','api.schedule','api.deadlines','api.download',
               'api.notifications','mentors.my_teams','mentors.workspace'}
    editable={'api.login','api.logout','api.forgot','api.reset','api.edit_profile',
              'api.avatar_upload','api.read_notifications','api.consultation','api.feedback'}
    if request.endpoint in editable or request.method in ('GET','HEAD') and request.endpoint in read_only:
        return
    abort(403,'В аккаунте ментора доступны только назначенные команды, рекомендации и личные настройки.')
