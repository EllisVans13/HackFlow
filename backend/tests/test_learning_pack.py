from conftest import login
from hackflow.models import db,Material,LearningProgress,Hackathon
from hackflow.learning_seed_v1 import populate_learning,CATALOG,MATERIAL_KINDS


def test_learning_pack_is_russian_in_allowed_formats_and_idempotent(app,client):
    with app.app_context():
        legacy=Material.query.filter_by(title='React: мышление компонентами').one()
        legacy_id=legacy.id
        db.session.add(LearningProgress(user_id=2,material_id=legacy_id))
        custom=Material(hackathon_id=1,title='Авторский материал',url='https://example.com/custom')
        db.session.add(custom);db.session.commit();custom_id=custom.id
        assert populate_learning(db.session.connection(),1)>0
        db.session.commit()
        first=Material.query.filter_by(catalog_key='git-video').one();first.title='Название организатора'
        db.session.add(LearningProgress(user_id=2,material_id=first.id));db.session.commit()
        assert populate_learning(db.session.connection(),1)==0
        db.session.commit()
        assert db.session.get(Material,custom_id).title=='Авторский материал'
        assert db.session.get(Material,legacy_id).url.startswith('https://rutube.ru/')
        assert LearningProgress.query.filter_by(user_id=2,material_id=legacy_id).count()==1
        assert Material.query.filter_by(catalog_key='git-video').one().title=='Название организатора'
        assert LearningProgress.query.filter_by(material_id=first.id,user_id=2).count()==1
        rows=Material.query.filter(Material.catalog_key.is_not(None)).all()
        assert len(rows)==16 and all(m.language=='ru' and m.kind in MATERIAL_KINDS for m in rows)
        assert all(m.url.startswith('https://rutube.ru/video/') for m in rows if m.kind=='video')
    login(client,'captain')
    result=client.get('/api/hackathons/1/materials')
    assert result.status_code==200
    assert any(m['kind']=='assignment' and not m['url'] for m in result.json['items'])
    assert any(m['kind']=='presentation' and m['url'].startswith('/learning/') for m in result.json['items'])


def test_material_formats_and_russian_language_are_checked_server_side(client):
    login(client,'organizer')
    base={'title':'Запись','topic':'Разработка','kind':'video','url':'https://rutube.ru/video/example/'}
    assert client.post('/api/hackathons/1/materials',json={**base,'kind':'unrelated'}).status_code==400
    assert client.post('/api/hackathons/1/materials',json={**base,'language':'en'}).status_code==400
    assert client.post('/api/hackathons/1/materials',json={**base,'url':''}).status_code==400
    assert client.post('/api/hackathons/1/materials',json={'title':'Практика','kind':'assignment','description':'Составьте план.','url':''}).status_code==201
    assert client.post('/api/hackathons/1/materials',json=base).status_code==201
    login(client,'captain')
    assert client.post('/api/hackathons/1/materials',json=base).status_code==403
