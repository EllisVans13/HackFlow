"""Team-city read model: aggregate progress, never task content or judging materials."""
from .models import db, Team, Task, Membership, User, Case, Submission, now

STYLES=('workshop','tower','lab','aframe','treehouse')

def city_data(hackathon,user,participant=False):
    teams=Team.query.filter_by(hackathon_id=hackathon.id).order_by(Team.created_at,Team.id).all()
    ids=[t.id for t in teams]
    tasks={tid:[] for tid in ids}
    for task in Task.query.filter(Task.team_id.in_(ids)):
        tasks[task.team_id].append(task.status)
    members={tid:[] for tid in ids}
    for membership,u in db.session.query(Membership,User).join(User,User.id==Membership.user_id).filter(Membership.team_id.in_(ids)):
        members[membership.team_id].append({'id':u.id,'nickname':u.nickname,'avatar':u.avatar})
    cases={c.id:c.title for c in Case.query.filter_by(hackathon_id=hackathon.id)}
    submissions={s.team_id:s for s in Submission.query.filter(Submission.team_id.in_(ids))}
    result=[]
    mine=None
    for t in teams:
        roster=members[t.id]
        if any(m['id']==user.id for m in roster):mine=t.id
        total=len(tasks[t.id]);done=tasks[t.id].count('done')
        progress=round(100*done/total) if total else 0
        submission=submissions.get(t.id)
        stage='submitted' if submission else 'building' if total else 'foundation' if t.case_id else 'plot'
        floors=(1+min(4,int(done*4/total))) if total else 0
        recruiting=t.open and len(roster)<hackathon.team_size and now()<=(hackathon.team_deadline or hackathon.registration_deadline) and hackathon.status in ('active','upcoming')
        project=None
        if submission and hackathon.results_published and t.city_showcase:
            project={'title':submission.title,'description':submission.description,'demo':submission.demo}
        result.append({'id':t.id,'name':t.name,'description':t.description,'style':t.city_style,
            'stage':stage,'floors':floors,'progress':progress,'total':total,'done':done,
            'members':roster,'capacity':hackathon.team_size,'recruiting':recruiting,
            'case_title':cases.get(t.case_id),'project':project,
            'can_customize':participant and t.captain_id==user.id,
            'showcase':t.city_showcase if t.captain_id==user.id else None})
    return {'items':result,'can_join':participant,'my_team_id':mine,'results_published':hackathon.results_published,
        'summary':{'teams':len(teams),'members':sum(len(r) for r in members.values()),
                   'tasks_done':sum(t['done'] for t in result),'submitted':len(submissions)}}
