from flask import Flask, render_template, request, redirect, url_for, jsonify, flash
from database import get_db, close_db, init_db
import calendar as cal
from datetime import date, datetime

app = Flask(__name__)
app.secret_key = 'clories-secret-key'

app.teardown_appcontext(close_db)

ACTIVITY_LABELS = {
    'sedentary':   'sedentary (little/no exercise)',
    'light':       'lightly active (1–3 days/week)',
    'moderate':    'moderately active (3–5 days/week)',
    'active':      'very active (6–7 days/week)',
    'very_active': 'extra active (physical job)',
}

ACTIVITY_MULTIPLIERS = {
    'sedentary':  1.2,
    'light':      1.375,
    'moderate':   1.55,
    'active':     1.725,
    'very_active': 1.9,
}


def get_settings():
    db = get_db()
    return db.execute('SELECT * FROM settings WHERE id = 1').fetchone()


@app.context_processor
def inject_globals():
    return {'nav_settings': get_settings()}


def calc_tdee(settings):
    """Mifflin-St Jeor BMR × activity multiplier."""
    w = float(settings['weight_kg'])
    h = float(settings['height_cm'])
    a = float(settings['age'])
    if settings['gender'] == 'female':
        bmr = 10 * w + 6.25 * h - 5 * a - 161
    else:
        bmr = 10 * w + 6.25 * h - 5 * a + 5
    return bmr * ACTIVITY_MULTIPLIERS.get(settings['activity_level'], 1.2)


# ── Page Routes ──────────────────────────────────────────────────────────────

@app.route('/')
def index():
    today = date.today()
    return redirect(url_for('calendar_view', year=today.year, month=today.month))


@app.route('/calendar/<int:year>/<int:month>')
def calendar_view(year, month):
    if month < 1 or month > 12:
        return redirect(url_for('index'))

    settings = get_settings()
    weeks = cal.Calendar().monthdayscalendar(year, month)
    month_name = cal.month_name[month]

    # Aggregate daily totals for the month
    first_day = f"{year:04d}-{month:02d}-01"
    last_day = f"{year:04d}-{month:02d}-{cal.monthrange(year, month)[1]:02d}"

    db = get_db()
    rows = db.execute(
        'SELECT date, SUM(calories) as total FROM meals WHERE date BETWEEN ? AND ? GROUP BY date',
        (first_day, last_day)
    ).fetchall()

    daily_totals = {row['date']: row['total'] for row in rows}

    def day_color(day):
        if day == 0:
            return ''
        date_str = f"{year:04d}-{month:02d}-{day:02d}"
        total = daily_totals.get(date_str)
        if total is None:
            return 'gray'
        if total <= settings['yellow_threshold']:
            return 'green'
        if total <= settings['red_threshold']:
            return 'yellow'
        return 'red'

    today_date = date.today()

    # Prev/next month navigation
    if month == 1:
        prev_year, prev_month = year - 1, 12
    else:
        prev_year, prev_month = year, month - 1

    if month == 12:
        next_year, next_month = year + 1, 1
    else:
        next_year, next_month = year, month + 1

    # Weight prediction based on logged days only
    tdee = calc_tdee(settings)
    total_deficit = sum(tdee - v for v in daily_totals.values())
    predicted_kg = total_deficit / 7700  # positive = loss, negative = gain
    is_loss = predicted_kg >= 0
    prediction = {
        'tdee': round(tdee),
        'days': len(daily_totals),
        'kg_str': f"{abs(predicted_kg):.2f}",
        'is_loss': is_loss,
    }

    return render_template('calendar.html',
        year=year, month=month, month_name=month_name,
        weeks=weeks, daily_totals=daily_totals,
        day_color=day_color, today=today_date,
        prev_year=prev_year, prev_month=prev_month,
        next_year=next_year, next_month=next_month,
        prediction=prediction)


@app.route('/day/<date_str>')
def day_view(date_str):
    try:
        parsed = datetime.strptime(date_str, '%Y-%m-%d')
    except ValueError:
        return redirect(url_for('index'))

    db = get_db()
    meals = db.execute(
        'SELECT * FROM meals WHERE date = ? ORDER BY created_at',
        (date_str,)
    ).fetchall()

    total = sum(m['calories'] for m in meals)
    settings = get_settings()

    return render_template('day.html',
        date=date_str, parsed_date=parsed,
        meals=meals, total=total, settings=settings)


@app.route('/settings', methods=['GET', 'POST'])
def settings_view():
    db = get_db()
    if request.method == 'POST':
        calorie_target  = request.form.get('calorie_target',  type=int)
        yellow_threshold = request.form.get('yellow_threshold', type=int)
        red_threshold   = request.form.get('red_threshold',   type=int)
        age             = request.form.get('age',             type=int)
        height_cm       = request.form.get('height_cm',       type=int)
        weight_kg       = request.form.get('weight_kg',       type=float)
        gender          = request.form.get('gender',          '').strip()
        activity_level  = request.form.get('activity_level',  '').strip()

        if all([calorie_target, yellow_threshold, red_threshold, age, height_cm, weight_kg, gender, activity_level]):
            errors = []
            if yellow_threshold > red_threshold:
                errors.append('yellow threshold must be ≤ red threshold.')
            if gender not in {'male', 'female'}:
                errors.append('invalid gender value.')
            if activity_level not in ACTIVITY_LABELS:
                errors.append('invalid activity level.')

            if errors:
                for e in errors:
                    flash(e, 'error')
            else:
                db.execute(
                    'UPDATE settings SET calorie_target=?, yellow_threshold=?, red_threshold=?, '
                    'age=?, height_cm=?, weight_kg=?, gender=?, activity_level=? WHERE id=1',
                    (calorie_target, yellow_threshold, red_threshold,
                     age, height_cm, weight_kg, gender, activity_level)
                )
                db.commit()
                flash('settings saved.', 'success')
        else:
            flash('all fields are required.', 'error')

        return redirect(url_for('settings_view'))

    settings = get_settings()
    return render_template('settings.html', settings=settings, activity_labels=ACTIVITY_LABELS)


# ── JSON API Routes ──────────────────────────────────────────────────────────

@app.route('/api/meals', methods=['POST'])
def add_meal():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Invalid JSON'}), 400

    meal_date = data.get('date')
    name = data.get('name', '').strip()
    calories = data.get('calories')

    if not meal_date or not name or calories is None:
        return jsonify({'error': 'date, name, and calories are required'}), 400

    try:
        calories = int(calories)
        if calories < 0:
            raise ValueError
    except (ValueError, TypeError):
        return jsonify({'error': 'Calories must be a non-negative integer'}), 400

    db = get_db()
    cursor = db.execute(
        'INSERT INTO meals (date, name, calories) VALUES (?, ?, ?)',
        (meal_date, name, calories)
    )
    db.commit()

    meal = db.execute('SELECT * FROM meals WHERE id = ?', (cursor.lastrowid,)).fetchone()

    return jsonify({
        'id': meal['id'],
        'date': meal['date'],
        'name': meal['name'],
        'calories': meal['calories'],
        'created_at': meal['created_at']
    }), 201


@app.route('/api/meals/<int:meal_id>', methods=['PUT'])
def update_meal(meal_id):
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Invalid JSON'}), 400

    name = data.get('name', '').strip()
    calories = data.get('calories')

    if not name or calories is None:
        return jsonify({'error': 'name and calories are required'}), 400

    try:
        calories = int(calories)
        if calories < 0:
            raise ValueError
    except (ValueError, TypeError):
        return jsonify({'error': 'Calories must be a non-negative integer'}), 400

    db = get_db()
    result = db.execute(
        'UPDATE meals SET name = ?, calories = ? WHERE id = ?',
        (name, calories, meal_id)
    )
    db.commit()

    if result.rowcount == 0:
        return jsonify({'error': 'Meal not found'}), 404

    meal = db.execute('SELECT * FROM meals WHERE id = ?', (meal_id,)).fetchone()
    return jsonify({
        'id': meal['id'],
        'date': meal['date'],
        'name': meal['name'],
        'calories': meal['calories'],
        'created_at': meal['created_at']
    })


@app.route('/api/meals/<int:meal_id>', methods=['DELETE'])
def delete_meal(meal_id):
    db = get_db()
    result = db.execute('DELETE FROM meals WHERE id = ?', (meal_id,))
    db.commit()

    if result.rowcount == 0:
        return jsonify({'error': 'Meal not found'}), 404

    return jsonify({'success': True})


@app.route('/api/meals/<date_str>', methods=['GET'])
def get_meals(date_str):
    db = get_db()
    meals = db.execute(
        'SELECT * FROM meals WHERE date = ? ORDER BY created_at',
        (date_str,)
    ).fetchall()

    total = sum(m['calories'] for m in meals)

    return jsonify({
        'meals': [{
            'id': m['id'],
            'date': m['date'],
            'name': m['name'],
            'calories': m['calories'],
            'created_at': m['created_at']
        } for m in meals],
        'total': total
    })


if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', debug=False)
