"""Awards are derived from official results; PDF never contains user-supplied HTML."""
import io
import gzip
import os
import secrets
from html import escape
from pathlib import Path
from flask import current_app
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.colors import HexColor
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.utils import ImageReader
import qrcode
from .models import *

def issue_awards(h):
    if not h.results_published or h.status!='completed':return
    db.session.flush()
    orgs=[db.session.get(User,r.user_id).nickname for r in EventRole.query.filter_by(hackathon_id=h.id,role='organizer').order_by(EventRole.user_id)]
    names=', '.join(orgs) or 'Организатор не указан'
    emails=[a.email for a in Admission.query.filter_by(hackathon_id=h.id)]
    members=[m.user_id for m in Membership.query.filter_by(hackathon_id=h.id)]
    users=User.query.filter((User.email.in_(emails)) | (User.id.in_(members))).all()
    for u in users:
        if u.role!='participant' or EventRole.query.filter(EventRole.user_id==u.id,EventRole.role.in_(['jury','organizer'])).first():continue
        result=PersonalResult.query.filter_by(user_id=u.id,hackathon_id=h.id).first()
        place=result.place if result and result.place in [1,2,3] else None
        if place is None:
            old=Award.query.filter_by(user_id=u.id,hackathon_id=h.id,kind='diploma').first()
            if old:db.session.delete(old)
        for kind,award_place in [('certificate',None)]+([('diploma',place)] if place else []):
            a=Award.query.filter_by(user_id=u.id,hackathon_id=h.id,kind=kind).first()
            snapshot=(u.nickname,h.title,names,award_place)
            if a and (a.recipient,a.event_title,a.organizers,a.place)==snapshot:continue
            if not a:a=Award(user_id=u.id,hackathon_id=h.id,kind=kind);db.session.add(a)
            a.recipient,a.event_title,a.organizers,a.place=snapshot
            a.token=secrets.token_urlsafe(24);a.issued_at=now()
            db.session.add(Notification(user_id=u.id,title='Готов '+('диплом' if kind=='diploma' else 'сертификат участника'),text=h.title+' — откройте вкладку «Мои дипломы» в профиле.'))

def award_data(a):
    return {'id':a.id,'hackathon_id':a.hackathon_id,'recipient':a.recipient,'event_title':a.event_title,'organizers':a.organizers,'place':a.place,'kind':'diploma' if a.place else 'certificate','title':f'Диплом {a.place} степени' if a.place else 'Сертификат участника','issued_at':a.issued_at.isoformat()+'Z','verification_url':current_app.config['PUBLIC_URL'].rstrip('/')+f'/results/{a.hackathon_id}?award={a.token}'}

def render_pdf(a):
    candidates=[os.environ.get('CERT_FONT_PATH',''),str(Path(__file__).parent/'assets'/'DejaVuSans.ttf.gz'),'/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf','C:/Windows/Fonts/arial.ttf','/System/Library/Fonts/Supplemental/Arial.ttf']
    font=next((p for p in candidates if p and Path(p).is_file()),None)
    if not font:raise RuntimeError('Для PDF нужен кириллический TTF: задайте CERT_FONT_PATH.')
    if 'AwardFont' not in pdfmetrics.getRegisteredFontNames():pdfmetrics.registerFont(TTFont('AwardFont',io.BytesIO(gzip.decompress(Path(font).read_bytes())) if font.endswith('.gz') else font))
    data=award_data(a);buffer=io.BytesIO();width,height=landscape(A4)
    c=canvas.Canvas(buffer,pagesize=(width,height));c.setTitle(data['title']);c.setAuthor('HackFlow')
    c.setFillColor(HexColor('#fbfaf7'));c.rect(0,0,width,height,fill=1,stroke=0)
    c.setStrokeColor(HexColor('#7655bd'));c.setLineWidth(2);c.rect(24,24,width-48,height-48)
    c.setFillColor(HexColor('#262038'));c.setFont('AwardFont',16);c.drawString(52,height-65,'HACKFLOW')
    c.setFont('AwardFont',32);c.drawCentredString(width/2,height-135,'ДИПЛОМ' if a.place else 'СЕРТИФИКАТ УЧАСТНИКА')
    def paragraph(text,y,size=18,maxheight=80):
        style=ParagraphStyle('award',fontName='AwardFont',fontSize=size,leading=size*1.35,alignment=1,textColor=HexColor('#262038'))
        p=Paragraph(escape(text),style);w,hh=p.wrap(width-160,maxheight)
        while hh>maxheight and style.fontSize>9:
            style.fontSize-=1;style.leading=style.fontSize*1.35
            p=Paragraph(escape(text),style);w,hh=p.wrap(width-160,maxheight)
        p.drawOn(c,80,y-hh)
    paragraph(f'{a.place} степени' if a.place else 'Подтверждает участие в хакатоне',height-155,20)
    paragraph(a.recipient,height-220,28)
    paragraph(a.event_title,height-290,22)
    paragraph('За призовое место в составе команды' if a.place else 'За участие в мероприятии',height-355,15)
    # A typed platform signature, explicitly distinguished from a legal electronic signature.
    style=ParagraphStyle('signature',fontName='AwardFont',fontSize=12,leading=17,textColor=HexColor('#262038'))
    p=Paragraph('Организатор: '+escape(a.organizers)+'<br/>Подпись организатора: '+escape(a.organizers),style)
    _,hh=p.wrap(width-260,90);p.drawOn(c,52,95)
    c.setFont('AwardFont',8);c.drawString(52,65,'Автоматически оформлено платформой. Не является квалифицированной электронной подписью.')
    c.drawString(52,49,'Дата выдачи: '+a.issued_at.strftime('%d.%m.%Y')+' · № '+str(a.id))
    qr=qrcode.make(data['verification_url']).convert('RGB');c.drawImage(ImageReader(qr),width-153,48,100,100)
    c.drawRightString(width-52,36,'Проверить документ и результаты')
    c.save();return buffer.getvalue()
