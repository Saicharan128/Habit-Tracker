from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, make_response
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, date
import calendar
import json
import io

# Excel export dependencies
try:
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment
    EXCEL_AVAILABLE = True
except ImportError:
    EXCEL_AVAILABLE = False
    print("openpyxl not available. Install with: pip install openpyxl")

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

    from datetime import timedelta

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

    from datetime import timedelta

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

    entries = Journal.query.filter_by(user_id=session['user_id']).order_by(Journal.date.desc()).all()
    
    journal_map = defaultdict(list)
    for entry in entries:
        dt = datetime.strptime(entry.date, "%Y-%m-%d")
        key = dt.strftime("%B %Y")  # e.g. "June 2024"
        journal_map[key].append({'date': entry.date, 'text': entry.content})

    return render_template("all_journals.html", journal_map=journal_map)

# ------------------ Export Routes ------------------
@app.route('/api/export/json')
def export_json():
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401

    try:
        user_id = session['user_id']
        
        # Get all habits
        habits = Habit.query.filter_by(user_id=user_id).all()
        habit_logs = HabitLog.query.join(Habit).filter(Habit.user_id == user_id).all()
        
        # Get all measurables
        measurables = Measurable.query.filter_by(user_id=user_id).all()
        measurable_logs = MeasurableLog.query.join(Measurable).filter(Measurable.user_id == user_id).all()
        
        # Get all journals
        journals = Journal.query.filter_by(user_id=user_id).all()
        
        # Prepare export data
        export_data = {
            'export_info': {
                'export_date': datetime.now().isoformat(),
                'user': session.get('username', 'Unknown'),
                'total_habits': len(habits),
                'total_measurables': len(measurables),
                'total_journal_entries': len(journals)
            },
            'habits': [
                {
                    'id': h.id,
                    'name': h.name,
                    'type': h.type,
                    'question': h.question,
                    'notes': h.notes,
                    'color': h.color,
                    'logs': [
                        {
                            'date': log.date,
                            'value': log.value
                        }
                        for log in habit_logs if log.habit_id == h.id
                    ]
                }
                for h in habits
            ],
            'measurables': [
                {
                    'id': m.id,
                    'name': m.name,
                    'question': m.question,
                    'unit_target': m.unit_target,
                    'target_type': m.target_type,
                    'notes': m.notes,
                    'color': m.color,
                    'logs': [
                        {
                            'date': log.date,
                            'value': log.value
                        }
                        for log in measurable_logs if log.measurable_id == m.id
                    ]
                }
                for m in measurables
            ],
            'journals': [
                {
                    'date': j.date,
                    'content': j.content
                }
                for j in journals
            ],
            'statistics': {
                'habit_completion_rates': {},
                'measurable_averages': {}
            }
        }
        
        # Calculate habit completion rates
        for habit in habits:
            logs = [log for log in habit_logs if log.habit_id == habit.id]
            if logs:
                completed = sum(1 for log in logs if log.value)
                total = len(logs)
                export_data['statistics']['habit_completion_rates'][habit.name] = {
                    'completed': completed,
                    'total': total,
                    'rate': round((completed / total) * 100, 2) if total > 0 else 0
                }
        
        # Calculate measurable averages
        for measurable in measurables:
            logs = [log for log in measurable_logs if log.measurable_id == measurable.id and log.value]
            if logs:
                avg = sum(log.value for log in logs) / len(logs)
                export_data['statistics']['measurable_averages'][measurable.name] = {
                    'average': round(avg, 2),
                    'total_entries': len(logs),
                    'highest': max(log.value for log in logs),
                    'lowest': min(log.value for log in logs)
                }
        
        return jsonify(export_data)
    except Exception as e:
        print(f"JSON export error: {str(e)}")
        return jsonify({'error': f'JSON export failed: {str(e)}'}), 500

@app.route('/api/export/excel')
def export_excel():
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401

    if not EXCEL_AVAILABLE:
        return jsonify({'error': 'Excel export not available. Please install openpyxl using: pip install openpyxl'}), 500

    try:
        user_id = session['user_id']
        
        # Create simple workbook
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Habit Data Export"
        
        # Add summary info
        ws.append(["Habit Tracker Data Export"])
        ws.append(["Export Date:", datetime.now().strftime("%Y-%m-%d %H:%M:%S")])
        ws.append(["User:", session.get('username', 'Unknown')])
        ws.append([])  # Empty row
        
        # Habits section
        ws.append(["=== HABITS ==="])
        ws.append(["Habit Name", "Type", "Question", "Notes", "Color"])
        
        habits = Habit.query.filter_by(user_id=user_id).all()
        for habit in habits:
            ws.append([
                habit.name or "",
                habit.type or "",
                habit.question or "",
                habit.notes or "",
                habit.color or ""
            ])
        
        ws.append([])  # Empty row
        
        # Habit logs section
        ws.append(["=== HABIT LOGS ==="])
        ws.append(["Habit Name", "Date", "Completed"])
        
        habit_logs = db.session.query(HabitLog).join(Habit).filter(Habit.user_id == user_id).all()
        for log in habit_logs:
            habit = Habit.query.get(log.habit_id)
            if habit:
                ws.append([
                    habit.name,
                    log.date,
                    "Yes" if log.value else "No"
                ])
        
        ws.append([])  # Empty row
        
        # Measurables section
        ws.append(["=== MEASURABLES ==="])
        ws.append(["Measurable Name", "Question", "Unit Target", "Target Type", "Notes", "Color"])
        
        measurables = Measurable.query.filter_by(user_id=user_id).all()
        for measurable in measurables:
            ws.append([
                measurable.name or "",
                measurable.question or "",
                measurable.unit_target or "",
                measurable.target_type or "",
                measurable.notes or "",
                measurable.color or ""
            ])
        
        ws.append([])  # Empty row
        
        # Measurable logs section
        ws.append(["=== MEASURABLE LOGS ==="])
        ws.append(["Measurable Name", "Date", "Value"])
        
        measurable_logs = db.session.query(MeasurableLog).join(Measurable).filter(Measurable.user_id == user_id).all()
        for log in measurable_logs:
            measurable = Measurable.query.get(log.measurable_id)
            if measurable:
                ws.append([
                    measurable.name,
                    log.date,
                    log.value if log.value is not None else 0
                ])
        
        ws.append([])  # Empty row
        
        # Journals section
        journals = Journal.query.filter_by(user_id=user_id).all()
        if journals:
            ws.append(["=== JOURNALS ==="])
            ws.append(["Date", "Content"])
            
            for journal in journals:
                # Limit content length for Excel compatibility
                content = journal.content or ""
                if len(content) > 500:
                    content = content[:500] + "... (truncated)"
                
                ws.append([
                    journal.date,
                    content
                ])
        
        # Auto-adjust column widths
        for column in ws.columns:
            max_length = 0
            column_letter = column[0].column_letter
            
            for cell in column:
                try:
                    cell_value = str(cell.value) if cell.value is not None else ""
                    if len(cell_value) > max_length:
                        max_length = len(cell_value)
                except:
                    pass
            
            # Set width (max 50 characters)
            adjusted_width = min(max_length + 2, 50)
            ws.column_dimensions[column_letter].width = adjusted_width
        
        # Save to memory
        output = io.BytesIO()
        wb.save(output)
        output.seek(0)
        
        response = make_response(output.read())
        response.headers['Content-Type'] = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        response.headers['Content-Disposition'] = f'attachment; filename=habit-analysis-{date.today().isoformat()}.xlsx'
        
        return response
        
    except Exception as e:
        print(f"Excel export error: {str(e)}")
        return jsonify({'error': f'Excel export failed: {str(e)}'}), 500

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully', 'success')
    return redirect(url_for('login'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, port=9000)
