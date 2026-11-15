"""Shared access rules for dedicated mentor accounts."""
from flask_login import current_user
from .models import db, Team, User


def assigned_mentor(team, user=None):
    user=user or current_user
    return bool(user.is_authenticated and user.role=='mentor' and not user.blocked and team.mentor_id==user.id)


def mentor_data(user):
    if not user or user.role!='mentor' or user.blocked:
        return None
    return {'id':user.id,'nickname':user.nickname,'avatar':user.avatar,
            'bio':user.mentor_bio or '', 'skills':user.mentor_skills or ''}
