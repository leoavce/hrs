from app.core_db import get_conn, init_db
from app.utils_security import pbkdf2_hash
from datetime import datetime, timedelta

def seed():
    init_db()
    with get_conn() as c:
        if not c.execute("SELECT 1 FROM departments LIMIT 1").fetchone():
            c.executemany("INSERT INTO departments(name) VALUES(?)", [('인사팀',),('개발팀',),('영업팀',)])
        if not c.execute("SELECT 1 FROM employees LIMIT 1").fetchone():
            c.executemany("INSERT INTO employees(employee_no,name,email,department_id,position) VALUES(?,?,?,?,?)", [
                ('A001','홍정우','hong@example.com',1,'매니저'),
                ('A002','김영희','kim@example.com',2,'개발자'),
                ('A003','박철수','park@example.com',2,'개발자'),
            ])
        if not c.execute("SELECT 1 FROM users LIMIT 1").fetchone():
            s1,h1 = pbkdf2_hash('admin1234');   c.execute("INSERT INTO users(username,salt,password_hash,role,employee_id) VALUES(?,?,?,?,?)", ('admin',s1,h1,'admin',None))
            s2,h2 = pbkdf2_hash('hr1234');      c.execute("INSERT INTO users(username,salt,password_hash,role,employee_id) VALUES(?,?,?,?,?)", ('hr1',s2,h2,'hr',1))
            s3,h3 = pbkdf2_hash('manager1234'); c.execute("INSERT INTO users(username,salt,password_hash,role,employee_id) VALUES(?,?,?,?,?)", ('manager1',s3,h3,'manager',3))
            s4,h4 = pbkdf2_hash('user1234');    c.execute("INSERT INTO users(username,salt,password_hash,role,employee_id) VALUES(?,?,?,?,?)", ('user',s4,h4,'user',1))
        # 연차 잔여 테이블 보정
        for emp_id in [1,2,3]:
            c.execute("INSERT OR IGNORE INTO leave_balances(employee_id, annual_total, annual_used) VALUES(?,?,?)", (emp_id, 15.0, 0.0))
        # 샘플 근태
        today = datetime.now().date()
        for i in range(5):
            d = (today - timedelta(days=i)).strftime('%Y-%m-%d')
            if not c.execute("SELECT 1 FROM attendance WHERE employee_id=1 AND date=?", (d,)).fetchone():
                c.execute("INSERT INTO attendance(employee_id,date,in_time,out_time,lunch_minutes,mode) VALUES(?,?,?,?,?,?)",
                          (1,d,'08:46','16:46',60,'office'))
        # 샘플 성과
        if not c.execute("SELECT 1 FROM competencies LIMIT 1").fetchone():
            c.executemany("INSERT INTO competencies(name,description) VALUES(?,?)", [
                ('협업','팀워크와 커뮤니케이션'),
                ('문제해결','문제 인식과 해결 능력'),
                ('기술스킬','직무 관련 기술'),
            ])
        if not c.execute("SELECT 1 FROM goals LIMIT 1").fetchone():
            c.executemany("""INSERT INTO goals(employee_id,quarter,title,description,weight,progress,manager_status,hr_status,status,updated_at)
                             VALUES(?,?,?,?,?,?,?,?,?, datetime('now'))""", [
                (1,'2025Q3','팀 운영 효율 개선','회의시간 20% 감축',0.4,55,'approved','pending','submitted'),
                (2,'2025Q3','신규 기능 A 출시','모듈 설계/구현',0.6,30,'pending','pending','draft'),
                (3,'2025Q3','성능 최적화','쿼리 30% 감소',0.5,70,'approved','approved','approved'),
            ])
        if not c.execute("SELECT 1 FROM reviews LIMIT 1").fetchone():
            c.executemany("""INSERT INTO reviews(employee_id,reviewer_id,period,category,score,comment,submitted_at)
                             VALUES(?,?,?,?,?,?, datetime('now'))""", [
                (2,1,'2025Q3','manager',4.5,'성과 안정적으로 달성'),
                (2,3,'2025Q3','peer',4.2,'협업 원활'),
                (3,1,'2025Q3','manager',4.8,'탁월한 문제 해결'),
            ])
