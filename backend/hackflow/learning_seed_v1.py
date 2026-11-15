"""Versioned Russian learning pack. SQL-only so migrations don't depend on ORM."""
import sqlalchemy as sa

MATERIAL_KINDS=('video','presentation','document','link','webinar','consultation','assignment')
# Titles/descriptions below are HackFlow summaries; linked content stays with its authors.
CATALOG=[
    ('git-video','Git и GitHub: основы командной работы','Командная работа','video','Русскоязычный урок Александра Ламкова: репозиторий, коммиты, ветки и совместная разработка.','https://rutube.ru/video/700de2627cda374e11ad27e4b11f9878/'),
    ('react-video','React: функциональные компоненты','Frontend','video','Русскоязычный урок Александра Ламкова о разделении интерфейса на компоненты.','https://rutube.ru/video/8f8979dd03f3888df3b8b577b62e1fd7/'),
    ('html-video','HTML: структура страницы и теги','Frontend','video','Вводный видеоурок на русском языке от автора курса Александра Ламкова.','https://rutube.ru/video/69866e7899b182b643618c2c5e5290bd/'),
    ('todo-video','Практика: список задач на JavaScript','Frontend','video','Русскоязычная запись практикума: небольшой работающий продукт без фреймворка.','https://rutube.ru/video/da9c7aff63b00a56ca4a684b429d0aee/'),
    ('html-guide','Справочник HTML','Frontend','document','Русскоязычная Дока: структура страницы, формы и семантическая разметка.','https://doka.guide/html/'),
    ('css-guide','CSS и адаптивная вёрстка','Frontend','document','Русскоязычная Дока: оформление, сетки и адаптивность интерфейса.','https://doka.guide/css/'),
    ('js-guide','JavaScript для интерфейсов','Frontend','document','Русскоязычная Дока: язык и работа с браузером.','https://doka.guide/js/'),
    ('js-book','Современный учебник JavaScript','Frontend','link','Русскоязычный учебник с примерами и упражнениями.','https://learn.javascript.ru/'),
    ('git-guide','Git: команды и совместная разработка','Командная работа','document','Краткое русскоязычное руководство Доки по работе с репозиторием.','https://doka.guide/tools/git-cli/'),
    ('a11y-guide','Доступность интерфейса','Дизайн и UX','document','Русскоязычные материалы Доки: клавиатура, формы и доступный интерфейс.','https://doka.guide/a11y/'),
    ('sql-guide','PostgreSQL: данные проекта','Backend','document','Русскоязычное руководство METANIT: таблицы, ключи, запросы и работа с данными.','https://metanit.com/sql/postgresql/'),
    ('python-guide','Python: основы для backend','Backend','document','Русскоязычное руководство METANIT по Python с примерами.','https://metanit.com/python/tutorial/'),
    ('fetch-guide','Запросы к API через fetch','Frontend','document','Русскоязычный учебник: запросы браузера к серверу и обработка ответа.','https://learn.javascript.ru/fetch'),
    ('forms-guide','Формы и работа с пользователем','Frontend','document','Русскоязычная Дока о формах: поля, отправка и семантика.','https://doka.guide/html/form/'),
    ('pitch-slides','Как подготовить защиту проекта','Защита проекта','presentation','Учебная презентация HackFlow на русском: проблема, решение, демонстрация, вклад команды и ограничения.','/learning/hackathon-pitch.html'),
    ('team-practice','Практическое задание: план команды','Командная работа','assignment','Опишите пользователя и проблему вашего кейса. Согласуйте три критерия готовности MVP. Создайте на доске минимум четыре задачи с ответственными и сроками. Обсудите план с назначенным ментором. Отметьте задание после выполнения.',''),
]

LEGACY={
 'https://react.dev/learn': 'react-video',
 'https://react.dev/learn/thinking-in-react': 'react-video',
 'https://flask.palletsprojects.com/en/stable/tutorial/': 'python-guide',
 'https://www.postgresql.org/docs/current/tutorial.html': 'sql-guide',
 'https://git-scm.com/book/ru/v2': 'git-guide',
}
LEGACY_TITLES={'React: практика','React: мышление компонентами','Flask: первый веб-проект','PostgreSQL: основы','Git: совместная разработка'}


def populate_learning(connection,hackathon_id=None):
    """Add missing items; preserve custom rows, completions and edits to keyed rows."""
    meta=sa.MetaData()
    materials=sa.Table('material',meta,autoload_with=connection)
    events=sa.Table('hackathon',meta,autoload_with=connection)
    query=sa.select(events.c.id,events.c.demo_key,events.c.title)
    if hackathon_id is not None: query=query.where(events.c.id==hackathon_id)
    count=0
    by_key={x[0]:x for x in CATALOG}
    for event in connection.execute(query).mappings().all():
        existing=connection.execute(sa.select(materials).where(materials.c.hackathon_id==event['id'])).mappings().all()
        keys={r['catalog_key'] for r in existing if r['catalog_key']}
        # Replace only recognized seed examples in seeded events, preserving row IDs/progress.
        for row in existing:
            key=LEGACY.get(row['url'])
            if (event['demo_key'] or event['title']=='IT Hack 2026') and key and row['title'] in LEGACY_TITLES and not row['catalog_key']:
                _,title,topic,kind,description,url=by_key[key]
                values=dict(title=title,topic=topic,kind=kind,description=description,url=url,language='ru')
                if key not in keys: values['catalog_key']=key
                connection.execute(materials.update().where(materials.c.id==row['id']).values(**values))
                keys.add(key)
        for key,title,topic,kind,description,url in CATALOG:
            if key in keys: continue
            connection.execute(materials.insert().values(hackathon_id=event['id'],catalog_key=key,
                title=title,topic=topic,kind=kind,description=description,url=url,language='ru'))
            keys.add(key);count+=1
    schedule=sa.Table('schedule',meta,autoload_with=connection)
    for old_title,new_title in [('Видеоурок: введение в React (запись)','Видеоурок: компоненты React (запись)'),('Разбор прототипа [демо]','Разбор интерфейса [демо, запись]')]:
        query=schedule.update().where(schedule.c.title==old_title,schedule.c.url.in_(['https://www.youtube.com/watch?v=Tn6-PIqc4UM','https://react.dev/learn']))
        if hackathon_id is not None: query=query.where(schedule.c.hackathon_id==hackathon_id)
        connection.execute(query.values(title=new_title,kind='recording',url='https://rutube.ru/video/8f8979dd03f3888df3b8b577b62e1fd7/'))
    return count
