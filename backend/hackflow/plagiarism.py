"""Bounded, local source similarity analysis. Uploaded code is never executed."""
from difflib import SequenceMatcher
from pathlib import Path
from time import monotonic
import zipfile
from werkzeug.exceptions import HTTPException
from .models import db,Submission,Team,Upload,CodeReport,AIReport,ReviewAssignment,Notification,now
from .services import source_archive,digest

VERSION='normalized-files-v2'
MAX_FILES=8
MAX_TOKENS=2000
TIME_BUDGET=3.0
LIMITATIONS=('Сходство файлов не доказывает плагиат. Общие шаблоны могут повышать показатель. '
             'Это максимальное сходство пары нормализованных файлов, а не доля плагиата во всём проекте. '
             'Сравнение выполняется только с ZIP отправленных проектов этого хакатона; поиска по интернету нет. '
             'Автоматических санкций и изменения баллов нет.')


def corpus_signature(submission):
    hid=db.session.get(Team,submission.team_id).hackathon_id
    corpus=Submission.query.join(Team,Submission.team_id==Team.id).filter(Team.hackathon_id==hid).order_by(Submission.id).all()
    return digest(VERSION+'|'+','.join(f'{s.id}:{s.source_id or 0}' for s in corpus))


def _source(upload,folder):
    if not upload:return None,'no_source'
    try:return source_archive(Path(folder)/upload.storage_name,max_files=MAX_FILES,max_tokens=MAX_TOKENS),None
    except (OSError,zipfile.BadZipFile,RuntimeError,ValueError,HTTPException):
        return None,'unreadable_source'


def notify_jury(submission,report):
    signature=report.report.get('corpus_signature','legacy')
    for assignment in ReviewAssignment.query.filter_by(submission_id=submission.id,kind='jury'):
        key=f'codecheck:{submission.id}:{signature}:{report.status}:{assignment.user_id}'
        if not Notification.query.filter_by(event_key=key).first():
            db.session.add(Notification(user_id=assignment.user_id,event_key=key,
                title='Отчёт проверки кода доступен',text=f'Проект {submission.code}: откройте назначенную работу и раздел «Проверка кода».'))


def run_analysis(submission,folder):
    # Serialize analyses of one immutable submission across web requests/workers.
    submission=Submission.query.filter_by(id=submission.id).with_for_update().one()
    report=CodeReport.query.filter_by(submission_id=submission.id).first()
    if not report:
        report=CodeReport(submission_id=submission.id,report={});db.session.add(report)
    signature=corpus_signature(submission)
    started=monotonic()
    base={'algorithm':VERSION,'corpus_signature':signature,'checked_at':now().isoformat()+'Z',
          'method':'Нормализация идентификаторов, строк и чисел; SequenceMatcher по токенам.',
          'limitations':LIMITATIONS,'file_limit':MAX_FILES,'token_limit':MAX_TOKENS}
    def finish(status,values):
        report.status=status;report.report={**base,**values}
        db.session.flush();notify_jury(submission,report)
        return report
    upload=db.session.get(Upload,submission.source_id) if submission.source_id else None
    source,error=_source(upload,folder)
    if error=='no_source':return finish('unavailable',{'message':'ZIP исходников не загружен. Анализ не выполнялся.'})
    if error:return finish('error',{'message':'Исходный ZIP отсутствует в хранилище или не читается. Проверка не выполнена.'})
    if not source and source.truncated:return finish('partial',{'message':'Лимит файлов достигнут до нахождения подходящего кода. Остальная часть ZIP не проверена.','partial':True,'files_total':source.total_files,'files_analyzed':0,'compared_projects':0,'max_similarity':None,'matches':[]})
    if not source:return finish('unavailable',{'message':'Нет поддерживаемых исходных файлов с минимум 40 токенами.'})
    own=list(source.values())[:MAX_FILES]
    partial=source.truncated
    hid=db.session.get(Team,submission.team_id).hackathon_id
    others=Submission.query.join(Team,Submission.team_id==Team.id).filter(Team.hackathon_id==hid,Submission.id!=submission.id).order_by(Submission.id).all()
    matches=[];skipped=[];comparisons=0
    for other in others:
        if monotonic()-started>TIME_BUDGET:
            partial=True;break
        other_upload=db.session.get(Upload,other.source_id) if other.source_id else None
        other_source,error=_source(other_upload,folder)
        if error or not other_source:
            skipped.append({'code':other.code,'reason':error or 'no_supported_files'});continue
        candidates=list(other_source.values())[:MAX_FILES]
        if other_source.truncated:partial=True
        best=None;fragments=[];project_comparisons=0;timed_out=False
        for a in own:
            for b in candidates:
                if monotonic()-started>TIME_BUDGET:
                    partial=True;timed_out=True;break
                matcher=SequenceMatcher(None,a[:MAX_TOKENS],b[:MAX_TOKENS],autojunk=True)
                ratio=round(100*matcher.ratio(),1);comparisons+=1;project_comparisons+=1
                if best is None or ratio>best:
                    best=ratio
                    fragments=[{'tokens':m.size,'left_offset':m.a,'right_offset':m.b,
                        'normalized_excerpt':' '.join(a[m.a:m.a+min(m.size,80)])}
                        for m in matcher.get_matching_blocks() if m.size>=25][:8]
            if timed_out:break
        if project_comparisons:
            matches.append({'code':other.code,'similarity':best,'fragments':fragments})
        if timed_out:break
    maximum=max((m['similarity'] for m in matches),default=None)
    values={'matches':sorted(matches,key=lambda m:-m['similarity']),
            'max_similarity':maximum,'files_total':source.total_files,'files_analyzed':len(own),
            'compared_projects':len(matches),'projects_total':len(others),'comparisons':comparisons,
            'skipped':skipped,'partial':partial,
            'risk':'high' if maximum is not None and maximum>=80 else 'medium' if maximum is not None and maximum>=50 else 'low' if maximum is not None else 'unknown'}
    if partial:values['message']='Анализ ограничен лимитом времени, файлов или токенов. Непроверенные части не считаются оригинальными.'
    elif not matches:values['message']='Нет других доступных ZIP для сравнения. Оригинальность не подтверждена.'
    status='partial' if partial else 'completed' if matches else 'insufficient_data'
    ai=AIReport.query.filter_by(submission_id=submission.id).first()
    observations={'files':len(source),'tokens':sum(map(len,source.values())),
                  'limitations':'По исходникам нельзя достоверно установить использование ИИ. Процент ИИ-кода не рассчитывается.'}
    if ai:ai.observations=observations
    else:db.session.add(AIReport(submission_id=submission.id,observations=observations))
    return finish(status,values)


def ensure_analysis(submission,folder):
    report=CodeReport.query.filter_by(submission_id=submission.id).first()
    if report and report.status!='error' and report.report.get('corpus_signature')==corpus_signature(submission):
        notify_jury(submission,report)
        return report
    return run_analysis(submission,folder)


def report_payload(submission,report):
    if not report:return {'status':'not_started','report':{}}
    data=report.report or {}
    allowed=('algorithm','checked_at','method','limitations','file_limit','token_limit','message',
             'max_similarity','files_total','files_analyzed','compared_projects','projects_total',
             'comparisons','partial','risk')
    safe={k:data[k] for k in allowed if k in data}
    if 'matches' in data:
        safe['matches']=[{'code':m['code'],'similarity':m['similarity'],
                         'fragments':[{k:f[k] for k in ('tokens','left_offset','right_offset','normalized_excerpt') if k in f}
                                      for f in m.get('fragments',[])]} for m in data['matches']]
    if 'skipped' in data:safe['skipped']=[{'code':m['code'],'reason':m['reason']} for m in data['skipped']]
    stale=data.get('corpus_signature')!=corpus_signature(submission)
    return {'status':'stale' if stale else report.status,'report':safe,'stale':stale}
