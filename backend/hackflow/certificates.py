"""Immutable award snapshots; result corrections revoke obsolete documents."""
from uuid import uuid4
from .models import db, AwardCertificate, PersonalResult, Hackathon, User, EventRole, Notification, now

def organizer_name(hid):
    row=(db.session.query(User.nickname).join(EventRole,EventRole.user_id==User.id)
         .filter(EventRole.hackathon_id==hid,EventRole.role=='organizer').order_by(EventRole.id).first())
    return row[0] if row else 'Организаторы хакатона'

def sync_awards(h):
    """Run inside the publication transaction, after PersonalResult is flushed."""
    if h.status!='completed' or not h.results_published:
        return 0
    desired={r.user_id:r for r in PersonalResult.query.filter(PersonalResult.hackathon_id==h.id,PersonalResult.place.between(1,3))}
    current={c.user_id:c for c in AwardCertificate.query.filter_by(hackathon_id=h.id,revoked_at=None)}
    for uid,cert in list(current.items()):
        result=desired.get(uid)
        if not result or cert.result_id!=result.id or cert.place!=result.place or cert.team_name!=result.team_name:
            cert.revoked_at=now();del current[uid]
    db.session.flush()  # Release the unique active-recipient index before reissuing.
    count=0;issuer=organizer_name(h.id)
    for uid,result in desired.items():
        if uid in current:
            continue
        user=db.session.get(User,uid)
        cert=AwardCertificate(public_id=uuid4().hex,hackathon_id=h.id,user_id=uid,result_id=result.id,
            recipient_name=user.nickname,team_name=result.team_name,event_title=h.title,organizer_name=issuer,
            place=result.place,is_demo=bool(h.demo_key))
        db.session.add(cert)
        db.session.add(Notification(user_id=uid,title=f'Диплом за {result.place} место',
            text=f'{h.title} — диплом доступен в профиле.',event_key='certificate:'+cert.public_id))
        count+=1
    return count

def certificate_valid(cert):
    if cert.revoked_at is not None:
        return False
    h=db.session.get(Hackathon,cert.hackathon_id)
    result=db.session.get(PersonalResult,cert.result_id)
    return bool(h and h.results_published and h.status=='completed' and result
                and result.user_id==cert.user_id and result.hackathon_id==cert.hackathon_id
                and result.place==cert.place and result.team_name==cert.team_name)

def recipient_certificates(uid,hid=None):
    query=(AwardCertificate.query.join(Hackathon,AwardCertificate.hackathon_id==Hackathon.id)
           .filter(AwardCertificate.user_id==uid,AwardCertificate.revoked_at.is_(None),
                   Hackathon.results_published.is_(True),Hackathon.status=='completed'))
    if hid is not None:
        query=query.filter(AwardCertificate.hackathon_id==hid)
    return [c for c in query.order_by(AwardCertificate.issued_at.desc(),AwardCertificate.id.desc()) if certificate_valid(c)]
