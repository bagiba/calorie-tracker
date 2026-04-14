import sqlite3
import os
import secrets

from flask import g

DATABASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'clories.db')


def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
    return g.db


def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()


def init_db():
    db = sqlite3.connect(DATABASE)
    db.executescript('''
        CREATE TABLE IF NOT EXISTS settings (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            calorie_target INTEGER DEFAULT 1600,
            yellow_threshold INTEGER DEFAULT 1600,
            red_threshold INTEGER DEFAULT 1850,
            age INTEGER DEFAULT 24,
            height_cm INTEGER DEFAULT 170,
            weight_kg REAL DEFAULT 80.0,
            gender TEXT DEFAULT 'male',
            activity_level TEXT DEFAULT 'sedentary'
        );

        INSERT OR IGNORE INTO settings (id) VALUES (1);

        CREATE TABLE IF NOT EXISTS meals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            name TEXT NOT NULL,
            calories INTEGER NOT NULL,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE INDEX IF NOT EXISTS idx_meals_date ON meals(date);

        CREATE TABLE IF NOT EXISTS calorie_goals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            yellow_threshold INTEGER NOT NULL,
            red_threshold INTEGER NOT NULL,
            effective_date TEXT NOT NULL UNIQUE
        );

        CREATE TABLE IF NOT EXISTS steps (
            date TEXT PRIMARY KEY,
            steps INTEGER NOT NULL
        );
    ''')

    # Seed calorie_goals from current settings if empty
    row = db.execute('SELECT yellow_threshold, red_threshold FROM settings WHERE id = 1').fetchone()
    if row:
        db.execute(
            'INSERT OR IGNORE INTO calorie_goals (yellow_threshold, red_threshold, effective_date) VALUES (?, ?, ?)',
            (row[0], row[1], '0001-01-01')
        )

    # Migrate existing settings table if columns are missing
    new_cols = [
        ('age',            'INTEGER DEFAULT 24'),
        ('height_cm',      'INTEGER DEFAULT 170'),
        ('weight_kg',      'REAL DEFAULT 80.0'),
        ('gender',         "TEXT DEFAULT 'male'"),
        ('activity_level', "TEXT DEFAULT 'sedentary'"),
    ]
    for col, definition in new_cols:
        try:
            db.execute(f'ALTER TABLE settings ADD COLUMN {col} {definition}')
        except sqlite3.OperationalError:
            pass  # column already exists

    # Add api_key column if missing, then seed a random key if empty
    try:
        db.execute("ALTER TABLE settings ADD COLUMN api_key TEXT DEFAULT ''")
    except sqlite3.OperationalError:
        pass
    row = db.execute('SELECT api_key FROM settings WHERE id = 1').fetchone()
    if row and not row[0]:
        db.execute('UPDATE settings SET api_key = ? WHERE id = 1', (secrets.token_hex(16),))

    db.commit()
    db.close()
