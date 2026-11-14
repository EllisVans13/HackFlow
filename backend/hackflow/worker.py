"""Periodic internal deadline/webinar notifications. Run one instance."""
import logging
import signal
from threading import Event
from . import create_app
from .models import db
from .services import dispatch_reminders

stop=Event()
signal.signal(signal.SIGTERM,lambda *_:stop.set())
signal.signal(signal.SIGINT,lambda *_:stop.set())
app=create_app()
while not stop.is_set():
    with app.app_context():
        try: dispatch_reminders()
        except Exception:
            db.session.rollback()
            logging.exception('Reminder job failed')
    stop.wait(60)
