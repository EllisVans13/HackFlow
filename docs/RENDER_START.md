# Запуск Docker-сервиса на Render

В Settings выберите Branch `main` и Docker Command:

```text
python -m hackflow.render_start
```

Команда применяет миграции и затем запускает Gunicorn с одним worker на порту из `PORT` (по умолчанию 8000). При ошибке миграции сервер не запускается, а причина остаётся в Logs. Кавычки и `sh -c` не нужны. Демоаккаунты и администратор автоматически не создаются.

`DATABASE_URL` должен содержать Internal Database URL PostgreSQL Render со схемой `postgresql+psycopg://`. Также задайте случайный постоянный `SECRET_KEY`, `COOKIE_SECURE=true`, `RATELIMIT_STORAGE_URI=memory://`. `PUBLIC_URL` и `CORS_ORIGINS` — фактический HTTPS-адрес сервиса без завершающего слеша. Значения секретов не публикуйте.
