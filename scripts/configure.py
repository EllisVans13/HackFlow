"""python scripts/configure.py — create local .env without touching existing secrets."""
from pathlib import Path
import secrets
root=Path(__file__).resolve().parents[1]
target=root/'.env'
if target.exists(): raise SystemExit('.env уже существует: изменения не внесены.')
password=secrets.token_hex(24)
text=(root/'.env.example').read_text(encoding='utf-8').replace('replace-with-at-least-32-random-characters',secrets.token_hex(32)).replace('replace-with-random-alphanumeric-password',password)
target.write_text(text,encoding='utf-8'); target.chmod(0o600)
print('.env создан для локального запуска. Для публикации задайте COOKIE_SECURE=true, PUBLIC_URL и SITE_DOMAIN.')
