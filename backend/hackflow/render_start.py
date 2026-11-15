"""Start Render with migrations: python -m hackflow.render_start."""
import os
from pathlib import Path
import subprocess
import sys


def main():
    os.chdir(Path(__file__).resolve().parents[1])
    subprocess.run(
        [sys.executable, '-m', 'flask', '--app', 'wsgi', 'db', 'upgrade'],
        check=True,
    )
    if os.environ.get('SEED_REVIEW_DEMO','true').lower()=='true':
        subprocess.run([sys.executable,'-m','flask','--app','wsgi','seed-review-demo'],check=True)
    # Replace this process so Gunicorn receives Render's shutdown signals.
    os.execv(sys.executable, [
        sys.executable, '-m', 'gunicorn',
        '--bind', '0.0.0.0:' + os.environ.get('PORT', '8000'),
        '--workers', '1', '--threads', '4', '--timeout', '120', 'wsgi:app',
    ])


if __name__ == '__main__':
    main()
