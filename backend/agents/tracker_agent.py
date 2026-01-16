from models import db, Event
class TrackerAgent:
    def __init__(self):
        pass
    def update(self, event):
        db.session.commit()
