from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import calendar

app = Flask(__name__)
app.secret_key = 'your-secret-key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ------------------ Models ------------------
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)

class Habit(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    type = db.Column(db.String(50), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    question = db.Column(db.String(255))
    notes = db.Column(db.Text)
    color = db.Column(db.String(20))

class Measurable(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    question = db.Column(db.String(255))
    unit_target = db.Column(db.String(50), nullable=False)
    target_type = db.Column(db.String(20), nullable=False)  # Atleast or Atmost
    notes = db.Column(db.Text)
    color = db.Column(db.String(20))

class HabitLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    habit_id = db.Column(db.Integer, db.ForeignKey('habit.id'), nullable=False)
    date = db.Column(db.String(10), nullable=False)  # 'YYYY-MM-DD'
    value = db.Column(db.Boolean)

class MeasurableLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    measurable_id = db.Column(db.Integer, db.ForeignKey('measurable.id'), nullable=False)
    date = db.Column(db.String(10), nullable=False)
    value = db.Column(db.Float)

class Journal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    date = db.Column(db.String(10), nullable=False)  # Format: YYYY-MM-DD
    content = db.Column(db.Text, nullable=True)

# ------------------ Routes ------------------
@app.route('/')
def home():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    username = session.get('username')
    year = request.args.get('year', type=int)
    month = request.args.get('month', type=int)
    today = datetime.today()

    if not year or not month:
        year = today.year
        month = today.month

    days_in_month = calendar.monthrange(year, month)[1]
    days = []
    for day in range(1, days_in_month + 1):
        date_obj = datetime(year, month, day)
        days.append({
            'day': day,
            'weekday': date_obj.strftime('%a'),
            'date_str': date_obj.strftime('%Y-%m-%d'),
            'is_today': day == today.day and month == today.month and year == today.year
        })

    start_date = f"{year}-{month:02d}-01"
    end_date = f"{year}-{month:02d}-{days_in_month:02d}"

    habit_logs = HabitLog.query.join(Habit).filter(
        Habit.user_id == session['user_id'],
        HabitLog.date.between(start_date, end_date)
    ).all()

    measurable_logs = MeasurableLog.query.join(Measurable).filter(
        Measurable.user_id == session['user_id'],
        MeasurableLog.date.between(start_date, end_date)
    ).all()

    # Separate badge maps
    habit_badges = {}
    measurable_badges = {}

    for log in habit_logs:
        if log.value:  # Only if marked "Yes"
            habit = Habit.query.get(log.habit_id)
            if habit:
                color = habit.color or '#60a5fa'
                habit_badges.setdefault(log.date, set()).add(color)

    for log in measurable_logs:
        if log.value and log.value > 0:
            measurable = Measurable.query.get(log.measurable_id)
            if measurable:
                color = measurable.color or '#22c55e'
                measurable_badges.setdefault(log.date, set()).add(color)

    month_name = datetime(year, month, 1).strftime('%B %Y')
    next_month, next_year = (1, year + 1) if month == 12 else (month + 1, year)
    prev_month, prev_year = (12, year - 1) if month == 1 else (month - 1, year)
    show_prev = (year > today.year) or (year == today.year and month > today.month)

    return render_template('home.html', username=username, days=days, month_name=month_name,
                           next_year=next_year, next_month=next_month,
                           prev_year=prev_year, prev_month=prev_month,
                           show_prev=show_prev,
                           habit_badges=habit_badges,
                           measurable_badges=measurable_badges)


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']

        if not username or not password:
            flash('Please fill out both fields', 'error')
            return redirect(url_for('register'))

        hashed_password = generate_password_hash(password)
        if User.query.filter_by(username=username).first():
            flash('Username already taken', 'error')
            return redirect(url_for('register'))

        new_user = User(username=username, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()

        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']

        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            session['username'] = username
            flash('Login successful!', 'success')
            return redirect(url_for('home'))
        else:
            flash('Invalid username or password', 'error')
            return redirect(url_for('login'))

    return render_template('login.html')

@app.route('/add_habit', methods=['POST'])
def add_habit():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if request.form.get('type') == 'measurable':
        new_measurable = Measurable(
            user_id=session['user_id'],
            name=request.form.get('name'),
            question=request.form.get('question'),
            unit_target=request.form.get('unit_target'),
            target_type=request.form.get('target_type'),
            notes=request.form.get('notes'),
            color=request.form.get('color')
        )
        db.session.add(new_measurable)
    else:
        new_habit = Habit(
            user_id=session['user_id'],
            type=request.form.get('type'),
            name=request.form.get('name'),
            question=request.form.get('question'),
            notes=request.form.get('notes'),
            color=request.form.get('color')
        )
        db.session.add(new_habit)

    db.session.commit()
    flash("Habit added successfully", "success")
    return redirect(url_for('home'))

@app.route('/day_data/<date_str>')
def day_data(date_str):
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401

    user_id = session['user_id']
    habits = Habit.query.filter_by(user_id=user_id).all()
    measurables = Measurable.query.filter_by(user_id=user_id).all()

    habit_logs = {log.habit_id: log.value for log in HabitLog.query.filter_by(date=date_str).all()}
    measurable_logs = {log.measurable_id: log.value for log in MeasurableLog.query.filter_by(date=date_str).all()}

    return jsonify({
        'habits': [{'id': h.id, 'name': h.name, 'question': h.question} for h in habits],
        'measurables': [{'id': m.id, 'name': m.name, 'question': m.question} for m in measurables],
        'habit_logs': habit_logs,
        'measurable_logs': measurable_logs
    })

@app.route('/update_habit', methods=['POST'])
def update_habit():
    habit_id = request.form['habit_id']
    date = request.form['date']
    value = request.form['value'] == 'true'

    log = HabitLog.query.filter_by(habit_id=habit_id, date=date).first()
    if not log:
        log = HabitLog(habit_id=habit_id, date=date, value=value)
        db.session.add(log)
    else:
        log.value = value
    db.session.commit()
    return 'OK'

@app.route('/update_measurable', methods=['POST'])
def update_measurable():
    measurable_id = request.form['measurable_id']
    date = request.form['date']
    value = float(request.form['value'])

    log = MeasurableLog.query.filter_by(measurable_id=measurable_id, date=date).first()
    if not log:
        log = MeasurableLog(measurable_id=measurable_id, date=date, value=value)
        db.session.add(log)
    else:
        log.value = value
    db.session.commit()
    return 'OK'

@app.route('/habit_analysis')
def habit_analysis():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    from datetime import date
    today = date.today()
    year, month = today.year, today.month
    user_id = session['user_id']

    # Get all habits
    habits = Habit.query.filter_by(user_id=user_id).all()

    # Get logs for current month
    logs = HabitLog.query.join(Habit).filter(
        Habit.user_id == user_id,
        HabitLog.date.like(f"{year}-{month:02d}-%"),
        HabitLog.value == True
    ).all()

    # Group logs by habit and collect marked "yes" dates
    from collections import defaultdict
    marked_dates = defaultdict(list)
    for log in logs:
        marked_dates[log.habit_id].append(log.date)

    import calendar
    month_days = calendar.monthrange(year, month)[1]
    calendar_days = [
        {
            'day': day,
            'date_str': f"{year}-{month:02d}-{day:02d}"
        }
        for day in range(1, month_days + 1)
    ]

    return render_template("habit_analysis.html", habits=habits, marked_dates=marked_dates,
                           calendar_days=calendar_days, month=month, year=year)

@app.route('/habit_visual/<int:habit_id>')
def habit_visual(habit_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    import calendar
    from datetime import datetime, timedelta
    from collections import defaultdict

    view = request.args.get('view', 'month')  # options: week, month, year
    habit = Habit.query.filter_by(id=habit_id, user_id=session['user_id']).first_or_404()
    logs = HabitLog.query.filter_by(habit_id=habit.id).order_by(HabitLog.date).all()

    log_map = {log.date: log.value for log in logs}
    today = datetime.today()

    labels = []
    values = []
    yes_count = 0
    no_count = 0
    streak = 0
    longest_streak = 0
    last_yes = None

    if view == "week":
        # Week starts on Sunday
        days_since_sunday = (today.weekday() + 1) % 7
        start_date = today - timedelta(days=days_since_sunday)
        days = [(start_date + timedelta(days=i)).date() for i in range(7)]
        labels = [d.strftime("%a %d") for d in days]

        for d in days:
            date_str = d.strftime("%Y-%m-%d")
            value = log_map.get(date_str, False)
            values.append(10 if value else 0)

            if value:
                yes_count += 1
                if last_yes and d == last_yes + timedelta(days=1):
                    streak += 1
                else:
                    streak = 1
                last_yes = d
            else:
                no_count += 1
                streak = 0
            longest_streak = max(longest_streak, streak)

    elif view == "year":
        labels = calendar.month_name[1:]
        values = [0] * 12
        for log in logs:
            if log.value:
                month = int(log.date[5:7])
                values[month - 1] += 10
        yes_count = sum(1 for v in values if v > 0)
        no_count = 12 - yes_count
        return render_template("habit_visual.html", habit=habit, view=view,
                               labels=labels, values=values,
                               yes_count=yes_count, no_count=no_count,
                               longest_streak=0)

    else:  # view == "month"
        year, month = today.year, today.month
        month_days = calendar.monthrange(year, month)[1]
        days = [datetime(year, month, day).date() for day in range(1, month_days + 1)]
        labels = [d.strftime("%b %d") for d in days]

        for d in days:
            date_str = d.strftime("%Y-%m-%d")
            value = log_map.get(date_str, False)
            values.append(10 if value else 0)

            if value:
                yes_count += 1
                if last_yes and d == last_yes + timedelta(days=1):
                    streak += 1
                else:
                    streak = 1
                last_yes = d
            else:
                no_count += 1
                streak = 0
            longest_streak = max(longest_streak, streak)

    return render_template("habit_visual.html", habit=habit, view=view,
                           labels=labels, values=values,
                           yes_count=yes_count, no_count=no_count,
                           longest_streak=longest_streak)

@app.route('/measurable_analysis')
def measurable_analysis():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    from datetime import datetime
    import calendar
    from collections import defaultdict

    today = datetime.today()
    year, month = today.year, today.month
    user_id = session['user_id']

    measurables = Measurable.query.filter_by(user_id=user_id).all()

    logs = MeasurableLog.query.join(Measurable).filter(
        Measurable.user_id == user_id,
        MeasurableLog.date.like(f"{year}-{month:02d}-%")
    ).all()

    marked_units = defaultdict(dict)
    for log in logs:
        marked_units[log.measurable_id][log.date] = log.value

    days = [
        {
            'day': d,
            'date_str': f"{year}-{month:02d}-{d:02d}"
        }
        for d in range(1, calendar.monthrange(year, month)[1] + 1)
    ]

    return render_template("measurable_analysis.html", measurables=measurables,
                           marked_units=marked_units, calendar_days=days,
                           month=month, year=year)

@app.route('/measurable_visual/<int:measurable_id>')
def measurable_visual(measurable_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    import calendar
    from datetime import datetime, timedelta
    from collections import defaultdict

    view = request.args.get('view', 'month')
    m = Measurable.query.filter_by(id=measurable_id, user_id=session['user_id']).first_or_404()
    logs = MeasurableLog.query.filter_by(measurable_id=m.id).order_by(MeasurableLog.date).all()

    log_map = {log.date: log.value for log in logs}
    today = datetime.today()

    labels = []
    values = []
    valid_values = []

    if view == "week":
        # Week starts Sunday
        days_since_sunday = (today.weekday() + 1) % 7
        start_date = today - timedelta(days=days_since_sunday)
        days = [(start_date + timedelta(days=i)).date() for i in range(7)]
        labels = [d.strftime("%a %d") for d in days]

    elif view == "year":
        labels = calendar.month_name[1:]
        values = [0] * 12
        for log in logs:
            month = int(log.date[5:7])
            values[month - 1] += float(log.value)
        avg = round(sum(values) / max(1, len([v for v in values if v > 0])), 2)
        return render_template("measurable_visual.html", m=m, view=view,
                               labels=labels, values=values, avg=avg,
                               highest=max(values), lowest=min(values))

    else:  # month
        year, month = today.year, today.month
        days = [datetime(year, month, d).date() for d in range(1, calendar.monthrange(year, month)[1] + 1)]
        labels = [d.strftime("%b %d") for d in days]

    if view in ['week', 'month']:
        for d in days:
            date_str = d.strftime("%Y-%m-%d")
            val = float(log_map.get(date_str, 0))
            values.append(val)
            if val > 0:
                valid_values.append(val)

        avg = round(sum(valid_values) / len(valid_values), 2) if valid_values else 0
        high = max(valid_values) if valid_values else 0
        low = min(valid_values) if valid_values else 0

        return render_template("measurable_visual.html", m=m, view=view,
                               labels=labels, values=values,
                               avg=avg, highest=high, lowest=low)

@app.route('/journal/<date>', methods=['GET'])
def get_journal(date):
    if 'user_id' not in session:
        return '', 401
    entry = Journal.query.filter_by(user_id=session['user_id'], date=date).first()
    return entry.content if entry else ''

@app.route('/journal/<date>', methods=['POST'])
def save_journal(date):
    if 'user_id' not in session:
        return '', 401
    content = request.form.get('content', '')
    entry = Journal.query.filter_by(user_id=session['user_id'], date=date).first()
    if entry:
        entry.content = content
    else:
        entry = Journal(user_id=session['user_id'], date=date, content=content)
        db.session.add(entry)
    db.session.commit()
    return 'Saved'

@app.route('/all_journals')
def all_journals():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    from collections import defaultdict
    from datetime import datetime

    entries = Journal.query.filter_by(user_id=session['user_id']).order_by(Journal.date.desc()).all()
    
    journal_map = defaultdict(list)
    for entry in entries:
        dt = datetime.strptime(entry.date, "%Y-%m-%d")
        key = dt.strftime("%B %Y")  # e.g. "June 2024"
        journal_map[key].append({'date': entry.date, 'text': entry.content})

    return render_template("all_journals.html", journal_map=journal_map)

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully', 'success')
    return redirect(url_for('login'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
