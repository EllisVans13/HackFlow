"""Explicit public demo credentials and isolated synthetic peer-review scenario."""
from datetime import timedelta
from io import BytesIO
from pathlib import Path
import zipfile
import secrets
from reportlab.pdfgen.canvas import Canvas
from reportlab.lib.pagesizes import A4
from werkzeug.security import generate_password_hash
from .models import *
from .certificate_pdf import register_fonts
from .peer_assessment import distribute
from .learning_seed_v1 import populate_learning

DEMO_PASSWORD='HackFlow-Demo-2026!'
ACCOUNTS=[('participant','Демо участник','participant'),('captain','Демо капитан 1','participant'),
          ('review2','Демо капитан 2','participant'),('review3','Демо капитан 3','participant'),('review4','Демо капитан 4','participant'),
          ('organizer','Демо организатор','organizer'),('jury','Демо жюри','jury'),
          ('mentor','Демо ментор','mentor'),('expert','Демо эксперт','expert'),('admin','Демо администратор','admin')]


def project_pdf(code,index):
    register_fonts();stream=BytesIO();canvas=Canvas(stream,pagesize=A4)
    canvas.setAuthor('');canvas.setTitle('Проект '+code);canvas.setFont('HFSans',18)
    canvas.drawString(40,790,'Демонстрационный проект '+code)
    canvas.setFont('HFSans',12)
    lines=['Учебные данные HackFlow. Это не реальный проект участника.',
           ['Планировщик студенческой команды','Каталог учебных материалов','Сервис студенческих событий','Панель командного прогресса'][index],
           'Проблема: информация о проекте распределена между сервисами.',
           'Решение: единый интерфейс, сохранение данных и понятные сроки.',
           'Основной сценарий: открыть проект, выполнить действие, увидеть результат.',
           'Ограничения: это синтетический материал для проверки Peer Review.',
           'Проверьте сценарий, интерфейс, техническое решение и описание.']
    for n,line in enumerate(lines):canvas.drawString(40,745-n*30,line)
    canvas.save();return stream.getvalue()


def seed_review_demo():
    folder=Path(__import__('flask').current_app.config['UPLOAD_FOLDER']);folder.mkdir(parents=True,exist_ok=True)
    users={}
    for short,nickname,role in ACCOUNTS:
        email=short+'@demo.hackflow.test';u=User.query.filter_by(email=email).first()
        if u and not u.is_demo:raise ValueError('Зарезервированный адрес занят недемонстрационным аккаунтом: '+email)
        if not u:
            u=User(email=email,nickname=nickname,role=role,is_demo=True,password_hash=generate_password_hash(DEMO_PASSWORD),mentor_skills='Архитектура, UX' if role=='mentor' else '')
            db.session.add(u);db.session.flush()
        users[short]=u
    h=Hackathon.query.filter_by(demo_key='peer-demo-2026').first()
    fresh=h is None
    if fresh:
        h=Hackathon(demo_key='peer-demo-2026',title='[Демо] Взаимная проверка проектов',description='Четыре учебные команды по одному участнику. Каждая оценивает три чужие работы анонимно. Итог: 80% жюри + 20% Peer Review.',
            rules='Скачайте обезличенный PDF и оцените три назначенных проекта по критериям из 100. Не оценивайте собственную работу.',
            start_at=now()-timedelta(days=5),end_at=now()+timedelta(days=7),registration_deadline=now()-timedelta(days=3),team_deadline=now()-timedelta(days=2),submission_deadline=now()-timedelta(hours=12),status='review',peer_enabled=True,difficulty='medium')
        db.session.add(h);db.session.flush()
        db.session.add_all([EventRole(user_id=users['organizer'].id,hackathon_id=h.id,role='organizer'),EventRole(user_id=users['jury'].id,hackathon_id=h.id,role='jury')])
        case=Case(hackathon_id=h.id,title='Единое пространство студенческого проекта',company='Демонстрационный кейс',description='Сделайте сценарий командной работы понятным.',requirements='Работающий сценарий, интерфейс и сохранение данных.',expected='Прототип и описание ограничений.');db.session.add(case);db.session.flush()
        db.session.add(Admission(hackathon_id=h.id,email=users['participant'].email))
        criteria=[]
        for title,maximum in [('Функциональность',30),('Удобство интерфейса',25),('Техническая реализация',25),('Описание и демонстрация',20)]:
            c=Criterion(hackathon_id=h.id,title=title,maximum=maximum);db.session.add(c);db.session.flush();criteria.append(c)
        db.session.add(Schedule(hackathon_id=h.id,title='Обсуждение проектов [демо]',description='Учебное событие без реальной онлайн-комнаты. Организатор может назначить настоящую встречу.',starts_at=now()+timedelta(days=1),duration_minutes=45,provider='offline',kind='consultation',speaker=users['mentor'].nickname,url=''))
    criteria=Criterion.query.filter_by(hackathon_id=h.id).all()
    for index,key in enumerate(['captain','review2','review3','review4']):
        user=users[key];code=secrets.token_hex(4).upper()
        t=Team.query.filter_by(hackathon_id=h.id,name=f'Демо команда {index+1}').first()
        if not t:
            if not fresh:continue  # Never recreate intentionally deleted team memberships.
            t=Team(hackathon_id=h.id,captain_id=user.id,mentor_id=users['mentor'].id,name=f'Демо команда {index+1}',code='PEER-DEMO-TEAM-'+str(index+1),case_id=case.id)
            db.session.add(t);db.session.flush();db.session.add(Membership(user_id=user.id,team_id=t.id,hackathon_id=h.id))
            db.session.add(Admission(hackathon_id=h.id,email=user.email))
            db.session.add(Task(team_id=t.id,creator_id=user.id,title='Проверить пользовательский сценарий',status='done'))
            db.session.add(Message(team_id=t.id,author_id=user.id,text='Демо: проект готов, ожидаем обратную связь.'))
        s=Submission.query.filter_by(team_id=t.id).first()
        if s:code=s.code
        pdf_name=f'demo-peer-{code}.pdf';zip_name=f'demo-peer-{code}.zip'
        if not (folder/pdf_name).exists():(folder/pdf_name).write_bytes(project_pdf(code,index))
        if not (folder/zip_name).exists():
            with zipfile.ZipFile(folder/zip_name,'w') as z:z.writestr('main.py','# Синтетический пример для демонстрации\n'+ '\n'.join(f'def transform_{i}(values):\n    if values:\n        return sum(values) + {index+i}\n    return 0\n' for i in range(12)))
        if not s:
            if not fresh:continue
            pdf=Upload(team_id=t.id,owner_id=user.id,storage_name=pdf_name,filename='project-'+code+'.pdf',purpose='anonymous',size=(folder/pdf_name).stat().st_size)
            source=Upload(team_id=t.id,owner_id=user.id,storage_name=zip_name,filename='source.zip',purpose='source',size=(folder/zip_name).stat().st_size)
            db.session.add_all([pdf,source]);db.session.flush()
            s=Submission(team_id=t.id,code=code,title='Учебный проект '+str(index+1),description='Демонстрационный сценарий',github='https://github.com/pallets/flask',demo='https://example.com',presentation_id=pdf.id,anonymous_file_id=pdf.id,source_id=source.id,anonymous_ready=True,anonymous_text='Учебная работа '+code+'. Платформа для студенческой команды; описание решения и ограничений — в PDF.',submitted_at=h.submission_deadline-timedelta(hours=4-index))
            db.session.add(s);db.session.flush()
            db.session.add_all([ReviewAssignment(submission_id=s.id,user_id=users['jury'].id,kind='jury'),ReviewAssignment(submission_id=s.id,user_id=users['expert'].id,kind='expert')])
            total=90-index*5;db.session.add(JuryScore(submission_id=s.id,user_id=users['jury'].id,total=total,scores={str(c.id):c.maximum*total/100 for c in criteria},comment='Демонстрационная оценка жюри.'))
    if fresh:
        db.session.flush();distribute(h)
    populate_learning(db.session.connection(),h.id);db.session.commit()
    return h
