# Запуск Docker-сервиса на Render

В Settings выберите Branch `main` и Docker Command:

```text
python -m hackflow.render_start
```

Команда применяет миграции и затем запускает Gunicorn с одним worker на порту из `PORT` (по умолчанию 8000). При ошибке миграции сервер не запускается, а причина остаётся в Logs. Кавычки и `sh -c` не нужны. Демоаккаунты и администратор автоматически не создаются.

`DATABASE_URL` должен содержать Internal Database URL PostgreSQL Render со схемой `postgresql+psycopg://`. Также задайте случайный постоянный `SECRET_KEY`, `COOKIE_SECURE=true`, `RATELIMIT_STORAGE_URI=memory://`. `PUBLIC_URL` и `CORS_ORIGINS` — фактический HTTPS-адрес сервиса без завершающего слеша. Значения секретов не публикуйте.


После миграции a18 оба entrypoint (`python -m hackflow.render_start` и `python start_render.py`) добавляют новый демонстрационный набор Peer Review с публичными доступами из README. SEED_REVIEW_DEMO=false отключает этот набор на Render. Полный владелец и существующие пароли не сбрасываются; публичный демоадминистратор ограничен только демоданными. В Compose миграционный сервис использует общий с приложением upload_data, чтобы демо-PDF открывались в веб-сервисе.
