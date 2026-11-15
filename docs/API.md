# REST API

Все приватные маршруты требуют session cookie. Мутации дополнительно требуют заголовок `X-CSRFToken`, полученный через `GET /api/auth/csrf`. Формат ошибок — `{ "error": "описание" }`, конфликты 409, запрет 403, отсутствие входа 401.

| Область | Маршруты |
|---|---|
| Проверка | GET /api/health |
| Доступ | GET /auth/csrf, /auth/me; POST /auth/register, /auth/login, /auth/logout, /auth/forgot, /auth/reset |
| События | GET/POST /hackathons; GET/PATCH /hackathons/:id |
| Допуск | POST /hackathons/:id/admissions: JSON email или multipart CSV file |
| Команды | GET/POST /hackathons/:id/teams; POST /hackathons/:id/join; GET/PATCH/DELETE /teams/:id |
| Заявки | POST /teams/:id/requests; PATCH /teams/:id/requests/:request |
| Кейсы | GET /hackathons/:id (cases); POST /hackathons/:id/cases |
| Доска | GET/POST /teams/:id/tasks; PATCH/DELETE /tasks/:id |
| Чат | GET/POST /teams/:id/messages?channel=team или organizer; POST /teams/:id/messages/read |
| Обучение | GET/POST /hackathons/:id/materials; POST /materials/:id/complete |
| Расписание | GET/POST /hackathons/:id/schedule; PATCH/DELETE /schedule/:id |
| Объявления | POST /hackathons/:id/announcements |
| Сдача | POST /teams/:id/uploads (file, purpose: presentation/source), /audit, /submission |
| Файлы | GET /uploads/:id |
| Решения | GET /hackathons/:id/submissions; PATCH /submissions/:id/anonymous |
| Жюри | POST /hackathons/:id/jury-invitations; DELETE /jury-invitations/:id; POST /jury-invitations/accept |
| Назначение | POST /submissions/:id/assign (user_id, kind: jury/expert) |
| Проверка | GET /hackathons/:id/jury; GET /jury/:id; POST /jury/:id/score, /jury/:id/flag |
| Критерии | PUT /hackathons/:id/criteria (items: [{title,maximum}]) |
| CodeCheck | GET/POST /submissions/:id/codecheck |
| GitHub | GET /teams/:id/github |
| Консультации | GET/POST /teams/:id/consultation; POST /teams/:id/consultation/assign; GET /expert/consultations |
| Обратная связь | GET /expert/assignments; GET/POST /submissions/:id/feedback; GET /hackathons/:id/experts |
| Рейтинг | GET /hackathons/:id/ranking; POST /hackathons/:id/publish; GET /ratings |
| Peer Review | GET/POST /hackathons/:id/peer; POST /peer/:submission; POST /hackathons/:id/peer/publish |
| Апелляции | GET/POST /hackathons/:id/appeals; PATCH /appeals/:id |
| Профиль | GET/PATCH /profile |
| Уведомления | GET /notifications; POST /notifications/read |
| Аналитика | GET /hackathons/:id/analytics, /hackathons/:id/staff, /hackathons/:id/roadmap |
| Администратор | GET /admin/users, /admin/audit; PATCH /admin/users/:id |

Кроме /api/health и /api/auth/csrf, в строках таблицы опущен префикс `/api`. Каталог хакатонов доступен без входа; закрытые данные — по допуску.

Создание задачи:

```json
{"title":"Собрать прототип","description":"Основной пользовательский путь","assignee_id":1,"deadline":"2026-12-01T12:00:00Z"}
```

Сдача:

```json
{"title":"Название","description":"Описание","github":"https://github.com/owner/repo","demo":"https://product.example.com","presentation_id":1}
```

Оценка (ID критериев берутся из API, не фиксированы):

```json
{"scores":{"1":27,"2":18,"3":18,"4":14,"5":13},"comment":"Экспертный комментарий"}
```

Принятие апелляции с изменением оценки: status=accepted, response=причина, jury_id, scores и comment. Система меняет конкретную оценку жюри, а не добавляет произвольные баллы поверх 100.

Дополнительно: POST /api/profile/avatar, POST /api/hackathons/:id/cover (multipart file PNG/JPEG, до 2 МБ), GET /api/media/:token, GET /api/hackathons/:id/learning-analytics.


Приглашения капитана: GET /api/teams/:id/candidates?q=ник, POST /api/teams/:id/invitations {user_id}, GET /api/team-invitations, POST /api/team-invitations/:id/respond {accept: true/false}.
Профиль level содержит earned (XP по каждому хакатону), thresholds, current, required, remaining и progress.


Модерация: GET /api/admin/hackathons; PATCH /api/admin/hackathons/:id {difficulty: easy|medium|hard, approval: approved|rejected, comment}. Доступно только администратору для заявок pending. POST /api/hackathons принимает difficulty и создаёт заявку pending. Каталог скрывает неодобренные мероприятия от посторонних. Опыт по опубликованным завершённым мероприятиям: easy=70, medium=150, hard=240; уровни 0–6 с порогами [0,250,700,1400,2500,4000,6000].

Владение: POST /api/admin/ownership {user_id} — только текущий владелец, получатель активный admin; прежний владелец сохраняет роль admin. User.is_owner возвращается в auth/me и списке пользователей. PATCH /api/admin/users/:id поддерживает роли participant/organizer/jury/admin, а назначение на событие — hackathon_id и event_role (organizer/jury). POST /api/hackathons/:id/jury-members {email} — назначение зарегистрированного пользователя жюри организатором своего хакатона. Все операции защищены проверками прав и CSRF.

DELETE /api/hackathons/:id/jury-members/:user — снять жюри своего хакатона (организатор события либо администратор). Отзывает событийную роль, назначения на проверки этого события и неиспользованные приглашения; оценки/история и роли других событий сохраняются.


## Менторы и образовательный трек

- `GET /hackathons/:id/mentors` — активные аккаунты mentor для зарегистрированных участников и организатора; профессиональные данные без email.
- `PUT /teams/:id/mentor {user_id}` — выбрать/сменить основного ментора; только капитан или организатор хакатона.
- `DELETE /teams/:id/mentor` — снять назначение; те же права. После завершения смена запрещена.
- `GET /mentor/teams` — собственные назначения аккаунта mentor.
- `GET /mentor/teams/:id` — кейс, состав, задачи и отправленный проект назначенной команды.
- Назначенный mentor читает `/teams/:id/tasks`, `/teams/:id/messages` (только team), `/uploads/:id`, материалы и расписание события; пишет рекомендации в `/teams/:id/consultation` и `/submissions/:id/feedback`. Изменение задач, отправка в командный чат, участие, сдача и оценивание запрещены.
- `PATCH /profile`: mentor_bio (до 3000 символов), mentor_skills (до 300) только у mentor. Роль меняет администратор.
- Материалы возвращают language; форматы: video/presentation/document/link/webinar/consultation/assignment. Для новых поддерживается ru; внешняя ссылка обязательна, кроме assignment. У задания без ссылки обязательно описание.

Пути указаны без префикса `/api`.


## Публичные итоги и архив

- `GET /api/public/results` — завершённые одобренные хакатоны, публичные поля карточки и results_published. Без входа/допуска.
- `GET /api/public/hackathons/:id/results` — официальный рейтинг завершённого одобренного мероприятия с опубликованными результатами. Для остальных состояний — 404 даже у организатора. Ответ: hackathon, items (place/team/title/score/criteria), критерии и tie_rule. Нет пользователей, файлов, приватных ссылок или индивидуальных судейских комментариев.
- `/results` и `/results/:id` — React-страницы для гостей и всех аккаунтов.

Внутренний `/api/hackathons/:id/ranking` сохранён для существующего рабочего интерфейса с прежними проверками входа/допуска. Публичные результаты читаются через отдельный public API.


## QR диплома и возврат из результатов

Поле verify_url диплома указывает на `/results/:hackathon_id?certificate=:public_id`. Публичный API `/api/public/hackathons/:id/results` принимает необязательный параметр certificate; для действительного документа этого мероприятия добавляет certificate {valid, number, recipient_name, team_name, organizer_name, place}. Для отозванного, неизвестного или чужого токена возвращает только {valid:false}. Без токена реквизиты дипломов не выдаются. Доступ к PDF по-прежнему ограничен. Старый HTML endpoint проверки токена сохранён.

Из кабинета используется маршрут `/#results/:id`: сохраняется меню, кнопки возвращают в `#archive` и `#hackathons`. Публичный `/results/:id` открывается отдельно и имеет ссылку «Все хакатоны» на `/#hackathons`.


## Проверка исходников и отчёт жюри

- `POST /api/submissions/:id/codecheck` — организатор хакатона выполняет повторную проверку; результат сохраняется, назначенному жюри отправляется уведомление без авторских данных.
- При `POST /api/submissions/:id/assign` с kind=jury проверка автоматически подготавливается.
- `GET /api/jury/:id` включает codecheck с безопасным списком полей; только назначенное жюри и после ручного обезличивания.
- `POST /api/jury/:id/codecheck {force:false}` — получить актуальную проверку; force=true принудительно пересчитывает. Те же проверки роли/назначения/обезличивания.
- GET отчёта не запускает анализ и отмечает stale при изменении версии метода/корпуса (ID отправок и immutable source_id). Интерфейс запускает POST при открытии работы.
- Статусы: not_started, completed, partial, insufficient_data, unavailable, error; stale вычисляется при выдаче. Есть checked_at, max_similarity (null если не вычислено), files_total/files_analyzed, compared_projects, matches с анонимным code и нормализованными fragments, skipped с анонимными причинами, limitations. Файлы, пути, авторы и внутренний corpus_signature в ответ жюри не включаются.
- Расчёт оценок не зависит от CodeCheck. Уведомления дедуплицируются по отправке/корпусу/статусу/судье.


## Взвешенное оценивание и встречи (a18)

- Новые мероприятия используют peer_enabled=true: итог = 0.8 × среднее жюри + 0.2 × среднее трёх команд. Сохранены legacy-мероприятия с прежней схемой. XP по сложности отдельно.
- POST /api/hackathons/:id/peer/distribute — организатор, минимум четыре сданных проекта с anonymous_ready и anonymous_file_id. Ровно три входящие и исходящие назначения, без самооценки; существующие назначения сохраняются.
- GET /api/hackathons/:id/peer/progress — готовность оценок организатору.
- POST /api/submissions/:id/anonymous-file — организатор, multipart file PDF + confirmed=true. Очищает метаданные/аннотации; видимое содержание проверяет организатор. После оценок подмена запрещена.
- GET /api/peer/:id/material — только член назначенной команды или организатор; ?download=1 для скачивания.
- GET /api/jury/:id/material — только назначенное анонимное жюри.
- POST /api/peer/:id — один отзыв капитана назначенной команды, критерии из 100. Публикация official/peer блокируется до трёх разных командных оценок каждой работы. Повторный отзыв и самооценка запрещены.
- Рейтинг содержит jury_score/peer_score, jury_component/peer_component, peer_count/peer_enabled и итог score из 100.
- Schedule возвращает/принимает duration_minutes (5–1440), provider (yandex/zoom/link/offline), starts_at ISO8601 с часовым поясом или UTC, url. Внешние комнаты создаются пользователем в сервисе; API HackFlow их не создаёт.
- Новая глобальная роль expert: назначенные проекты/рекомендации и личные настройки, без участия/оценок/управления.
- User.is_demo ограничивает публичного демоадминистратора демоданными. Резервированный домен demo.hackflow.test нельзя использовать для веб-регистрации. Демоstaff не назначается на реальные проекты.
