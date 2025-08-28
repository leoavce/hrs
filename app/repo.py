from app.core_db import get_conn
from datetime import datetime

class Repo:
    def __init__(self): pass

    # ===== Users =====
    def user_by_username(self, username: str):
        with get_conn() as c:
            return c.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()

    def create_user(self, username: str, salt: str, hash_hex: str, role: str, employee_id: int | None):
        with get_conn() as conn:
            conn.execute("INSERT INTO users(username,salt,password_hash,role,employee_id) VALUES(?,?,?,?,?)",
                         (username, salt, hash_hex, role, employee_id))

    def users(self):
        with get_conn() as c:
            return c.execute("SELECT * FROM users ORDER BY id").fetchall()

    def update_user_password(self, user_id: int, salt: str, hash_hex: str):
        with get_conn() as c:
            c.execute("UPDATE users SET salt=?, password_hash=? WHERE id=?", (salt, hash_hex, user_id))

    def update_user_role(self, user_id: int, role: str, employee_id: int | None):
        with get_conn() as c:
            c.execute("UPDATE users SET role=?, employee_id=? WHERE id=?", (role, employee_id, user_id))

    def delete_user(self, user_id: int):
        with get_conn() as c:
            c.execute("DELETE FROM users WHERE id=?", (user_id,))

    # ===== Departments / Employees =====
    def departments(self):
        with get_conn() as c:
            return c.execute("SELECT * FROM departments ORDER BY id").fetchall()

    def add_department(self, name: str):
        with get_conn() as c:
            c.execute("INSERT INTO departments(name) VALUES(?)", (name,))

    def employees(self):
        with get_conn() as c:
            return c.execute("SELECT * FROM employees ORDER BY id").fetchall()

    def add_employee(self, employee_no: str, name: str, email: str, department_id: int, position: str | None):
        with get_conn() as c:
            c.execute("INSERT INTO employees(employee_no,name,email,department_id,position) VALUES(?,?,?,?,?)",
                      (employee_no, name, email, department_id, position))
            emp_id = c.execute("SELECT id FROM employees WHERE employee_no=?", (employee_no,)).fetchone()["id"]
            c.execute("INSERT OR IGNORE INTO leave_balances(employee_id) VALUES(?)", (emp_id,))

    # ===== Attendance =====
    def attendance_for(self, employee_id: int, date_str: str):
        with get_conn() as c:
            return c.execute("SELECT * FROM attendance WHERE employee_id=? AND date=?", (employee_id, date_str)).fetchone()

    def attendance_range(self, employee_id: int, s: str, e: str):
        with get_conn() as c:
            return c.execute("SELECT * FROM attendance WHERE employee_id=? AND date BETWEEN ? AND ? ORDER BY date", (employee_id, s, e)).fetchall()

    def upsert_attendance(self, data: dict):
        with get_conn() as c:
            old = c.execute("SELECT id FROM attendance WHERE employee_id=? AND date=?", (data['employee_id'], data['date'])).fetchone()
            if old:
                c.execute("""UPDATE attendance SET in_time=?, out_time=?, lunch_minutes=?, mode=?, note=? 
                             WHERE employee_id=? AND date=?""",
                          (data.get('in_time'), data.get('out_time'), data.get('lunch_minutes',60), data.get('mode','office'), data.get('note'),
                           data['employee_id'], data['date']))
            else:
                c.execute("""INSERT INTO attendance(employee_id,date,in_time,out_time,lunch_minutes,mode,note) 
                             VALUES(?,?,?,?,?,?,?)""",
                          (data['employee_id'], data['date'], data.get('in_time'), data.get('out_time'),
                           data.get('lunch_minutes',60), data.get('mode','office'), data.get('note')))

    # ===== Requests (2-stage approval) =====
    def _derive_status(self, m, h):
        if m=="rejected" or h=="rejected": return "rejected"
        if m=="approved" and h=="approved": return "approved"
        return "pending"

    # Overtime
    def save_overtime(self, data: dict):
        with get_conn() as c:
            c.execute("""INSERT INTO overtime_requests(employee_id,date,start_time,end_time,minutes,reason) VALUES(?,?,?,?,?,?)""",
                      (data['employee_id'], data['date'], data['start_time'], data['end_time'], data['minutes'], data.get('reason')))

    def overtimes_for_role(self, role: str, manager_dept_id: int | None):
        sql = "SELECT o.* FROM overtime_requests o"
        params = []
        if role=="manager" and manager_dept_id:
            sql += " JOIN employees e ON o.employee_id=e.id WHERE e.department_id=?"
            params.append(manager_dept_id)
        elif role=="hr":
            sql += " WHERE o.manager_status='approved'"
        return get_conn().execute(sql, tuple(params)).fetchall() if params or "WHERE" in sql else \
               get_conn().execute("SELECT * FROM overtime_requests ORDER BY id DESC").fetchall()

    def set_overtime_stage(self, id: int, stage: str, approve: bool):
        col = "manager_status" if stage=="manager" else "hr_status"
        with get_conn() as c:
            c.execute(f"UPDATE overtime_requests SET {col}=? WHERE id=?", ("approved" if approve else "rejected", id))
            row = c.execute("SELECT manager_status, hr_status FROM overtime_requests WHERE id=?", (id,)).fetchone()
            status = self._derive_status(row["manager_status"], row["hr_status"])
            c.execute("UPDATE overtime_requests SET status=? WHERE id=?", (status, id))

    # Leave
    def save_leave(self, data: dict):
        with get_conn() as c:
            if data.get('type')=="연차":
                bal = c.execute("SELECT * FROM leave_balances WHERE employee_id=?", (data['employee_id'],)).fetchone()
                if not bal:
                    c.execute("INSERT OR IGNORE INTO leave_balances(employee_id) VALUES(?)", (data['employee_id'],))
            c.execute("""INSERT INTO leave_requests(employee_id,start_date,end_date,type,reason) VALUES(?,?,?,?,?)""",
                      (data['employee_id'], data['start_date'], data['end_date'], data['type'], data.get('reason')))

    def leaves_for_role(self, role: str, manager_dept_id: int | None):
        sql = "SELECT l.* FROM leave_requests l"
        params = []
        if role=="manager" and manager_dept_id:
            sql += " JOIN employees e ON l.employee_id=e.id WHERE e.department_id=?"
            params.append(manager_dept_id)
        elif role=="hr":
            sql += " WHERE l.manager_status='approved'"
        return get_conn().execute(sql, tuple(params)).fetchall() if params or "WHERE" in sql else \
               get_conn().execute("SELECT * FROM leave_requests ORDER BY id DESC").fetchall()

    def set_leave_stage(self, id: int, stage: str, approve: bool):
        from datetime import datetime as dt
        col = "manager_status" if stage=="manager" else "hr_status"
        with get_conn() as c:
            c.execute(f"UPDATE leave_requests SET {col}=? WHERE id=?", ("approved" if approve else "rejected", id))
            row = c.execute("SELECT manager_status, hr_status, employee_id, start_date, end_date, type FROM leave_requests WHERE id=?", (id,)).fetchone()
            status = self._derive_status(row["manager_status"], row["hr_status"])
            c.execute("UPDATE leave_requests SET status=? WHERE id=?", (status, id))
            # 연차 최종 승인 시 잔여 차감
            if status=="approved" and row["type"]=="연차":
                d1 = dt.strptime(row["start_date"], "%Y-%m-%d").date()
                d2 = dt.strptime(row["end_date"], "%Y-%m-%d").date()
                days = (d2 - d1).days + 1
                bal = c.execute("SELECT * FROM leave_balances WHERE employee_id=?", (row["employee_id"],)).fetchone()
                used = (bal["annual_used"] or 0) + days
                total = bal["annual_total"] or 15.0
                if used > total:  # 초과 시 승인 롤백
                    c.execute(f"UPDATE leave_requests SET {col}='pending', status='pending' WHERE id=?", (id,))
                else:
                    c.execute("UPDATE leave_balances SET annual_used=? WHERE employee_id=?", (used, row["employee_id"]))

    # Correction
    def save_correction(self, data: dict):
        with get_conn() as c:
            c.execute("""INSERT INTO correction_requests(employee_id,date,new_in_time,new_out_time,new_lunch_minutes,reason) VALUES(?,?,?,?,?,?)""",
                      (data['employee_id'], data['date'], data.get('new_in_time'), data.get('new_out_time'),
                       data.get('new_lunch_minutes'), data.get('reason')))

    def corrections_for_role(self, role: str, manager_dept_id: int | None):
        sql = "SELECT cr.* FROM correction_requests cr"
        params = []
        if role=="manager" and manager_dept_id:
            sql += " JOIN employees e ON cr.employee_id=e.id WHERE e.department_id=?"
            params.append(manager_dept_id)
        elif role=="hr":
            sql += " WHERE cr.manager_status='approved'"
        return get_conn().execute(sql, tuple(params)).fetchall() if params or "WHERE" in sql else \
               get_conn().execute("SELECT * FROM correction_requests ORDER BY id DESC").fetchall()

    def set_correction_stage(self, id: int, stage: str, approve: bool):
        col = "manager_status" if stage=="manager" else "hr_status"
        with get_conn() as c:
            c.execute(f"UPDATE correction_requests SET {col}=? WHERE id=?", ("approved" if approve else "rejected", id))
            row = c.execute("SELECT manager_status, hr_status, employee_id, date, new_in_time, new_out_time, new_lunch_minutes FROM correction_requests WHERE id=?", (id,)).fetchone()
            status = self._derive_status(row["manager_status"], row["hr_status"])
            c.execute("UPDATE correction_requests SET status=? WHERE id=?", (status, id))
            if status=="approved":
                a = c.execute("SELECT * FROM attendance WHERE employee_id=? AND date=?", (row["employee_id"], row["date"])).fetchone()
                if a:
                    c.execute("UPDATE attendance SET in_time=?, out_time=?, lunch_minutes=? WHERE id=?",
                              (row["new_in_time"], row["new_out_time"], row["new_lunch_minutes"] or a["lunch_minutes"], a["id"]))
                else:
                    c.execute("INSERT INTO attendance(employee_id,date,in_time,out_time,lunch_minutes,mode) VALUES(?,?,?,?,?, 'office')",
                              (row["employee_id"], row["date"], row["new_in_time"], row["new_out_time"], row["new_lunch_minutes"] or 60))

    # ===== Overview =====
    def overview(self, base_date: str, dept_id: int | None, name_query: str | None):
        sql = """SELECT e.*, a.in_time, a.out_time, a.lunch_minutes, a.mode, a.note
                 FROM employees e LEFT JOIN attendance a 
                 ON a.employee_id=e.id AND a.date=?"""
        params = [base_date]
        filters=[]
        if dept_id:
            filters.append("e.department_id=?"); params.append(dept_id)
        if name_query:
            filters.append("(e.name LIKE ? OR e.email LIKE ? OR e.employee_no LIKE ?)")
            params += [f"%{name_query}%"]*3
        if filters:
            sql += " WHERE " + " AND ".join(filters)
        sql += " ORDER BY e.id"
        with get_conn() as c:
            return c.execute(sql, tuple(params)).fetchall()

    # ===== Settings / Holidays / Leave balances =====
    def get_settings(self):
        with get_conn() as c:
            s = c.execute("SELECT * FROM settings LIMIT 1").fetchone()
            if not s:
                c.execute("INSERT INTO settings(default_lunch, weekly_cap_minutes) VALUES(60, 3120)")
                s = c.execute("SELECT * FROM settings LIMIT 1").fetchone()
            return s

    def update_settings(self, **kwargs):
        sets=[]; vals=[]
        for k,v in kwargs.items():
            sets.append(f"{k}=?"); vals.append(v)
        if not sets: return
        with get_conn() as c:
            c.execute(f"UPDATE settings SET {', '.join(sets)}", tuple(vals))

    def holidays(self):
        with get_conn() as c:
            return c.execute("SELECT * FROM holidays ORDER BY date").fetchall()

    def add_holiday(self, date_str: str, name: str):
        with get_conn() as c:
            c.execute("INSERT OR IGNORE INTO holidays(date,name) VALUES(?,?)", (date_str, name))

    def delete_holiday(self, date_str: str):
        with get_conn() as c:
            c.execute("DELETE FROM holidays WHERE date=?", (date_str,))

    def get_leave_balance(self, employee_id: int):
        with get_conn() as c:
            b = c.execute("SELECT * FROM leave_balances WHERE employee_id=?", (employee_id,)).fetchone()
            if not b:
                c.execute("INSERT OR IGNORE INTO leave_balances(employee_id) VALUES(?)", (employee_id,))
                b = c.execute("SELECT * FROM leave_balances WHERE employee_id=?", (employee_id,)).fetchone()
            return b

    def set_leave_total(self, employee_id: int, total: float):
        with get_conn() as c:
            c.execute("UPDATE leave_balances SET annual_total=? WHERE employee_id=?", (total, employee_id))

    # ===== Audit =====
    def audit(self, actor_user_id: int, action: str, target_type: str, target_id: int, detail: str | None = None):
        with get_conn() as c:
            c.execute("INSERT INTO audit_logs(actor_user_id,action,target_type,target_id,detail) VALUES(?,?,?,?,?)",
                      (actor_user_id, action, target_type, target_id, detail))

    def audit_recent(self, limit: int = 200):
        with get_conn() as c:
            return c.execute("SELECT * FROM audit_logs ORDER BY id DESC LIMIT ?", (limit,)).fetchall()

    # ===== Performance =====
    # Goals
    def goals_for_role(self, role: str, employee_id: int | None, manager_dept_id: int | None, quarter: str | None = None):
        sql = "SELECT g.* FROM goals g"
        params=[]; where=[]
        if quarter:
            where.append("g.quarter=?"); params.append(quarter)
        if role in ("admin","hr"):
            pass
        elif role=="manager" and manager_dept_id:
            sql += " JOIN employees e ON g.employee_id=e.id"
            where.append("e.department_id=?"); params.append(manager_dept_id)
        else:
            where.append("g.employee_id=?"); params.append(employee_id)
        if where:
            sql += " WHERE " + " AND ".join(where)
        # SQLite에는 NULLS LAST가 없으므로 is null 플래그로 정렬
        sql += " ORDER BY (g.updated_at IS NULL) ASC, g.updated_at DESC"
        with get_conn() as c:
            return c.execute(sql, tuple(params)).fetchall()

    def create_goal(self, employee_id: int, quarter: str, title: str, description: str, weight: float):
        with get_conn() as c:
            c.execute("""INSERT INTO goals(employee_id,quarter,title,description,weight,status,updated_at) 
                         VALUES(?,?,?,?,?,'draft', datetime('now'))""",
                      (employee_id, quarter, title, description, weight))

    def update_goal_progress(self, id: int, progress: float):
        with get_conn() as c:
            c.execute("UPDATE goals SET progress=?, updated_at=datetime('now') WHERE id=?", (progress, id))

    def submit_goal(self, id: int):
        with get_conn() as c:
            c.execute("UPDATE goals SET status='submitted', updated_at=datetime('now') WHERE id=?", (id,))

    def approve_goal_stage(self, id: int, stage: str, approve: bool):
        col = "manager_status" if stage=="manager" else "hr_status"
        with get_conn() as c:
            c.execute(f"UPDATE goals SET {col}=? WHERE id=?", ("approved" if approve else "rejected", id))
            row = c.execute("SELECT manager_status, hr_status FROM goals WHERE id=?", (id,)).fetchone()
            status = "pending"
            if row["manager_status"]=="rejected" or row["hr_status"]=="rejected":
                status="rejected"
            elif row["manager_status"]=="approved" and row["hr_status"]=="approved":
                status="approved"
            c.execute("UPDATE goals SET status=?, updated_at=datetime('now') WHERE id=?", (status, id))

    # Reviews
    def add_review(self, employee_id: int, reviewer_id: int, period: str, category: str, score: float, comment: str):
        with get_conn() as c:
            c.execute("""INSERT INTO reviews(employee_id,reviewer_id,period,category,score,comment,submitted_at)
                         VALUES(?,?,?,?,?,?, datetime('now'))""",
                      (employee_id, reviewer_id, period, category, score, comment))

    def reviews_for_role(self, role: str, employee_id: int | None, manager_dept_id: int | None, period: str | None):
        sql = "SELECT r.* FROM reviews r"
        params=[]; where=[]
        if period:
            where.append("r.period=?"); params.append(period)
        if role in ("admin","hr"):
            pass
        elif role=="manager" and manager_dept_id:
            sql += " JOIN employees e ON r.employee_id=e.id"
            where.append("e.department_id=?"); params.append(manager_dept_id)
        else:
            where.append("r.employee_id=?"); params.append(employee_id)
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY r.submitted_at DESC"
        with get_conn() as c:
            return c.execute(sql, tuple(params)).fetchall()

    def review_avg_by_employee(self, period: str | None):
        sql = "SELECT employee_id, AVG(score) AS avg_score, COUNT(*) AS cnt FROM reviews"
        params=[]
        if period:
            sql += " WHERE period=?"; params.append(period)
        sql += " GROUP BY employee_id"
        with get_conn() as c:
            return c.execute(sql, tuple(params)).fetchall()

    # Competencies
    def competencies(self):
        with get_conn() as c:
            return c.execute("SELECT * FROM competencies ORDER BY id").fetchall()

    def add_competency(self, name: str, description: str):
        with get_conn() as c:
            c.execute("INSERT INTO competencies(name,description) VALUES(?,?)", (name, description))

    def set_employee_competency(self, employee_id: int, competency_id: int, level: int, note: str | None):
        with get_conn() as c:
            c.execute("""INSERT INTO employee_competencies(employee_id,competency_id,level,note) 
                         VALUES(?,?,?,?) 
                         ON CONFLICT(employee_id,competency_id) DO UPDATE SET level=excluded.level, note=excluded.note""",
                      (employee_id, competency_id, level, note))

    def employee_competencies(self, employee_id: int):
        with get_conn() as c:
            return c.execute("""SELECT ec.*, c.name FROM employee_competencies ec 
                                JOIN competencies c ON ec.competency_id=c.id
                                WHERE ec.employee_id=? ORDER BY c.id""", (employee_id,)).fetchall()

    # Feedback
    def add_feedback(self, from_id: int, to_id: int, comment: str, visibility: str):
        with get_conn() as c:
            c.execute("INSERT INTO feedback(from_id,to_id,comment,visibility,created_at) VALUES(?,?,?,?, datetime('now'))",
                      (from_id, to_id, comment, visibility))

    def feedback_received(self, to_id: int):
        with get_conn() as c:
            return c.execute("SELECT * FROM feedback WHERE to_id=? ORDER BY created_at DESC", (to_id,)).fetchall()

    def feedback_given(self, from_id: int):
        with get_conn() as c:
            return c.execute("SELECT * FROM feedback WHERE from_id=? ORDER BY created_at DESC", (from_id,)).fetchall()

    # Dashboard helpers
    def goal_progress_avg_by_employee(self, quarter: str | None):
        sql = "SELECT employee_id, AVG(progress) AS avg_prog, COUNT(*) AS cnt FROM goals"
        params=[]
        if quarter:
            sql += " WHERE quarter=?"; params.append(quarter)
        sql += " GROUP BY employee_id"
        with get_conn() as c:
            return c.execute(sql, tuple(params)).fetchall()

    def pending_goal_counts(self):
        with get_conn() as c:
            return c.execute(
                "SELECT COUNT(*) AS cnt FROM goals WHERE status='submitted' OR manager_status='pending' OR hr_status='pending'"
            ).fetchone()["cnt"]
