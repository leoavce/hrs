# HRIS — Zero-Dependency (Performance Edition)

**오프라인 / 표준 라이브러리만 사용 (Tkinter, sqlite3, hashlib 등)**  
회사 보안 네트워크에서도 실행 가능하게 설계했습니다. (pip/인터넷 불필요)

## 포함 모듈
- 근태(출퇴근·점심) / 휴가 / 근무수정 신청 + **2단계 결재(매니저→HR)**
- 사용자/권한, 휴일 관리, 감사 로그, 설정(주간 캡/점심), 백업/복원, CSV 임포트
- ✅ **Performance Plus 세트**:
  - 목표(OKR/KPI) 관리: 분기/가중치/진행률, 제출/승인(2단계)
  - 성과 평가(360/self/peer/manager): 기간별 점수/코멘트, 평균
  - 역량 모델·직원 역량 수준 관리
  - 피드백(받은/보낸), 공개범위 설정
  - 대시보드: 목표 평균진행률, 평가 평균점수, Top/Bottom, 대기건수

## 실행
```powershell
# 프로젝트 루트에서 (Python 3.10+ 권장; Tkinter 포함)
python app/main.py
