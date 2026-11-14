from datetime import timedelta
from pathlib import Path
import secrets
from flask import current_app
from werkzeug.security import generate_password_hash
from .models import *
from .services import publish_results

def demo_pdf():
    stream=b'BT /F1 18 Tf 40 140 Td (HackFlow DEMO presentation) Tj ET'
    objects=[b'<< /Type /Catalog /Pages 2 0 R >>',b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 500 200] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>',b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',b'<< /Length '+str(len(stream)).encode()+b' >>\nstream\n'+stream+b'\nendstream']
    data=b'%PDF-1.4\n';offsets=[]
    for i,obj in enumerate(objects,1):
        offsets.append(len(data));data+=str(i).encode()+b' 0 obj\n'+obj+b'\nendobj\n'
    start=len(data);data+=b'xref\n0 6\n0000000000 65535 f \n'+b''.join(f'{x:010} 00000 n \n'.encode() for x in offsets)
    return data+b'trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n'+str(start).encode()+b'\n%%EOF'


def enrich(password):
    if len(password)<12: raise ValueError('Минимум 12 символов')
    if not User.query.filter_by(role='admin').first():
        if User.query.filter_by(email='admin@hackflow.test').first():
            raise ValueError('Email admin@hackflow.test уже занят; создайте администратора через init-admin.')
        db.session.add(User(email='admin@hackflow.test',nickname='Главный администратор',role='admin',is_owner=True,password_hash=generate_password_hash(password)))
        db.session.flush()
    us=[]
    for name in ['participant','captain','organizer','jury','builder']:
        u=User.query.filter_by(email=name+'@hackflow.test').first()
        if not u:
            u=User(email=name+'@hackflow.test',nickname=name,password_hash=generate_password_hash(password),role='organizer' if name=='organizer' else 'participant');db.session.add(u);db.session.flush()
        us.append(u)
    participant,cap,org,jury,builder=us
    for i,status in enumerate(['completed','completed','active','active','upcoming','upcoming','review']):
        key=f'showcase-{i}'
        if Hackathon.query.filter_by(demo_key=key).first():continue
        start=now()+timedelta(days=-40 if status=='completed' else -8 if status=='review' else 4 if status=='upcoming' else -1)
        h=Hackathon(difficulty=['easy','medium','hard'][i%3],demo_key=key,title=f'[Демо] Хакатон {i+1}',description='Демонстрационное мероприятие: учебные команды и результаты.',rules='Один кейс на команду.',start_at=start,end_at=start+timedelta(days=7),registration_deadline=start+timedelta(days=3),team_deadline=start+timedelta(days=4),submission_deadline=start+timedelta(days=6),status=status,team_size=5,closed=True);db.session.add(h);db.session.flush()
        db.session.add_all([EventRole(user_id=org.id,hackathon_id=h.id,role='organizer'),EventRole(user_id=jury.id,hackathon_id=h.id,role='jury')])
        case=Case(hackathon_id=h.id,title='Студенческий сервис',company='Демо',description='Упростите командную работу.',requirements='Прототип и презентация',expected='Работающий продукт');db.session.add(case)
        criterion=Criterion(hackathon_id=h.id,title='Качество решения',maximum=100);db.session.add(criterion);db.session.flush()
        for u in [participant,cap,builder]:db.session.add(Admission(hackathon_id=h.id,email=u.email))
        for j,owner in enumerate([cap,builder]):
            t=Team(hackathon_id=h.id,captain_id=owner.id,name=f'Демо-команда {i}.{j}',code=secrets.token_urlsafe(9),case_id=case.id);db.session.add(t);db.session.flush()
            members=[owner,participant] if j==0 and status in ['completed','review'] else [owner]
            for u in members:db.session.add(Membership(user_id=u.id,team_id=t.id,hackathon_id=h.id))
            for k,st in enumerate(['todo','doing','review','done']):db.session.add(Task(team_id=t.id,creator_id=owner.id,assignee_id=owner.id,title=f'Демо-задача {k+1}',status=st,deadline=h.submission_deadline))
            db.session.add(Message(team_id=t.id,author_id=owner.id,text='Демо: прототип готов, проверим сценарий.'))
            if status in ['completed','review']:
                filename=secrets.token_hex(24)+'.pdf';Path(current_app.config['UPLOAD_FOLDER'],filename).write_bytes(demo_pdf())
                f=Upload(team_id=t.id,owner_id=owner.id,storage_name=filename,filename='demo.pdf',size=len(demo_pdf()),purpose='presentation');db.session.add(f);db.session.flush()
                s=Submission(team_id=t.id,code=secrets.token_hex(3).upper(),title='Демо-проект',description='Демонстрационное решение',github='https://github.com/pallets/flask',demo='https://example.com',presentation_id=f.id,submitted_at=h.submission_deadline-timedelta(hours=2+j),anonymous_ready=True,anonymous_text='Обезличенное демонстрационное решение');db.session.add(s);db.session.flush()
                db.session.add(ReviewAssignment(submission_id=s.id,user_id=jury.id,kind='jury'))
                if status=='completed':db.session.add(JuryScore(submission_id=s.id,user_id=jury.id,scores={str(criterion.id):90-j*10-i},total=90-j*10-i,comment='Демонстрационная проверка'))
        db.session.add(Material(hackathon_id=h.id,title='React: практика',url='https://react.dev/learn',description='Учебный материал'))
        db.session.add(Schedule(hackathon_id=h.id,title='Разбор прототипа [демо]',starts_at=start+timedelta(days=2),url='https://react.dev/learn',speaker='Демо-эксперт'))
        db.session.flush()
        if status=='completed':publish_results(h)
    db.session.commit()
    refresh_demo_content()

# Only seed-owned rows are refreshed. User-created events, names and passwords stay intact.
SHOWCASE = [
    ('Campus Connect', 'Сервисы для студенческих сообществ: от поиска команды до совместных проектов.', 'Объединить студенческое сообщество', ['Линия связи', 'Соседи по коду']),
    ('Город рядом', 'Удобные городские маршруты, локальные события и доступные общественные пространства.', 'Городской маршрут без барьеров', ['Городские легенды', 'Точка на карте']),
    ('Зачётный сервис', 'Инструменты, которые помогают учиться, планировать нагрузку и готовиться к экзаменам.', 'Учебный план без перегрузки', ['После пары', 'Пятый семестр']),
    ('Зелёный код', 'Цифровые решения для осознанного потребления и повседневных экологичных привычек.', 'Сервис разумного потребления', ['Вторая жизнь', 'Лист и байт']),
    ('Финтех: первый шаг', 'Понятные личные финансы: бюджет, финансовые цели и безопасные платежи.', 'Первый личный бюджет', ['Баланс', 'Карманный план']),
    ('Зимний спринт', 'Полезные сервисы для зимнего кампуса, студенческих встреч и обмена вещами.', 'Зимний кампус', ['Тёплый старт', 'Снежный коммит']),
    ('Доступная среда', 'Интерфейсы и сервисы, которыми удобно пользоваться людям с разными возможностями.', 'Доступный цифровой сервис', ['Без границ', 'Равный доступ']),
]
DEMO_NAMES = ['Илья Соколов','Софья Крылова','Максим Лебедев','Алина Орлова',
              'Артём Кузнецов','Дарья Миронова','Никита Волков','Ева Смирнова',
              'Роман Беляев','Полина Зайцева','Кирилл Фомин','Вера Павлова']

def refresh_demo_content():
    events=[(i,Hackathon.query.filter_by(demo_key=f'showcase-{i}').first()) for i in range(len(SHOWCASE))]
    if not any(h for _,h in events):return
    participants=[]
    for i,name in enumerate(DEMO_NAMES):
        email=f'showcase.member.{i+1}@hackflow.test'
        u=User.query.filter_by(email=email).first()
        if not u:
            nickname=name;suffix=1
            while User.query.filter_by(nickname=nickname).first():
                nickname=f'{name} · {suffix}';suffix+=1
            u=User(email=email,nickname=nickname,role='participant',password_hash=generate_password_hash(secrets.token_urlsafe(32)))
            db.session.add(u);db.session.flush()
        participants.append(u)
    for i,h in events:
        if not h:continue
        title,description,case_title,names=SHOWCASE[i]
        if h.title==f'[Демо] Хакатон {i+1}':h.title=title
        if h.description=='Демонстрационное мероприятие: учебные команды и результаты.':h.description=description
        for case in Case.query.filter_by(hackathon_id=h.id,title='Студенческий сервис'):
            case.title=case_title;case.description=description
        teams=Team.query.filter_by(hackathon_id=h.id).order_by(Team.id).all()
        for j,t in enumerate(teams):
            if j>=len(names):break
            if t.name==f'Демо-команда {i}.{j}':t.name=names[j]
            for k,task in enumerate(Task.query.filter_by(team_id=t.id).order_by(Task.id)):
                if task.title==f'Демо-задача {k+1}' and k<4:
                    task.title=['Разобрать пользовательский сценарий','Собрать интерфейс прототипа','Проверить основные сценарии','Подготовить демонстрацию'][k]
            # Preserve published histories: new sample memberships are only for active/upcoming events.
            if h.status not in ('active','upcoming'):continue
            for offset in range(2):
                u=participants[(i*4+j*2+offset)%len(participants)]
                if u.blocked or u.role!='participant' or EventRole.query.filter_by(user_id=u.id).first():continue
                if Membership.query.filter_by(user_id=u.id,hackathon_id=h.id).first():continue
                if Message.query.filter_by(team_id=t.id,author_id=u.id).first():continue
                if Membership.query.filter_by(team_id=t.id).count()>=h.team_size:break
                if not Admission.query.filter_by(hackathon_id=h.id,email=u.email).first():db.session.add(Admission(hackathon_id=h.id,email=u.email))
                db.session.add(Membership(user_id=u.id,team_id=t.id,hackathon_id=h.id));db.session.flush()
                text=['Собрала заметки по сценарию, добавлю их в задачи.','Прототип готов к обсуждению. Посмотрим его на встрече?'][offset]
                db.session.add(Message(team_id=t.id,author_id=u.id,text=text))
    db.session.commit()
