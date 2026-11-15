from io import BytesIO
from urllib.parse import urlsplit
from flask import Blueprint, abort, current_app, jsonify, render_template, send_file, url_for
from flask_login import current_user, login_required
from .models import db, AwardCertificate, EventRole
from .certificates import certificate_valid, recipient_certificates
from .certificate_pdf import certificate_pdf

certificates_api=Blueprint('certificates',__name__)

def public_verification_url(cert):
    base=current_app.config['PUBLIC_URL'].rstrip('/')
    if urlsplit(base).scheme not in ('http','https') or not urlsplit(base).netloc:
        abort(503,'Настройте PUBLIC_URL для проверки дипломов.')
    return base+url_for('certificates.verify_certificate',token=cert.public_id)

def certificate_data(cert):
    return {'id':cert.public_id,'number':f'HF-{cert.id:06d}','hackathon_id':cert.hackathon_id,
        'recipient_name':cert.recipient_name,'team_name':cert.team_name,'event_title':cert.event_title,
        'organizer_name':cert.organizer_name,'place':cert.place,'is_demo':cert.is_demo,
        'issued_at':cert.issued_at.isoformat()+'Z',
        'download_url':url_for('certificates.download_certificate',token=cert.public_id),
        'preview_url':url_for('certificates.preview_certificate',token=cert.public_id),
        'verify_url':public_verification_url(cert)}

@certificates_api.get('/profile/certificates')
@login_required
def my_certificates():
    from flask import request
    raw=request.args.get('hackathon_id');hid=None
    if raw is not None:
        try:hid=int(raw)
        except ValueError:abort(400,'Некорректный хакатон.')
    return jsonify(items=[certificate_data(c) for c in recipient_certificates(current_user.id,hid)])

def authorized_certificate(token):
    cert=AwardCertificate.query.filter_by(public_id=token).first_or_404()
    permitted=(cert.user_id==current_user.id or current_user.role=='admin'
        or EventRole.query.filter_by(user_id=current_user.id,hackathon_id=cert.hackathon_id,role='organizer').first())
    if not permitted:abort(403,'Этот диплом принадлежит другому участнику.')
    if not certificate_valid(cert):abort(409,'Диплом отозван или итоги хакатона ещё не опубликованы.')
    return cert

def pdf_response(token,attachment):
    cert=authorized_certificate(token)
    data=certificate_pdf(cert,public_verification_url(cert))
    response=send_file(BytesIO(data),mimetype='application/pdf',as_attachment=attachment,
        download_name=f'hackflow-diploma-{cert.place}-HF-{cert.id:06d}.pdf',max_age=0)
    response.headers['Cache-Control']='private, no-store'
    return response

@certificates_api.get('/certificates/<token>/download')
@login_required
def download_certificate(token):
    return pdf_response(token,True)

@certificates_api.get('/certificates/<token>/preview')
@login_required
def preview_certificate(token):
    return pdf_response(token,False)

@certificates_api.get('/certificates/<token>/verify')
def verify_certificate(token):
    cert=AwardCertificate.query.filter_by(public_id=token).first_or_404()
    return render_template('certificate_verify.html',cert=cert,valid=certificate_valid(cert),
        number=f'HF-{cert.id:06d}',roman={1:'I',2:'II',3:'III'}[cert.place])
