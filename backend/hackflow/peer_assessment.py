"""Up to three independent anonymous team reviews; final score = 0.8 jury + 0.2 peer."""
from collections import deque
from flask import abort
from .models import db,Hackathon,Team,Submission,PeerAssignment,PeerReview


def projects(hid):
    return Submission.query.join(Team,Submission.team_id==Team.id).filter(Team.hackathon_id==hid).order_by(Submission.id).all()


def required_reviewers(hid):
    return min(3,max(0,len(projects(hid))-1))


def peer_summary(submission):
    assignments=PeerAssignment.query.filter_by(submission_id=submission.id).all()
    expected={a.team_id for a in assignments}
    reviews=PeerReview.query.filter_by(submission_id=submission.id).all()
    valid=[r for r in reviews if r.team_id in expected and r.team_id!=submission.team_id]
    required=required_reviewers(db.session.get(Team,submission.team_id).hackathon_id)
    complete=required>0 and len(expected)==required and len({r.team_id for r in valid})==required
    return {'required':required,'assigned':len(expected),'received':len(valid),'complete':complete,
            'average':sum(r.total for r in valid)/len(valid) if valid else None,'reviews':valid}


def assert_peer_complete(h):
    if not h.peer_enabled:return
    if required_reviewers(h.id)==0:abort(409,'Для Peer Review нужны хотя бы две команды со сданными проектами.')
    for s in projects(h.id):
        if not peer_summary(s)['complete']:
            abort(409,f"Проекту нужны оценки всех назначенных команд ({required_reviewers(h.id)}). Peer Review ещё не завершён.")


def distribute(h):
    if h.results_published or h.peer_published:abort(409,'Этап оценивания уже закрыт.')
    entries=projects(h.id)
    if len(entries)<2:abort(409,'Для Peer Review нужны хотя бы две команды со сданными проектами: команда не может проверять себя.')
    required=min(3,len(entries)-1)
    if any(not s.anonymous_ready or not s.anonymous_file_id for s in entries):
        abort(409,'Для каждого проекта подготовьте обезличенные текст и PDF.')
    by_id={s.id:s for s in entries};by_team={s.team_id:s for s in entries}
    existing=PeerAssignment.query.filter(PeerAssignment.submission_id.in_(by_id)).all()
    incoming={s.id:set() for s in entries};outgoing={s.team_id:set() for s in entries}
    for a in existing:
        if a.team_id not in by_team or by_id[a.submission_id].team_id==a.team_id:abort(409,'Есть несовместимые прежние назначения.')
        incoming[a.submission_id].add(a.team_id);outgoing[a.team_id].add(a.submission_id)
    if any(len(v)>required for v in [*incoming.values(),*outgoing.values()]):abort(409,'Прежние назначения превышают доступное число рецензентов.')
    # Integral max flow preserves existing assignments and balances up to three reviews per team.
    capacity={};adj={}
    def edge(a,b,n):
        capacity[a,b]=n;capacity[b,a]=0;adj.setdefault(a,[]).append(b);adj.setdefault(b,[]).append(a)
    source=('start',0);sink=('end',0)
    for team in by_team:edge(source,('team',team),required-len(outgoing[team]))
    for s in entries:edge(('project',s.id),sink,required-len(incoming[s.id]))
    for team in by_team:
        for s in entries:
            if team!=s.team_id and team not in incoming[s.id]:edge(('team',team),('project',s.id),1)
    flow=0
    while True:
        prev={source:None};queue=deque([source])
        while queue and sink not in prev:
            a=queue.popleft()
            for b in adj.get(a,[]):
                if b not in prev and capacity[a,b]>0:prev[b]=a;queue.append(b)
        if sink not in prev:break
        node=sink
        while prev[node] is not None:
            parent=prev[node];capacity[parent,node]-=1;capacity[node,parent]+=1;node=parent
        flow+=1
    if flow!=sum(required-len(v) for v in incoming.values()):abort(409,'Прежние назначения не позволяют равномерное распределение без самооценки.')
    added=0
    for team in by_team:
        for s in entries:
            pair=(('team',team),('project',s.id))
            if pair in capacity and capacity[pair]==0:
                db.session.add(PeerAssignment(team_id=team,submission_id=s.id));added+=1
    h.peer_enabled=True;h.status='review'
    return added
