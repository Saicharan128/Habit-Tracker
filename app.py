from flask import Flask, render_template, redirect, url_for, request, jsonify
from datetime import datetime, timedelta, date
from models import db, Habit, HabitStatus
import calendar

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///habits.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# --- DEVELOPMENT‐ONLY: drop & recreate tables on each run ---
with app.app_context():
    db.init_app(app)
    db.drop_all()      # ⚠️ wipes data each restart
    db.create_all()

@app.route('/')
def home():
    return redirect(url_for('dashboard'))

@app.route('/dashboard')
def dashboard():
    yesno_habits      = Habit.query.filter_by(habit_type='yesno').all()
    measurable_habits = Habit.query.filter_by(habit_type='measurable').all()

    today = datetime.now().date()
    dates = [today + timedelta(days=i) for i in range(180)]

    rows = HabitStatus.query.filter(HabitStatus.date.in_(dates)).all()
    status_map = {(r.habit_id, r.date): r.status for r in rows}

    return render_template(
        'index.html',
        yesno_habits=yesno_habits,
        measurable_habits=measurable_habits,
        dates=dates,
        status_map=status_map,
        get_day=lambda d: d.strftime('%a').upper()
    )

@app.route('/add-yesno', methods=['GET', 'POST'])
def add_yesno():
    if request.method == 'POST':
        new = Habit(
            name=request.form['name'],
            color=request.form['color'],
            question=request.form['question'],
            frequency=request.form['frequency'],
            reminder=request.form['reminder'],
            notes=request.form.get('notes', ''),
            habit_type='yesno'
        )
        db.session.add(new)
        db.session.commit()
        return redirect(url_for('dashboard'))
    return render_template('add_yesno.html')

@app.route('/add-measurable', methods=['GET', 'POST'])
def add_measurable():
    if request.method == 'POST':
        new = Habit(
            name=request.form['name'],
            color=request.form['color'],
            question=request.form['question'],
            unit=request.form['unit'],
            target=float(request.form['target']),
            target_type=request.form['target_type'],
            frequency=request.form['frequency'],
            reminder=request.form['reminder'],
            notes=request.form.get('notes', ''),
            habit_type='measurable'
        )
        db.session.add(new)
        db.session.commit()
        return redirect(url_for('dashboard'))
    return render_template('add_measurable.html')

@app.route('/update-status', methods=['POST'])
def update_status():
    data = request.get_json()
    hid = data['habit_id']
    d   = datetime.fromisoformat(data['date']).date()
    new_status = data['status']
    hs = HabitStatus.query.filter_by(habit_id=hid, date=d).first()
    if not hs:
        hs = HabitStatus(habit_id=hid, date=d, status=new_status)
        db.session.add(hs)
    else:
        hs.status = new_status
    db.session.commit()
    return jsonify(success=True)

@app.route('/habit/<int:hid>/<ds>')
def detail(hid, ds):
    habit    = Habit.query.get_or_404(hid)
    sel_date = datetime.fromisoformat(ds).date()

    # load all statuses
    rows = HabitStatus.query.filter_by(habit_id=hid).all()
    status_map = {r.date: r.status for r in rows}

    # helper to compute % done
    def pct(done, total):
        return int(done/total*100) if total else 0

    # week/month/year scores
    week  = [sel_date - timedelta(days=i) for i in range(6, -1, -1)]
    score_week  = pct(sum(1 for d in week  if status_map.get(d)=='done'), 7)
    month = [sel_date - timedelta(days=i) for i in range(29, -1, -1)]
    score_month = pct(sum(1 for d in month if status_map.get(d)=='done'), 30)
    year  = [sel_date - timedelta(days=i) for i in range(364, -1, -1)]
    score_year  = pct(sum(1 for d in year  if status_map.get(d)=='done'), 365)
    total_done  = sum(1 for s in status_map.values() if s=='done')

    # history (last 6 weeks)
    history = []
    for wk in range(6, 0, -1):
        start = sel_date - timedelta(days=wk*7 - 1)
        days = [start + timedelta(days=i) for i in range(7)]
        history.append(sum(1 for d in days if status_map.get(d)=='done'))

    # best streak calculation
    best_len = curr = 0
    best_start = best_end = None
    prev = None
    for r in sorted(rows, key=lambda r: r.date):
        if r.status=='done' and prev and (r.date - prev)==timedelta(days=1):
            curr += 1
        elif r.status=='done':
            curr = 1
            streak_start = r.date
        else:
            curr = 0
        if curr > best_len:
            best_len = curr
            best_start = streak_start
            best_end   = r.date
        prev = r.date

    # calendar data for last 4 months
    cal_data = []
    cy, cm = sel_date.year, sel_date.month
    for i in reversed(range(4)):
        m, y = cm - i, cy
        while m < 1:
            m += 12
            y -= 1
        ndays = calendar.monthrange(y, m)[1]
        days = []
        for day in range(1, ndays+1):
            dt = date(y, m, day)
            days.append({'day': day, 'status': status_map.get(dt, 'pending')})
        cal_data.append({'year': y, 'month': calendar.month_abbr[m], 'days': days})

    return render_template('detail.html',
        habit=habit,
        sel_date=sel_date,
        score_week=score_week,
        score_month=score_month,
        score_year=score_year,
        total_done=total_done,
        history=history,
        best_len=best_len,
        best_start=best_start,
        best_end=best_end,
        calendar_data=cal_data
    )

if __name__ == '__main__':
    app.run(debug=True)
