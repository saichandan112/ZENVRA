/**
 * ZENVRA Database Layer
 * Uses Capacitor SQLite for native on-device storage
 * Falls back to localStorage when running in browser
 */

const ZenvraDB = (() => {
  let db = null;
  let isNative = false;
  let isReady = false;
  const readyCallbacks = [];

  // ── Table Definitions ──────────────────────────────────────
  const TABLES = `
    CREATE TABLE IF NOT EXISTS daily_logs (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      log_date TEXT UNIQUE NOT NULL,
      steps INTEGER DEFAULT 0,
      water INTEGER DEFAULT 0,
      cal_in INTEGER DEFAULT 0,
      protein_g REAL DEFAULT 0,
      carbs_g REAL DEFAULT 0,
      fat_g REAL DEFAULT 0,
      cal_burned INTEGER DEFAULT 0,
      workouts_done INTEGER DEFAULT 0,
      watch_done INTEGER DEFAULT 0,
      created_at TEXT DEFAULT (datetime('now','localtime'))
    );

    CREATE TABLE IF NOT EXISTS workouts (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      log_date TEXT NOT NULL,
      workout_id TEXT,
      workout_name TEXT NOT NULL,
      workout_emoji TEXT DEFAULT '',
      category TEXT DEFAULT 'custom',
      sets INTEGER DEFAULT 0,
      reps INTEGER DEFAULT 0,
      weight_kg REAL DEFAULT 0,
      duration_min INTEGER DEFAULT 0,
      cal_burned INTEGER DEFAULT 0,
      feel TEXT DEFAULT '',
      logged_at TEXT DEFAULT (datetime('now','localtime'))
    );

    CREATE TABLE IF NOT EXISTS meals (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      log_date TEXT NOT NULL,
      meal_name TEXT NOT NULL,
      meal_time TEXT DEFAULT '',
      cal INTEGER DEFAULT 0,
      protein_g REAL DEFAULT 0,
      carbs_g REAL DEFAULT 0,
      fat_g REAL DEFAULT 0,
      logged_at TEXT DEFAULT (datetime('now','localtime'))
    );

    CREATE TABLE IF NOT EXISTS metrics (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      weight_kg REAL,
      height_cm REAL,
      bmi REAL,
      body_fat_pct REAL,
      resting_hr INTEGER,
      recorded_at TEXT DEFAULT (datetime('now','localtime'))
    );

    CREATE TABLE IF NOT EXISTS personal_records (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      pr_key TEXT UNIQUE NOT NULL,
      pr_value REAL NOT NULL DEFAULT 0,
      updated_at TEXT DEFAULT (datetime('now','localtime'))
    );

    CREATE TABLE IF NOT EXISTS streaks (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      streak_count INTEGER DEFAULT 0,
      last_date TEXT,
      best_streak INTEGER DEFAULT 0,
      updated_at TEXT DEFAULT (datetime('now','localtime'))
    );

    CREATE TABLE IF NOT EXISTS thoughts (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      text TEXT NOT NULL,
      cat TEXT DEFAULT 'general',
      added_at TEXT DEFAULT (datetime('now','localtime'))
    );

    CREATE TABLE IF NOT EXISTS reminders (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      reminder_key TEXT UNIQUE NOT NULL,
      enabled INTEGER DEFAULT 0,
      time_value TEXT DEFAULT '',
      updated_at TEXT DEFAULT (datetime('now','localtime'))
    );

    CREATE TABLE IF NOT EXISTS milestones (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      milestone_key TEXT UNIQUE NOT NULL,
      milestone_name TEXT NOT NULL,
      goal REAL NOT NULL,
      progress REAL DEFAULT 0,
      emoji TEXT DEFAULT '',
      updated_at TEXT DEFAULT (datetime('now','localtime'))
    );

    CREATE TABLE IF NOT EXISTS sessions (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      session_key TEXT UNIQUE NOT NULL,
      session_value TEXT DEFAULT '',
      updated_at TEXT DEFAULT (datetime('now','localtime'))
    );

    CREATE TABLE IF NOT EXISTS app_data (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      data_key TEXT UNIQUE NOT NULL,
      data_value TEXT DEFAULT '',
      updated_at TEXT DEFAULT (datetime('now','localtime'))
    );
  `;

  // ── Helper: Today's date string ────────────────────────────
  function today() {
    return new Date().toISOString().split('T')[0];
  }

  // ── Initialize ─────────────────────────────────────────────
  async function init() {
    if (isReady) return;

    try {
      if (window.Capacitor && window.Capacitor.isNativePlatform()) {
        const { CapacitorSQLite } = await import('@capacitor-community/sqlite');
        const sqlitePlugin = CapacitorSQLite;

        await sqlitePlugin.createConnection({
          database: 'zenvra_db',
          version: 1,
          encrypted: false,
          mode: 'no-encryption'
        });

        await sqlitePlugin.open({ database: 'zenvra_db' });

        db = {
          run: async (sql, params = []) => {
            return await sqlitePlugin.execute({
              database: 'zenvra_db',
              statements: sql,
              values: params
            });
          },
          query: async (sql, params = []) => {
            const result = await sqlitePlugin.query({
              database: 'zenvra_db',
              statement: sql,
              values: params
            });
            return result.values || [];
          }
        };

        isNative = true;

        // Create tables
        const tableStatements = TABLES.split(';').filter(s => s.trim());
        for (const stmt of tableStatements) {
          await db.run(stmt + ';');
        }
      } else {
        // Browser fallback: use Web SQL or localStorage wrapper
        await initBrowserDB();
      }
    } catch (e) {
      console.warn('SQLite init failed, using localStorage fallback:', e);
      await initBrowserDB();
    }

    isReady = true;
    readyCallbacks.forEach(cb => cb());
    readyCallbacks.length = 0;
  }

  // ── Browser fallback using localStorage with SQL-like API ──
  async function initBrowserDB() {
    isNative = false;
    db = {
      run: async (sql) => {
        // Parse basic SQL for localStorage
        return { changes: 0 };
      },
      query: async (sql) => {
        return [];
      }
    };
    // For browser, we maintain localStorage compatibility
  }

  function onReady(cb) {
    if (isReady) return cb();
    readyCallbacks.push(cb);
  }

  // ══════════════════════════════════════════════════════════
  //  STORAGE API  (works with both SQLite and localStorage)
  // ══════════════════════════════════════════════════════════

  // ── Generic Key-Value Storage ──────────────────────────────
  async function setItem(key, value) {
    const val = typeof value === 'object' ? JSON.stringify(value) : String(value);
    if (isNative && db) {
      await db.run(
        `INSERT INTO app_data (data_key, data_value, updated_at)
         VALUES ('${key}', '${val.replace(/'/g, "''")}', datetime('now','localtime'))
         ON CONFLICT(data_key) DO UPDATE SET
         data_value = '${val.replace(/'/g, "''")}', updated_at = datetime('now','localtime');`
      );
    }
    localStorage.setItem(key, val);
  }

  async function getItem(key, defaultVal = null) {
    if (isNative && db) {
      try {
        const rows = await db.query(
          `SELECT data_value FROM app_data WHERE data_key = '${key}';`
        );
        if (rows.length > 0) {
          return rows[0].data_value;
        }
      } catch (e) {}
    }
    return localStorage.getItem(key) || defaultVal;
  }

  async function removeItem(key) {
    if (isNative && db) {
      await db.run(`DELETE FROM app_data WHERE data_key = '${key}';`);
    }
    localStorage.removeItem(key);
  }

  // ── Daily Log ──────────────────────────────────────────────
  async function getDailyLog(date) {
    date = date || today();
    if (isNative && db) {
      const rows = await db.query(
        `SELECT * FROM daily_logs WHERE log_date = '${date}';`
      );
      if (rows.length > 0) return rows[0];
      await db.run(
        `INSERT INTO daily_logs (log_date) VALUES ('${date}');`
      );
      const newRows = await db.query(
        `SELECT * FROM daily_logs WHERE log_date = '${date}';`
      );
      return newRows[0] || null;
    }
    // localStorage fallback
    const key = `zvr_daily_${date}`;
    let data = localStorage.getItem(key);
    if (data) return JSON.parse(data);
    const newLog = {
      log_date: date, steps: 0, water: 0, cal_in: 0,
      protein_g: 0, carbs_g: 0, fat_g: 0, cal_burned: 0,
      workouts_done: 0, watch_done: 0
    };
    localStorage.setItem(key, JSON.stringify(newLog));
    return newLog;
  }

  async function updateDailyLog(updates, date) {
    date = date || today();
    if (isNative && db) {
      await getDailyLog(date); // ensure exists
      const setClauses = Object.entries(updates)
        .map(([k, v]) => `${k} = ${typeof v === 'string' ? `'${v}'` : v}`)
        .join(', ');
      await db.run(
        `UPDATE daily_logs SET ${setClauses} WHERE log_date = '${date}';`
      );
      return await getDailyLog(date);
    }
    // localStorage fallback
    const key = `zvr_daily_${date}`;
    let data = await getDailyLog(date);
    Object.assign(data, updates);
    localStorage.setItem(key, JSON.stringify(data));
    return data;
  }

  // ── Workouts ───────────────────────────────────────────────
  async function addWorkout(workout) {
    const date = today();
    if (isNative && db) {
      const w = workout;
      await db.run(
        `INSERT INTO workouts (log_date, workout_id, workout_name, workout_emoji, category, sets, reps, weight_kg, duration_min, cal_burned, feel)
         VALUES ('${date}', '${w.workout_id || ''}', '${(w.workout_name || '').replace(/'/g, "''")}', '${w.workout_emoji || ''}', '${w.category || 'custom'}', ${w.sets || 0}, ${w.reps || 0}, ${w.weight_kg || 0}, ${w.duration_min || 0}, ${w.cal_burned || 0}, '${(w.feel || '').replace(/'/g, "''")}');`
      );
      // Update daily log
      const daily = await getDailyLog(date);
      await updateDailyLog({
        workouts_done: (daily.workouts_done || 0) + 1,
        cal_burned: (daily.cal_burned || 0) + (w.cal_burned || 0)
      });
      return workout;
    }
    // localStorage fallback
    const key = `zvr_workouts_${date}`;
    let workouts = JSON.parse(localStorage.getItem(key) || '[]');
    workout.logged_at = new Date().toISOString();
    workouts.push(workout);
    localStorage.setItem(key, JSON.stringify(workouts));
    return workout;
  }

  async function getWorkoutsToday() {
    const date = today();
    if (isNative && db) {
      return await db.query(
        `SELECT * FROM workouts WHERE log_date = '${date}' ORDER BY logged_at DESC;`
      );
    }
    return JSON.parse(localStorage.getItem(`zvr_workouts_${date}`) || '[]');
  }

  // ── Meals ──────────────────────────────────────────────────
  async function addMeal(meal) {
    const date = today();
    if (isNative && db) {
      const m = meal;
      await db.run(
        `INSERT INTO meals (log_date, meal_name, meal_time, cal, protein_g, carbs_g, fat_g)
         VALUES ('${date}', '${(m.meal_name || '').replace(/'/g, "''")}', '${m.meal_time || ''}', ${m.cal || 0}, ${m.protein_g || 0}, ${m.carbs_g || 0}, ${m.fat_g || 0});`
      );
      // Update daily log totals
      const daily = await getDailyLog(date);
      await updateDailyLog({
        cal_in: (daily.cal_in || 0) + (m.cal || 0),
        protein_g: (daily.protein_g || 0) + (m.protein_g || 0),
        carbs_g: (daily.carbs_g || 0) + (m.carbs_g || 0),
        fat_g: (daily.fat_g || 0) + (m.fat_g || 0)
      });
      return meal;
    }
    // localStorage fallback
    const key = `zvr_meals_${date}`;
    let meals = JSON.parse(localStorage.getItem(key) || '[]');
    meal.logged_at = new Date().toISOString();
    meals.push(meal);
    localStorage.setItem(key, JSON.stringify(meals));
    return meal;
  }

  async function getMealsToday() {
    const date = today();
    if (isNative && db) {
      return await db.query(
        `SELECT * FROM meals WHERE log_date = '${date}' ORDER BY logged_at DESC;`
      );
    }
    return JSON.parse(localStorage.getItem(`zvr_meals_${date}`) || '[]');
  }

  // ── Metrics ────────────────────────────────────────────────
  async function saveMetrics(metrics) {
    const bmi = (metrics.weight_kg && metrics.height_cm)
      ? parseFloat((metrics.weight_kg / ((metrics.height_cm / 100) ** 2)).toFixed(1))
      : 0;
    if (isNative && db) {
      await db.run(
        `INSERT INTO metrics (weight_kg, height_cm, bmi, body_fat_pct, resting_hr)
         VALUES (${metrics.weight_kg || 0}, ${metrics.height_cm || 0}, ${bmi}, ${metrics.body_fat_pct || 0}, ${metrics.resting_hr || 0});`
      );
      return { ...metrics, bmi };
    }
    const data = { ...metrics, bmi, recorded_at: new Date().toISOString() };
    localStorage.setItem('zvr_metrics', JSON.stringify(data));
    return data;
  }

  async function getLatestMetrics() {
    if (isNative && db) {
      const rows = await db.query(
        `SELECT * FROM metrics ORDER BY recorded_at DESC LIMIT 1;`
      );
      return rows[0] || null;
    }
    const data = localStorage.getItem('zvr_metrics');
    return data ? JSON.parse(data) : null;
  }

  // ── Personal Records ───────────────────────────────────────
  async function updatePR(key, value) {
    if (isNative && db) {
      const existing = await db.query(
        `SELECT pr_value FROM personal_records WHERE pr_key = '${key}';`
      );
      if (existing.length === 0 || value > existing[0].pr_value) {
        await db.run(
          `INSERT INTO personal_records (pr_key, pr_value, updated_at)
           VALUES ('${key}', ${value}, datetime('now','localtime'))
           ON CONFLICT(pr_key) DO UPDATE SET
           pr_value = ${value}, updated_at = datetime('now','localtime');`
        );
      }
      return;
    }
    // localStorage fallback
    const prs = JSON.parse(localStorage.getItem('zvr_prs') || '{}');
    if (!prs[key] || value > prs[key]) {
      prs[key] = value;
      localStorage.setItem('zvr_prs', JSON.stringify(prs));
    }
  }

  async function getPRs() {
    if (isNative && db) {
      const rows = await db.query(`SELECT pr_key, pr_value FROM personal_records;`);
      const prs = {};
      rows.forEach(r => prs[r.pr_key] = r.pr_value);
      return prs;
    }
    return JSON.parse(localStorage.getItem('zvr_prs') || '{}');
  }

  // ── Streaks ────────────────────────────────────────────────
  async function updateStreak() {
    const date = today();
    if (isNative && db) {
      let rows = await db.query(`SELECT * FROM streaks ORDER BY id DESC LIMIT 1;`);
      if (rows.length === 0) {
        await db.run(
          `INSERT INTO streaks (streak_count, last_date, best_streak) VALUES (1, '${date}', 1);`
        );
        return { streak_count: 1, last_date: date, best_streak: 1 };
      }
      const s = rows[0];
      if (s.last_date === date) return s;
      const yesterday = new Date();
      yesterday.setDate(yesterday.getDate() - 1);
      const yesterdayStr = yesterday.toISOString().split('T')[0];
      const newCount = s.last_date === yesterdayStr ? s.streak_count + 1 : 1;
      const newBest = Math.max(s.best_streak || 0, newCount);
      await db.run(
        `UPDATE streaks SET streak_count = ${newCount}, last_date = '${date}', best_streak = ${newBest}, updated_at = datetime('now','localtime') WHERE id = ${s.id};`
      );
      return { streak_count: newCount, last_date: date, best_streak: newBest };
    }
    // localStorage fallback
    let streak = JSON.parse(localStorage.getItem('zvr_streak') || '{"streak_count":0,"last_date":"","best_streak":0}');
    if (streak.last_date === date) return streak;
    const yesterday = new Date();
    yesterday.setDate(yesterday.getDate() - 1);
    const yesterdayStr = yesterday.toISOString().split('T')[0];
    streak.streak_count = streak.last_date === yesterdayStr ? streak.streak_count + 1 : 1;
    streak.best_streak = Math.max(streak.best_streak || 0, streak.streak_count);
    streak.last_date = date;
    localStorage.setItem('zvr_streak', JSON.stringify(streak));
    return streak;
  }

  async function getStreak() {
    if (isNative && db) {
      const rows = await db.query(`SELECT * FROM streaks ORDER BY id DESC LIMIT 1;`);
      return rows[0] || { streak_count: 0, last_date: '', best_streak: 0 };
    }
    return JSON.parse(localStorage.getItem('zvr_streak') || '{"streak_count":0,"last_date":"","best_streak":0}');
  }

  // ── Thoughts ───────────────────────────────────────────────
  async function addThought(thought) {
    if (isNative && db) {
      await db.run(
        `INSERT INTO thoughts (text, cat) VALUES ('${thought.text.replace(/'/g, "''")}', '${thought.cat || 'general'}');`
      );
      return thought;
    }
    const thoughts = JSON.parse(localStorage.getItem('zvr_thoughts') || '[]');
    thought.id = Date.now();
    thoughts.push(thought);
    localStorage.setItem('zvr_thoughts', JSON.stringify(thoughts));
    return thought;
  }

  async function getThoughts(cat) {
    if (isNative && db) {
      const where = cat ? `WHERE cat = '${cat}'` : '';
      return await db.query(`SELECT * FROM thoughts ${where} ORDER BY added_at DESC;`);
    }
    const thoughts = JSON.parse(localStorage.getItem('zvr_thoughts') || '[]');
    return cat ? thoughts.filter(t => t.cat === cat) : thoughts;
  }

  async function deleteThought(id) {
    if (isNative && db) {
      await db.run(`DELETE FROM thoughts WHERE id = ${id};`);
      return;
    }
    let thoughts = JSON.parse(localStorage.getItem('zvr_thoughts') || '[]');
    thoughts = thoughts.filter(t => t.id !== id);
    localStorage.setItem('zvr_thoughts', JSON.stringify(thoughts));
  }

  // ── Reminders ──────────────────────────────────────────────
  async function setReminder(key, enabled, timeValue) {
    if (isNative && db) {
      await db.run(
        `INSERT INTO reminders (reminder_key, enabled, time_value, updated_at)
         VALUES ('${key}', ${enabled ? 1 : 0}, '${timeValue || ''}', datetime('now','localtime'))
         ON CONFLICT(reminder_key) DO UPDATE SET
         enabled = ${enabled ? 1 : 0}, time_value = '${timeValue || ''}', updated_at = datetime('now','localtime');`
      );
      return;
    }
    const reminders = JSON.parse(localStorage.getItem('zvr_reminders') || '{}');
    reminders[key] = { enabled, time_value: timeValue };
    localStorage.setItem('zvr_reminders', JSON.stringify(reminders));
  }

  async function getReminder(key) {
    if (isNative && db) {
      const rows = await db.query(
        `SELECT * FROM reminders WHERE reminder_key = '${key}';`
      );
      return rows[0] || { enabled: 0, time_value: '' };
    }
    const reminders = JSON.parse(localStorage.getItem('zvr_reminders') || '{}');
    return reminders[key] || { enabled: false, time_value: '' };
  }

  // ── Milestones ─────────────────────────────────────────────
  async function updateMilestone(key, name, goal, progress, emoji) {
    if (isNative && db) {
      await db.run(
        `INSERT INTO milestones (milestone_key, milestone_name, goal, progress, emoji, updated_at)
         VALUES ('${key}', '${name.replace(/'/g, "''")}', ${goal}, ${progress}, '${emoji || ''}', datetime('now','localtime'))
         ON CONFLICT(milestone_key) DO UPDATE SET
         progress = ${progress}, updated_at = datetime('now','localtime');`
      );
      return;
    }
    const ms = JSON.parse(localStorage.getItem('zvr_milestones') || '{}');
    ms[key] = { name, goal, progress, emoji };
    localStorage.setItem('zvr_milestones', JSON.stringify(ms));
  }

  async function getMilestones() {
    if (isNative && db) {
      return await db.query(`SELECT * FROM milestones ORDER BY milestone_key;`);
    }
    return JSON.parse(localStorage.getItem('zvr_milestones') || '{}');
  }

  // ── Session/Onboarding ─────────────────────────────────────
  async function setSession(key, value) {
    if (isNative && db) {
      await db.run(
        `INSERT INTO sessions (session_key, session_value, updated_at)
         VALUES ('${key}', '${String(value).replace(/'/g, "''")}', datetime('now','localtime'))
         ON CONFLICT(session_key) DO UPDATE SET
         session_value = '${String(value).replace(/'/g, "''")}', updated_at = datetime('now','localtime');`
      );
    }
    localStorage.setItem(key, String(value));
  }

  async function getSession(key) {
    if (isNative && db) {
      const rows = await db.query(
        `SELECT session_value FROM sessions WHERE session_key = '${key}';`
      );
      if (rows.length > 0) return rows[0].session_value;
    }
    return localStorage.getItem(key);
  }

  // ── Export All Data ────────────────────────────────────────
  async function exportAll() {
    const data = {};
    if (isNative && db) {
      data.daily_logs = await db.query(`SELECT * FROM daily_logs ORDER BY log_date DESC;`);
      data.workouts = await db.query(`SELECT * FROM workouts ORDER BY logged_at DESC;`);
      data.meals = await db.query(`SELECT * FROM meals ORDER BY logged_at DESC;`);
      data.metrics = await db.query(`SELECT * FROM metrics ORDER BY recorded_at DESC;`);
      data.personal_records = await db.query(`SELECT * FROM personal_records;`);
      data.streaks = await db.query(`SELECT * FROM streaks ORDER BY id DESC LIMIT 1;`);
      data.thoughts = await db.query(`SELECT * FROM thoughts ORDER BY added_at DESC;`);
      data.milestones = await db.query(`SELECT * FROM milestones;`);
    } else {
      data.daily_log = await getDailyLog();
      data.workouts = await getWorkoutsToday();
      data.meals = await getMealsToday();
      data.metrics = await getLatestMetrics();
      data.personal_records = await getPRs();
      data.streak = await getStreak();
    }
    return data;
  }

  // ── Public API ─────────────────────────────────────────────
  return {
    init,
    onReady,
    isNativePlatform: () => isNative,

    // Key-value
    setItem,
    getItem,
    removeItem,

    // Daily logs
    getDailyLog,
    updateDailyLog,

    // Workouts
    addWorkout,
    getWorkoutsToday,

    // Meals
    addMeal,
    getMealsToday,

    // Metrics
    saveMetrics,
    getLatestMetrics,

    // Personal Records
    updatePR,
    getPRs,

    // Streaks
    updateStreak,
    getStreak,

    // Thoughts
    addThought,
    getThoughts,
    deleteThought,

    // Reminders
    setReminder,
    getReminder,

    // Milestones
    updateMilestone,
    getMilestones,

    // Session
    setSession,
    getSession,

    // Export
    exportAll
  };
})();

// Auto-init when DOM ready
document.addEventListener('DOMContentLoaded', () => {
  ZenvraDB.init().catch(e => console.warn('DB init error:', e));
});
