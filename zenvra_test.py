"""
╔══════════════════════════════════════════════════════════════════╗
║            ZENVRA — Quick Database Test                          ║
║                                                                  ║
║  Run this to verify everything works before starting the server  ║
║                                                                  ║
║    python zenvra_test.py                                         ║
╚══════════════════════════════════════════════════════════════════╝
"""

import sys
import json
from pathlib import Path

# Allow importing from same directory
sys.path.insert(0, str(Path(__file__).parent))
from zenvra_database import ZenvraDB

def run_tests():
    print("\n" + "═"*55)
    print("  ✦  ZENVRA DATABASE TEST SUITE")
    print("═"*55)

    # ── Init ────────────────────────────────────────────────────
    print("\n[1/9] Initialising database...")
    db = ZenvraDB(Path(__file__).parent / "zenvra_test.db")
    print("      ✓ Database created")

    # ── Daily log ───────────────────────────────────────────────
    print("\n[2/9] Daily log...")
    today = db.get_or_create_daily()
    assert 'log_date' in today, "FAIL: no log_date"
    updated = db.update_daily({'steps': 5000, 'water': 4})
    assert updated['steps'] == 5000, "FAIL: steps not saved"
    assert updated['water'] == 4, "FAIL: water not saved"
    print(f"      ✓ Date: {today['log_date']}  steps=5000  water=4/8")

    # ── Workouts ────────────────────────────────────────────────
    print("\n[3/9] Logging workouts...")
    w1 = db.add_workout({
        'workout_id': 'bench', 'workout_name': 'Bench Press',
        'workout_emoji': '🏋️', 'category': 'gym',
        'sets': 4, 'reps': 8, 'weight_kg': 80,
        'cal_burned': 220, 'feel': '💪 Beast mode'
    })
    assert w1.get('workout_name') == 'Bench Press', "FAIL: workout not saved"
    w2 = db.add_workout({
        'workout_id': 'pushup', 'workout_name': 'Push-Ups',
        'workout_emoji': '💪', 'category': 'calisthenics',
        'sets': 5, 'reps': 25, 'cal_burned': 80
    })
    workouts = db.get_workouts_today()
    assert len(workouts) == 2, f"FAIL: expected 2 workouts, got {len(workouts)}"
    print(f"      ✓ 2 workouts logged: Bench Press (80kg), Push-Ups (25 reps)")

    # ── PRs ─────────────────────────────────────────────────────
    print("\n[4/9] Personal records...")
    db.update_pr('bench_kg', 80)
    db.update_pr('bench_kg', 75)  # Should NOT update (lower)
    db.update_pr('pushup_max', 25)
    prs = db.get_prs()
    assert prs['bench_kg'] == 80, f"FAIL: bench PR should be 80, got {prs['bench_kg']}"
    assert prs['pushup_max'] == 25, "FAIL: pushup PR not saved"
    print(f"      ✓ Bench PR: {prs['bench_kg']}kg  Push-Up PR: {prs['pushup_max']} reps")

    # ── Meals ───────────────────────────────────────────────────
    print("\n[5/9] Logging meals...")
    m1 = db.add_meal({
        'meal_name': 'Grilled Chicken + Rice', 'meal_time': 'Lunch',
        'cal': 480, 'protein_g': 42, 'carbs_g': 55, 'fat_g': 8
    })
    m2 = db.add_meal({
        'meal_name': 'Greek Yoghurt + Berries', 'meal_time': 'Breakfast',
        'cal': 210, 'protein_g': 18, 'carbs_g': 24, 'fat_g': 4
    })
    meals = db.get_meals_today()
    assert len(meals) == 2, "FAIL: 2 meals expected"
    daily = db.get_or_create_daily()
    assert daily['cal_in'] == 690, f"FAIL: total cal should be 690, got {daily['cal_in']}"
    print(f"      ✓ 2 meals  Total: 690 kcal  Protein: {daily['protein_g']}g")

    # ── Metrics ─────────────────────────────────────────────────
    print("\n[6/9] Body metrics...")
    db.save_metrics({'weight_kg': 78.5, 'height_cm': 178, 'body_fat_pct': 16.2, 'resting_hr': 58})
    m = db.get_latest_metrics()
    assert m['weight_kg'] == 78.5, "FAIL: weight not saved"
    print(f"      ✓ Weight: {m['weight_kg']}kg  BMI: {m['bmi']}  BF: {m['body_fat_pct']}%")

    # ── Streak ──────────────────────────────────────────────────
    print("\n[7/9] Streak tracking...")
    s = db.update_streak()
    assert s['streak_count'] >= 1, "FAIL: streak should be >= 1"
    s2 = db.update_streak()  # Should NOT increment twice on same day
    assert s2['streak_count'] == s['streak_count'], "FAIL: double-counted streak"
    print(f"      ✓ Streak: {s['streak_count']} day(s)  Last: {s['last_date']}")

    # ── Thoughts ────────────────────────────────────────────────
    print("\n[8/9] Importing thoughts...")
    t1 = db.add_thought({'text': 'Strength is built in silence.', 'cat': 'gym'})
    t2 = db.add_thought({'text': 'Progress over perfection.', 'cat': 'work'})
    count = db.add_thoughts_bulk([
        {'text': 'Rest is a weapon.', 'cat': 'gym'},
        {'text': 'Show up anyway.', 'cat': 'gym'},
    ])
    gym_thoughts = db.get_thoughts('gym')
    assert len(gym_thoughts) == 3, f"FAIL: 3 gym thoughts expected, got {len(gym_thoughts)}"
    print(f"      ✓ Gym thoughts: {len(gym_thoughts)}  Work thoughts: {len(db.get_thoughts('work'))}")

    # ── Milestones ──────────────────────────────────────────────
    print("\n[9/9] Milestones...")
    daily_today = db.get_or_create_daily()
    ms = db.update_milestones({
        'pushup_max': 25,
        'steps': daily_today.get('steps', 5000),
        'water': daily_today.get('water', 4),
        'deadlift_kg': 0,
        'streak_count': s['streak_count'],
    })
    assert len(ms) == 5, f"FAIL: 5 milestones expected, got {len(ms)}"
    print(f"      ✓ 5 milestones tracked")
    for m in ms:
        bar = '█' * int((m['progress'] / m['goal']) * 10) + '░' * (10 - int((m['progress'] / m['goal']) * 10))
        print(f"         {bar}  {m['milestone_name']} ({m['progress']:.0f}/{m['goal']:.0f})")

    # ── Export ──────────────────────────────────────────────────
    print("\n✓ JSON export check...")
    export = db.export_json()
    assert 'streak' in export
    assert 'personal_records' in export
    assert 'milestones' in export
    print(f"      ✓ Export has {len(export)} top-level keys")

    # ── Final dashboard ─────────────────────────────────────────
    db.print_dashboard()

    # Cleanup test DB
    import os
    test_db = Path(__file__).parent / "zenvra_test.db"
    if test_db.exists():
        os.remove(test_db)

    print("═"*55)
    print("  ✅  ALL TESTS PASSED — Database is working perfectly!")
    print("═"*55)
    print(f"\n  Now run:  python zenvra_database.py")
    print("  Then open: http://localhost:5000\n")

if __name__ == '__main__':
    run_tests()
