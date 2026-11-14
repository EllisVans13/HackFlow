import os
import secrets
from datetime import timedelta
import click
from werkzeug.security import generate_password_hash
from .models import *

def register_commands(app):
    @app.cli.command('reminders')
    def reminders():
        from .services import dispatch_reminders
        click.echo(f'Отправлено: {dispatch_reminders()}')

    @app.cli.command('init-admin')
    @click.option('--email',prompt=True)
    @click.option('--nickname',default='Администратор',prompt=True)
    @click.password_option(confirmation_prompt=True)
    def init_admin(email,nickname,password):
        """Создать первого администратора локально, без открытого API."""
        if User.query.filter_by(role='admin').first(): raise click.ClickException('Администратор уже существует.')
        if len(password)<12: raise click.ClickException('Пароль — минимум 12 символов.')
        db.session.add(User(email=email.lower(),nickname=nickname,role='admin',is_owner=True,password_hash=generate_password_hash(password)))
        db.session.commit(); click.echo('Администратор создан.')

    @app.cli.command('reset-password')
    @click.option('--email',prompt=True)
    @click.password_option(confirmation_prompt=True)
    def reset_password(email,password):
        """Восстановление при отсутствии SMTP; только через доступ к серверу."""
        u=User.query.filter_by(email=email.lower()).first()
        if not u or len(password)<12: raise click.ClickException('Аккаунт не найден или пароль короче 12 символов.')
        u.password_hash=generate_password_hash(password); db.session.commit(); click.echo('Пароль изменён.')

    @app.cli.command('seed-showcase')
    @click.option('--password',envvar='DEMO_PASSWORD',required=True)
    def seed_showcase(password):
        from .demo import enrich
        enrich(password); click.echo('Демоданные добавлены.')

    @app.cli.command('seed-demo')
    @click.option('--password',envvar='DEMO_PASSWORD',required=True,help='Демонстрационный пароль, минимум 12 символов.')
    def seed_demo(password):
        """Предзаполнить демонстрационный хакатон. Не создаёт администратора."""
        if not Hackathon.query.first(): seed(password)
        from .demo import enrich
        enrich(password); click.echo('Демо готово: participant, captain, organizer, jury @hackflow.test. Администратор: flask init-admin.')

def seed(password):
    if len(password)<12: raise click.ClickException('DEMO_PASSWORD должен содержать минимум 12 символов.')
    if Hackathon.query.first(): raise click.ClickException('База уже заполнена. Seed не изменяет существующие данные.')
    users=[]
    for name,nick,role in [('participant','Александр','participant'),('captain','Мария Волкова','participant'),('organizer','Анна Смирнова','organizer'),('jury','Дмитрий Орлов','participant')]:
        u=User(email=name+'@hackflow.test',nickname=nick,role=role,password_hash=generate_password_hash(password)); db.session.add(u); users.append(u)
    db.session.flush(); participant,captain,org,jury=users
    current=now()
    h=Hackathon(title='IT Hack 2026',description='Создавай полезные продукты. Объединяйся с единомышленниками, решай реальные задачи бизнеса и превращай идеи в работающие решения.',rules='Команды от 1 до 5 участников. Выберите один кейс. Сдайте PDF-презентацию, репозиторий GitHub и ссылку на продукт до дедлайна. Соблюдайте академическую честность. При равных баллах выше проект, отправленный раньше.',start_at=current-timedelta(days=1),end_at=current+timedelta(days=7),registration_deadline=current+timedelta(days=2),submission_deadline=current+timedelta(days=5),status='active',team_size=5,closed=True)
    db.session.add(h); db.session.flush()
    db.session.add_all([EventRole(user_id=org.id,hackathon_id=h.id,role='organizer'),EventRole(user_id=jury.id,hackathon_id=h.id,role='jury'),Admission(hackathon_id=h.id,email=participant.email),Admission(hackathon_id=h.id,email=captain.email)])
    c=Case(hackathon_id=h.id,title='Единая среда для студенческих хакатонов',company='Актион',description='Участники переключаются между мессенджерами, таск-трекерами и образовательными сервисами. Создайте одно пространство, которое объединит весь путь команды.',requirements='Авторизация, команды, доска задач, чат, учебные материалы, расписание и сдача проекта.',expected='Работающая веб-платформа с сохранением данных, доступная с компьютера и телефона.')
    db.session.add(c); db.session.flush()
    db.session.add(Case(hackathon_id=h.id,title='Персональная траектория обучения',company='Актион Образование',description='Помогите студенту построить учебный план и отслеживать прогресс.',requirements='Каталог материалов, цели, рекомендации и прогресс.',expected='Прототип образовательного продукта.'))
    t=Team(hackathon_id=h.id,captain_id=captain.id,name='Код будущего',description='Делаем сложное простым. Ищем frontend-разработчика и дизайнера.',code='HACKFLOW26',case_id=c.id)
    db.session.add(t); db.session.flush(); db.session.add(Membership(user_id=captain.id,team_id=t.id,hackathon_id=h.id))
    for title,status,desc in [('Изучить бизнес-кейс','done','Собрать требования и определить основной сценарий.'),('Спроектировать пользовательский путь','doing','Описать путь участника от входа до сдачи проекта.'),('Подготовить прототип интерфейса','doing','Продумать навигацию и основные экраны.'),('Реализовать REST API','todo','Настроить Flask Blueprints и проверки доступа.'),('Подготовить презентацию','todo','Показать проблему, решение и демонстрационный сценарий.')]:
        db.session.add(Task(team_id=t.id,creator_id=captain.id,assignee_id=captain.id,title=title,status=status,description=desc,deadline=current+timedelta(days=3)))
    db.session.add(Message(team_id=t.id,author_id=captain.id,text='Привет! Добро пожаловать в команду. Начнём с кейса и распределим задачи 🚀'))
    track=Track(hackathon_id=h.id,title='От идеи до работающего продукта'); db.session.add(track); db.session.flush()
    for title,kind,topic,url,desc in [('Flask: первый веб-проект','document','Backend','https://flask.palletsprojects.com/en/stable/tutorial/','Официальное руководство по созданию приложения.'),('React: мышление компонентами','document','Frontend','https://react.dev/learn/thinking-in-react','Как разделить интерфейс на компоненты.'),('Git: совместная разработка','document','Командная работа','https://git-scm.com/book/ru/v2','Ветки, коммиты и совместная работа над проектом.'),('PostgreSQL: основы','document','Backend','https://www.postgresql.org/docs/current/tutorial.html','Таблицы, ограничения и работа с данными.')]:
        db.session.add(Material(hackathon_id=h.id,track_id=track.id,title=title,kind=kind,topic=topic,url=url,description=desc))
    for days,title,kind,speaker,url in [(0,'Старт и разбор кейса','opening','Команда Актион',''),(1,'Архитектура веб-продукта','consultation','Дмитрий Орлов',''),(3,'Подготовка к защите','workshop','Анна Смирнова',''),(5,'Дедлайн сдачи проектов','deadline','',''),(6,'Финальная защита','final','','')]:
        db.session.add(Schedule(hackathon_id=h.id,title=title,description='Демонстрационное событие. Организатор добавит действующую ссылку перед началом.',starts_at=current+timedelta(days=days),kind=kind,speaker=speaker,url=url))
    # Public recorded technical webinar. Clearly distinguished from live demo events.
    db.session.add(Schedule(hackathon_id=h.id,title='Видеоурок: введение в React (запись)',description='Открытая запись из официального учебного курса React.',starts_at=current+timedelta(hours=2),kind='recording',speaker='React',url='https://www.youtube.com/watch?v=Tn6-PIqc4UM'))
    for title,maximum in [('Функциональность',30),('Оригинальность',20),('Техническая реализация',20),('Дизайн и удобство',15),('Презентация и защита',15)]: db.session.add(Criterion(hackathon_id=h.id,title=title,maximum=maximum))
    for u in [participant,captain]:
        db.session.add(Notification(user_id=u.id,title='Вы допущены к IT Hack 2026',text='Присоединяйтесь к команде по коду HACKFLOW26 и начинайте работу.'))
    db.session.add(Activity(user_id=captain.id,action='team.create')); db.session.commit()
