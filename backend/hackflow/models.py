from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from sqlalchemy import UniqueConstraint, CheckConstraint, ForeignKeyConstraint

db = SQLAlchemy()

def now():
    return datetime.now(timezone.utc).replace(tzinfo=None)

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(254), unique=True, nullable=False, index=True)
    nickname = db.Column(db.String(64), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='participant')
    is_owner = db.Column(db.Boolean,nullable=False,default=False)
    blocked = db.Column(db.Boolean, default=False, nullable=False)
    github = db.Column(db.String(300), default='')
    telegram = db.Column(db.String(100), default='')
    avatar = db.Column(db.String(300), default='')
    theme = db.Column(db.String(20), default='holiday')
    created_at = db.Column(db.DateTime, default=now, nullable=False)

    __table_args__ = (db.Index('uq_platform_owner','is_owner',unique=True,postgresql_where=db.text('is_owner'),sqlite_where=db.text('is_owner')),CheckConstraint("NOT is_owner OR (role='admin' AND NOT blocked)",name='owner_is_active_admin'))

class Hackathon(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, default='')
    rules = db.Column(db.Text, default='')
    cover = db.Column(db.String(200), default='')
    start_at = db.Column(db.DateTime, nullable=False)
    end_at = db.Column(db.DateTime, nullable=False)
    registration_deadline = db.Column(db.DateTime, nullable=False)
    team_deadline = db.Column(db.DateTime)
    difficulty = db.Column(db.String(20),nullable=False,default='easy')
    approval = db.Column(db.String(20),nullable=False,default='approved')
    review_comment = db.Column(db.Text,default='')
    demo_key = db.Column(db.String(80), unique=True)
    submission_deadline = db.Column(db.DateTime, nullable=False)
    team_size = db.Column(db.Integer, nullable=False, default=5)
    closed = db.Column(db.Boolean, default=True, nullable=False)
    status = db.Column(db.String(20), default='active', nullable=False)
    results_published = db.Column(db.Boolean, default=False, nullable=False)
    peer_published = db.Column(db.Boolean, default=False, nullable=False)
    tie_rule = db.Column(db.String(200), default='При равенстве баллов — более ранняя сдача, затем код проекта.')
    __table_args__ = (CheckConstraint('team_size > 0 AND team_size <= 20'),)

class EventRole(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    hackathon_id = db.Column(db.Integer, db.ForeignKey('hackathon.id'), nullable=False, index=True)
    role = db.Column(db.String(20), nullable=False)
    __table_args__ = (UniqueConstraint('user_id', 'hackathon_id', 'role'),)

class Admission(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    hackathon_id = db.Column(db.Integer, db.ForeignKey('hackathon.id'), nullable=False)
    email = db.Column(db.String(254), nullable=False)
    __table_args__ = (UniqueConstraint('hackathon_id', 'email'),)

class Case(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    hackathon_id = db.Column(db.Integer, db.ForeignKey('hackathon.id'), nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False)
    company = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=False)
    requirements = db.Column(db.Text, default='')
    expected = db.Column(db.Text, default='')
    url = db.Column(db.String(500), default='')

class Team(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    hackathon_id = db.Column(db.Integer, db.ForeignKey('hackathon.id'), nullable=False, index=True)
    captain_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, default='')
    city_style = db.Column(db.String(20), nullable=False, default='workshop', server_default='workshop')
    city_showcase = db.Column(db.Boolean, nullable=False, default=False, server_default=db.false())
    code = db.Column(db.String(32), unique=True, nullable=False)
    open = db.Column(db.Boolean, default=True, nullable=False)
    case_id = db.Column(db.Integer, db.ForeignKey('case.id'))
    created_at = db.Column(db.DateTime, default=now, nullable=False)
    __table_args__ = (UniqueConstraint('id', 'hackathon_id'), UniqueConstraint('hackathon_id', 'name'))

class Membership(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    team_id = db.Column(db.Integer, nullable=False, index=True)
    hackathon_id = db.Column(db.Integer, nullable=False)
    __table_args__ = (UniqueConstraint('user_id', 'hackathon_id'), ForeignKeyConstraint(['team_id','hackathon_id'], ['team.id','team.hackathon_id'], ondelete='CASCADE'))

class JoinRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    team_id = db.Column(db.Integer, db.ForeignKey('team.id', ondelete='CASCADE'), nullable=False)
    status = db.Column(db.String(20), default='pending', nullable=False)
    __table_args__ = (UniqueConstraint('user_id','team_id'),)

class Invitation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    hackathon_id = db.Column(db.Integer, db.ForeignKey('hackathon.id'), nullable=False)
    email = db.Column(db.String(254), nullable=False)
    token_hash = db.Column(db.String(64), unique=True, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    used = db.Column(db.Boolean, default=False, nullable=False)
    revoked = db.Column(db.Boolean, default=False, nullable=False)

class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey('team.id', ondelete='CASCADE'), nullable=False, index=True)
    creator_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    assignee_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, default='')
    status = db.Column(db.String(20), default='todo', nullable=False)
    deadline = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=now, nullable=False)
    __table_args__ = (CheckConstraint("status IN ('todo','doing','review','done')"),)

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey('team.id', ondelete='CASCADE'), nullable=False, index=True)
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    channel = db.Column(db.String(20), default='team', nullable=False)
    text = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=now, nullable=False)
    read_at = db.Column(db.DateTime)

class Track(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    hackathon_id = db.Column(db.Integer, db.ForeignKey('hackathon.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)

class Material(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    hackathon_id = db.Column(db.Integer, db.ForeignKey('hackathon.id'), nullable=False, index=True)
    track_id = db.Column(db.Integer, db.ForeignKey('track.id'))
    title = db.Column(db.String(200), nullable=False)
    topic = db.Column(db.String(100), default='Разработка')
    kind = db.Column(db.String(40), default='document')
    description = db.Column(db.Text, default='')
    url = db.Column(db.String(500), nullable=False)

class LearningProgress(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    material_id = db.Column(db.Integer, db.ForeignKey('material.id', ondelete='CASCADE'), nullable=False)
    __table_args__ = (UniqueConstraint('user_id','material_id'),)

class Schedule(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    hackathon_id = db.Column(db.Integer, db.ForeignKey('hackathon.id'), nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, default='')
    starts_at = db.Column(db.DateTime, nullable=False)
    speaker = db.Column(db.String(200), default='')
    kind = db.Column(db.String(40), default='webinar')
    url = db.Column(db.String(500), default='')

class Submission(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey('team.id'), nullable=False, unique=True)
    code = db.Column(db.String(20), nullable=False, unique=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    github = db.Column(db.String(500), nullable=False)
    demo = db.Column(db.String(500), nullable=False)
    presentation_id = db.Column(db.Integer, db.ForeignKey('upload.id'), nullable=False)
    source_id = db.Column(db.Integer, db.ForeignKey('upload.id'))
    submitted_at = db.Column(db.DateTime, default=now, nullable=False)
    anonymous_text = db.Column(db.Text)
    anonymous_ready = db.Column(db.Boolean, default=False, nullable=False)
    flagged = db.Column(db.Boolean, default=False, nullable=False)

class Upload(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey('team.id'), nullable=False)
    owner_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    storage_name = db.Column(db.String(100), unique=True, nullable=False)
    filename = db.Column(db.String(200), nullable=False)
    size = db.Column(db.Integer, nullable=False)
    purpose = db.Column(db.String(20), nullable=False)

class Criterion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    hackathon_id = db.Column(db.Integer, db.ForeignKey('hackathon.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    maximum = db.Column(db.Integer, nullable=False)
    __table_args__ = (CheckConstraint('maximum > 0 AND maximum <= 100'),)

class ReviewAssignment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    submission_id = db.Column(db.Integer, db.ForeignKey('submission.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    kind = db.Column(db.String(20), default='jury', nullable=False)
    __table_args__ = (UniqueConstraint('submission_id','user_id','kind'),)

class ExpertComment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    submission_id = db.Column(db.Integer, db.ForeignKey('submission.id'), nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    text = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=now, nullable=False)

class JuryScore(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    submission_id = db.Column(db.Integer, db.ForeignKey('submission.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    scores = db.Column(db.JSON, nullable=False)
    total = db.Column(db.Float, nullable=False)
    comment = db.Column(db.Text, nullable=False)
    updated_at = db.Column(db.DateTime, default=now, nullable=False)
    __table_args__ = (UniqueConstraint('submission_id','user_id'), CheckConstraint('total >= 0 AND total <= 100'))

class ScoreHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    submission_id = db.Column(db.Integer, db.ForeignKey('submission.id'), nullable=False)
    actor_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    before = db.Column(db.JSON)
    after = db.Column(db.JSON, nullable=False)
    reason = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=now, nullable=False)

class PeerAssignment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey('team.id'), nullable=False)
    submission_id = db.Column(db.Integer, db.ForeignKey('submission.id'), nullable=False)
    __table_args__ = (UniqueConstraint('team_id','submission_id'),)

class PeerReview(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey('team.id'), nullable=False)
    submission_id = db.Column(db.Integer, db.ForeignKey('submission.id'), nullable=False)
    scores = db.Column(db.JSON, nullable=False)
    total = db.Column(db.Float, nullable=False)
    comment = db.Column(db.Text, nullable=False)
    __table_args__ = (UniqueConstraint('team_id','submission_id'),)

class CodeReport(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    submission_id = db.Column(db.Integer, db.ForeignKey('submission.id'), unique=True, nullable=False)
    status = db.Column(db.String(20), default='pending', nullable=False)
    report = db.Column(db.JSON, nullable=False, default=dict)
    created_at = db.Column(db.DateTime, default=now, nullable=False)

class AIReport(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    submission_id = db.Column(db.Integer, db.ForeignKey('submission.id'), unique=True, nullable=False)
    observations = db.Column(db.JSON, nullable=False)

class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False)
    text = db.Column(db.Text, default='')
    event_key = db.Column(db.String(150), unique=True)
    read = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=now, nullable=False)

class Appeal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    submission_id = db.Column(db.Integer, db.ForeignKey('submission.id'), nullable=False)
    reason = db.Column(db.Text, nullable=False)
    explanation = db.Column(db.Text, nullable=False)
    materials = db.Column(db.String(500), default='')
    status = db.Column(db.String(40), default='sent', nullable=False)
    response = db.Column(db.Text, default='')
    created_at = db.Column(db.DateTime, default=now, nullable=False)

class Activity(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    action = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=now, nullable=False, index=True)

class PersonalResult(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    hackathon_id = db.Column(db.Integer, db.ForeignKey('hackathon.id'), nullable=False)
    team_name = db.Column(db.String(100), nullable=False)
    case_title = db.Column(db.String(200), default='')
    score = db.Column(db.Float, nullable=False)
    place = db.Column(db.Integer, nullable=False)
    __table_args__ = (UniqueConstraint('user_id','hackathon_id'),)

class AuditLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    actor_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    action = db.Column(db.String(200), nullable=False)
    detail = db.Column(db.JSON, default=dict)
    created_at = db.Column(db.DateTime, default=now, nullable=False)

class PasswordReset(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    token_hash = db.Column(db.String(64), nullable=False, unique=True)
    expires_at = db.Column(db.DateTime, nullable=False)
    used = db.Column(db.Boolean, nullable=False, default=False)


class ConsultationAssignment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey('team.id', ondelete='CASCADE'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    __table_args__ = (UniqueConstraint('team_id','user_id'),)

class ConsultationComment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey('team.id', ondelete='CASCADE'), nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    text = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=now, nullable=False)


class Media(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    token = db.Column(db.String(64), unique=True, nullable=False)
    owner_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    hackathon_id = db.Column(db.Integer, db.ForeignKey('hackathon.id'))
    purpose = db.Column(db.String(20), nullable=False)

class TeamInvitation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey('team.id', ondelete='CASCADE'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    status = db.Column(db.String(20), nullable=False, default='pending')
    expires_at = db.Column(db.DateTime, nullable=False)
    __table_args__ = (UniqueConstraint('team_id','user_id',name='uq_team_invitation_recipient'),)
