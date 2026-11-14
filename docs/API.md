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
