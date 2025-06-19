from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class Habit(db.Model):
    id          = db.Column(db.Integer, primary_key=True)
    name        = db.Column(db.String(100), nullable=False)
    color       = db.Column(db.String(20), nullable=False)
    question    = db.Column(db.String(200), nullable=False)
    # fields for measurable habits
    unit        = db.Column(db.String(20))
    target      = db.Column(db.Float)
    target_type = db.Column(db.String(20))
    frequency   = db.Column(db.String(50), nullable=False)
    reminder    = db.Column(db.String(20), nullable=False)
    notes       = db.Column(db.Text)
    habit_type  = db.Column(db.String(20), default='yesno')

class HabitStatus(db.Model):
    id       = db.Column(db.Integer, primary_key=True)
    habit_id = db.Column(db.Integer, db.ForeignKey('habit.id'), nullable=False)
    date     = db.Column(db.Date, nullable=False)
    status   = db.Column(db.String(10), nullable=False)  # 'pending','done','missed'
    __table_args__ = (
        db.UniqueConstraint('habit_id', 'date', name='unique_habit_date'),
    )
