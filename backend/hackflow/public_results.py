"""Public event archive and official results with an explicit safe field list."""
from flask import Blueprint, abort, jsonify
from .models import Hackathon, Criterion
from .services import ranking
from .catalog_assets import cover_for

public_results_api=Blueprint('public_results',__name__)


def event_data(h):
    return {'id':h.id,'title':h.title,'description':h.description,
            'start_at':h.start_at.isoformat()+'Z','end_at':h.end_at.isoformat()+'Z',
            'difficulty':h.difficulty,'cover':cover_for(h),
            'is_demo':bool(h.demo_key and h.demo_key.startswith('showcase-')),
            'results_published':h.results_published}


@public_results_api.get('/public/results')
def archive():
    events=Hackathon.query.filter_by(status='completed',approval='approved').order_by(Hackathon.end_at.desc(),Hackathon.id.desc())
    return jsonify(items=[event_data(h) for h in events])


@public_results_api.get('/public/hackathons/<int:hid>/results')
def results(hid):
    h=Hackathon.query.filter_by(id=hid,status='completed',approval='approved',results_published=True).first()
    if not h: abort(404,'Опубликованные результаты не найдены.')
    # Do not expose identities, grades by individual reviewers, private files or URLs.
    rows=[{key:r[key] for key in ('place','team','title','score','criteria')} for r in ranking(h)]
    return jsonify(hackathon=event_data(h),items=rows,tie_rule=h.tie_rule,
                   criteria=[{'id':c.id,'title':c.title,'maximum':c.maximum}
                             for c in Criterion.query.filter_by(hackathon_id=hid).order_by(Criterion.id)])
