import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime, date
from app.seed import seed
from app.repo import Repo
from app.utils_security import pbkdf2_verify, pbkdf2_hash
from app.utils_time import today_str, week_range_of, to_minutes, minutes_to_hhmm, DAILY_REGULAR_MINUTES, calc_work_buckets, WEEKLY_MAX_MINUTES
from app.ui_common import export_tree_to_csv
from app.core_db import backup_to, restore_from

# ---- 기본 스타일 살짝 손봄(이미지와 톤 맞춰 약간 차분하게) ----
def apply_style(root: tk.Tk):
    style = ttk.Style(root)
    try:
        style.theme_use('clam')
    except:
        pass
    style.configure('Treeview.Heading', font=('맑은 고딕', 10, 'bold'))
    style.configure('TButton', font=('맑은 고딕', 10))
    style.configure('TLabel', font=('맑은 고딕', 10))
    style.configure('TEntry', font=('맑은 고딕', 10))
    root.option_add('*Font', '맑은 고딕 10')

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("HRIS (Zero-Dependency — Performance Edition)")
        self.geometry("1280x820")
        apply_style(self)
        self.repo = Repo()
        seed()
        self.user = None
        self._build_login()

    # ===== Login =====
    def _build_login(self):
        win = tk.Toplevel(self); win.title("로그인"); win.grab_set(); win.resizable(False,False)
        tk.Label(win, text="아이디").grid(row=0, column=0, padx=8, pady=6, sticky="e")
        tk.Label(win, text="비밀번호").grid(row=1, column=0, padx=8, pady=6, sticky="e")
        u = tk.Entry(win); p = tk.Entry(win, show="*")
        u.grid(row=0, column=1, padx=8, pady=6); p.grid(row=1, column=1, padx=8, pady=6)
        err = tk.Label(win, text="", fg="#b91c1c"); err.grid(row=2, column=0, columnspan=2)
        def do_login():
            row = self.repo.user_by_username(u.get().strip())
            if not row:
                err.config(text="존재하지 않는 계정입니다."); return
            if not pbkdf2_verify(p.get(), row["salt"], row["password_hash"]):
                err.config(text="비밀번호가 올바르지 않습니다."); return
            self.user = row; win.destroy(); self._build_main()
        ttk.Button(win, text="로그인", command=do_login).grid(row=3, column=0, columnspan=2, pady=8)

    # ===== Main Tabs =====
    def _build_main(self):
        nb = ttk.Notebook(self); nb.pack(fill="both", expand=True)

        # 사용자 공통
        self.tab_daily = ttk.Frame(nb); self.tab_apply = ttk.Frame(nb); self.tab_my = ttk.Frame(nb)
        nb.add(self.tab_daily, text="일일근무현황")
        nb.add(self.tab_apply, text="신청하기")
        nb.add(self.tab_my, text="내 근무내역 조회")

        role = self.user["role"]
        if role in ("admin","hr","manager"):
            self.tab_approval = ttk.Frame(nb); self.tab_overview = ttk.Frame(nb)
            nb.add(self.tab_approval, text="결재관리")
            nb.add(self.tab_overview, text="사용자근무현황보기")
        if role in ("admin","hr"):
            self.tab_holidays = ttk.Frame(nb); self.tab_users = ttk.Frame(nb); self.tab_audit = ttk.Frame(nb); self.tab_settings = ttk.Frame(nb); self.tab_backup = ttk.Frame(nb)
            nb.add(self.tab_holidays, text="휴일 관리")
            nb.add(self.tab_users, text="사용자/권한")
            nb.add(self.tab_audit, text="감사 로그")
            nb.add(self.tab_settings, text="설정")
            nb.add(self.tab_backup, text="백업/복원")

        # Performance
        self.tab_goals = ttk.Frame(nb); nb.add(self.tab_goals, text="목표(OKR/KPI)")
        self.tab_reviews = ttk.Frame(nb); nb.add(self.tab_reviews, text="성과 평가")
        self.tab_comp = ttk.Frame(nb); nb.add(self.tab_comp, text="역량")
        self.tab_feedback = ttk.Frame(nb); nb.add(self.tab_feedback, text="피드백")
        self.tab_dash = ttk.Frame(nb); nb.add(self.tab_dash, text="대시보드")

        # Build UIs
        self._build_daily(self.tab_daily)
        self._build_apply(self.tab_apply)
        self._build_my(self.tab_my)
        if hasattr(self, "tab_approval"): self._build_approval(self.tab_approval)
        if hasattr(self, "tab_overview"): self._build_overview(self.tab_overview)
        if hasattr(self, "tab_holidays"): self._build_holidays(self.tab_holidays)
        if hasattr(self, "tab_users"): self._build_users(self.tab_users)
        if hasattr(self, "tab_audit"): self._build_audit(self.tab_audit)
        if hasattr(self, "tab_settings"): self._build_settings(self.tab_settings)
        if hasattr(self, "tab_backup"): self._build_backup(self.tab_backup)
        # Performance
        self._build_goals(self.tab_goals)
        self._build_reviews(self.tab_reviews)
        self._build_comp(self.tab_comp)
        self._build_feedback(self.tab_feedback)
        self._build_dash(self.tab_dash)

    # ===== Daily =====
    def _build_daily(self, parent):
        top = ttk.Frame(parent); top.pack(fill="x")
        self.lbl_status = ttk.Label(top, text="근무상태 -"); self.lbl_status.pack(side="left", padx=6, pady=6)
        self.lbl_plan = ttk.Label(top, text="업무종료 예정 -"); self.lbl_plan.pack(side="left", padx=6, pady=6)

        cols = ("구분","시간","분","비고")
        self.daily_tree = ttk.Treeview(parent, columns=cols, show="headings", height=6)
        for c in cols: self.daily_tree.heading(c, text=c)
        self.daily_tree.pack(fill="x", padx=8, pady=6)

        self.lbl_week = ttk.Label(parent, text=f"0분 / {WEEKLY_MAX_MINUTES//60}시간")
        self.lbl_week.pack(anchor="w", padx=8)
        self._refresh_daily()

    def _refresh_daily(self):
        today = today_str(); emp_id = self.user["employee_id"] or 1
        a = self.repo.attendance_for(emp_id, today)
        if a and a["in_time"]:
            in_m = to_minutes(a["in_time"])
            status = "근무중" if not a["out_time"] else "근무종료"
            plan_out = in_m + DAILY_REGULAR_MINUTES + (a["lunch_minutes"] or 60)
            self.lbl_status.config(text=status)
            self.lbl_plan.config(text=f"업무종료 예정 {plan_out//60:02d}:{plan_out%60:02d} (8시간)")
        else:
            self.lbl_status.config(text="기록 없음")
            self.lbl_plan.config(text="업무종료 예정 -")

        for i in self.daily_tree.get_children(): self.daily_tree.delete(i)
        from datetime import datetime as dt
        d = dt.strptime(today, '%Y-%m-%d').date()
        b = calc_work_buckets(a["in_time"] if a else None, a["out_time"] if a else None,
                              (a["lunch_minutes"] if a else 60), d, False)
        rows = [
            ("일반근무", b["regular"], b["regular"], ""),
            ("연장", b["overtime"], b["overtime"], ""),
            ("야간", b["night"], b["night"], ""),
            ("휴일", b["holiday"], b["holiday"], "")
        ]
        for r in rows:
            self.daily_tree.insert("", "end", values=(r[0], f"{r[1]//60}시간 {r[1]%60}분", r[2], r[3]))

        # 주간 합계 + 캡 경고
        start, end = week_range_of(date.today())
        recs = self.repo.attendance_range(emp_id, start.strftime('%Y-%m-%d'), end.strftime('%Y-%m-%d'))
        total=0
        for r in recs:
            if r["in_time"] and r["out_time"]:
                bd = dt.strptime(r["date"], '%Y-%m-%d').date()
                bb = calc_work_buckets(r["in_time"], r["out_time"], (r["lunch_minutes"] or 0), bd, False)
                total += bb["total"]
        self.lbl_week.config(text=f"{minutes_to_hhmm(total)} / {WEEKLY_MAX_MINUTES//60}시간")
        cap = self.repo.get_settings()["weekly_cap_minutes"] or 3120
        if total > cap:
            messagebox.showwarning("주의", f"이번주 누적 {minutes_to_hhmm(total)} — 주간 캡({cap//60}시간) 초과")

    # ===== Apply =====
    def _build_apply(self, parent):
        frm = ttk.Frame(parent); frm.pack(fill="x", padx=8, pady=8)
        ttk.Button(frm, text="초과 근무 신청", command=self._apply_ot).pack(side="left", padx=4)
        ttk.Button(frm, text="휴가 신청", command=self._apply_leave).pack(side="left", padx=4)
        ttk.Button(frm, text="근무 수정 신청", command=self._apply_corr).pack(side="left", padx=4)

    def _apply_ot(self):
        self._simple_form("초과근무", ["일자(YYYY-MM-DD)","시작(HH:MM)","종료(HH:MM)","사유"], self._save_ot)

    def _save_ot(self, vals):
        sdate, s, e, reason = vals
        mins = to_minutes(e) - to_minutes(s)
        self.repo.save_overtime(dict(employee_id=self.user["employee_id"] or 1, date=sdate, start_time=s, end_time=e, minutes=mins, reason=reason))
        messagebox.showinfo("저장", "초과근무 신청 완료")

    def _apply_leave(self):
        self._simple_form("휴가", ["시작일(YYYY-MM-DD)","종료일(YYYY-MM-DD)","구분(연차/반차(오전)/반차(오후)/병가)","사유"], self._save_leave)

    def _save_leave(self, vals):
        s,e,t,reason = vals
        if t=="연차":
            bal = self.repo.get_leave_balance(self.user["employee_id"] or 1)
            from datetime import datetime as dt
            days = (dt.strptime(e,"%Y-%m-%d").date() - dt.strptime(s,"%Y-%m-%d").date()).days + 1
            if (bal["annual_used"] or 0) + days > (bal["annual_total"] or 0):
                messagebox.showwarning("경고", "연차 잔여가 부족합니다."); return
        self.repo.save_leave(dict(employee_id=self.user["employee_id"] or 1, start_date=s, end_date=e, type=t, reason=reason))
        messagebox.showinfo("저장", "휴가 신청 완료")

    def _apply_corr(self):
        self._simple_form("근무수정", ["일자(YYYY-MM-DD)","출근(HH:MM)","퇴근(HH:MM)","점심(분)","사유"], self._save_corr)

    def _save_corr(self, vals):
        d, it, ot, lm, reason = vals
        try: lm = int(lm)
        except: lm = 60
        self.repo.save_correction(dict(employee_id=self.user["employee_id"] or 1, date=d, new_in_time=it, new_out_time=ot, new_lunch_minutes=lm, reason=reason))
        messagebox.showinfo("저장", "근무 수정 신청 완료")

    def _simple_form(self, title, labels, on_save):
        win = tk.Toplevel(self); win.title(title); entries=[]
        for i,l in enumerate(labels):
            tk.Label(win, text=l).grid(row=i, column=0, padx=6, pady=4, sticky="e")
            e = tk.Entry(win); e.grid(row=i, column=1, padx=6, pady=4); entries.append(e)
        def save():
            vals = [e.get().strip() for e in entries]
            if any(v=="" for v in vals):
                messagebox.showwarning("경고","모든 값을 입력하세요."); return
            on_save(vals); win.destroy()
        ttk.Button(win, text="저장", command=save).grid(row=len(labels), column=0, columnspan=2, pady=6)

    # ===== My History =====
    def _build_my(self, parent):
        frm = ttk.Frame(parent); frm.pack(fill="x", padx=8, pady=8)
        ttk.Label(frm, text="시작일 YYYY-MM-DD").pack(side="left"); s = tk.Entry(frm); s.pack(side="left", padx=4)
        ttk.Label(frm, text="종료일").pack(side="left"); e = tk.Entry(frm); e.pack(side="left", padx=4)
        ttk.Button(frm, text="검색", command=lambda:self._reload_my(s.get(), e.get())).pack(side="left", padx=4)
        ttk.Button(frm, text="CSV 내보내기", command=lambda: export_tree_to_csv(self.my_tree, "my_history")).pack(side="left", padx=4)
        cols=("DATE","STATE","TIME","메모","분"); self.my_tree=ttk.Treeview(parent, columns=cols, show="headings", height=12)
        for c in cols: self.my_tree.heading(c, text=c)
        self.my_tree.pack(fill="both", expand=True, padx=8, pady=8)

    def _reload_my(self, s, e):
        emp = self.user["employee_id"] or 1
        recs = self.repo.attendance_range(emp, s, e)
        for i in self.my_tree.get_children(): self.my_tree.delete(i)
        total=0; days=0
        for r in recs:
            worked=0
            if r["in_time"] and r["out_time"]:
                worked = to_minutes(r["out_time"]) - to_minutes(r["in_time"]) - (r["lunch_minutes"] or 0)
                total += worked; days += 1
            state = "실근무" if worked>0 else "기록없음"
            self.my_tree.insert("", "end", values=(r["date"], state, minutes_to_hhmm(worked), r["note"] or "", worked))
        avg = int(total/days) if days else 0
        messagebox.showinfo("요약", f"총 {minutes_to_hhmm(total)} / 평균 {minutes_to_hhmm(avg)}")

    # ===== Approval (two-stage) =====
    def _build_approval(self, parent):
        frm = ttk.Frame(parent); frm.pack(fill="x", padx=8, pady=8)
        ttk.Button(frm, text="선택 승인(매니저)", command=lambda:self._approve_stage('manager', True)).pack(side="left", padx=4)
        ttk.Button(frm, text="선택 반려(매니저)", command=lambda:self._approve_stage('manager', False)).pack(side="left", padx=4)
        ttk.Button(frm, text="선택 승인(HR)", command=lambda:self._approve_stage('hr', True)).pack(side="left", padx=4)
        ttk.Button(frm, text="선택 반려(HR)", command=lambda:self._approve_stage('hr', False)).pack(side="left", padx=4)

        self.ot_tree = ttk.Treeview(parent, columns=("ID","사번","일자","시간","M","HR","최종","사유"), show="headings", height=6)
        for c in ("ID","사번","일자","시간","M","HR","최종","사유"): self.ot_tree.heading(c, text=c)
        self.ot_tree.pack(fill="x", padx=8, pady=4)

        self.leave_tree = ttk.Treeview(parent, columns=("ID","사번","기간","구분","M","HR","최종","사유"), show="headings", height=6)
        for c in ("ID","사번","기간","구분","M","HR","최종","사유"): self.leave_tree.heading(c, text=c)
        self.leave_tree.pack(fill="x", padx=8, pady=4)

        self.corr_tree = ttk.Treeview(parent, columns=("ID","사번","일자","출근","퇴근","점심","M","HR","최종"), show="headings", height=6)
        for c in ("ID","사번","일자","출근","퇴근","점심","M","HR","최종"): self.corr_tree.heading(c, text=c)
        self.corr_tree.pack(fill="x", padx=8, pady=4)

        self._reload_approval()

    def _reload_approval(self):
        role = self.user["role"]; dept_id = None
        if role=="manager":
            emp_id = self.user["employee_id"]
            if emp_id:
                e = [x for x in self.repo.employees() if x["id"]==emp_id]
                if e: dept_id = e[0]["department_id"]

        for t in (self.ot_tree, self.leave_tree, self.corr_tree):
            for i in t.get_children(): t.delete(i)

        for o in self.repo.overtimes_for_role(role, dept_id):
            self.ot_tree.insert("", "end", values=(o["id"], o["employee_id"], o["date"], f"{o['start_time']}-{o['end_time']}({o['minutes']}분)", o["manager_status"], o["hr_status"], o["status"], o["reason"] or ""))

        for l in self.repo.leaves_for_role(role, dept_id):
            self.leave_tree.insert("", "end", values=(l["id"], l["employee_id"], f"{l['start_date']}~{l['end_date']}", l["type"], l["manager_status"], l["hr_status"], l["status"], l["reason"] or ""))

        for c in self.repo.corrections_for_role(role, dept_id):
            self.corr_tree.insert("", "end", values=(c["id"], c["employee_id"], c["date"], c["new_in_time"] or "", c["new_out_time"] or "", c["new_lunch_minutes"] or "", c["manager_status"], c["hr_status"], c["status"]))

    def _approve_stage(self, stage: str, approve: bool):
        t = None; sel=None
        for tree in (self.ot_tree, self.leave_tree, self.corr_tree):
            s = tree.selection()
            if s: t=tree; sel=s[0]; break
        if not t:
            messagebox.showwarning("경고","항목을 선택하세요."); return
        row = t.item(sel)["values"]; rid = int(row[0])
        if t is self.ot_tree: self.repo.set_overtime_stage(rid, stage, approve)
        elif t is self.leave_tree: self.repo.set_leave_stage(rid, stage, approve)
        else: self.repo.set_correction_stage(rid, stage, approve)
        self.repo.audit(self.user["id"], f"{stage}_{'approve' if approve else 'reject'}", "request", rid, None)
        self._reload_approval(); messagebox.showinfo("완료","처리되었습니다.")

    # ===== Overview =====
    def _build_overview(self, parent):
        frm = ttk.Frame(parent); frm.pack(fill="x", padx=8, pady=8)
        ttk.Label(frm, text="부서ID(0=전체)").pack(side="left"); dept = tk.Entry(frm, width=6); dept.insert(0,"0"); dept.pack(side="left", padx=4)
        ttk.Label(frm, text="이름/메일/사번").pack(side="left"); nameq = tk.Entry(frm); nameq.pack(side="left", padx=4)
        ttk.Label(frm, text="기준일 YYYY-MM-DD").pack(side="left"); base = tk.Entry(frm); base.insert(0, today_str()); base.pack(side="left", padx=4)
        ttk.Button(frm, text="검색", command=lambda:self._reload_overview(base.get(), int(dept.get() or "0"), nameq.get().strip() or None)).pack(side="left", padx=4)
        ttk.Button(frm, text="CSV 내보내기", command=lambda: export_tree_to_csv(self.ov_tree, "overview")).pack(side="left", padx=4)

        cols=("이름","사번","부서ID","직위","출근","퇴근","점심","휴가구분","비고","분")
        self.ov_tree=ttk.Treeview(parent, columns=cols, show="headings", height=14)
        for c in cols: self.ov_tree.heading(c, text=c)
        self.ov_tree.pack(fill="both", expand=True, padx=8, pady=8)

    def _reload_overview(self, base, dept_id, nameq):
        rows = self.repo.overview(base, dept_id if dept_id>0 else None, nameq)
        for i in self.ov_tree.get_children(): self.ov_tree.delete(i)
        for r in rows:
            worked = 0
            if r["in_time"] and r["out_time"]:
                worked = to_minutes(r["out_time"]) - to_minutes(r["in_time"]) - (r["lunch_minutes"] or 0)
            self.ov_tree.insert("", "end", values=(
                r["name"], r["employee_no"], r["department_id"], r["position"] or "",
                r["in_time"] or "", r["out_time"] or "", r["lunch_minutes"] or "",
                "휴가" if (r["mode"]=="vacation") else "", r["note"] or "", worked
            ))

    # ===== Holidays =====
    def _build_holidays(self, parent):
        frm = ttk.Frame(parent); frm.pack(fill="x", padx=8, pady=8)
        d = tk.Entry(frm); n = tk.Entry(frm); d.insert(0, today_str())
        ttk.Label(frm, text="일자 YYYY-MM-DD").pack(side="left"); d.pack(side="left", padx=4)
        ttk.Label(frm, text="이름").pack(side="left"); n.pack(side="left", padx=4)
        ttk.Button(frm, text="추가", command=lambda:(self.repo.add_holiday(d.get(), n.get()), self._reload_holidays())).pack(side="left", padx=4)
        ttk.Button(frm, text="삭제(선택)", command=self._del_holiday).pack(side="left", padx=4)

        cols=("date","name"); self.h_tree=ttk.Treeview(parent, columns=cols, show="headings", height=14)
        for c in cols: self.h_tree.heading(c, text=c)
        self.h_tree.pack(fill="both", expand=True, padx=8, pady=8); self._reload_holidays()

    def _reload_holidays(self):
        for i in self.h_tree.get_children(): self.h_tree.delete(i)
        for h in self.repo.holidays():
            self.h_tree.insert("", "end", values=(h["date"], h["name"]))

    def _del_holiday(self):
        sel = self.h_tree.selection()
        if not sel: return
        d = self.h_tree.item(sel[0])["values"][0]
        self.repo.delete_holiday(d); self._reload_holidays()

    # ===== Users & Roles =====
    def _build_users(self, parent):
        frm = ttk.Frame(parent); frm.pack(fill="x", padx=8, pady=8)
        ttk.Button(frm, text="새 사용자", command=self._new_user).pack(side="left", padx=4)
        ttk.Button(frm, text="비밀번호 재설정", command=self._reset_pw).pack(side="left", padx=4)
        ttk.Button(frm, text="역할/직원 매핑", command=self._set_role).pack(side="left", padx=4)
        ttk.Button(frm, text="삭제", command=self._del_user).pack(side="left", padx=4)

        cols=("ID","username","role","employee_id")
        self.u_tree=ttk.Treeview(parent, columns=cols, show="headings", height=14)
        for c in cols: self.u_tree.heading(c, text=c)
        self.u_tree.pack(fill="both", expand=True, padx=8, pady=8)
        self._reload_users()

    def _reload_users(self):
        for i in self.u_tree.get_children(): self.u_tree.delete(i)
        for u in self.repo.users():
            self.u_tree.insert("", "end", values=(u["id"], u["username"], u["role"], u["employee_id"]))

    def _new_user(self):
        win = tk.Toplevel(self); win.title("새 사용자"); es = []
        for i,l in enumerate(["username","password","role(admin/hr/manager/user)","employee_id(선택)"]):
            tk.Label(win, text=l).grid(row=i, column=0, padx=6, pady=4, sticky="e")
            e=tk.Entry(win); e.grid(row=i,column=1,padx=6,pady=4); es.append(e)
        def save():
            username, pw, role, emp = [x.get().strip() for x in es]
            if not username or not pw or role not in ("admin","hr","manager","user"):
                messagebox.showwarning("경고","입력값 확인"); return
            salt, h = pbkdf2_hash(pw)
            emp_id = int(emp) if emp else None
            self.repo.create_user(username, salt, h, role, emp_id)
            self._reload_users(); win.destroy()
        ttk.Button(win, text="저장", command=save).grid(row=4, column=0, columnspan=2, pady=6)

    def _reset_pw(self):
        sel = self.u_tree.selection()
        if not sel: return
        uid = int(self.u_tree.item(sel[0])["values"][0])
        win = tk.Toplevel(self); win.title("비밀번호 재설정")
        tk.Label(win, text="새 비밀번호").grid(row=0,column=0,padx=6,pady=6,sticky="e")
        e=tk.Entry(win, show="*"); e.grid(row=0,column=1,padx=6,pady=6)
        def save():
            salt, h = pbkdf2_hash(e.get().strip())
            self.repo.update_user_password(uid, salt, h)
            win.destroy(); messagebox.showinfo("완료","변경되었습니다.")
        ttk.Button(win, text="저장", command=save).grid(row=1,column=0,columnspan=2,pady=6)

    def _set_role(self):
        sel = self.u_tree.selection()
        if not sel: return
        uid = int(self.u_tree.item(sel[0])["values"][0])
        win = tk.Toplevel(self); win.title("역할/직원 매핑")
        tk.Label(win, text="role(admin/hr/manager/user)").grid(row=0,column=0,padx=6,pady=6,sticky="e")
        r=tk.Entry(win); r.grid(row=0,column=1,padx=6,pady=6)
        tk.Label(win, text="employee_id(optional)").grid(row=1,column=0,padx=6,pady=6,sticky="e")
        e=tk.Entry(win); e.grid(row=1,column=1,padx=6,pady=6)
        def save():
            role=r.get().strip(); emp_id=int(e.get().strip()) if e.get().strip() else None
            if role not in ("admin","hr","manager","user"):
                messagebox.showwarning("경고","역할값 확인"); return
            self.repo.update_user_role(uid, role, emp_id)
            win.destroy(); self._reload_users()
        ttk.Button(win, text="저장", command=save).grid(row=2,column=0,columnspan=2,pady=6)

    def _del_user(self):
        sel = self.u_tree.selection()
        if not sel: return
        uid = int(self.u_tree.item(sel[0])["values"][0])
        if messagebox.askyesno("확인","삭제하시겠습니까?"):
            self.repo.delete_user(uid); self._reload_users()

    # ===== Audit =====
    def _build_audit(self, parent):
        frm = ttk.Frame(parent); frm.pack(fill="x", padx=8, pady=8)
        ttk.Button(frm, text="CSV 내보내기", command=lambda: export_tree_to_csv(self.audit_tree, "audit")).pack(side="left")
        cols=("ID","행위자","액션","타깃","상세")
        self.audit_tree=ttk.Treeview(parent, columns=cols, show="headings", height=16)
        for c in cols: self.audit_tree.heading(c, text=c)
        self.audit_tree.pack(fill="both", expand=True, padx=8, pady=8)
        self._reload_audit()

    def _reload_audit(self):
        for i in self.audit_tree.get_children(): self.audit_tree.delete(i)
        for log in self.repo.audit_recent():
            self.audit_tree.insert("", "end", values=(log["id"], log["actor_user_id"], log["action"], f"{log['target_type']}:{log['target_id']}", log["detail"] or ""))

    # ===== Settings =====
    def _build_settings(self, parent):
        s = self.repo.get_settings()
        frm = ttk.Frame(parent); frm.pack(fill="x", padx=8, pady=8)
        ttk.Label(frm, text="주간 캡(분)").pack(side="left")
        cap = tk.Entry(frm, width=8); cap.insert(0, str(s["weekly_cap_minutes"] or 3120)); cap.pack(side="left", padx=6)
        ttk.Label(frm, text="점심 기본(분)").pack(side="left")
        lunch = tk.Entry(frm, width=8); lunch.insert(0, str(s["default_lunch"] or 60)); lunch.pack(side="left", padx=6)
        ttk.Button(frm, text="저장", command=lambda:(self.repo.update_settings(weekly_cap_minutes=int(cap.get() or "3120"), default_lunch=int(lunch.get() or "60")), messagebox.showinfo("완료","저장되었습니다."))).pack(side="left", padx=6)

    # ===== Backup / Restore =====
    def _build_backup(self, parent):
        frm = ttk.Frame(parent); frm.pack(fill="x", padx=8, pady=8)
        ttk.Button(frm, text="DB 백업", command=self._do_backup).pack(side="left", padx=6)
        ttk.Button(frm, text="DB 복원", command=self._do_restore).pack(side="left", padx=6)
        ttk.Button(frm, text="직원 CSV 임포트", command=self._import_employees_csv).pack(side="left", padx=6)
        ttk.Label(parent, text="임포트 CSV: employee_no,name,email,department_id,position", foreground="#6b7280").pack(anchor="w", padx=8)

    def _do_backup(self):
        path = filedialog.asksaveasfilename(defaultextension=".db", filetypes=[("SQLite DB","*.db")])
        if not path: return
        backup_to(path); messagebox.showinfo("완료", f"백업됨: {path}")

    def _do_restore(self):
        path = filedialog.askopenfilename(filetypes=[("SQLite DB","*.db"),("All files","*.*")])
        if not path: return
        restore_from(path); messagebox.showinfo("완료", "복원되었습니다. 앱을 재시작하세요.")

    def _import_employees_csv(self):
        path = filedialog.askopenfilename(filetypes=[("CSV","*.csv")])
        if not path: return
        import csv
        with open(path, "r", encoding="utf-8-sig") as f:
            r = csv.reader(f)
            for row in r:
                if not row or row[0].startswith("#"): continue
                try:
                    eno,name,email,dept,position = row
                    self.repo.add_employee(eno.strip(), name.strip(), email.strip(), int(dept.strip()), position.strip() or None)
                except Exception:
                    pass
        messagebox.showinfo("완료", "직원 임포트 완료")

    # ===== Performance: Goals =====
    def _build_goals(self, parent):
        frm = ttk.Frame(parent); frm.pack(fill="x", padx=8, pady=8)
        ttk.Label(frm, text="분기(예: 2025Q3)").pack(side="left")
        q = tk.Entry(frm, width=10); q.insert(0,"2025Q3"); q.pack(side="left", padx=6)
        ttk.Button(frm, text="새 목표", command=lambda:self._new_goal(q.get())).pack(side="left", padx=4)
        ttk.Button(frm, text="진행률 변경", command=self._update_goal_progress).pack(side="left", padx=4)
        ttk.Button(frm, text="제출", command=self._submit_goal).pack(side="left", padx=4)
        ttk.Button(frm, text="승인(매니저)", command=lambda:self._approve_goal('manager', True)).pack(side="left", padx=4)
        ttk.Button(frm, text="반려(매니저)", command=lambda:self._approve_goal('manager', False)).pack(side="left", padx=4)
        ttk.Button(frm, text="승인(HR)", command=lambda:self._approve_goal('hr', True)).pack(side="left", padx=4)
        ttk.Button(frm, text="반려(HR)", command=lambda:self._approve_goal('hr', False)).pack(side="left", padx=4)

        cols=("ID","분기","직원ID","제목","가중치","진행률","상태","M","HR")
        self.goal_tree=ttk.Treeview(parent, columns=cols, show="headings", height=16)
        for c in cols: self.goal_tree.heading(c, text=c)
        self.goal_tree.pack(fill="both", expand=True, padx=8, pady=8)
        self.goal_quarter = q
        self._reload_goals(q.get())

    def _reload_goals(self, quarter):
        role = self.user["role"]; emp_id = self.user["employee_id"]; dept_id=None
        if role=="manager" and emp_id:
            e = [x for x in self.repo.employees() if x["id"]==emp_id]
            if e: dept_id = e[0]["department_id"]
        for i in self.goal_tree.get_children(): self.goal_tree.delete(i)
        for g in self.repo.goals_for_role(role, emp_id, dept_id, quarter):
            self.goal_tree.insert("", "end", values=(g["id"], g["quarter"], g["employee_id"], g["title"], g["weight"], g["progress"], g["status"], g["manager_status"], g["hr_status"]))

    def _sel_id(self, tree):
        sel = tree.selection()
        if not sel: return None
        return int(tree.item(sel[0])["values"][0])

    def _new_goal(self, quarter):
        win = tk.Toplevel(self); win.title("새 목표")
        entries=[]
        for i,l in enumerate(["제목","설명","가중치(0~1)","대상 직원ID(미입력시 본인)"]):
            tk.Label(win, text=l).grid(row=i,column=0,padx=6,pady=4,sticky="e")
            e=tk.Entry(win); e.grid(row=i,column=1,padx=6,pady=4); entries.append(e)
        def save():
            title, desc, weight, emp = [x.get().strip() for x in entries]
            if not title: messagebox.showwarning("경고","제목 필요"); return
            try: w=float(weight or "1.0")
            except: w=1.0
            emp_id = int(emp) if emp else (self.user["employee_id"] or 1)
            self.repo.create_goal(emp_id, quarter, title, desc, w)
            self._reload_goals(quarter); win.destroy()
        ttk.Button(win, text="저장", command=save).grid(row=4, column=0, columnspan=2, pady=6)

    def _update_goal_progress(self):
        gid = self._sel_id(self.goal_tree)
        if not gid: messagebox.showwarning("경고","선택하세요"); return
        win = tk.Toplevel(self); win.title("진행률 변경")
        tk.Label(win, text="진행률(0~100)").grid(row=0,column=0,padx=6,pady=6,sticky="e")
        e=tk.Entry(win); e.grid(row=0,column=1,padx=6,pady=6)
        def save():
            try: v=float(e.get().strip())
            except: v=0.0
            self.repo.update_goal_progress(gid, v)
            self._reload_goals(self.goal_quarter.get()); win.destroy()
        ttk.Button(win, text="저장", command=save).grid(row=1,column=0,columnspan=2,pady=6)

    def _submit_goal(self):
        gid = self._sel_id(self.goal_tree)
        if not gid: messagebox.showwarning("경고","선택하세요"); return
        self.repo.submit_goal(gid)
        self._reload_goals(self.goal_quarter.get())

    def _approve_goal(self, stage, ok):
        gid = self._sel_id(self.goal_tree)
        if not gid: messagebox.showwarning("경고","선택하세요"); return
        self.repo.approve_goal_stage(gid, stage, ok)
        self._reload_goals(self.goal_quarter.get())

    # ===== Performance: Reviews =====
    def _build_reviews(self, parent):
        frm = ttk.Frame(parent); frm.pack(fill="x", padx=8, pady=8)
        ttk.Label(frm, text="기간(예: 2025Q3)").pack(side="left")
        p = tk.Entry(frm, width=10); p.insert(0,"2025Q3"); p.pack(side="left", padx=6)
        ttk.Button(frm, text="평가 입력", command=lambda:self._new_review(p.get())).pack(side="left", padx=4)
        ttk.Button(frm, text="새로고침", command=lambda:self._reload_reviews(p.get())).pack(side="left", padx=4)

        cols=("ID","대상직원","리뷰어","기간","유형","점수","코멘트")
        self.rv_tree=ttk.Treeview(parent, columns=cols, show="headings", height=16)
        for c in cols: self.rv_tree.heading(c, text=c)
        self.rv_tree.pack(fill="both", expand=True, padx=8, pady=8)
        self.rv_period=p
        self._reload_reviews(p.get())

    def _new_review(self, period):
        win = tk.Toplevel(self); win.title("평가 입력")
        es=[]
        labels=["대상 직원ID(미입력시 본인)","유형(self/peer/manager)","점수(1~5)","코멘트"]
        for i,l in enumerate(labels):
            tk.Label(win, text=l).grid(row=i,column=0,padx=6,pady=4,sticky="e")
            e=tk.Entry(win); e.grid(row=i,column=1,padx=6,pady=4); es.append(e)
        def save():
            emp = int(es[0].get().strip()) if es[0].get().strip() else (self.user["employee_id"] or 1)
            cat = es[1].get().strip() or "self"
            try: score=float(es[2].get().strip())
            except: score=3.0
            comment=es[3].get().strip()
            self.repo.add_review(emp, self.user["id"], period, cat, score, comment)
            self._reload_reviews(period); win.destroy()
        ttk.Button(win, text="저장", command=save).grid(row=len(labels),column=0,columnspan=2,pady=6)

    def _reload_reviews(self, period):
        role=self.user["role"]; emp=self.user["employee_id"]; dept_id=None
        if role=="manager" and emp:
            e = [x for x in self.repo.employees() if x["id"]==emp]
            if e: dept_id = e[0]["department_id"]
        for i in self.rv_tree.get_children(): self.rv_tree.delete(i)
        for r in self.repo.reviews_for_role(role, emp, dept_id, period):
            self.rv_tree.insert("", "end", values=(r["id"], r["employee_id"], r["reviewer_id"], r["period"], r["category"], r["score"], r["comment"] or ""))

    # ===== Performance: Competencies =====
    def _build_comp(self, parent):
        frm = ttk.Frame(parent); frm.pack(fill="x", padx=8, pady=8)
        ttk.Button(frm, text="역량 추가", command=self._add_comp).pack(side="left", padx=4)
        ttk.Button(frm, text="직원 역량 설정", command=self._set_emp_comp).pack(side="left", padx=4)
        ttk.Label(frm, text="(참고: 직원 역량 설정은 admin/hr 권장)").pack(side="left", padx=8)

        cols=("ID","이름","설명")
        self.comp_tree=ttk.Treeview(parent, columns=cols, show="headings", height=8)
        for c in cols: self.comp_tree.heading(c, text=c)
        self.comp_tree.pack(fill="x", padx=8, pady=4)
        self._reload_comp()

        ttk.Label(parent, text="내 역량 수준").pack(anchor="w", padx=8)
        cols2=("comp_id","역량","레벨","메모")
        self.ec_tree=ttk.Treeview(parent, columns=cols2, show="headings", height=8)
        for c in cols2: self.ec_tree.heading(c, text=c)
        self.ec_tree.pack(fill="x", padx=8, pady=4)
        self._reload_emp_comp()

    def _reload_comp(self):
        for i in self.comp_tree.get_children(): self.comp_tree.delete(i)
        for c in self.repo.competencies():
            self.comp_tree.insert("", "end", values=(c["id"], c["name"], c["description"] or ""))

    def _reload_emp_comp(self):
        for i in self.ec_tree.get_children(): self.ec_tree.delete(i)
        emp = self.user["employee_id"] or 1
        for ec in self.repo.employee_competencies(emp):
            self.ec_tree.insert("", "end", values=(ec["competency_id"], ec["name"], ec["level"], ec["note"] or ""))

    def _add_comp(self):
        win = tk.Toplevel(self); win.title("역량 추가")
        n=tk.Entry(win); d=tk.Entry(win)
        tk.Label(win, text="이름").grid(row=0,column=0,padx=6,pady=6,sticky="e"); n.grid(row=0,column=1,padx=6,pady=6)
        tk.Label(win, text="설명").grid(row=1,column=0,padx=6,pady=6,sticky="e"); d.grid(row=1,column=1,padx=6,pady=6)
        def save():
            self.repo.add_competency(n.get().strip(), d.get().strip())
            self._reload_comp(); win.destroy()
        ttk.Button(win, text="저장", command=save).grid(row=2,column=0,columnspan=2,pady=6)

    def _set_emp_comp(self):
        win = tk.Toplevel(self); win.title("직원 역량 설정")
        es=[]
        labels=["직원ID(미입력시 본인)","역량ID","레벨(1~5)","메모"]
        for i,l in enumerate(labels):
            tk.Label(win, text=l).grid(row=i,column=0,padx=6,pady=4,sticky="e")
            e=tk.Entry(win); e.grid(row=i,column=1,padx=6,pady=4); es.append(e)
        def save():
            emp = int(es[0].get().strip()) if es[0].get().strip() else (self.user["employee_id"] or 1)
            comp = int(es[1].get().strip())
            lvl = int(es[2].get().strip() or "3")
            note = es[3].get().strip()
            self.repo.set_employee_competency(emp, comp, lvl, note)
            self._reload_emp_comp(); win.destroy()
        ttk.Button(win, text="저장", command=save).grid(row=len(labels),column=0,columnspan=2,pady=6)

    # ===== Performance: Feedback =====
    def _build_feedback(self, parent):
        frm = ttk.Frame(parent); frm.pack(fill="x", padx=8, pady=8)
        ttk.Button(frm, text="피드백 남기기", command=self._add_feedback).pack(side="left", padx=4)
        ttk.Button(frm, text="새로고침", command=self._reload_feedback).pack(side="left", padx=4)

        ttk.Label(parent, text="받은 피드백").pack(anchor="w", padx=8)
        cols=("ID","FROM","TO","내용","공개범위","일시")
        self.fd_in=ttk.Treeview(parent, columns=cols, show="headings", height=8)
        for c in cols: self.fd_in.heading(c, text=c)
        self.fd_in.pack(fill="x", padx=8, pady=4)

        ttk.Label(parent, text="보낸 피드백").pack(anchor="w", padx=8)
        self.fd_out=ttk.Treeview(parent, columns=cols, show="headings", height=8)
        for c in cols: self.fd_out.heading(c, text=c)
        self.fd_out.pack(fill="x", padx=8, pady=4)

        self._reload_feedback()

    def _add_feedback(self):
        win = tk.Toplevel(self); win.title("피드백")
        es=[]
        labels=["대상 직원ID(사용자ID가 아님 주의)","내용","공개범위(private/manager/public)"]
        for i,l in enumerate(labels):
            tk.Label(win, text=l).grid(row=i,column=0,padx=6,pady=4,sticky="e")
            e=tk.Entry(win); e.grid(row=i,column=1,padx=6,pady=4); es.append(e)
        def save():
            try:
                to_id=int(es[0].get().strip())
            except:
                messagebox.showwarning("경고","직원ID를 정수로 입력"); return
            comment=es[1].get().strip()
            vis=es[2].get().strip() or "manager"
            self.repo.add_feedback(self.user["id"], to_id, comment, vis)
            self._reload_feedback(); win.destroy()
        ttk.Button(win, text="저장", command=save).grid(row=len(labels),column=0,columnspan=2,pady=6)

    def _reload_feedback(self):
        for t in (self.fd_in, self.fd_out):
            for i in t.get_children(): t.delete(i)
        uid = self.user["id"]
        for r in self.repo.feedback_received(uid):
            self.fd_in.insert("", "end", values=(r["id"], r["from_id"], r["to_id"], r["comment"], r["visibility"], r["created_at"]))
        for r in self.repo.feedback_given(uid):
            self.fd_out.insert("", "end", values=(r["id"], r["from_id"], r["to_id"], r["comment"], r["visibility"], r["created_at"]))

    # ===== Performance: Dashboard =====
    def _build_dash(self, parent):
        frm = ttk.Frame(parent); frm.pack(fill="x", padx=8, pady=8)
        ttk.Label(frm, text="분기").pack(side="left")
        q=tk.Entry(frm, width=10); q.insert(0,"2025Q3"); q.pack(side="left", padx=6)
        ttk.Label(frm, text="기간").pack(side="left")
        p=tk.Entry(frm, width=10); p.insert(0,"2025Q3"); p.pack(side="left", padx=6)
        ttk.Button(frm, text="새로고침", command=lambda:self._reload_dash(q.get(), p.get())).pack(side="left", padx=6)

        self.lbl_dash = ttk.Label(parent, text="")
        self.lbl_dash.pack(fill="x", padx=8, pady=6)

        cols=("employee_id","평균 진행%","목표 수")
        self.d_goal=ttk.Treeview(parent, columns=cols, show="headings", height=6)
        for c in cols: self.d_goal.heading(c, text=c)
        self.d_goal.pack(fill="x", padx=8, pady=4)

        cols2=("employee_id","평균 점수","리뷰 수")
        self.d_rev=ttk.Treeview(parent, columns=cols2, show="headings", height=6)
        for c in cols2: self.d_rev.heading(c, text=c)
        self.d_rev.pack(fill="x", padx=8, pady=4)

        self._reload_dash(q.get(), p.get())

    def _reload_dash(self, quarter, period):
        for t in (self.d_goal, self.d_rev):
            for i in t.get_children(): t.delete(i)

        # goal averages
        top=-1; bottom=10**9; top_e=None; bottom_e=None
        pcnt=0
        avgs = self.repo.goal_progress_avg_by_employee(quarter)
        for g in avgs:
            self.d_goal.insert("", "end", values=(g["employee_id"], round(g["avg_prog"],1), g["cnt"]))
            if g["avg_prog"]>top: top=g["avg_prog"]; top_e=g["employee_id"]
            if g["avg_prog"]<bottom: bottom=g["avg_prog"]; bottom_e=g["employee_id"]
            pcnt += g["cnt"]

        # reviews
        avg_sum=0; avg_cnt=0
        for r in self.repo.review_avg_by_employee(period):
            self.d_rev.insert("", "end", values=(r["employee_id"], round(r["avg_score"],2), r["cnt"]))
            avg_sum += r["avg_score"]; avg_cnt += 1

        pend = self.repo.pending_goal_counts()
        overall = f"Goal Top:{top_e}({round(top,1) if top>=0 else 0}%), Bottom:{bottom_e}({round(bottom,1) if bottom<10**9 else 0}%), 리뷰 평균:{round(avg_sum/avg_cnt,2) if avg_cnt else 0}, 대기 목표:{pend}"
        self.lbl_dash.config(text=overall)

if __name__ == "__main__":
    App().mainloop()
