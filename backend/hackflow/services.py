import hashlib
import io
import ipaddress
import re
import socket
import tokenize
import zipfile
from collections import Counter
from datetime import timedelta
from difflib import SequenceMatcher
from urllib.parse import urlparse
import requests
from flask import abort
from .models import *

def digest(value): return hashlib.sha256(value.encode()).hexdigest()

def safe_url(value, github=False):
    if not value: return ''
    p=urlparse(value)
    try: port=p.port
    except ValueError: abort(400,'Некорректный порт URL.')
    if p.scheme != 'https' or not p.hostname or p.username or p.password or port not in (None,443):
        abort(400,'Используйте публичный HTTPS-адрес без учётных данных.')
    if github and (p.hostname.lower() != 'github.com' or not re.fullmatch(r'/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/?',p.path)):
        abort(400,'Нужна ссылка https://github.com/owner/repository')
    if p.hostname.lower() in ('localhost','metadata.google.internal') or p.hostname.endswith('.local'):
        abort(400,'Локальные адреса запрещены.')
    try:
        if not ipaddress.ip_address(p.hostname).is_global: abort(400,'Приватные адреса запрещены.')
    except ValueError: pass
    return value

def github_repo(url):
    safe_url(url,github=True)
    path=urlparse(url).path.strip('/').removesuffix('.git')
    try:
        r=requests.get('https://api.github.com/repos/'+path,timeout=8,allow_redirects=False,headers={'Accept':'application/vnd.github+json'})
        if r.status_code != 200: return {'status':'unknown','message':f'GitHub ответил HTTP {r.status_code}; доступность не подтверждена.'}
        data=r.json()
        readme=requests.get('https://api.github.com/repos/'+path+'/readme',timeout=8,allow_redirects=False)
        return {'status':'ok','message':'Публичный репозиторий доступен','readme':'ok' if readme.status_code==200 else 'unknown','stars':data.get('stargazers_count',0),'language':data.get('language'),'updated_at':data.get('updated_at')}
    except (requests.RequestException,ValueError): return {'status':'unknown','message':'GitHub временно недоступен.'}

def audit_submission(data, team, external=True):
    h=db.session.get(Hackathon,team.hackathon_id)
    checks=[]
    def add(name,status,text): checks.append({'name':name,'status':status,'message':text})
    for key,label in [('title','Название'),('description','Описание'),('github','GitHub'),('demo','Демонстрация')]:
        add(key,'ok' if str(data.get(key,'')).strip() else 'error',label)
    try: upload_id=int(data.get('presentation_id')) if data.get('presentation_id') else None
    except (TypeError,ValueError): abort(400,'Некорректный идентификатор презентации.')
    upload=db.session.get(Upload,upload_id) if upload_id else None
    add('presentation','ok' if upload and upload.team_id==team.id and upload.purpose=='presentation' else 'error','Презентация PDF')
    add('deadline','ok' if now()<=h.submission_deadline else 'error','Дедлайн сдачи')
    add('case','ok' if team.case_id else 'error','Кейс выбран')
    if data.get('github'):
        safe_url(data['github'],github=True)
        result=github_repo(data['github']) if external else {'status':'unknown','readme':'unknown'}
        add('repository',result['status'],result.get('message','Доступность репозитория не проверена'))
        add('readme',result.get('readme','unknown'),'Наличие README')
    if data.get('demo'):
        safe_url(data['demo'])
        # Do not fetch arbitrary visitor URLs server-side (SSRF/DNS-rebinding).
        add('demo_access','unknown','Проверьте открытие демонстрации вручную. Сервер не запрашивает произвольные URL.')
    return checks

IGNORED={'node_modules','vendor','.git','dist','build','.venv','venv','__pycache__'}
EXTENSIONS={'.py','.js','.jsx','.ts','.tsx','.java','.go','.c','.cpp','.rs'}

class SourceArchive(dict):
    total_files=0
    truncated=False


def source_archive(path,max_files=32,max_tokens=10000):
    from pathlib import PurePosixPath
    result=SourceArchive()
    with zipfile.ZipFile(path) as z:
        infos=z.infolist()
        if len(infos)>1000 or sum(i.file_size for i in infos)>20*1024*1024: abort(400,'Архив слишком большой: максимум 1000 файлов / 20 МБ после распаковки.')
        candidates=[]
        for info in infos:
            p=PurePosixPath(info.filename)
            if p.is_absolute() or '..' in p.parts or any(x in IGNORED for x in p.parts): continue
            if p.suffix.lower() not in EXTENSIONS or info.file_size>256*1024: continue
            candidates.append(info)
        result.total_files=len(candidates)
        result.truncated=len(candidates)>max_files
        for info in candidates[:max_files]:
            p=PurePosixPath(info.filename)
            text=z.read(info).decode('utf-8',errors='replace')
            # Identifiers and literals are normalized; comments/imports omitted.
            text=re.sub(r'(?m)^\s*(?:import |from |//|#).*$', '',text)
            parts=re.findall(r'''"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|[A-Za-z_]\w*|\d+(?:\.\d+)?|[^\s\w]''',text)
            keywords=set('if else for while return def class function const let var async await try except throw new public private static void int in of True False None'.split())
            normalized=['STR' if x.startswith(('\"',"'")) else 'NUM' if x[0].isdigit() else x if x in keywords or not x.isidentifier() else 'ID' for x in parts]
            if len(normalized)>max_tokens:result.truncated=True
            if len(normalized)>=40: result[str(p)]=normalized[:max_tokens]
    return result

def run_codecheck(submission, folder):
    from .plagiarism import run_analysis
    return run_analysis(submission,folder)


def ranking(h):
    from .peer_assessment import peer_summary
    rows=[]
    criteria=Criterion.query.filter_by(hackathon_id=h.id).all()
    for s in Submission.query.join(Team,Submission.team_id==Team.id).filter(Team.hackathon_id==h.id).all():
        scores=JuryScore.query.filter_by(submission_id=s.id).all()
        if not scores:continue
        team=db.session.get(Team,s.team_id);jury=sum(r.total for r in scores)/len(scores)
        peer=peer_summary(s);ready=not h.peer_enabled or peer['complete']
        average=peer['average'] if peer['complete'] else None
        total=(.8*jury+.2*average) if h.peer_enabled and ready else jury if not h.peer_enabled else None
        combined={}
        for c in criteria:
            j=sum(float(r.scores.get(str(c.id),0)) for r in scores)/len(scores)
            p=sum(float(r.scores.get(str(c.id),0)) for r in peer['reviews'])/peer['required'] if peer['complete'] else 0
            combined[str(c.id)]=round(.8*j+.2*p,2) if h.peer_enabled else round(j,2)
        rows.append({'submission_id':s.id,'team_id':team.id,'team':team.name,'title':s.title,'code':s.code,
                     'score':round(total,2) if total is not None else None,
                     'jury_score':round(jury,2),'peer_score':round(average,2) if average is not None else None,
                     'jury_component':round(jury*(.8 if h.peer_enabled else 1),2),
                     'peer_component':round(.2*average,2) if h.peer_enabled and average is not None else 0 if not h.peer_enabled else None,
                     'peer_count':peer['received'],'peer_enabled':h.peer_enabled,'ready':ready,
                     'submitted_at':s.submitted_at.isoformat(),'criteria':combined})
    rows.sort(key=lambda r:(-(r['score'] if r['score'] is not None else -1),r['submitted_at'],r['code']))
    for i,row in enumerate(rows,1):row['place']=i if row['ready'] else None
    return rows


def publish_results(h):
    from .peer_assessment import assert_peer_complete
    assert_peer_complete(h)
    for row in ranking(h):
        for member in Membership.query.filter_by(team_id=row['team_id']).all():
            result=PersonalResult.query.filter_by(user_id=member.user_id,hackathon_id=h.id).first()
            team=db.session.get(Team,row['team_id'])
            case=db.session.get(Case,team.case_id) if team.case_id else None
            if not result:
                result=PersonalResult(user_id=member.user_id,hackathon_id=h.id,team_name=row['team'],score=row['score'],place=row['place'],case_title=case.title if case else ''); db.session.add(result)
            else:
                result.team_name=row['team']; result.score=row['score']; result.place=row['place']; result.case_title=case.title if case else ''
    h.results_published=True; h.status='completed'
    h.peer_published=True
    db.session.flush()
    from .certificates import sync_awards
    sync_awards(h)

def dispatch_reminders():
    """Idempotent periodic job; run flask reminders once per minute."""
    count=0
    def send(uid,key,title,message):
        nonlocal count
        if not Notification.query.filter_by(event_key=key).first():
            db.session.add(Notification(user_id=uid,event_key=key,title=title,text=message)); count+=1
    for h in Hackathon.query.filter(Hackathon.results_published.is_(False)):
        emails=[a.email for a in Admission.query.filter_by(hackathon_id=h.id)]
        users=User.query.filter(User.email.in_(emails)).all()
        remaining=h.submission_deadline-now()
        if timedelta(0)<remaining<=timedelta(hours=24):
            for u in users: send(u.id,f'deadline:{h.id}:{h.submission_deadline.isoformat()}:{u.id}','До сдачи менее 24 часов',h.title)
        for event in Schedule.query.filter_by(hackathon_id=h.id):
            if event.kind in ['webinar','consultation','workshop'] and timedelta(0)<=event.starts_at-now()<=timedelta(minutes=15):
                for u in users: send(u.id,f'event:{event.id}:{event.starts_at.isoformat()}:{u.id}','Скоро начало мероприятия',event.title)
    db.session.commit()
    return count
