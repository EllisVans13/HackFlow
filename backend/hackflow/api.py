import csv
import io
import json
import re
import secrets
import smtplib
import zipfile
from email.message import EmailMessage
from datetime import datetime, timedelta
from pathlib import Path
from flask import Blueprint, request, jsonify, abort, current_app, send_from_directory
from flask_login import current_user, login_user, logout_user, login_required
from flask_wtf.csrf import generate_csrf
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from sqlalchemy import func
from . import limiter
from .models import *
from .services import digest, safe_url, audit_submission, github_repo, ranking, publish_results, run_codecheck, source_archive

api=Blueprint('api',__name__)

def body():
    value=request.get_json(silent=True)
    if not isinstance(value,dict): abort(400,'Ожидается JSON-объект.')
    return value

def text(data,key,maximum=5000,required=True):
    value=data.get(key,'')
    if not isinstance(value,str): abort(400,'Некорректное поле: '+key)
    value=value.strip()
    if (required and not value) or len(value)>maximum: abort(400,'Проверьте поле: '+key)
    return value

def integer(value):
    try: return int(value)
    except (TypeError,ValueError): abort(400,'Ожидается целое число.')

def date(value):
    try:
        dt=datetime.fromisoformat(value.replace('Z','+00:00'))
        return dt.astimezone(__import__('datetime').timezone.utc).replace(tzinfo=None) if dt.tzinfo else dt
    except (AttributeError,TypeError,ValueError): abort(400,'Некорректная дата. Используйте ISO 8601 / UTC.')

def get(model,id): return db.get_or_404(model,id)

def serialize(obj,fields):
    return {key: getattr(obj,key).isoformat()+'Z' if isinstance(getattr(obj,key),datetime) else getattr(obj,key) for key in fields.split()}

def participant_account(u):
    return u.role=='participant' and not EventRole.query.filter(EventRole.user_id==u.id,EventRole.role.in_(['organizer','jury'])).first()

def require_participant(u=None):
    if not participant_account(u or current_user): abort(403,'Участие доступно только аккаунтам участников.')

def user_data(u):
    d=serialize(u,'id email nickname role is_owner github telegram avatar theme created_at blocked'); d['participant']=participant_account(u); return d

def event_role(hid,role): return EventRole.query.filter_by(user_id=current_user.id,hackathon_id=hid,role=role).first() is not None

def organizer(hid): return current_user.role=='admin' or event_role(hid,'organizer')

def require_organizer(hid):
    if not organizer(hid): abort(403,'Требуются права организатора этого хакатона.')

def require_admin():
    if current_user.role!='admin': abort(403,'Требуются права администратора.')

def admitted(h):
    if h.approval!='approved': return organizer(h.id)
    return organizer(h.id) or event_role(h.id,'jury') or Admission.query.filter_by(hackathon_id=h.id,email=current_user.email).first() is not None

def require_admission(h):
    if not admitted(h): abort(403,'Нет допуска к закрытому хакатону.')

def member_team(hid,uid=None):
    m=Membership.query.filter_by(hackathon_id=hid,user_id=uid or current_user.id).first()
    return db.session.get(Team,m.team_id) if m else None

def team_access(t,write=False):
    if write: require_participant()
    if participant_account(current_user) and Membership.query.filter_by(team_id=t.id,user_id=current_user.id).first(): return
    if not write and organizer(t.hackathon_id): return
    abort(403,'Нет доступа к пространству этой команды.')

def captain(t):
    require_participant()
    if t.captain_id!=current_user.id: abort(403,'Действие доступно капитану команды.')

def activity(action): db.session.add(Activity(user_id=current_user.id,action=action))

def audit(action,detail=None): db.session.add(AuditLog(actor_id=current_user.id,action=action,detail=detail or {}))

def notify(uid,title,message=''): db.session.add(Notification(user_id=uid,title=title,text=message))

def notify_team(t,title,message='',exclude=None):
    for m in Membership.query.filter_by(team_id=t.id):
        if m.user_id!=exclude: notify(m.user_id,title,message)

def notify_event(hid,title,message=''):
    emails=[a.email for a in Admission.query.filter_by(hackathon_id=hid)]
    for u in User.query.filter(User.email.in_(emails)).all(): notify(u.id,title,message)

def commit(): db.session.commit()

def add_member(t,u):
    require_participant(u)
    h=get(Hackathon,t.hackathon_id)
    if True and not Admission.query.filter_by(hackathon_id=h.id,email=u.email).first(): abort(403,'Участник не допущен.')
    if member_team(h.id,u.id): abort(409,'Участник уже состоит в команде этого хакатона.')
    if Membership.query.filter_by(team_id=t.id).count()>=h.team_size: abort(409,'Команда заполнена.')
    if now()>(h.team_deadline or h.registration_deadline): abort(403,'Приём участников завершён.')
    db.session.add(Membership(team_id=t.id,hackathon_id=h.id,user_id=u.id))
    notify(u.id,'Вы добавлены в команду',t.name)

def team_data(t):
    members=[]
    for m in Membership.query.filter_by(team_id=t.id):
        u=get(User,m.user_id); members.append({'id':u.id,'nickname':u.nickname,'captain':u.id==t.captain_id})
    tasks=Task.query.filter_by(team_id=t.id).all()
    data=serialize(t,'id hackathon_id name description captain_id case_id open created_at')
    data.update(members=members,tasks_total=len(tasks),tasks_done=sum(x.status=='done' for x in tasks),progress=round(100*sum(x.status=='done' for x in tasks)/len(tasks)) if tasks else 0)
    if t.captain_id==current_user.id or organizer(t.hackathon_id): data['code']=t.code
    return data

def h_data(h,full=False):
    d=serialize(h,'id title description cover difficulty approval review_comment start_at end_at registration_deadline team_deadline submission_deadline team_size closed status results_published peer_published tie_rule')
    if current_user.is_authenticated:
        d['admitted']=admitted(h); d['organizer']=organizer(h.id); d['jury']=event_role(h.id,'jury'); t=member_team(h.id); d['team_id']=t.id if t else None
    if full: d['rules']=h.rules
    return d

@api.get('/health')
def health():
    db.session.execute(db.text('SELECT 1'))
    return jsonify(status='ok',database=db.engine.dialect.name)

@api.get('/auth/csrf')
def csrf_token(): return jsonify(token=generate_csrf())

@api.get('/auth/me')
@login_required
def me(): return jsonify(user=user_data(current_user),roles=[serialize(r,'hackathon_id role') for r in EventRole.query.filter_by(user_id=current_user.id)])

@api.post('/auth/register')
@limiter.limit('8/hour')
def register():
    d=body(); email=text(d,'email',254).lower(); nick=text(d,'nickname',64); password=text(d,'password',200)
    if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email) or len(password)<10: abort(400,'Проверьте email. Пароль — минимум 10 символов.')
    if User.query.filter((User.email==email)|(User.nickname==nick)).first(): abort(409,'Email или никнейм уже используется.')
    u=User(email=email,nickname=nick,password_hash=generate_password_hash(password)); db.session.add(u); commit(); login_user(u)
    activity('registration'); commit(); return jsonify(user=user_data(u)),201

@api.post('/auth/login')
@limiter.limit('10/minute;60/hour')
def login():
    d=body(); email=text(d,'email',254).lower(); password=text(d,'password',200)
    u=User.query.filter_by(email=email).first()
    if not u or not check_password_hash(u.password_hash,password) or u.blocked: abort(403,'Неверные данные или аккаунт заблокирован.')
    login_user(u); return jsonify(user=user_data(u))

@api.post('/auth/logout')
@login_required
def logout(): logout_user(); return jsonify(ok=True)

@api.post('/auth/forgot')
@limiter.limit('3/hour')
def forgot():
    d=body(); email=text(d,'email',254).lower(); u=User.query.filter_by(email=email).first()
    if u and current_app.config['MAIL_SERVER']:
        token=secrets.token_urlsafe(32)
        db.session.add(PasswordReset(user_id=u.id,token_hash=digest(token),expires_at=now()+timedelta(hours=1)))
        msg=EmailMessage(); msg['Subject']='HackFlow — восстановление пароля'; msg['From']=current_app.config['MAIL_FROM']; msg['To']=u.email
        msg.set_content(current_app.config['PUBLIC_URL']+'/?reset='+token)
        try:
            with smtplib.SMTP(current_app.config['MAIL_SERVER'],current_app.config['MAIL_PORT'],timeout=10) as server:
                server.starttls()
                if current_app.config['MAIL_USER']: server.login(current_app.config['MAIL_USER'],current_app.config['MAIL_PASSWORD'])
                server.send_message(msg)
            commit()
        except (OSError,smtplib.SMTPException): db.session.rollback(); current_app.logger.warning('Ошибка отправки письма восстановления')
    return jsonify(message='Если аккаунт существует и почта настроена, ссылка отправлена. Иначе обратитесь к администратору.')

@api.post('/auth/reset')
@limiter.limit('10/hour')
def reset():
    d=body(); token=text(d,'token',200); password=text(d,'password',200)
    if len(password)<10: abort(400,'Пароль — минимум 10 символов.')
    r=PasswordReset.query.filter_by(token_hash=digest(token),used=False).with_for_update().first()
    if not r or r.expires_at<now(): abort(403,'Ссылка недействительна.')
    get(User,r.user_id).password_hash=generate_password_hash(password); r.used=True; commit(); return jsonify(ok=True)

@api.get('/hackathons')
def hackathons(): return jsonify(items=[h_data(h) for h in Hackathon.query.order_by(Hackathon.start_at.desc()) if h.approval=='approved' or (current_user.is_authenticated and organizer(h.id))])

@api.get('/hackathons/<int:hid>')
@login_required
def hackathon(hid):
    h=get(Hackathon,hid); require_admission(h)
    return jsonify(hackathon=h_data(h,True),cases=[serialize(c,'id title company description requirements expected url') for c in Case.query.filter_by(hackathon_id=hid)],criteria=[serialize(c,'id title maximum') for c in Criterion.query.filter_by(hackathon_id=hid)])

@api.post('/hackathons')
@login_required
def create_hackathon():
    if current_user.role not in ('organizer','admin'): abort(403,'Администратор должен назначить вас организатором.')
    d=body(); h=Hackathon(title=text(d,'title',200),description=text(d,'description'),rules=text(d,'rules',10000,False),start_at=date(d.get('start_at')),end_at=date(d.get('end_at')),registration_deadline=date(d.get('registration_deadline')),submission_deadline=date(d.get('submission_deadline')),team_size=integer(d.get('team_size',5)),closed=bool(d.get('closed',True)),status='upcoming')
    if not h.registration_deadline<=h.submission_deadline<=h.end_at or h.start_at>=h.end_at: abort(400,'Проверьте порядок сроков.')
    h.difficulty=d.get('difficulty','easy')
    if h.difficulty not in ['easy','medium','hard']:abort(400,'Выберите сложность.')
    h.approval='pending'
    h.team_deadline=date(d.get('team_deadline') or d.get('registration_deadline'))
    if not h.registration_deadline<=h.team_deadline<=h.submission_deadline: abort(400,'Проверьте сроки регистрации, команд и сдачи.')
    db.session.add(h); db.session.flush(); db.session.add(EventRole(user_id=current_user.id,hackathon_id=h.id,role='organizer'))
    for title,maximum in [('Функциональность',30),('Оригинальность',20),('Техническая реализация',20),('Дизайн и удобство',15),('Презентация и защита',15)]: db.session.add(Criterion(hackathon_id=h.id,title=title,maximum=maximum))
    audit('hackathon.create',{'id':h.id}); commit(); return jsonify(hackathon=h_data(h,True)),201

@api.patch('/hackathons/<int:hid>')
@login_required
def edit_hackathon(hid):
    h=get(Hackathon,hid); require_organizer(hid); d=body()
    if 'difficulty' in d or 'approval' in d:abort(403,'Сложность и одобрение назначает администратор.')
    for field in ['title','description','rules']:
        if field in d: setattr(h,field,text(d,field,10000))
    for field in ['start_at','end_at','registration_deadline','team_deadline','submission_deadline']:
        if field in d and d[field]: setattr(h,field,date(d[field]))
    if not h.registration_deadline <= (h.team_deadline or h.registration_deadline) <= h.submission_deadline <= h.end_at or h.start_at>=h.end_at: abort(400,'Проверьте порядок дат.')
    if 'status' in d:
        if d['status'] not in ['upcoming','active','review','completed']: abort(400,'Некорректный статус.')
        h.status=d['status']
    audit('hackathon.update',{'id':hid}); notify_event(hid,'Информация о хакатоне обновлена'); commit(); return jsonify(hackathon=h_data(h,True))

@api.post('/hackathons/<int:hid>/admissions')
@login_required
def admissions(hid):
    get(Hackathon,hid); require_organizer(hid)
    if 'file' in request.files:
        try: rows=list(csv.DictReader(io.StringIO(request.files['file'].read().decode('utf-8-sig'))))
        except (UnicodeDecodeError,csv.Error): abort(400,'Нужен CSV UTF-8 со столбцом email.')
        if len(rows)>1000: abort(400,'Максимум 1000 строк за импорт.')
        emails=[str(r.get('email','')).strip().lower() for r in rows]
    else: emails=[text(body(),'email',254).lower()]
    count=0
    for email in set(emails):
        if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email): abort(400,'Некорректный email в списке.')
        if not Admission.query.filter_by(hackathon_id=hid,email=email).first(): db.session.add(Admission(hackathon_id=hid,email=email)); count+=1
    audit('admission.import',{'hackathon':hid,'count':count}); commit(); return jsonify(added=count)

@api.get('/hackathons/<int:hid>/teams')
@login_required
def teams(hid):
    require_admission(get(Hackathon,hid)); return jsonify(items=[team_data(t) for t in Team.query.filter_by(hackathon_id=hid)])

@api.post('/hackathons/<int:hid>/teams')
@login_required
def create_team(hid):
    require_participant()
    h=get(Hackathon,hid); require_admission(h); d=body()
    if now()>(h.team_deadline or h.registration_deadline): abort(403,'Регистрация команд завершена.')
    uid=integer(d.get('captain_id',current_user.id))
    if uid!=current_user.id: abort(403,'Создайте команду от своего имени.')
    u=get(User,uid)
    # Lock participant to serialize team membership/capacity mutations.
    db.session.execute(db.select(User).where(User.id==uid).with_for_update())
    if member_team(hid,uid): abort(409,'Участник уже состоит в команде.')
    t=Team(hackathon_id=hid,captain_id=uid,name=text(d,'name',100),description=text(d,'description',3000,False),code=secrets.token_urlsafe(9))
    db.session.add(t); db.session.flush(); add_member(t,u); activity('team.create'); commit(); return jsonify(team=team_data(t)),201

@api.post('/hackathons/<int:hid>/join')
@login_required
def join_code(hid):
    require_participant()
    require_admission(get(Hackathon,hid)); d=body()
    t=Team.query.filter_by(hackathon_id=hid,code=text(d,'code',32)).with_for_update().first()
    if not t: abort(404,'Команда с таким кодом не найдена.')
    add_member(t,current_user); activity('team.join'); commit(); return jsonify(team=team_data(t))

@api.get('/teams/<int:tid>')
@login_required
def team_detail(tid):
    t=get(Team,tid); team_access(t)
    requests_=[]
    if t.captain_id==current_user.id or organizer(t.hackathon_id):
        requests_=[{'id':r.id,'nickname':get(User,r.user_id).nickname,'status':r.status} for r in JoinRequest.query.filter_by(team_id=tid,status='pending')]
    s=Submission.query.filter_by(team_id=tid).first()
    return jsonify(team=team_data(t),requests=requests_,submission=serialize(s,'id code title description github demo presentation_id submitted_at anonymous_ready') if s else None)

@api.delete('/teams/<int:tid>')
@login_required
def delete_team(tid):
    t=get(Team,tid)
    if not organizer(t.hackathon_id): captain(t)
    if now()>=get(Hackathon,t.hackathon_id).start_at: abort(403,'После начала хакатона удаление команды запрещено.')
    Membership.query.filter_by(team_id=tid).delete(); JoinRequest.query.filter_by(team_id=tid).delete(); Task.query.filter_by(team_id=tid).delete(); Message.query.filter_by(team_id=tid).delete()
    db.session.delete(t); activity('team.delete'); commit(); return jsonify(ok=True)

@api.post('/teams/<int:tid>/requests')
@login_required
def request_join(tid):
    require_participant()
    t=get(Team,tid); h=get(Hackathon,t.hackathon_id); require_admission(h)
    if not t.open or now()>(h.team_deadline or h.registration_deadline): abort(403,'Команда не принимает заявки.')
    if member_team(h.id): abort(409,'Вы уже состоите в команде.')
    db.session.add(JoinRequest(team_id=tid,user_id=current_user.id)); notify(t.captain_id,'Новая заявка в команду',current_user.nickname); commit(); return jsonify(ok=True),201

@api.patch('/teams/<int:tid>/requests/<int:rid>')
@login_required
def decide_join(tid,rid):
    t=Team.query.filter_by(id=tid).with_for_update().first_or_404(); captain(t); r=get(JoinRequest,rid); d=body()
    if r.team_id!=tid or r.status!='pending': abort(409,'Заявка недоступна.')
    if d.get('accept'): add_member(t,get(User,r.user_id)); r.status='accepted'
    else: r.status='rejected'
    commit(); return jsonify(ok=True)

@api.patch('/teams/<int:tid>')
@login_required
def edit_team(tid):
    t=get(Team,tid)
    if not organizer(t.hackathon_id): captain(t)
    d=body()
    if 'case_id' in d:
        c=get(Case,integer(d['case_id']))
        if c.hackathon_id!=t.hackathon_id: abort(400,'Кейс другого хакатона.')
        if Submission.query.filter_by(team_id=tid).first(): abort(403,'Проект уже отправлен.')
        t.case_id=c.id
    if 'captain_id' in d:
        uid=integer(d['captain_id'])
        if not Membership.query.filter_by(team_id=tid,user_id=uid).first(): abort(400,'Капитан должен состоять в команде.')
        t.captain_id=uid
    if 'open' in d: t.open=bool(d['open'])
    activity('team.update'); commit(); return jsonify(team=team_data(t))

@api.route('/teams/<int:tid>/tasks',methods=['GET','POST'])
@login_required
def tasks(tid):
    t=get(Team,tid); team_access(t,request.method=='POST')
    if request.method=='POST':
        d=body(); assignee=integer(d.get('assignee_id') or current_user.id)
        if not Membership.query.filter_by(team_id=tid,user_id=assignee).first(): abort(400,'Ответственный должен состоять в команде.')
        task=Task(team_id=tid,creator_id=current_user.id,assignee_id=assignee,title=text(d,'title',200),description=text(d,'description',5000,False),deadline=date(d['deadline']) if d.get('deadline') else None)
        db.session.add(task); activity('task.create'); commit()
    return jsonify(items=[serialize(task,'id team_id creator_id assignee_id title description status deadline created_at') for task in Task.query.filter_by(team_id=tid).order_by(Task.id)])

@api.route('/tasks/<int:taskid>',methods=['PATCH','DELETE'])
@login_required
def edit_task(taskid):
    task=get(Task,taskid); t=get(Team,task.team_id); team_access(t,True)
    if current_user.id not in (task.creator_id,task.assignee_id,t.captain_id): abort(403,'Редактировать задачу может автор, ответственный или капитан.')
    if request.method=='DELETE': db.session.delete(task)
    else:
        d=body()
        if 'status' in d:
            if d['status'] not in ('todo','doing','review','done'): abort(400,'Неизвестный статус.')
            task.status=d['status']
        for key in ['title','description']:
            if key in d: setattr(task,key,text(d,key,5000, key=='title'))
        if 'assignee_id' in d:
            uid=integer(d['assignee_id'])
            if not Membership.query.filter_by(team_id=t.id,user_id=uid).first(): abort(400,'Ответственный не в команде.')
            task.assignee_id=uid
        if 'deadline' in d: task.deadline=date(d['deadline']) if d['deadline'] else None
    activity('task.update'); commit(); return jsonify(ok=True)

@api.route('/teams/<int:tid>/messages',methods=['GET','POST'])
@login_required
def messages(tid):
    t=get(Team,tid); channel=request.args.get('channel','team')
    if channel not in ['team','organizer']: abort(400,'Неизвестный канал.')
    if channel=='organizer':
        if current_user.id!=t.captain_id and not organizer(t.hackathon_id): abort(403,'Переписка доступна только капитану и организатору.')
    else: team_access(t,True)
    if request.method=='POST':
        message=Message(team_id=tid,author_id=current_user.id,channel=channel,text=text(body(),'text',4000)); db.session.add(message)
        if channel=='team': notify_team(t,'Новое сообщение',current_user.nickname,exclude=current_user.id)
        elif current_user.id!=t.captain_id: notify(t.captain_id,'Сообщение организатора')
        else:
            for r in EventRole.query.filter_by(hackathon_id=t.hackathon_id,role='organizer'): notify(r.user_id,'Сообщение капитана',t.name)
        activity('message.send'); commit()
    after=integer(request.args.get('after',0))
    rows=Message.query.filter(Message.team_id==tid,Message.channel==channel,Message.id>after).order_by(Message.id.desc()).limit(100).all()[::-1]
    return jsonify(items=[dict(serialize(m,'id author_id text created_at read_at'),author=get(User,m.author_id).nickname,avatar=get(User,m.author_id).avatar) for m in rows])

@api.post('/teams/<int:tid>/messages/read')
@login_required
def messages_read(tid):
    t=get(Team,tid)
    if current_user.id!=t.captain_id and not organizer(t.hackathon_id): abort(403,'Нет доступа.')
    Message.query.filter(Message.team_id==tid,Message.channel=='organizer',Message.author_id!=current_user.id,Message.read_at.is_(None)).update({'read_at':now()})
    commit(); return jsonify(ok=True)

@api.get('/hackathons/<int:hid>/materials')
@login_required
def materials(hid):
    require_admission(get(Hackathon,hid)); done={p.material_id for p in LearningProgress.query.filter_by(user_id=current_user.id)}
    return jsonify(items=[dict(serialize(m,'id title topic kind description url'),completed=m.id in done) for m in Material.query.filter_by(hackathon_id=hid)])

@api.post('/materials/<int:mid>/complete')
@login_required
def complete_material(mid):
    m=get(Material,mid); require_admission(get(Hackathon,m.hackathon_id))
    p=LearningProgress.query.filter_by(user_id=current_user.id,material_id=mid).first()
    if not p: db.session.add(LearningProgress(user_id=current_user.id,material_id=mid)); activity('material.complete')
    commit(); return jsonify(ok=True)

@api.get('/hackathons/<int:hid>/schedule')
@login_required
def schedule(hid):
    require_admission(get(Hackathon,hid)); return jsonify(items=[serialize(s,'id title description starts_at speaker kind url') for s in Schedule.query.filter_by(hackathon_id=hid).order_by(Schedule.starts_at)])

@api.post('/hackathons/<int:hid>/<string:kind>')
@login_required
def create_content(hid,kind):
    require_organizer(hid); get(Hackathon,hid); d=body()
    if kind=='cases':
        obj=Case(hackathon_id=hid,title=text(d,'title',200),company=text(d,'company',150),description=text(d,'description'),requirements=text(d,'requirements',10000,False),expected=text(d,'expected',5000,False),url=safe_url(text(d,'url',500,False)))
    elif kind=='materials':
        obj=Material(hackathon_id=hid,title=text(d,'title',200),topic=text(d,'topic',100,False) or 'Разработка',description=text(d,'description',5000,False),kind=text(d,'kind',40,False) or 'document',url=safe_url(text(d,'url',500)))
    elif kind=='schedule':
        obj=Schedule(hackathon_id=hid,title=text(d,'title',200),description=text(d,'description',5000,False),starts_at=date(d.get('starts_at')),speaker=text(d,'speaker',200,False),url=safe_url(text(d,'url',500,False)),kind=text(d,'kind',40,False) or 'webinar')
    elif kind=='announcements':
        notify_event(hid,text(d,'title',200),text(d,'description',5000)); audit('announcement.create',{'hackathon':hid}); commit(); return jsonify(ok=True),201
    else: abort(404,'Раздел не найден.')
    db.session.add(obj); notify_event(hid,'Новый материал: '+obj.title if kind=='materials' else 'Обновление: '+obj.title); audit(kind+'.create',{'hackathon':hid}); commit(); return jsonify(id=obj.id),201

@api.route('/schedule/<int:sid>',methods=['PATCH','DELETE'])
@login_required
def edit_schedule(sid):
    s=get(Schedule,sid); require_organizer(s.hackathon_id)
    if request.method=='DELETE': db.session.delete(s)
    else:
        d=body()
        for key in ['title','description','speaker','kind']:
            if key in d: setattr(s,key,text(d,key,5000,key=='title'))
        if 'starts_at' in d: s.starts_at=date(d['starts_at'])
        if 'url' in d: s.url=safe_url(text(d,'url',500,False))
    notify_event(s.hackathon_id,'Расписание изменено',s.title); audit('schedule.update',{'id':sid}); commit(); return jsonify(ok=True)

@api.post('/teams/<int:tid>/uploads')
@login_required
def upload(tid):
    t=get(Team,tid); team_access(t,True); captain(t)
    if Submission.query.filter_by(team_id=tid).first() or now()>get(Hackathon,t.hackathon_id).submission_deadline: abort(403,'Материалы итогового решения зафиксированы или дедлайн истёк.')
    file=request.files.get('file'); purpose=request.form.get('purpose','presentation')
    if not file or purpose not in ['presentation','source']: abort(400,'Выберите PDF-презентацию или ZIP исходников.')
    data=file.read(); ext='.pdf' if purpose=='presentation' else '.zip'
    if not file.filename.lower().endswith(ext): abort(400,'Неверное расширение файла.')
    if purpose=='presentation' and not data.startswith(b'%PDF-'): abort(400,'Файл не является PDF.')
    filename=secrets.token_hex(24)+ext; path=Path(current_app.config['UPLOAD_FOLDER'])/filename
    path.write_bytes(data)
    if purpose=='source':
        try: source_archive(path)
        except (zipfile.BadZipFile,RuntimeError,ValueError): path.unlink(missing_ok=True); abort(400,'Некорректный ZIP-архив.')
    obj=Upload(team_id=tid,owner_id=current_user.id,storage_name=filename,filename=secure_filename(file.filename) or 'presentation.pdf',size=len(data),purpose=purpose)
    db.session.add(obj); commit(); return jsonify(id=obj.id,filename=obj.filename),201

@api.get('/uploads/<int:uid>')
@login_required
def download(uid):
    f=get(Upload,uid); t=get(Team,f.team_id)
    assigned=ConsultationAssignment.query.filter_by(team_id=t.id,user_id=current_user.id).first()
    s=Submission.query.filter_by(team_id=t.id).first()
    expert=bool(s and ReviewAssignment.query.filter_by(submission_id=s.id,user_id=current_user.id,kind='expert').first())
    if not assigned and not expert: team_access(t)
    return send_from_directory(current_app.config['UPLOAD_FOLDER'],f.storage_name,as_attachment=True,download_name=f.filename)

@api.post('/teams/<int:tid>/audit')
@login_required
def submission_audit(tid):
    t=get(Team,tid); team_access(t,True); captain(t)
    return jsonify(checks=audit_submission(body(),t))

@api.post('/teams/<int:tid>/submission')
@login_required
def submit(tid):
    t=Team.query.filter_by(id=tid).with_for_update().first_or_404(); team_access(t,True); captain(t); d=body()
    if Submission.query.filter_by(team_id=tid).first(): abort(409,'Итоговое решение уже отправлено. MVP поддерживает одну отправку.')
    checks=audit_submission(d,t,external=False)
    if any(c['status']=='error' for c in checks): return jsonify(error='Исправьте ошибки перед сдачей.',checks=checks),400
    s=Submission(team_id=tid,code=secrets.token_hex(3).upper(),title=text(d,'title',200),description=text(d,'description',15000),github=safe_url(text(d,'github',500),github=True),demo=safe_url(text(d,'demo',500)),presentation_id=integer(d.get('presentation_id')))
    source=Upload.query.filter_by(team_id=tid,purpose='source').order_by(Upload.id.desc()).first()
    s.source_id=source.id if source else None
    db.session.add(s); db.session.flush(); notify_team(t,'Проект отправлен',s.title)
    for r in EventRole.query.filter_by(hackathon_id=t.hackathon_id,role='organizer'): notify(r.user_id,'Новый проект',t.name)
    activity('submission.send'); commit(); return jsonify(id=s.id,code=s.code,submitted_at=s.submitted_at.isoformat()+'Z'),201

@api.get('/hackathons/<int:hid>/submissions')
@login_required
def submissions(hid):
    require_organizer(hid)
    rows=[]
    for s in Submission.query.join(Team,Submission.team_id==Team.id).filter(Team.hackathon_id==hid):
        rows.append(dict(serialize(s,'id code title description github demo presentation_id submitted_at anonymous_ready anonymous_text flagged'),team=get(Team,s.team_id).name,team_id=s.team_id))
    return jsonify(items=rows)

@api.patch('/submissions/<int:sid>/anonymous')
@login_required
def anonymize(sid):
    s=get(Submission,sid); require_organizer(get(Team,s.team_id).hackathon_id); d=body()
    if d.get('confirmed') is not True: abort(400,'Подтвердите ручную проверку обезличивания.')
    content=text(d,'text',30000)
    if re.search(r'https?://|github\.com|@',content,re.I): abort(400,'В обезличенной версии запрещены ссылки и email. Вставьте проверенные материалы текстом.')
    s.anonymous_text=content; s.anonymous_ready=True; audit('submission.anonymize',{'id':sid}); commit(); return jsonify(ok=True)

@api.post('/hackathons/<int:hid>/jury-invitations')
@login_required
def invite_jury(hid):
    require_organizer(hid); get(Hackathon,hid); email=text(body(),'email',254).lower()
    if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email): abort(400,'Некорректный email.')
    token=secrets.token_urlsafe(32); invite=Invitation(hackathon_id=hid,email=email,token_hash=digest(token),expires_at=now()+timedelta(days=3)); db.session.add(invite); audit('jury.invite',{'hackathon':hid,'email':email}); commit()
    return jsonify(id=invite.id,link=current_app.config['PUBLIC_URL']+'/?invite='+token,expires_at=invite.expires_at.isoformat()+'Z',message='Передайте одноразовую ссылку приглашённому эксперту.'),201

@api.delete('/jury-invitations/<int:iid>')
@login_required
def revoke_invite(iid):
    i=get(Invitation,iid); require_organizer(i.hackathon_id); i.revoked=True; audit('jury.revoke',{'id':iid}); commit(); return jsonify(ok=True)

@api.post('/jury-invitations/accept')
@login_required
def accept_invite():
    i=Invitation.query.filter_by(token_hash=digest(text(body(),'token',200))).with_for_update().first()
    if not i or i.used or i.revoked or i.expires_at<now() or i.email!=current_user.email: abort(403,'Приглашение недействительно или вы вошли с другим email.')
    if member_team(i.hackathon_id): abort(403,'Участник команды не может быть жюри того же хакатона.')
    if not event_role(i.hackathon_id,'jury'): db.session.add(EventRole(user_id=current_user.id,hackathon_id=i.hackathon_id,role='jury'))
    i.used=True; commit(); return jsonify(hackathon_id=i.hackathon_id)

@api.post('/submissions/<int:sid>/assign')
@login_required
def assign(sid):
    s=get(Submission,sid); hid=get(Team,s.team_id).hackathon_id; require_organizer(hid); d=body(); uid=integer(d.get('user_id')); get(User,uid); kind=d.get('kind','jury')
    if kind not in ['jury','expert']: abort(400,'Некорректная роль.')
    if member_team(hid,uid): abort(403,'Конфликт интересов: участник этого хакатона.')
    if kind=='jury' and not EventRole.query.filter_by(user_id=uid,hackathon_id=hid,role='jury').first(): abort(403,'Пользователь не принял приглашение жюри.')
    if kind=='jury' and (ConsultationAssignment.query.filter_by(team_id=s.team_id,user_id=uid).first() or ReviewAssignment.query.filter_by(user_id=uid,submission_id=sid,kind='expert').first()): abort(403,'Эксперт, знающий авторов, не может анонимно оценивать их проект.')
    if kind=='expert' and ReviewAssignment.query.filter_by(user_id=uid,submission_id=sid,kind='jury').first(): abort(403,'Жюри уже назначено на анонимное оценивание.')
    db.session.add(ReviewAssignment(user_id=uid,submission_id=sid,kind=kind)); notify(uid,'Вам назначен проект для проверки',s.code); audit('review.assign',{'id':sid,'user':uid,'kind':kind}); commit(); return jsonify(ok=True)

@api.get('/hackathons/<int:hid>/jury')
@login_required
def jury_list(hid):
    get(Hackathon,hid)
    if not event_role(hid,'jury'): abort(403,'Вы не входите в жюри этого мероприятия.')
    result=[]
    for a in ReviewAssignment.query.filter_by(user_id=current_user.id,kind='jury'):
        s=get(Submission,a.submission_id)
        if get(Team,s.team_id).hackathon_id!=hid or not s.anonymous_ready: continue
        score=JuryScore.query.filter_by(submission_id=s.id,user_id=current_user.id).first()
        result.append({'id':s.id,'code':s.code,'scored':score is not None})
    return jsonify(items=result)

def require_jury_submission(s):
    hid=get(Team,s.team_id).hackathon_id
    if not event_role(hid,'jury') or not ReviewAssignment.query.filter_by(user_id=current_user.id,submission_id=s.id,kind='jury').first() or not s.anonymous_ready: abort(403,'Анонимная работа вам не назначена.')
    return hid

@api.get('/jury/<int:sid>')
@login_required
def jury_project(sid):
    s=get(Submission,sid); hid=require_jury_submission(s); score=JuryScore.query.filter_by(submission_id=sid,user_id=current_user.id).first(); report=CodeReport.query.filter_by(submission_id=sid).first()
    # Explicit allowlist. No team identifiers, original URLs or filenames.
    return jsonify(project={'id':s.id,'code':s.code,'text':s.anonymous_text},criteria=[serialize(c,'id title maximum') for c in Criterion.query.filter_by(hackathon_id=hid)],score=serialize(score,'scores total comment') if score else None,codecheck={'status':report.status,'report':report.report} if report else {'status':'not_started'})

def validate_scores(d,hid):
    scores=d.get('scores'); criteria=Criterion.query.filter_by(hackathon_id=hid).all()
    if not isinstance(scores,dict) or set(scores)!={str(c.id) for c in criteria}: abort(400,'Заполните все критерии.')
    for c in criteria:
        value=scores[str(c.id)]
        if isinstance(value,bool) or not isinstance(value,(int,float)) or not 0<=value<=c.maximum: abort(400,'Баллы вне диапазона: '+c.title)
    comment=text(d,'comment',5000); return scores,sum(scores.values()),comment

@api.post('/jury/<int:sid>/score')
@login_required
def jury_score(sid):
    s=get(Submission,sid); hid=require_jury_submission(s); h=get(Hackathon,hid)
    if h.results_published: abort(403,'Результаты опубликованы. Изменение оценки возможно через организатора с указанием причины.')
    d=body(); scores,total,comment=validate_scores(d,hid); old=JuryScore.query.filter_by(submission_id=sid,user_id=current_user.id).first()
    before=serialize(old,'scores total comment') if old else None
    if not old: old=JuryScore(submission_id=sid,user_id=current_user.id); db.session.add(old)
    old.scores=scores; old.total=total; old.comment=comment; old.updated_at=now()
    db.session.add(ScoreHistory(submission_id=sid,actor_id=current_user.id,before=before,after={'scores':scores,'total':total,'comment':comment},reason=text(d,'reason',5000,False) or 'Оценивание жюри'))
    activity('jury.score'); commit(); return jsonify(total=total)

@api.post('/jury/<int:sid>/flag')
@login_required
def flag_project(sid):
    s=get(Submission,sid); hid=require_jury_submission(s); s.flagged=True
    for r in EventRole.query.filter_by(hackathon_id=hid,role='organizer'): notify(r.user_id,'Требуется дополнительная проверка',s.code)
    audit('submission.flag',{'id':sid}); commit(); return jsonify(ok=True)

@api.post('/submissions/<int:sid>/codecheck')
@login_required
def codecheck(sid):
    s=get(Submission,sid); hid=get(Team,s.team_id).hackathon_id; require_organizer(hid)
    r=run_codecheck(s,current_app.config['UPLOAD_FOLDER']); audit('codecheck.run',{'id':sid}); notify_team(get(Team,s.team_id),'CodeCheck завершён',r.status); commit(); return jsonify(status=r.status,report=r.report)

@api.get('/submissions/<int:sid>/codecheck')
@login_required
def codecheck_report(sid):
    s=get(Submission,sid); t=get(Team,s.team_id)
    if event_role(t.hackathon_id,'jury'): require_jury_submission(s)
    else: team_access(t)
    r=CodeReport.query.filter_by(submission_id=sid).first(); ai=AIReport.query.filter_by(submission_id=sid).first()
    return jsonify(status=r.status if r else 'not_started',report=r.report if r else {},ai=ai.observations if ai else None)

@api.get('/hackathons/<int:hid>/experts')
@login_required
def experts(hid):
    require_admission(get(Hackathon,hid)); rows=[]
    for a in ReviewAssignment.query.filter_by(kind='expert'):
        s=get(Submission,a.submission_id)
        if get(Team,s.team_id).hackathon_id==hid: rows.append({'nickname':get(User,a.user_id).nickname})
    return jsonify(items=rows)

@api.route('/submissions/<int:sid>/feedback',methods=['GET','POST'])
@login_required
def feedback(sid):
    s=get(Submission,sid); t=get(Team,s.team_id); expert=ReviewAssignment.query.filter_by(submission_id=sid,user_id=current_user.id,kind='expert').first()
    if not expert: team_access(t)
    if request.method=='POST':
        if not expert and not organizer(t.hackathon_id): abort(403,'Вы не назначены экспертом.')
        db.session.add(ExpertComment(submission_id=sid,author_id=current_user.id,text=text(body(),'text',5000))); notify_team(t,'Новая экспертная обратная связь'); commit()
    return jsonify(items=[dict(serialize(c,'id text created_at'),author=get(User,c.author_id).nickname) for c in ExpertComment.query.filter_by(submission_id=sid)])

@api.get('/expert/assignments')
@login_required
def expert_assignments():
    return jsonify(items=[dict(serialize(get(Submission,a.submission_id),'id title description github demo presentation_id'),code=get(Submission,a.submission_id).code) for a in ReviewAssignment.query.filter_by(user_id=current_user.id,kind='expert')])

@api.put('/hackathons/<int:hid>/criteria')
@login_required
def criteria_update(hid):
    require_organizer(hid); get(Hackathon,hid); d=body(); items=d.get('items')
    if not isinstance(items,list) or not items or len(items)>20: abort(400,'Нужен список критериев.')
    if Submission.query.join(Team,Submission.team_id==Team.id).filter(Team.hackathon_id==hid).first(): abort(403,'Критерии фиксируются после первой сдачи.')
    values=[(text(i,'title',200),integer(i.get('maximum'))) for i in items]
    if sum(m for _,m in values)!=100 or any(m<=0 for _,m in values): abort(400,'Сумма максимумов должна равняться 100.')
    Criterion.query.filter_by(hackathon_id=hid).delete()
    for title,maximum in values: db.session.add(Criterion(hackathon_id=hid,title=title,maximum=maximum))
    audit('criteria.update',{'hackathon':hid}); commit(); return jsonify(ok=True)

@api.get('/hackathons/<int:hid>/ranking')
def team_ranking(hid):
    h=get(Hackathon,hid)
    if not h.results_published and not (current_user.is_authenticated and organizer(hid)): return jsonify(published=False,items=[],tie_rule=h.tie_rule)
    return jsonify(published=h.results_published,items=ranking(h),tie_rule=h.tie_rule)

@api.post('/hackathons/<int:hid>/publish')
@login_required
def publish(hid):
    h=get(Hackathon,hid); require_organizer(hid)
    projects=Submission.query.join(Team,Submission.team_id==Team.id).filter(Team.hackathon_id==hid).all()
    if not projects: abort(400,'Нет отправленных проектов.')
    for s in projects:
        assignments=ReviewAssignment.query.filter_by(submission_id=s.id,kind='jury').all()
        if not assignments or any(not JuryScore.query.filter_by(submission_id=s.id,user_id=a.user_id).first() for a in assignments): abort(409,'Не все назначенные проверки завершены.')
    publish_results(h); notify_event(hid,'Результаты опубликованы',h.title); audit('results.publish',{'hackathon':hid}); commit(); return jsonify(items=ranking(h))

@api.route('/hackathons/<int:hid>/peer',methods=['GET','POST'])
@login_required
def peer(hid):
    h=get(Hackathon,hid); require_admission(h); t=member_team(hid)
    if request.method=='POST':
        require_organizer(hid); d=body(); target=get(Submission,integer(d.get('submission_id'))); team=get(Team,integer(d.get('team_id')))
        if get(Team,target.team_id).hackathon_id!=hid or team.hackathon_id!=hid or target.team_id==team.id: abort(400,'Нельзя назначить собственный проект или проект другого события.')
        if not target.anonymous_ready: abort(400,'Сначала подготовьте обезличенные материалы.')
        db.session.add(PeerAssignment(team_id=team.id,submission_id=target.id)); commit(); return jsonify(ok=True)
    rows=[]
    if t:
        for a in PeerAssignment.query.filter_by(team_id=t.id):
            s=get(Submission,a.submission_id); review=PeerReview.query.filter_by(team_id=t.id,submission_id=s.id).first()
            rows.append({'id':s.id,'code':s.code,'text':s.anonymous_text,'reviewed':review is not None})
    votes=[]
    if h.peer_published or organizer(hid):
        for sid,avg in db.session.query(PeerReview.submission_id,func.avg(PeerReview.total)).join(Submission,PeerReview.submission_id==Submission.id).join(Team,Submission.team_id==Team.id).filter(Team.hackathon_id==hid).group_by(PeerReview.submission_id).all(): votes.append({'code':get(Submission,sid).code,'score':round(avg,2)})
        votes.sort(key=lambda v:-v['score'])
    return jsonify(items=rows,published=h.peer_published,results=votes)

@api.post('/peer/<int:sid>')
@login_required
def peer_review(sid):
    s=get(Submission,sid); hid=get(Team,s.team_id).hackathon_id; h=get(Hackathon,hid); t=member_team(hid)
    if not t: abort(403,'Сначала вступите в команду.')
    captain(t)
    if s.team_id==t.id or not PeerAssignment.query.filter_by(team_id=t.id,submission_id=sid).first() or h.peer_published: abort(403,'Отзыв недоступен.')
    scores,total,comment=validate_scores(body(),hid)
    db.session.add(PeerReview(team_id=t.id,submission_id=sid,scores=scores,total=total,comment=comment)); activity('peer.review'); commit(); return jsonify(ok=True),201

@api.post('/hackathons/<int:hid>/peer/publish')
@login_required
def peer_publish(hid):
    h=get(Hackathon,hid); require_organizer(hid); h.peer_published=True; audit('peer.publish',{'hackathon':hid}); commit(); return jsonify(ok=True)

@api.route('/hackathons/<int:hid>/appeals',methods=['GET','POST'])
@login_required
def appeals(hid):
    h=get(Hackathon,hid); require_admission(h); t=member_team(hid)
    if request.method=='POST':
        if not h.results_published or not t: abort(403,'Апелляции принимаются после публикации результатов.')
        captain(t); s=Submission.query.filter_by(team_id=t.id).first()
        if not s: abort(400,'Нет проекта.')
        d=body(); db.session.add(Appeal(submission_id=s.id,reason=text(d,'reason',3000),explanation=text(d,'explanation',10000),materials=safe_url(text(d,'materials',500,False)))); activity('appeal.send'); commit()
    rows=Appeal.query.join(Submission,Appeal.submission_id==Submission.id).join(Team,Submission.team_id==Team.id).filter(Team.hackathon_id==hid)
    if not organizer(hid): rows=rows.filter(Team.id==t.id) if t else rows.filter(db.false())
    return jsonify(items=[serialize(a,'id submission_id reason explanation materials status response created_at') for a in rows])

@api.patch('/appeals/<int:aid>')
@login_required
def appeal_decision(aid):
    a=get(Appeal,aid); s=get(Submission,a.submission_id); hid=get(Team,s.team_id).hackathon_id; require_organizer(hid); d=body()
    if d.get('status') not in ['review','clarification','accepted','rejected']: abort(400,'Неизвестный статус.')
    a.status=d['status']; a.response=text(d,'response',10000)
    if 'scores' in d:
        if a.status!='accepted': abort(400,'Изменение оценки доступно только при принятой апелляции.')
        uid=integer(d.get('jury_id')); score=JuryScore.query.filter_by(submission_id=s.id,user_id=uid).first()
        if not score: abort(400,'Оценка указанного эксперта не найдена.')
        scores,total,comment=validate_scores(d,hid)
        db.session.add(ScoreHistory(submission_id=s.id,actor_id=current_user.id,before=serialize(score,'scores total comment'),after={'scores':scores,'total':total,'comment':comment},reason=a.response))
        score.scores=scores; score.total=total; score.comment=comment; db.session.flush(); publish_results(get(Hackathon,hid))
    notify_team(get(Team,s.team_id),'Решение по апелляции',a.response); audit('appeal.decide',{'id':aid,'status':a.status}); commit(); return jsonify(ok=True)

@api.get('/notifications')
@login_required
def notifications(): return jsonify(items=[serialize(n,'id title text read created_at') for n in Notification.query.filter_by(user_id=current_user.id).order_by(Notification.id.desc()).limit(100)])

@api.post('/notifications/read')
@login_required
def read_notifications(): Notification.query.filter_by(user_id=current_user.id,read=False).update({'read':True}); commit(); return jsonify(ok=True)

@api.get('/profile')
@login_required
def profile():
    if not participant_account(current_user): return jsonify(user=user_data(current_user),staff=True,history=[],events=[])
    results=PersonalResult.query.filter_by(user_id=current_user.id).all()
    activities=Activity.query.filter(Activity.user_id==current_user.id,Activity.created_at>=now()-timedelta(days=365)).all(); counts={}
    for a in activities:
        key=a.created_at.date().isoformat(); counts[key]=counts.get(key,0)+1
    history=[dict(serialize(r,'hackathon_id team_name case_title score place'),title=get(Hackathon,r.hackathon_id).title) for r in results]
    return jsonify(level=experience(current_user.id),user=user_data(current_user),rating=round(sum(r.score for r in results)/len(results),2) if results else 0,participations=len(results),wins=sum(r.place==1 for r in results),history=history,activity=counts,events=[h_data(h) for h in Hackathon.query.all() if member_team(h.id)])

@api.patch('/profile')
@login_required
def edit_profile():
    d=body()
    if 'nickname' in d: current_user.nickname=text(d,'nickname',64)
    if 'github' in d: current_user.github=safe_url(text(d,'github',300,False))
    if 'telegram' in d: current_user.telegram=text(d,'telegram',100,False)
    if 'theme' in d:
        if d['theme'] not in ['yellow','purple','holiday']: abort(400,'Неизвестная тема.')
        current_user.theme=d['theme']
    activity('profile.update'); commit(); return jsonify(user=user_data(current_user))

@api.get('/ratings')
@login_required
def personal_ratings():
    rows=[dict(nickname=u.nickname,**experience(u.id)) for u in User.query.all() if participant_account(u)]
    rows.sort(key=lambda r:(-r['xp'],r['nickname']))
    return jsonify(items=rows)

@api.get('/hackathons/<int:hid>/analytics')
@login_required
def analytics(hid):
    h=get(Hackathon,hid); require_organizer(hid); teams_=Team.query.filter_by(hackathon_id=hid).all(); warnings=[]; task_count=done=sent=0
    for t in teams_:
        ts=Task.query.filter_by(team_id=t.id).all(); task_count+=len(ts); done+=sum(task.status=='done' for task in ts); s=Submission.query.filter_by(team_id=t.id).first(); sent+=bool(s)
        ids=[m.user_id for m in Membership.query.filter_by(team_id=t.id)]
        recent=Activity.query.filter(Activity.user_id.in_(ids),Activity.created_at>now()-timedelta(days=2)).first() if ids else None
        if not recent: warnings.append({'team':t.name,'reason':'Нет действий участников за последние 48 часов.'})
        if not s and h.submission_deadline-now()<timedelta(days=2): warnings.append({'team':t.name,'reason':'До дедлайна менее 48 часов или он истёк, проект не отправлен.'})
        overdue=sum(bool(x.deadline and x.deadline<now() and x.status!='done') for x in ts)
        if overdue: warnings.append({'team':t.name,'reason':f'Просроченных задач: {overdue}.'})
        if len(ts)>0 and sum(x.status!='done' for x in ts)/len(ts)>.7: warnings.append({'team':t.name,'reason':'Более 70% задач не завершены.'})
        if s:
            pending=sum(not bool(JuryScore.query.filter_by(submission_id=s.id,user_id=a.user_id).first()) for a in ReviewAssignment.query.filter_by(submission_id=s.id,kind='jury'))
            if pending: warnings.append({'team':t.name,'reason':f'Незавершённых проверок: {pending}.'})
    return jsonify(participants=Admission.query.filter_by(hackathon_id=hid).count(),teams=len(teams_),tasks=task_count,done=done,submitted=sent,warnings=warnings,progress=[{'team':t.name,'progress':team_data(t)['progress']} for t in teams_])

@api.get('/admin/users')
@login_required
def admin_users():
    require_admin(); return jsonify(items=[dict(user_data(u),event_roles=[dict(hackathon_id=r.hackathon_id,title=get(Hackathon,r.hackathon_id).title,role=r.role) for r in EventRole.query.filter_by(user_id=u.id)]) for u in User.query.order_by(User.id)],hackathons=[{'id':h.id,'title':h.title} for h in Hackathon.query.order_by(Hackathon.id)])

@api.patch('/admin/users/<int:uid>')
@login_required
def admin_update(uid):
    require_admin(); u=User.query.filter_by(id=uid).with_for_update().first_or_404(); d=body()
    if u.is_owner: abort(403,'Права главного администратора изменяются только передачей владения.')
    if u.id==current_user.id: abort(403,'Изменение собственных административных прав запрещено.')
    if 'role' in d:
        if d['role'] not in ['participant','organizer','admin','jury']: abort(400,'Неизвестная роль.')
        u.role=d['role']
        if d['role']!='organizer': EventRole.query.filter_by(user_id=uid,role='organizer').delete()
        if d['role'] not in ['participant','jury']: EventRole.query.filter_by(user_id=uid,role='jury').delete()
        if d['role']=='participant': EventRole.query.filter_by(user_id=uid,role='jury').delete()
    if 'blocked' in d:
        if not isinstance(d['blocked'],bool): abort(400,'Ожидается логический статус блокировки.')
        u.blocked=d['blocked']
    if 'hackathon_id' in d:
        hid=integer(d['hackathon_id']); get(Hackathon,hid)
        event_kind=d.get('event_role','organizer')
        if event_kind not in ['organizer','jury'] or u.role!=event_kind: abort(400,'Роль аккаунта должна соответствовать назначению.')
        assignment=EventRole.query.filter_by(user_id=uid,hackathon_id=hid,role=event_kind).first()
        if d.get('assign',True):
            if not assignment: db.session.add(EventRole(user_id=uid,hackathon_id=hid,role=event_kind))
        elif assignment: db.session.delete(assignment)
    audit('user.update',{'user':uid,'changes':{k:d[k] for k in ['role','blocked','hackathon_id','assign','event_role'] if k in d}}); commit(); return jsonify(user=user_data(u))

@api.get('/admin/audit')
@login_required
def audit_log():
    require_admin(); return jsonify(items=[serialize(a,'id actor_id action detail created_at') for a in AuditLog.query.order_by(AuditLog.id.desc()).limit(200)])

@api.get('/hackathons/<int:hid>/staff')
@login_required
def staff(hid):
    require_organizer(hid)
    return jsonify(items=[dict(serialize(r,'user_id role'),nickname=get(User,r.user_id).nickname,email=get(User,r.user_id).email) for r in EventRole.query.filter_by(hackathon_id=hid)],invitations=[serialize(i,'id email expires_at used revoked') for i in Invitation.query.filter_by(hackathon_id=hid)],admissions=[a.email for a in Admission.query.filter_by(hackathon_id=hid)])

@api.get('/hackathons/<int:hid>/roadmap')
@login_required
def roadmap(hid):
    h=get(Hackathon,hid); require_admission(h); t=member_team(hid); s=Submission.query.filter_by(team_id=t.id).first() if t else None
    count=Material.query.filter_by(hackathon_id=hid).count(); learned=LearningProgress.query.join(Material,LearningProgress.material_id==Material.id).filter(Material.hackathon_id==hid,LearningProgress.user_id==current_user.id).count()
    done=bool(t and Task.query.filter_by(team_id=t.id).count()>0 and not Task.query.filter(Task.team_id==t.id,Task.status!='done').first())
    stages=[('Допуск к хакатону',True),('Формирование команды',bool(t)),('Выбор кейса',bool(t and t.case_id)),('Изучение материалов',bool(count and learned>=count)),('Разработка',done),('Подготовка презентации',bool(t and Upload.query.filter_by(team_id=t.id,purpose='presentation').first())),('Сдача проекта',bool(s)),('Проверка жюри',bool(s and JuryScore.query.filter_by(submission_id=s.id).first())),('Публикация результатов',h.results_published)]
    return jsonify(items=[{'title':title,'completed':complete} for title,complete in stages],progress=round(100*sum(v for _,v in stages)/len(stages)),deadline=h.submission_deadline.isoformat()+'Z')

@api.route('/teams/<int:tid>/consultation',methods=['GET','POST'])
@login_required
def consultation(tid):
    t=get(Team,tid); assignment=ConsultationAssignment.query.filter_by(team_id=tid,user_id=current_user.id).first()
    if not assignment: team_access(t)
    if request.method=='POST':
        if not assignment and not organizer(t.hackathon_id): abort(403,'Вы не назначены экспертом этой команды.')
        db.session.add(ConsultationComment(team_id=tid,author_id=current_user.id,text=text(body(),'text',5000)))
        notify_team(t,'Новые рекомендации эксперта'); activity('expert.feedback'); commit()
    return jsonify(team={'id':t.id,'name':t.name,'case_id':t.case_id},experts=[{'id':r.user_id,'nickname':get(User,r.user_id).nickname} for r in ConsultationAssignment.query.filter_by(team_id=tid)],items=[dict(serialize(m,'id text created_at'),author=get(User,m.author_id).nickname,avatar=get(User,m.author_id).avatar) for m in ConsultationComment.query.filter_by(team_id=tid)])

@api.post('/teams/<int:tid>/consultation/assign')
@login_required
def consultation_assign(tid):
    t=get(Team,tid); require_organizer(t.hackathon_id); uid=integer(body().get('user_id')); get(User,uid)
    if EventRole.query.filter_by(user_id=uid,hackathon_id=t.hackathon_id,role='jury').first() or member_team(t.hackathon_id,uid): abort(403,'Жюри и участники не могут консультировать команды того же хакатона.')
    db.session.add(ConsultationAssignment(team_id=tid,user_id=uid)); notify(uid,'Вам назначена консультация команды',t.name); audit('consultation.assign',{'team':tid,'user':uid}); commit(); return jsonify(ok=True)

@api.get('/expert/consultations')
@login_required
def expert_consultations():
    return jsonify(items=[{'team_id':a.team_id,'team':get(Team,a.team_id).name,'hackathon_id':get(Team,a.team_id).hackathon_id} for a in ConsultationAssignment.query.filter_by(user_id=current_user.id)])

@api.get('/teams/<int:tid>/github')
@login_required
def github_info(tid):
    t=get(Team,tid); team_access(t); s=Submission.query.filter_by(team_id=tid).first()
    if not s: return jsonify(status='not_submitted',message='Репозиторий появится после сдачи проекта.')
    return jsonify(github_repo(s.github))


def save_image(purpose,hid=None):
    from PIL import Image, UnidentifiedImageError
    Image.MAX_IMAGE_PIXELS=12_000_000
    file=request.files.get('file')
    if not file: abort(400,'Выберите PNG или JPEG.')
    raw=file.read()
    if len(raw)>2*1024*1024: abort(400,'Изображение не должно превышать 2 МБ.')
    try:
        image=Image.open(io.BytesIO(raw))
        if image.format not in ['PNG','JPEG'] or image.width*image.height>12_000_000: abort(400,'Нужен PNG/JPEG до 12 мегапикселей.')
        image.load(); image=image.convert('RGB'); image.thumbnail((1600,900) if purpose=='cover' else (256,256))
    except (UnidentifiedImageError,OSError,Image.DecompressionBombError): abort(400,'Неверное изображение.')
    token=secrets.token_hex(24)
    image.save(Path(current_app.config['UPLOAD_FOLDER'])/(token+'.jpg'),format='JPEG',quality=88)
    db.session.add(Media(token=token,owner_id=current_user.id,hackathon_id=hid,purpose=purpose))
    return '/api/media/'+token

@api.post('/profile/avatar')
@login_required
def avatar_upload():
    current_user.avatar=save_image('avatar'); activity('profile.avatar'); commit(); return jsonify(user=user_data(current_user))

@api.post('/hackathons/<int:hid>/cover')
@login_required
def cover_upload(hid):
    h=get(Hackathon,hid); require_organizer(hid); h.cover=save_image('cover',hid); audit('hackathon.cover',{'id':hid}); commit(); return jsonify(cover=h.cover)

@api.get('/media/<string:token>')
@login_required
def media_download(token):
    m=Media.query.filter_by(token=token).first_or_404()
    # Covers are catalogue metadata. Avatars are visible only after sign-in.
    return send_from_directory(current_app.config['UPLOAD_FOLDER'],m.token+'.jpg',mimetype='image/jpeg')

@api.get('/hackathons/<int:hid>/learning-analytics')
@login_required
def learning_analytics(hid):
    require_organizer(hid); get(Hackathon,hid)
    material_ids=[m.id for m in Material.query.filter_by(hackathon_id=hid)]
    emails=[a.email for a in Admission.query.filter_by(hackathon_id=hid)]
    rows=[]
    for u in User.query.filter(User.email.in_(emails)).order_by(User.id):
        count=LearningProgress.query.filter(LearningProgress.user_id==u.id,LearningProgress.material_id.in_(material_ids)).count() if material_ids else 0
        rows.append({'nickname':u.nickname,'completed':count,'total':len(material_ids),'percent':round(count/len(material_ids)*100) if material_ids else 0})
    return jsonify(items=rows)


def experience(uid):
    rows=PersonalResult.query.join(Hackathon,PersonalResult.hackathon_id==Hackathon.id).filter(PersonalResult.user_id==uid,Hackathon.results_published.is_(True),Hackathon.status=='completed').all()
    rewards={'easy':70,'medium':150,'hard':240}
    rows=[r for r in rows if get(Hackathon,r.hackathon_id).approval=='approved']
    xp=sum(rewards[get(Hackathon,r.hackathon_id).difficulty] for r in rows)
    thresholds=[0,250,700,1400,2500,4000,6000]
    index=max(i for i,t in enumerate(thresholds) if xp>=t)
    lower=thresholds[index]; upper=thresholds[index+1] if index+1<len(thresholds) else None
    return {'earned':[{'hackathon_id':r.hackathon_id,'title':get(Hackathon,r.hackathon_id).title,'score':r.score,'difficulty':get(Hackathon,r.hackathon_id).difficulty,'xp':rewards[get(Hackathon,r.hackathon_id).difficulty]} for r in rows],'thresholds':thresholds,'current':xp-lower,'required':upper-lower if upper else None,'remaining':max(0,upper-xp) if upper else 0,'level':index,'xp':xp,'next':upper,'progress':round(100*(xp-lower)/(upper-lower)) if upper else 100}

@api.post('/hackathons/<int:hid>/register')
@login_required
def register_event(hid):
    require_participant(); h=get(Hackathon,hid)
    if h.approval!='approved' or h.status not in ['upcoming','active'] or now()>h.registration_deadline: abort(403,'Регистрация закрыта.')
    if not Admission.query.filter_by(hackathon_id=hid,email=current_user.email).first():
        db.session.add(Admission(hackathon_id=hid,email=current_user.email)); activity('hackathon.register')
    commit(); return jsonify(hackathon=h_data(h,True))

@api.get('/hackathons/<int:hid>/deadlines')
@login_required
def deadlines(hid):
    h=get(Hackathon,hid); require_admission(h)
    rows=[]
    for label,dt in [('Регистрация',h.registration_deadline),('Формирование команд',h.team_deadline or h.registration_deadline),('Сдача проекта',h.submission_deadline)]:
        seconds=int((dt-now()).total_seconds())
        status='Завершён' if h.status=='completed' else 'Истёк' if seconds<0 else 'Скоро' if seconds<86400 else 'Впереди'
        rows.append({'title':label,'at':dt.isoformat()+'Z','status':status,'seconds':max(0,seconds)})
    return jsonify(items=rows)


@api.get('/teams/<int:tid>/candidates')
@login_required
def invite_candidates(tid):
    t=get(Team,tid); captain(t); require_admission(get(Hackathon,t.hackathon_id))
    emails=[a.email for a in Admission.query.filter_by(hackathon_id=t.hackathon_id)]
    users=User.query.filter(User.email.in_(emails),User.blocked.is_(False)).order_by(User.nickname).all()
    query=request.args.get('q','').strip().lower()[:64]
    rows=[]
    for u in users:
        if not participant_account(u) or member_team(t.hackathon_id,u.id) or query not in u.nickname.lower(): continue
        inv=TeamInvitation.query.filter_by(team_id=tid,user_id=u.id,status='pending').first()
        rows.append({'id':u.id,'nickname':u.nickname,'avatar':u.avatar,'level':experience(u.id)['level'],'invited':bool(inv and inv.expires_at>now())})
        if len(rows)>=100:break
    return jsonify(items=rows)

@api.post('/teams/<int:tid>/invitations')
@login_required
def send_team_invite(tid):
    t=Team.query.filter_by(id=tid).with_for_update().first_or_404();captain(t)
    h=get(Hackathon,t.hackathon_id);u=get(User,integer(body().get('user_id')));require_participant(u)
    if u.blocked or not Admission.query.filter_by(hackathon_id=h.id,email=u.email).first(): abort(403,'Участник должен зарегистрироваться на этот хакатон.')
    if member_team(h.id,u.id): abort(409,'Участник уже состоит в команде.')
    if now()>(h.team_deadline or h.registration_deadline):abort(403,'Формирование команд завершено.')
    if Membership.query.filter_by(team_id=tid).count()>=h.team_size:abort(409,'Команда заполнена.')
    inv=TeamInvitation.query.filter_by(team_id=tid,user_id=u.id).first()
    if inv and inv.status=='pending' and inv.expires_at>now():abort(409,'Приглашение уже отправлено.')
    if not inv:inv=TeamInvitation(team_id=tid,user_id=u.id);db.session.add(inv)
    inv.status='pending';inv.expires_at=min(now()+timedelta(days=3),h.team_deadline or h.registration_deadline)
    notify(u.id,'Приглашение в команду',t.name+' · '+h.title+' — откройте уведомления, чтобы ответить.');activity('team.invite');commit()
    return jsonify(id=inv.id),201

@api.get('/team-invitations')
@login_required
def my_team_invites():
    require_participant()
    return jsonify(items=[{'id':i.id,'team':get(Team,i.team_id).name,'hackathon':get(Hackathon,get(Team,i.team_id).hackathon_id).title,'expires_at':i.expires_at.isoformat()+'Z'} for i in TeamInvitation.query.filter_by(user_id=current_user.id,status='pending') if i.expires_at>now()])

@api.post('/team-invitations/<int:iid>/respond')
@login_required
def respond_team_invite(iid):
    require_participant();i=get(TeamInvitation,iid)
    if i.user_id!=current_user.id:abort(403,'Чужое приглашение.')
    t=Team.query.filter_by(id=i.team_id).with_for_update().first_or_404()
    i=TeamInvitation.query.filter_by(id=iid).populate_existing().with_for_update().first_or_404()
    if i.status!='pending' or i.expires_at<=now():abort(409,'Приглашение недействительно.')
    accept=body().get('accept')
    if not isinstance(accept,bool):abort(400,'Укажите принять или отклонить.')
    if accept:
        add_member(t,current_user);i.status='accepted';activity('team.join')
    else:i.status='declined'
    commit();return jsonify(ok=True,hackathon_id=t.hackathon_id)


@api.get('/admin/hackathons')
@login_required
def admin_hackathons():
    require_admin();return jsonify(items=[h_data(h,True) for h in Hackathon.query.order_by(Hackathon.id.desc())])

@api.patch('/admin/hackathons/<int:hid>')
@login_required
def review_hackathon(hid):
    require_admin();h=Hackathon.query.filter_by(id=hid).with_for_update().first_or_404();d=body()
    if h.approval!='pending':abort(409,'Заявка уже рассмотрена.')
    difficulty=d.get('difficulty',h.difficulty);decision=d.get('approval')
    if difficulty not in ['easy','medium','hard'] or decision not in ['approved','rejected']:abort(400,'Проверьте сложность и решение.')
    h.difficulty=difficulty;h.approval=decision;h.review_comment=text(d,'comment',5000,False)
    for r in EventRole.query.filter_by(hackathon_id=hid,role='organizer'):notify(r.user_id,'Решение по заявке хакатона',h.title+' · '+decision+' · '+h.review_comment)
    audit('hackathon.review',{'id':hid,'difficulty':difficulty,'approval':decision});commit();return jsonify(hackathon=h_data(h,True))


@api.post('/admin/ownership')
@login_required
def transfer_ownership():
    require_admin()
    users=User.query.order_by(User.id).populate_existing().with_for_update().all()
    owner=next((u for u in users if u.id==current_user.id),None)
    if not owner or not owner.is_owner:abort(403,'Только главный администратор передаёт владение.')
    uid=integer(body().get('user_id'));target=next((u for u in users if u.id==uid),None)
    if not target or target.id==owner.id or target.role!='admin' or target.blocked:abort(400,'Выберите другого активного администратора.')
    owner.is_owner=False;db.session.flush();target.is_owner=True
    audit('ownership.transfer',{'from':owner.id,'to':target.id});notify(target.id,'Вам переданы права главного администратора');commit()
    return jsonify(user=user_data(owner))

@api.post('/hackathons/<int:hid>/jury-members')
@login_required
def appoint_jury(hid):
    require_organizer(hid);get(Hackathon,hid)
    email=text(body(),'email',254).lower();u=User.query.filter_by(email=email).first()
    if not u:abort(404,'Пользователь должен сначала зарегистрироваться.')
    if u.blocked or u.role not in ['participant','jury'] or Membership.query.filter_by(user_id=u.id).first():abort(409,'У этого пользователя несовместимые права или он состоит в команде.')
    if not EventRole.query.filter_by(user_id=u.id,hackathon_id=hid,role='jury').first():
        db.session.add(EventRole(user_id=u.id,hackathon_id=hid,role='jury'));notify(u.id,'Вы назначены жюри',get(Hackathon,hid).title)
    audit('jury.appoint',{'hackathon':hid,'user':u.id});commit();return jsonify(ok=True)

@api.delete('/hackathons/<int:hid>/jury-members/<int:uid>')
@login_required
def remove_jury(hid,uid):
    require_organizer(hid);get(Hackathon,hid);user=get(User,uid)
    role=EventRole.query.filter_by(hackathon_id=hid,user_id=uid,role='jury').with_for_update().first()
    if not role:abort(404,'Пользователь не состоит в жюри этого хакатона.')
    projects=[s.id for s in Submission.query.join(Team,Submission.team_id==Team.id).filter(Team.hackathon_id==hid)]
    removed=ReviewAssignment.query.filter(ReviewAssignment.user_id==uid,ReviewAssignment.kind=='jury',ReviewAssignment.submission_id.in_(projects)).delete(synchronize_session=False)
    Invitation.query.filter_by(hackathon_id=hid,email=user.email,used=False,revoked=False).update({'revoked':True})
    db.session.delete(role)
    notify(uid,'Вы сняты с жюри хакатона',get(Hackathon,hid).title)
    audit('jury.remove',{'hackathon':hid,'user':uid,'assignments_removed':removed});commit()
    return jsonify(ok=True)


@api.get('/public/results')
def published_events():
    return jsonify(items=[serialize(h,'id title end_at') for h in Hackathon.query.filter_by(results_published=True).order_by(Hackathon.end_at.desc())])

@api.get('/public/hackathons/<int:hid>/results')
def public_results(hid):
    h=get(Hackathon,hid)
    if not h.results_published:abort(404,'Результаты ещё не опубликованы.')
    rows=[{k:r[k] for k in ['place','team','title','score','criteria']} for r in ranking(h)]
    return jsonify(hackathon=serialize(h,'id title end_at tie_rule'),items=rows,criteria=[serialize(c,'id title maximum') for c in Criterion.query.filter_by(hackathon_id=hid)])

@api.get('/public/awards/<string:token>')
def verify_award(token):
    from .awards import award_data
    a=Award.query.filter_by(token=token).first_or_404()
    h=get(Hackathon,a.hackathon_id)
    if not h.results_published or h.status!='completed':abort(404,'Документ недействителен.')
    # A random certificate identifier reveals only the named document, not an account profile.
    return jsonify(verified=True,award=award_data(a))

@api.get('/profile/awards')
@login_required
def my_awards():
    require_participant()
    from .awards import award_data
    rows=Award.query.join(Hackathon,Award.hackathon_id==Hackathon.id).filter(Award.user_id==current_user.id,Hackathon.results_published.is_(True),Hackathon.status=='completed').order_by(Award.issued_at.desc(),Award.kind)
    return jsonify(items=[award_data(a) for a in rows])

@api.get('/profile/awards/<int:aid>/pdf')
@login_required
def download_award(aid):
    from .awards import render_pdf
    from flask import send_file
    a=get(Award,aid)
    if a.user_id!=current_user.id:abort(403,'Скачивание доступно владельцу документа.')
    h=get(Hackathon,a.hackathon_id)
    if not h.results_published or h.status!='completed':abort(404,'Документ недействителен.')
    return send_file(io.BytesIO(render_pdf(a)),mimetype='application/pdf',as_attachment=True,download_name=f'hackflow-{a.kind}-{a.id}.pdf')
