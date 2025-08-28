import sqlite3, shutil
from pathlib import Path
from app.utils_paths import appdata_dir

DB_PATH = appdata_dir() / "hris.db"

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_conn(); cur = conn.cursor()
    cur.executescript(
        '''
        CREATE TABLE IF NOT EXISTS departments(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS employees(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_no TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            department_id INTEGER,
            position TEXT
        );
        CREATE TABLE IF NOT EXISTS attendance(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            in_time TEXT,
            out_time TEXT,
            lunch_minutes INTEGER DEFAULT 60,
            mode TEXT DEFAULT 'office',
            note TEXT,
            UNIQUE(employee_id, date)
        );
        CREATE TABLE IF NOT EXISTS overtime_requests(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            minutes INTEGER NOT NULL,
            reason TEXT,
            manager_status TEXT DEFAULT 'pending',
            hr_status TEXT DEFAULT 'pending',
            status TEXT DEFAULT 'pending'
        );
        CREATE TABLE IF NOT EXISTS leave_requests(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            type TEXT DEFAULT '연차',
            reason TEXT,
            manager_status TEXT DEFAULT 'pending',
            hr_status TEXT DEFAULT 'pending',
            status TEXT DEFAULT 'pending'
        );
        CREATE TABLE IF NOT EXISTS correction_requests(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            new_in_time TEXT,
            new_out_time TEXT,
            new_lunch_minutes INTEGER,
            reason TEXT,
            manager_status TEXT DEFAULT 'pending',
            hr_status TEXT DEFAULT 'pending',
            status TEXT DEFAULT 'pending'
        );
        CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            salt TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL,
            employee_id INTEGER
        );
        CREATE TABLE IF NOT EXISTS settings(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            alert_request TEXT DEFAULT '팝업 알림',
            alert_approve TEXT DEFAULT '팝업 알림',
            alert_complete TEXT DEFAULT '팝업 알림',
            default_lunch INTEGER DEFAULT 60,
            weekly_cap_minutes INTEGER DEFAULT 3120
        );
        CREATE TABLE IF NOT EXISTS holidays(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS audit_logs(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            actor_user_id INTEGER,
            action TEXT,
            target_type TEXT,
            target_id INTEGER,
            detail TEXT
        );
        CREATE TABLE IF NOT EXISTS leave_balances(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER UNIQUE NOT NULL,
            annual_total REAL DEFAULT 15.0,
            annual_used  REAL DEFAULT 0.0
        );
        -- ===== Performance =====
        CREATE TABLE IF NOT EXISTS goals(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER NOT NULL,
            quarter TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            weight REAL DEFAULT 1.0,
            progress REAL DEFAULT 0.0,
            manager_status TEXT DEFAULT 'pending',
            hr_status TEXT DEFAULT 'pending',
            status TEXT DEFAULT 'draft',
            updated_at TEXT
        );
        CREATE TABLE IF NOT EXISTS reviews(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER NOT NULL,   -- 피평가자
            reviewer_id INTEGER NOT NULL,   -- 평가자(사용자 id)
            period TEXT NOT NULL,           -- 예: 2025Q3
            category TEXT NOT NULL,         -- self/peer/manager
            score REAL NOT NULL,
            comment TEXT,
            submitted_at TEXT
        );
        CREATE TABLE IF NOT EXISTS competencies(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT
        );
        CREATE TABLE IF NOT EXISTS employee_competencies(
            employee_id INTEGER NOT NULL,
            competency_id INTEGER NOT NULL,
            level INTEGER DEFAULT 3,
            note TEXT,
            PRIMARY KEY(employee_id, competency_id)
        );
        CREATE TABLE IF NOT EXISTS feedback(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_id INTEGER NOT NULL,  -- 보낸 사람(사용자 id)
            to_id INTEGER NOT NULL,    -- 받은 사람(사용자 id)
            comment TEXT NOT NULL,
            visibility TEXT DEFAULT 'manager', -- private/manager/public
            created_at TEXT
        );
        '''
    )
    conn.commit(); conn.close()

def backup_to(path: str):
    src = DB_PATH; dst = Path(path); dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)

def restore_from(path: str):
    src = Path(path); shutil.copy2(src, DB_PATH)
