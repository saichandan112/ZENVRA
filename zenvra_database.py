"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                         ZENVRA DATABASE SYSTEM                               ║
║              Mind, Body & Soul — Complete Python Backend                     ║
║                                                                              ║
║  Run this file in VS Code:  python zenvra_database.py                        ║
║  Then open:  http://localhost:5000  in your browser                          ║
╚══════════════════════════════════════════════════════════════════════════════╝

INSTALL DEPENDENCIES FIRST (run in VS Code terminal):
    pip install flask flask-cors

WHAT THIS DOES:
  • Creates a local SQLite database (zenvra.db) — no internet required
  • Runs a local web server at http://localhost:5000
  • Serves the ZENVRA HTML app files
  • Provides a REST API so all app data saves to zenvra.db instead of localStorage
  • Gives you a live dashboard showing all stored data
  • Lets you export all your data as JSON or CSV

TABLES CREATED:
  1. daily_logs      — workouts, meals, water, steps per day
  2. workouts        — individual workout entries with sets/reps/weight
  3. meals           — meal entries with macros (kcal, protein, carbs, fat)
  4. metrics         — body metrics (weight, height, BMI, body fat, heart rate)
  5. personal_records— push-up, pull-up, bench, deadlift, squat, plank, steps PRs
  6. streaks         — daily streak tracking
  7. thoughts        — imported user thoughts with category
  8. reminders       — reminder settings (morning, midday, evening, custom)
  9. milestones      — milestone achievements log
  10. sessions        — onboarding state and app session metadata
"""

import sqlite3
import json
import os
import csv
import io
from datetime import datetime, date, timedelta
from pathlib import Path

# ─── Try to import Flask for web server ─────────────────────────────────────
try:
    from flask import Flask, request, jsonify, send_from_directory, Response
    from flask_cors import CORS
    FLASK_AVAILABLE = True
except ImportError:
    FLASK_AVAILABLE = False

# ─── Configuration ───────────────────────────────────────────────────────────
DB_PATH     = Path(__file__).parent / "zenvra.db"
STATIC_DIR  = Path(__file__).parent  # Serve HTML files from same folder
PORT        = 5000

# ═════════════════════════════════════════════════════════════════════════════
#  DATABASE CLASS
# ═════════════════════════════════════════════════════════════════════════════

class ZenvraDB:
    """Complete SQLite database manager for the ZENVRA app."""

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = str(db_path)
        self.init_database()

    # ─── CONNECTION ──────────────────────────────────────────────────────────
    def conn(self):
        c = sqlite3.connect(self.db_path)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA foreign_keys = ON")
        c.execute("PRAGMA journal_mode = WAL")  # Better concurrent access
        return c

    def q(self, sql: str, params=(), fetchall=True):
        """Execute a query and return results."""
        with self.conn() as c:
            cur = c.execute(sql, params)
            if fetchall:
                return [dict(r) for r in cur.fetchall()]
            return dict(cur.fetchone()) if cur.fetchone() else None

    def run(self, sql: str, params=()):
        """Execute a write query."""
        with self.conn() as c:
            cur = c.execute(sql, params)
            c.commit()
            return cur.lastrowid

    # ─── INIT ─────────────────────────────────────────────────────────────────
    def init_database(self):
        """Create all tables if they don't exist."""
        with self.conn() as c:
            c.executescript("""
                -- ── 1. DAILY LOGS (summary per day) ─────────────────────────
                CREATE TABLE IF NOT EXISTS daily_logs (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    log_date    TEXT    NOT NULL UNIQUE,   -- YYYY-MM-DD
                    steps       INTEGER DEFAULT 0,
                    water       INTEGER DEFAULT 0,         -- glasses (0-8)
                    cal_in      INTEGER DEFAULT 0,
                    protein_g   REAL    DEFAULT 0,
                    carbs_g     REAL    DEFAULT 0,
                    fat_g       REAL    DEFAULT 0,
                    watch_ids   TEXT    DEFAULT '[]',      -- JSON array of watched content IDs
                    created_at  TEXT    DEFAULT (datetime('now')),
                    updated_at  TEXT    DEFAULT (datetime('now'))
                );

                -- ── 2. WORKOUTS (individual sessions) ────────────────────────
                CREATE TABLE IF NOT EXISTS workouts (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    log_date        TEXT    NOT NULL,
                    workout_id      TEXT    NOT NULL,      -- e.g. 'bench', 'pushup'
                    workout_name    TEXT    NOT NULL,
                    workout_emoji   TEXT,
                    category        TEXT,                  -- gym, calisthenics, running, etc.
                    sets            INTEGER,
                    reps            INTEGER,
                    weight_kg       REAL,
                    duration_min    INTEGER,
                    distance_km     REAL,
                    hold_sec        INTEGER,
                    cal_burned      INTEGER DEFAULT 0,
                    feel            TEXT,                  -- '💪 Beast mode', etc.
                    raw_data        TEXT    DEFAULT '{}',  -- full JSON data from app
                    logged_at       TEXT    DEFAULT (datetime('now')),
                    FOREIGN KEY (log_date) REFERENCES daily_logs(log_date)
                );

                -- ── 3. MEALS ─────────────────────────────────────────────────
                CREATE TABLE IF NOT EXISTS meals (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    log_date    TEXT    NOT NULL,
                    meal_name   TEXT    NOT NULL,
                    meal_time   TEXT,                      -- 'Breakfast', 'Lunch', etc.
                    cal         INTEGER DEFAULT 0,
                    protein_g   REAL    DEFAULT 0,
                    carbs_g     REAL    DEFAULT 0,
                    fat_g       REAL    DEFAULT 0,
                    logged_at   TEXT    DEFAULT (datetime('now')),
                    FOREIGN KEY (log_date) REFERENCES daily_logs(log_date)
                );

                -- ── 4. BODY METRICS ──────────────────────────────────────────
                CREATE TABLE IF NOT EXISTS metrics (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    weight_kg   REAL,
                    height_cm   REAL,
                    body_fat_pct REAL,
                    resting_hr  INTEGER,
                    bmi         REAL    GENERATED ALWAYS AS
                                    (ROUND(weight_kg / ((height_cm/100)*(height_cm/100)), 1))
                                    STORED,
                    recorded_at TEXT    DEFAULT (datetime('now'))
                );

                -- ── 5. PERSONAL RECORDS ──────────────────────────────────────
                CREATE TABLE IF NOT EXISTS personal_records (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    pushup_max      INTEGER DEFAULT 0,
                    pullup_max      INTEGER DEFAULT 0,
                    bench_kg        REAL    DEFAULT 0,
                    deadlift_kg     REAL    DEFAULT 0,
                    squat_kg        REAL    DEFAULT 0,
                    plank_sec       INTEGER DEFAULT 0,
                    best_steps_day  INTEGER DEFAULT 0,
                    updated_at      TEXT    DEFAULT (datetime('now'))
                );

                -- ── 6. STREAKS ────────────────────────────────────────────────
                CREATE TABLE IF NOT EXISTS streaks (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    streak_count INTEGER DEFAULT 0,
                    last_date   TEXT,                      -- date string of last active day
                    updated_at  TEXT    DEFAULT (datetime('now'))
                );

                -- ── 7. THOUGHTS (user-imported) ───────────────────────────────
                CREATE TABLE IF NOT EXISTS thoughts (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    thought_id  TEXT    UNIQUE,            -- UUID from app
                    text        TEXT    NOT NULL,
                    category    TEXT    NOT NULL,          -- work, gym, relationship, etc.
                    source      TEXT    DEFAULT 'user',    -- 'user' | 'builtin'
                    created_at  TEXT    DEFAULT (datetime('now'))
                );

                -- ── 8. REMINDERS ─────────────────────────────────────────────
                CREATE TABLE IF NOT EXISTS reminders (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    morning     INTEGER DEFAULT 0,         -- boolean
                    midday      INTEGER DEFAULT 0,
                    evening     INTEGER DEFAULT 0,
                    custom      INTEGER DEFAULT 0,
                    custom_hour TEXT    DEFAULT '07',
                    custom_min  TEXT    DEFAULT '00',
                    custom_ampm TEXT    DEFAULT 'AM',
                    updated_at  TEXT    DEFAULT (datetime('now'))
                );

                -- ── 9. MILESTONES ────────────────────────────────────────────
                CREATE TABLE IF NOT EXISTS milestones (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    milestone_key   TEXT    UNIQUE,        -- e.g. '100_pushup_day'
                    milestone_name  TEXT    NOT NULL,
                    achieved        INTEGER DEFAULT 0,
                    achieved_at     TEXT,
                    progress        REAL    DEFAULT 0,
                    goal            REAL    NOT NULL
                );

                -- ── 10. APP SESSIONS & SETTINGS ──────────────────────────────
                CREATE TABLE IF NOT EXISTS app_settings (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    key         TEXT    UNIQUE NOT NULL,
                    value       TEXT    NOT NULL,
                    updated_at  TEXT    DEFAULT (datetime('now'))
                );

                -- ── INDEXES ──────────────────────────────────────────────────
                CREATE INDEX IF NOT EXISTS idx_workouts_date ON workouts(log_date);
                CREATE INDEX IF NOT EXISTS idx_meals_date    ON meals(log_date);
                CREATE INDEX IF NOT EXISTS idx_thoughts_cat  ON thoughts(category);
            """)
            c.commit()

        self._seed_defaults()
        print(f"✦ Database ready: {self.db_path}")

    def _seed_defaults(self):
        """Insert default rows if tables are empty."""
        with self.conn() as c:
            # Default personal records row
            c.execute("INSERT OR IGNORE INTO personal_records(id) VALUES(1)")
            # Default streak row
            c.execute("INSERT OR IGNORE INTO streaks(id) VALUES(1)")
            # Default reminders row
            c.execute("INSERT OR IGNORE INTO reminders(id) VALUES(1)")
            # Default app settings
            defaults = [
                ('gender', 'male'),
                ('onboarded', '0'),
                ('app_version', '1.0.0'),
            ]
            c.executemany(
                "INSERT OR IGNORE INTO app_settings(key,value) VALUES(?,?)",
                defaults
            )
            # Default milestones
            milestones = [
                ('100_pushup_day',  '100-Rep Push-Up Day',   100),
                ('10000_steps',     '10,000 Step Day',        10000),
                ('perfect_hydration','Perfect Hydration',      8),
                ('100kg_deadlift',  '100kg Deadlift',         100),
                ('21_day_streak',   '21-Day Streak',          21),
            ]
            c.executemany(
                "INSERT OR IGNORE INTO milestones(milestone_key,milestone_name,goal) VALUES(?,?,?)",
                milestones
            )
            c.commit()

    # ═════════════════════════════════════════════════════════════════════════
    #  DAILY LOG
    # ═════════════════════════════════════════════════════════════════════════

    def get_or_create_daily(self, log_date: str = None) -> dict:
        """Get today's log, creating it if it doesn't exist."""
        if not log_date:
            log_date = date.today().isoformat()
        with self.conn() as c:
            c.execute(
                "INSERT OR IGNORE INTO daily_logs(log_date) VALUES(?)",
                (log_date,)
            )
            c.commit()
            row = c.execute(
                "SELECT * FROM daily_logs WHERE log_date=?", (log_date,)
            ).fetchone()
            return dict(row) if row else {}

    def update_daily(self, data: dict, log_date: str = None) -> dict:
        """Update today's daily log fields."""
        if not log_date:
            log_date = date.today().isoformat()
        self.get_or_create_daily(log_date)
        fields = {k: v for k, v in data.items()
                  if k in ('steps','water','cal_in','protein_g','carbs_g','fat_g','watch_ids')}
        if not fields:
            return self.get_or_create_daily(log_date)
        set_clause = ", ".join(f"{k}=?" for k in fields)
        set_clause += ", updated_at=datetime('now')"
        with self.conn() as c:
            c.execute(
                f"UPDATE daily_logs SET {set_clause} WHERE log_date=?",
                (*fields.values(), log_date)
            )
            c.commit()
        return self.get_or_create_daily(log_date)

    def get_week_logs(self) -> list:
        """Get last 7 days of daily logs."""
        seven_ago = (date.today() - timedelta(days=6)).isoformat()
        return self.q(
            "SELECT * FROM daily_logs WHERE log_date >= ? ORDER BY log_date DESC",
            (seven_ago,)
        )

    # ═════════════════════════════════════════════════════════════════════════
    #  WORKOUTS
    # ═════════════════════════════════════════════════════════════════════════

    def add_workout(self, data: dict, log_date: str = None) -> dict:
        """Log a workout session."""
        if not log_date:
            log_date = date.today().isoformat()
        self.get_or_create_daily(log_date)
        raw = json.dumps(data.get('raw_data', data))
        row_id = self.run("""
            INSERT INTO workouts
                (log_date, workout_id, workout_name, workout_emoji, category,
                 sets, reps, weight_kg, duration_min, distance_km,
                 hold_sec, cal_burned, feel, raw_data)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            log_date,
            data.get('workout_id',''),
            data.get('workout_name',''),
            data.get('workout_emoji',''),
            data.get('category',''),
            data.get('sets'),
            data.get('reps'),
            data.get('weight_kg'),
            data.get('duration_min'),
            data.get('distance_km'),
            data.get('hold_sec'),
            data.get('cal_burned', 0),
            data.get('feel',''),
            raw
        ))
        return self.get_workout(row_id)

    def get_workout(self, workout_db_id: int) -> dict:
        rows = self.q("SELECT * FROM workouts WHERE id=?", (workout_db_id,), fetchall=True)
        return rows[0] if rows else {}

    def get_workouts_today(self, log_date: str = None) -> list:
        if not log_date:
            log_date = date.today().isoformat()
        return self.q(
            "SELECT * FROM workouts WHERE log_date=? ORDER BY logged_at DESC",
            (log_date,)
        )

    def delete_workout(self, workout_db_id: int) -> bool:
        self.run("DELETE FROM workouts WHERE id=?", (workout_db_id,))
        return True

    def get_workout_history(self, workout_id: str, limit: int = 30) -> list:
        """Get history for a specific exercise (e.g. all bench press sessions)."""
        return self.q(
            "SELECT * FROM workouts WHERE workout_id=? ORDER BY logged_at DESC LIMIT ?",
            (workout_id, limit)
        )

    # ═════════════════════════════════════════════════════════════════════════
    #  MEALS
    # ═════════════════════════════════════════════════════════════════════════

    def add_meal(self, data: dict, log_date: str = None) -> dict:
        """Log a meal."""
        if not log_date:
            log_date = date.today().isoformat()
        self.get_or_create_daily(log_date)
        row_id = self.run("""
            INSERT INTO meals (log_date, meal_name, meal_time, cal, protein_g, carbs_g, fat_g)
            VALUES (?,?,?,?,?,?,?)
        """, (
            log_date,
            data.get('meal_name',''),
            data.get('meal_time',''),
            data.get('cal', 0),
            data.get('protein_g', 0),
            data.get('carbs_g', 0),
            data.get('fat_g', 0),
        ))
        # Update daily macro totals
        self._recalc_daily_macros(log_date)
        rows = self.q("SELECT * FROM meals WHERE id=?", (row_id,))
        return rows[0] if rows else {}

    def _recalc_daily_macros(self, log_date: str):
        """Recalculate and save daily macro totals from all meals that day."""
        with self.conn() as c:
            totals = c.execute("""
                SELECT COALESCE(SUM(cal),0)       as cal_in,
                       COALESCE(SUM(protein_g),0) as protein_g,
                       COALESCE(SUM(carbs_g),0)   as carbs_g,
                       COALESCE(SUM(fat_g),0)      as fat_g
                FROM meals WHERE log_date=?
            """, (log_date,)).fetchone()
            c.execute("""
                UPDATE daily_logs SET cal_in=?, protein_g=?, carbs_g=?, fat_g=?,
                                      updated_at=datetime('now')
                WHERE log_date=?
            """, (totals['cal_in'], totals['protein_g'],
                  totals['carbs_g'], totals['fat_g'], log_date))
            c.commit()

    def get_meals_today(self, log_date: str = None) -> list:
        if not log_date:
            log_date = date.today().isoformat()
        return self.q(
            "SELECT * FROM meals WHERE log_date=? ORDER BY logged_at ASC",
            (log_date,)
        )

    def delete_meal(self, meal_id: int) -> bool:
        rows = self.q("SELECT log_date FROM meals WHERE id=?", (meal_id,))
        self.run("DELETE FROM meals WHERE id=?", (meal_id,))
        if rows:
            self._recalc_daily_macros(rows[0]['log_date'])
        return True

    # ═════════════════════════════════════════════════════════════════════════
    #  BODY METRICS
    # ═════════════════════════════════════════════════════════════════════════

    def save_metrics(self, data: dict) -> dict:
        """Save a new body metrics measurement."""
        row_id = self.run("""
            INSERT INTO metrics (weight_kg, height_cm, body_fat_pct, resting_hr)
            VALUES (?,?,?,?)
        """, (
            data.get('weight_kg'),
            data.get('height_cm'),
            data.get('body_fat_pct'),
            data.get('resting_hr'),
        ))
        rows = self.q("SELECT * FROM metrics WHERE id=?", (row_id,))
        return rows[0] if rows else {}

    def get_latest_metrics(self) -> dict:
        rows = self.q("SELECT * FROM metrics ORDER BY recorded_at DESC LIMIT 1")
        return rows[0] if rows else {
            'weight_kg': 72, 'height_cm': 176, 'body_fat_pct': 18, 'resting_hr': 62, 'bmi': 23.2
        }

    def get_metrics_history(self, limit: int = 30) -> list:
        return self.q(
            "SELECT * FROM metrics ORDER BY recorded_at DESC LIMIT ?", (limit,)
        )

    # ═════════════════════════════════════════════════════════════════════════
    #  PERSONAL RECORDS
    # ═════════════════════════════════════════════════════════════════════════

    def get_prs(self) -> dict:
        rows = self.q("SELECT * FROM personal_records WHERE id=1")
        return rows[0] if rows else {}

    def update_pr(self, field: str, value) -> dict:
        """Update a personal record if value is greater than current."""
        valid = {'pushup_max','pullup_max','bench_kg','deadlift_kg','squat_kg','plank_sec','best_steps_day'}
        if field not in valid:
            return self.get_prs()
        current = self.get_prs()
        if current and float(value) > float(current.get(field, 0) or 0):
            self.run(f"""
                UPDATE personal_records
                SET {field}=?, updated_at=datetime('now')
                WHERE id=1
            """, (value,))
            print(f"  🏆 NEW PR: {field} = {value}")
        return self.get_prs()

    def update_prs_from_workout(self, workout_id: str, data: dict) -> dict:
        """Auto-update PRs based on workout data (mirrors app JS logic)."""
        pr_map = {
            'pushup':    ('pushup_max',  'reps'),
            'pullup':    ('pullup_max',  'reps'),
            'bench':     ('bench_kg',    'weight_kg'),
            'deadlift':  ('deadlift_kg', 'weight_kg'),
            'squat-bar': ('squat_kg',    'weight_kg'),
            'plank':     ('plank_sec',   'hold_sec'),
        }
        if workout_id in pr_map:
            pr_field, data_key = pr_map[workout_id]
            val = data.get(data_key) or data.get('reps') or data.get('weight_kg')
            if val:
                self.update_pr(pr_field, val)
        return self.get_prs()

    # ═════════════════════════════════════════════════════════════════════════
    #  STREAKS
    # ═════════════════════════════════════════════════════════════════════════

    def update_streak(self) -> dict:
        """Update streak count based on today's activity."""
        today_str = date.today().isoformat()
        yesterday_str = (date.today() - timedelta(days=1)).isoformat()
        rows = self.q("SELECT * FROM streaks WHERE id=1")
        s = rows[0] if rows else {'streak_count': 0, 'last_date': None}

        if s['last_date'] == today_str:
            return s  # Already counted today
        elif s['last_date'] == yesterday_str:
            new_count = s['streak_count'] + 1
        else:
            new_count = 1  # Streak broken, restart

        self.run("""
            UPDATE streaks SET streak_count=?, last_date=?, updated_at=datetime('now')
            WHERE id=1
        """, (new_count, today_str))
        return self.q("SELECT * FROM streaks WHERE id=1")[0]

    def get_streak(self) -> dict:
        rows = self.q("SELECT * FROM streaks WHERE id=1")
        return rows[0] if rows else {'streak_count': 0, 'last_date': None}

    # ═════════════════════════════════════════════════════════════════════════
    #  THOUGHTS
    # ═════════════════════════════════════════════════════════════════════════

    def add_thought(self, data: dict) -> dict:
        """Import a user thought."""
        row_id = self.run("""
            INSERT OR IGNORE INTO thoughts (thought_id, text, category, source)
            VALUES (?,?,?,?)
        """, (
            data.get('id', f"u_{datetime.now().timestamp()}"),
            data.get('text',''),
            data.get('cat', data.get('category','work')),
            data.get('source','user'),
        ))
        rows = self.q("SELECT * FROM thoughts WHERE id=?", (row_id,))
        return rows[0] if rows else {}

    def add_thoughts_bulk(self, thoughts: list) -> int:
        """Import multiple thoughts at once."""
        count = 0
        for t in thoughts:
            r = self.add_thought(t)
            if r:
                count += 1
        return count

    def get_thoughts(self, category: str = None) -> list:
        if category:
            return self.q("SELECT * FROM thoughts WHERE category=? ORDER BY created_at DESC", (category,))
        return self.q("SELECT * FROM thoughts ORDER BY created_at DESC")

    def delete_thought(self, thought_id: str) -> bool:
        self.run("DELETE FROM thoughts WHERE thought_id=?", (thought_id,))
        return True

    def clear_thoughts(self) -> bool:
        self.run("DELETE FROM thoughts WHERE source='user'")
        return True

    # ═════════════════════════════════════════════════════════════════════════
    #  REMINDERS
    # ═════════════════════════════════════════════════════════════════════════

    def get_reminders(self) -> dict:
        rows = self.q("SELECT * FROM reminders WHERE id=1")
        return rows[0] if rows else {}

    def save_reminders(self, data: dict) -> dict:
        fields = {k: v for k, v in data.items()
                  if k in ('morning','midday','evening','custom','custom_hour','custom_min','custom_ampm')}
        if not fields:
            return self.get_reminders()
        set_clause = ", ".join(f"{k}=?" for k in fields)
        self.run(
            f"UPDATE reminders SET {set_clause}, updated_at=datetime('now') WHERE id=1",
            tuple(fields.values())
        )
        return self.get_reminders()

    # ═════════════════════════════════════════════════════════════════════════
    #  APP SETTINGS
    # ═════════════════════════════════════════════════════════════════════════

    def get_setting(self, key: str, default=None):
        rows = self.q("SELECT value FROM app_settings WHERE key=?", (key,))
        return rows[0]['value'] if rows else default

    def set_setting(self, key: str, value: str):
        self.run(
            "INSERT OR REPLACE INTO app_settings(key,value,updated_at) VALUES(?,?,datetime('now'))",
            (key, str(value))
        )

    def get_all_settings(self) -> dict:
        rows = self.q("SELECT key, value FROM app_settings")
        return {r['key']: r['value'] for r in rows}

    # ═════════════════════════════════════════════════════════════════════════
    #  MILESTONES
    # ═════════════════════════════════════════════════════════════════════════

    def update_milestones(self, progress_data: dict) -> list:
        """
        Update milestone progress based on current stats.
        progress_data: {'pushup_max': 80, 'steps': 10500, 'water': 8,
                         'deadlift_kg': 95, 'streak_count': 14}
        """
        map_ = {
            '100_pushup_day':   progress_data.get('pushup_max', 0),
            '10000_steps':      progress_data.get('steps', 0),
            'perfect_hydration':progress_data.get('water', 0),
            '100kg_deadlift':   progress_data.get('deadlift_kg', 0),
            '21_day_streak':    progress_data.get('streak_count', 0),
        }
        with self.conn() as c:
            for key, prog in map_.items():
                row = c.execute(
                    "SELECT * FROM milestones WHERE milestone_key=?", (key,)
                ).fetchone()
                if not row:
                    continue
                achieved = int(prog >= row['goal'])
                achieved_at = datetime.now().isoformat() if achieved and not row['achieved'] else row['achieved_at']
                c.execute("""
                    UPDATE milestones SET progress=?, achieved=?, achieved_at=?
                    WHERE milestone_key=?
                """, (min(prog, row['goal']), achieved, achieved_at, key))
            c.commit()
        return self.get_milestones()

    def get_milestones(self) -> list:
        return self.q("SELECT * FROM milestones ORDER BY id")

    # ═════════════════════════════════════════════════════════════════════════
    #  DATA EXPORT
    # ═════════════════════════════════════════════════════════════════════════

    def export_json(self) -> dict:
        """Export all app data as a single JSON object."""
        return {
            'exported_at':      datetime.now().isoformat(),
            'app_version':      self.get_setting('app_version', '1.0.0'),
            'settings':         self.get_all_settings(),
            'streak':           self.get_streak(),
            'personal_records': self.get_prs(),
            'metrics':          self.get_latest_metrics(),
            'metrics_history':  self.get_metrics_history(),
            'reminders':        self.get_reminders(),
            'milestones':       self.get_milestones(),
            'thoughts':         self.get_thoughts(),
            'week_logs':        self.get_week_logs(),
            'workouts_today':   self.get_workouts_today(),
            'meals_today':      self.get_meals_today(),
        }

    def export_workouts_csv(self) -> str:
        """Export all workout history as CSV string."""
        rows = self.q("SELECT * FROM workouts ORDER BY logged_at DESC")
        if not rows:
            return "No workout data yet."
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
        return output.getvalue()

    def export_meals_csv(self) -> str:
        """Export all meal history as CSV string."""
        rows = self.q("SELECT * FROM meals ORDER BY logged_at DESC")
        if not rows:
            return "No meal data yet."
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
        return output.getvalue()

    # ═════════════════════════════════════════════════════════════════════════
    #  DASHBOARD (text summary for terminal)
    # ═════════════════════════════════════════════════════════════════════════

    def print_dashboard(self):
        """Print a formatted dashboard to the terminal."""
        print("\n" + "═"*60)
        print("  ✦  ZENVRA DATABASE DASHBOARD")
        print("═"*60)

        today = self.get_or_create_daily()
        print(f"\n  📅 TODAY  ({today.get('log_date','—')})")
        print(f"     Steps:    {today.get('steps',0):,}")
        print(f"     Water:    {today.get('water',0)}/8 glasses")
        print(f"     Calories: {today.get('cal_in',0)} kcal")
        print(f"     Protein:  {today.get('protein_g',0)}g")

        workouts = self.get_workouts_today()
        print(f"\n  🏋️  WORKOUTS TODAY  ({len(workouts)} logged)")
        for w in workouts:
            print(f"     • {w.get('workout_emoji','')} {w.get('workout_name','')}  "
                  f"cal_burned={w.get('cal_burned',0)}")

        meals = self.get_meals_today()
        print(f"\n  🥗 MEALS TODAY  ({len(meals)} logged)")
        for m in meals:
            print(f"     • {m.get('meal_name','')}  {m.get('cal',0)}kcal")

        streak = self.get_streak()
        print(f"\n  🔥 STREAK:  {streak.get('streak_count',0)} days")

        prs = self.get_prs()
        print(f"\n  🏆 PERSONAL RECORDS")
        pr_labels = {
            'pushup_max':'Push-Ups','pullup_max':'Pull-Ups',
            'bench_kg':'Bench Press','deadlift_kg':'Deadlift',
            'squat_kg':'Barbell Squat','plank_sec':'Plank Hold',
            'best_steps_day':'Best Step Day',
        }
        for k, label in pr_labels.items():
            v = prs.get(k, 0)
            suffix = 'kg' if 'kg' in k else ('s' if 'sec' in k else '')
            print(f"     {label}: {v}{suffix}")

        thoughts = self.get_thoughts()
        print(f"\n  ✨ IMPORTED THOUGHTS:  {len(thoughts)}")

        metrics = self.get_latest_metrics()
        print(f"\n  📊 BODY METRICS  (latest)")
        print(f"     Weight: {metrics.get('weight_kg','—')}kg  |  "
              f"BMI: {metrics.get('bmi','—')}  |  "
              f"BF: {metrics.get('body_fat_pct','—')}%")

        print(f"\n  📁 Database file:  {self.db_path}")
        print("═"*60 + "\n")


# ═════════════════════════════════════════════════════════════════════════════
#  FLASK WEB SERVER & REST API
# ═════════════════════════════════════════════════════════════════════════════

def create_app(db: ZenvraDB) -> "Flask":
    app = Flask(__name__, static_folder=str(STATIC_DIR), static_url_path='')
    CORS(app)

    def ok(data=None, msg="ok"):
        return jsonify({"status": "ok", "msg": msg, "data": data})

    def err(msg="error", code=400):
        return jsonify({"status": "error", "msg": msg}), code

    # ── Serve HTML files ────────────────────────────────────────────────────
    @app.route('/')
    def index():
        """Serve onboarding page if not yet onboarded, else main app."""
        onboarded = db.get_setting('onboarded', '0')
        if onboarded == '1':
            return send_from_directory(STATIC_DIR, 'zenvra-complete.html')
        return send_from_directory(STATIC_DIR, 'zenvra-onboarding.html')

    @app.route('/app')
    def main_app():
        return send_from_directory(STATIC_DIR, 'zenvra-complete.html')

    @app.route('/onboarding')
    def onboarding():
        return send_from_directory(STATIC_DIR, 'zenvra-onboarding.html')

    # ── Daily Log ───────────────────────────────────────────────────────────
    @app.route('/api/daily', methods=['GET'])
    def get_daily():
        date_param = request.args.get('date')
        return ok(db.get_or_create_daily(date_param))

    @app.route('/api/daily', methods=['POST'])
    def update_daily():
        data = request.get_json() or {}
        return ok(db.update_daily(data, data.get('date')))

    @app.route('/api/daily/week', methods=['GET'])
    def get_week():
        return ok(db.get_week_logs())

    # ── Workouts ────────────────────────────────────────────────────────────
    @app.route('/api/workouts', methods=['GET'])
    def get_workouts():
        date_param = request.args.get('date')
        return ok(db.get_workouts_today(date_param))

    @app.route('/api/workouts', methods=['POST'])
    def add_workout():
        data = request.get_json()
        if not data:
            return err("No data provided")
        w = db.add_workout(data, data.get('date'))
        db.update_prs_from_workout(data.get('workout_id',''), data)
        db.update_streak()
        return ok(w, "Workout logged ✦")

    @app.route('/api/workouts/<int:wid>', methods=['DELETE'])
    def del_workout(wid):
        db.delete_workout(wid)
        return ok(msg="Workout deleted")

    @app.route('/api/workouts/history/<workout_id>', methods=['GET'])
    def workout_history(workout_id):
        limit = int(request.args.get('limit', 30))
        return ok(db.get_workout_history(workout_id, limit))

    # ── Meals ───────────────────────────────────────────────────────────────
    @app.route('/api/meals', methods=['GET'])
    def get_meals():
        date_param = request.args.get('date')
        return ok(db.get_meals_today(date_param))

    @app.route('/api/meals', methods=['POST'])
    def add_meal():
        data = request.get_json()
        if not data:
            return err("No data provided")
        m = db.add_meal(data, data.get('date'))
        return ok(m, "Meal logged ✦")

    @app.route('/api/meals/<int:mid>', methods=['DELETE'])
    def del_meal(mid):
        db.delete_meal(mid)
        return ok(msg="Meal deleted")

    # ── Steps & Water ───────────────────────────────────────────────────────
    @app.route('/api/steps', methods=['POST'])
    def add_steps():
        data = request.get_json() or {}
        add = int(data.get('add', 0))
        today = db.get_or_create_daily()
        new_steps = (today.get('steps', 0) or 0) + add
        result = db.update_daily({'steps': new_steps})
        prs = db.get_prs()
        if new_steps > (prs.get('best_steps_day') or 0):
            db.update_pr('best_steps_day', new_steps)
        return ok({'steps': new_steps}, f"+{add:,} steps logged")

    @app.route('/api/water', methods=['POST'])
    def add_water():
        today = db.get_or_create_daily()
        current = today.get('water', 0) or 0
        if current >= 8:
            return ok({'water': 8}, "Already fully hydrated!")
        new_water = current + 1
        db.update_daily({'water': new_water})
        return ok({'water': new_water}, f"💧 {new_water}/8 glasses")

    # ── Metrics ─────────────────────────────────────────────────────────────
    @app.route('/api/metrics', methods=['GET'])
    def get_metrics():
        return ok(db.get_latest_metrics())

    @app.route('/api/metrics', methods=['POST'])
    def save_metrics():
        data = request.get_json()
        if not data:
            return err("No data provided")
        m = db.save_metrics(data)
        return ok(m, "Metrics saved ✦")

    @app.route('/api/metrics/history', methods=['GET'])
    def metrics_history():
        limit = int(request.args.get('limit', 30))
        return ok(db.get_metrics_history(limit))

    # ── Personal Records ────────────────────────────────────────────────────
    @app.route('/api/prs', methods=['GET'])
    def get_prs():
        return ok(db.get_prs())

    @app.route('/api/prs', methods=['POST'])
    def update_pr():
        data = request.get_json() or {}
        field = data.get('field')
        value = data.get('value')
        if not field or value is None:
            return err("field and value required")
        return ok(db.update_pr(field, value))

    # ── Streak ──────────────────────────────────────────────────────────────
    @app.route('/api/streak', methods=['GET'])
    def get_streak():
        return ok(db.get_streak())

    @app.route('/api/streak/update', methods=['POST'])
    def update_streak():
        return ok(db.update_streak(), "Streak updated")

    # ── Thoughts ────────────────────────────────────────────────────────────
    @app.route('/api/thoughts', methods=['GET'])
    def get_thoughts():
        cat = request.args.get('category')
        return ok(db.get_thoughts(cat))

    @app.route('/api/thoughts', methods=['POST'])
    def add_thought():
        data = request.get_json()
        if not data:
            return err("No data")
        if isinstance(data, list):
            count = db.add_thoughts_bulk(data)
            return ok({'count': count}, f"✦ {count} thoughts imported")
        t = db.add_thought(data)
        return ok(t, "Thought added")

    @app.route('/api/thoughts/<thought_id>', methods=['DELETE'])
    def del_thought(thought_id):
        db.delete_thought(thought_id)
        return ok(msg="Thought removed")

    @app.route('/api/thoughts/clear', methods=['DELETE'])
    def clear_thoughts():
        db.clear_thoughts()
        return ok(msg="All thoughts cleared")

    # ── Reminders ───────────────────────────────────────────────────────────
    @app.route('/api/reminders', methods=['GET'])
    def get_reminders():
        return ok(db.get_reminders())

    @app.route('/api/reminders', methods=['POST'])
    def save_reminders():
        data = request.get_json() or {}
        return ok(db.save_reminders(data), "Reminders saved")

    # ── Settings ────────────────────────────────────────────────────────────
    @app.route('/api/settings', methods=['GET'])
    def get_settings():
        return ok(db.get_all_settings())

    @app.route('/api/settings', methods=['POST'])
    def save_setting():
        data = request.get_json() or {}
        for k, v in data.items():
            db.set_setting(k, v)
        return ok(db.get_all_settings(), "Settings saved")

    # ── Milestones ──────────────────────────────────────────────────────────
    @app.route('/api/milestones', methods=['GET'])
    def get_milestones():
        return ok(db.get_milestones())

    @app.route('/api/milestones/update', methods=['POST'])
    def update_milestones():
        data = request.get_json() or {}
        return ok(db.update_milestones(data))

    # ── Export ──────────────────────────────────────────────────────────────
    @app.route('/api/export/json', methods=['GET'])
    def export_json():
        data = db.export_json()
        return Response(
            json.dumps(data, indent=2),
            mimetype='application/json',
            headers={'Content-Disposition': 'attachment;filename=zenvra_export.json'}
        )

    @app.route('/api/export/workouts.csv', methods=['GET'])
    def export_workouts_csv():
        return Response(
            db.export_workouts_csv(),
            mimetype='text/csv',
            headers={'Content-Disposition': 'attachment;filename=zenvra_workouts.csv'}
        )

    @app.route('/api/export/meals.csv', methods=['GET'])
    def export_meals_csv():
        return Response(
            db.export_meals_csv(),
            mimetype='text/csv',
            headers={'Content-Disposition': 'attachment;filename=zenvra_meals.csv'}
        )

    # ── Full state sync (mirrors localStorage behaviour) ────────────────────
    @app.route('/api/sync', methods=['GET'])
    def sync_get():
        """Return full app state in the same format as the app's localStorage."""
        today = db.get_or_create_daily()
        workouts = db.get_workouts_today()
        meals = db.get_meals_today()
        streak = db.get_streak()
        prs = db.get_prs()
        reminders = db.get_reminders()
        thoughts = db.get_thoughts()
        metrics = db.get_latest_metrics()
        settings = db.get_all_settings()

        return ok({
            'today': {
                **today,
                'workouts': workouts,
                'meals': meals,
            },
            'streak': streak,
            'prs': prs,
            'reminders': reminders,
            'thoughts': thoughts,
            'metrics': metrics,
            'gender': settings.get('gender','male'),
            'onboarded': settings.get('onboarded','0'),
        })

    @app.route('/api/sync', methods=['POST'])
    def sync_post():
        """Accept full state from app and persist it."""
        data = request.get_json() or {}
        if 'steps' in data:
            db.update_daily({'steps': data['steps']})
        if 'water' in data:
            db.update_daily({'water': data['water']})
        if 'gender' in data:
            db.set_setting('gender', data['gender'])
        if 'onboarded' in data:
            db.set_setting('onboarded', str(data['onboarded']))
        if 'metrics' in data:
            db.save_metrics(data['metrics'])
        if 'reminders' in data:
            db.save_reminders(data['reminders'])
        if 'thoughts' in data and isinstance(data['thoughts'], list):
            db.add_thoughts_bulk(data['thoughts'])
        return ok(msg="State synced ✦")

    # ── Live Dashboard (browser) ─────────────────────────────────────────────
    @app.route('/dashboard')
    def dashboard():
        today = db.get_or_create_daily()
        workouts = db.get_workouts_today()
        meals = db.get_meals_today()
        streak = db.get_streak()
        prs = db.get_prs()
        milestones = db.get_milestones()
        thoughts = db.get_thoughts()
        metrics = db.get_latest_metrics()

        ms_html = "".join(
            f"""<tr>
                  <td>{m.get('milestone_name','')}</td>
                  <td>{m.get('progress',0):,.0f} / {m.get('goal',0):,.0f}</td>
                  <td>{'✅ Achieved' if m.get('achieved') else '⏳ In Progress'}</td>
               </tr>"""
            for m in milestones
        )
        workout_html = "".join(
            f"<tr><td>{w.get('workout_emoji','')} {w.get('workout_name','')}</td>"
            f"<td>{w.get('cal_burned',0)} kcal</td>"
            f"<td>{w.get('feel','—')}</td></tr>"
            for w in workouts
        ) or "<tr><td colspan='3' style='color:#aaa;'>No workouts logged today</td></tr>"
        meal_html = "".join(
            f"<tr><td>{m.get('meal_name','')}</td><td>{m.get('cal',0)} kcal</td>"
            f"<td>{m.get('protein_g',0)}g / {m.get('carbs_g',0)}g / {m.get('fat_g',0)}g</td></tr>"
            for m in meals
        ) or "<tr><td colspan='3' style='color:#aaa;'>No meals logged today</td></tr>"

        return f"""<!DOCTYPE html>
<html><head>
<meta charset='UTF-8'>
<meta name='viewport' content='width=device-width,initial-scale=1'>
<title>ZENVRA — Database Dashboard</title>
<link href='https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,400;1,400&family=Jost:wght@300;400;500&display=swap' rel='stylesheet'>
<style>
*{{margin:0;padding:0;box-sizing:border-box;}}
body{{background:#F6F1E9;font-family:'Jost',sans-serif;color:#1C1914;padding:24px;}}
h1{{font-family:'Playfair Display',serif;font-size:36px;font-weight:400;color:#B8935A;margin-bottom:4px;}}
.subtitle{{font-size:13px;color:#6E6657;margin-bottom:32px;}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:16px;margin-bottom:32px;}}
.stat{{background:#FDFAF5;border:1px solid rgba(28,25,20,.09);border-radius:16px;padding:20px;}}
.stat-val{{font-family:'Playfair Display',serif;font-size:40px;font-weight:400;color:#1C1914;}}
.stat-lbl{{font-size:11px;color:#6E6657;margin-top:4px;letter-spacing:1px;text-transform:uppercase;}}
.stat-sub{{font-size:12px;color:#B8935A;margin-top:2px;}}
h2{{font-family:'Playfair Display',serif;font-size:22px;font-weight:400;margin:24px 0 12px;}}
table{{width:100%;background:#FDFAF5;border-radius:14px;overflow:hidden;border-collapse:collapse;margin-bottom:24px;}}
th{{background:#1C1914;color:#FDFAF5;padding:12px 16px;text-align:left;font-size:11px;letter-spacing:1px;text-transform:uppercase;font-weight:500;}}
td{{padding:12px 16px;border-bottom:1px solid rgba(28,25,20,.06);font-size:13px;}}
tr:last-child td{{border-bottom:none;}}
.links{{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:32px;}}
.link-btn{{background:#B8935A;color:#fff;padding:10px 20px;border-radius:100px;text-decoration:none;font-size:12px;font-weight:500;letter-spacing:.5px;transition:background .2s;}}
.link-btn:hover{{background:#D4AF72;}}
.link-btn.outline{{background:transparent;color:#B8935A;border:1px solid #B8935A;}}
.link-btn.outline:hover{{background:#B8935A;color:#fff;}}
.refresh{{font-size:11px;color:#aaa;margin-top:32px;}}
</style>
</head><body>
<h1>✦ ZENVRA Dashboard</h1>
<p class='subtitle'>Live database view · Auto-served from {self.db_path}</p>

<div class='links'>
  <a class='link-btn' href='/'>Open App</a>
  <a class='link-btn outline' href='/api/export/json'>Export JSON</a>
  <a class='link-btn outline' href='/api/export/workouts.csv'>Export Workouts CSV</a>
  <a class='link-btn outline' href='/api/export/meals.csv'>Export Meals CSV</a>
  <a class='link-btn outline' href='/api/sync'>View Full State</a>
</div>

<div class='grid'>
  <div class='stat'>
    <div class='stat-val'>{today.get('steps',0):,}</div>
    <div class='stat-lbl'>Steps Today</div>
    <div class='stat-sub'>Goal: 10,000</div>
  </div>
  <div class='stat'>
    <div class='stat-val'>{today.get('water',0)}<span style='font-size:20px'>/8</span></div>
    <div class='stat-lbl'>Water Glasses</div>
    <div class='stat-sub'>{"✅ Hydrated!" if today.get('water',0)>=8 else "Keep going"}</div>
  </div>
  <div class='stat'>
    <div class='stat-val'>{today.get('cal_in',0)}</div>
    <div class='stat-lbl'>Calories In</div>
    <div class='stat-sub'>Protein: {today.get('protein_g',0)}g</div>
  </div>
  <div class='stat'>
    <div class='stat-val'>{len(workouts)}</div>
    <div class='stat-lbl'>Workouts Today</div>
    <div class='stat-sub'>{len(meals)} meals logged</div>
  </div>
  <div class='stat'>
    <div class='stat-val'>{streak.get('streak_count',0)}🔥</div>
    <div class='stat-lbl'>Day Streak</div>
    <div class='stat-sub'>Last: {streak.get('last_date','—')}</div>
  </div>
  <div class='stat'>
    <div class='stat-val'>{len(thoughts)}</div>
    <div class='stat-lbl'>Imported Thoughts</div>
    <div class='stat-sub'>User-added quotes</div>
  </div>
  <div class='stat'>
    <div class='stat-val'>{metrics.get('weight_kg','—')}</div>
    <div class='stat-lbl'>Weight (kg)</div>
    <div class='stat-sub'>BMI: {metrics.get('bmi','—')}</div>
  </div>
  <div class='stat'>
    <div class='stat-val'>{prs.get('deadlift_kg',0) or '—'}</div>
    <div class='stat-lbl'>Deadlift PR (kg)</div>
    <div class='stat-sub'>Bench: {prs.get('bench_kg',0) or '—'}kg</div>
  </div>
</div>

<h2>🏋️ Today's Workouts</h2>
<table><thead><tr><th>Exercise</th><th>Calories Burned</th><th>Feel</th></tr></thead>
<tbody>{workout_html}</tbody></table>

<h2>🥗 Today's Meals</h2>
<table><thead><tr><th>Meal</th><th>Calories</th><th>Protein / Carbs / Fat</th></tr></thead>
<tbody>{meal_html}</tbody></table>

<h2>🏆 Milestones</h2>
<table><thead><tr><th>Milestone</th><th>Progress</th><th>Status</th></tr></thead>
<tbody>{ms_html}</tbody></table>

<p class='refresh'>Dashboard · <a href='/dashboard' style='color:#B8935A'>Refresh</a> · DB: {DB_PATH}</p>
</body></html>"""

    return app


# ═════════════════════════════════════════════════════════════════════════════
#  MAIN
# ═════════════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    print("""
╔══════════════════════════════════════════════════════════════╗
║                  ZENVRA DATABASE SYSTEM                      ║
╚══════════════════════════════════════════════════════════════╝
""")

    # 1. Init database
    db = ZenvraDB()
    db.print_dashboard()

    if not FLASK_AVAILABLE:
        print("⚠  Flask not installed. Database created but web server skipped.")
        print("   Run:  pip install flask flask-cors")
        print("   Then: python zenvra_database.py")
        print()
        print("   Database file is ready at:", DB_PATH)
        print("   You can use ZenvraDB() class directly in your code.")
        raise SystemExit(0)

    # 2. Copy HTML files into working dir if needed
    for fname in ('zenvra-complete.html', 'zenvra-onboarding.html'):
        src = Path(__file__).parent.parent / fname
        dest = Path(__file__).parent / fname
        if src.exists() and not dest.exists():
            import shutil
            shutil.copy(src, dest)
            print(f"  Copied {fname} → {dest}")

    # 3. Start web server
    app = create_app(db)

    print(f"""
  ✦ ZENVRA server running!
  ─────────────────────────────────────────────
  🌐 App:        http://localhost:{PORT}
  📊 Dashboard:  http://localhost:{PORT}/dashboard
  📁 Database:   {DB_PATH}
  ─────────────────────────────────────────────
  REST API endpoints:
    GET  /api/daily            → today's log
    POST /api/workouts         → log workout
    POST /api/meals            → log meal
    POST /api/steps            → add steps
    POST /api/water            → add glass
    GET  /api/prs              → personal records
    GET  /api/streak           → streak info
    GET  /api/thoughts         → imported thoughts
    POST /api/thoughts         → add thought(s)
    GET  /api/sync             → full app state
    GET  /api/export/json      → export all data
    GET  /api/export/workouts.csv
    GET  /api/export/meals.csv
  ─────────────────────────────────────────────
  Press CTRL+C to stop.
""")

    app.run(debug=False, port=PORT, host='127.0.0.1')
