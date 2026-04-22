## 작업 모드 (Working Mode)

- 기본적으로 분석 → 제안 → 승인 → 수정 순서로 진행한다.
- Default flow: Analyze → Propose → Confirm → Modify

- 사용자가 명시적으로 요청하기 전에는 파일을 수정하지 않는다.
- Do NOT modify files without explicit user request.

- 기본적으로 질문은 한글로 한다.
---

## 작업 범위 (Scope)

- 금지:
  - 프로젝트 루트 밖 접근 금지
  - Do NOT access outside project root

---

## 금지 (Forbidden)

- 민감 파일 접근 금지:
  - `.env`, `.pem`, `.key`, `.p12`
  - `service-account*.json`
  - `Secrets/**`

- Do NOT access secrets or credentials

- Git 변경 금지:
  - `git commit`
  - `git push`
  - `git reset`
  - `git clean`

- 파일 삭제 금지:
  - `rm`, `del`, `rmdir`

- Unity 실행/빌드 금지:
  - Do NOT run Unity Editor
  - Do NOT build project
  - Do NOT run Addressables build

---

## 허용 작업 (Allowed)

- 코드 분석 (Code analysis)
- 오류 분석 (Error debugging)
- 최소 수정 제안 (Minimal patch suggestion)
- read-only 명령:
  - `git diff`
  - `git status`
  - `grep`, `rg`

---

## 오류 처리 (Error Handling)

예: `NullReferenceException`

- null 체크 확인
- Check object reference
- `GetComponent` 결과 확인
- 초기화 순서 확인

---

## 응답 방식 (Response Format)

1. 원인 (Cause)
2. 해결 방법 (Fix)
3. 주의사항 (Caution)

---

## Python Specific Rules (파이썬 특화 규칙)

- 작업 범위:
  - `app/**`
  - `crawler/**`
  - `static/**`
  - `templates/**`
  - `requirements.txt`
  - `*.py`

- 수정 가능:
  - 모든 Python 스크립트
  - HTML, CSS, JavaScript 파일
  - 설정 파일 (제외: `.env`, 비밀 키)

- 제한:
  - `.env` 파일 (읽기 전용, 수정 금지)
  - 비밀 키, API 키 (노출 금지)
  - 외부 서비스 인증 정보

- 금지:
  - 크롤링 속도 제한 무시
  - 네이버 서비스 이용약관 위반
  - 지나친 빈도의 크롤링 (rate limiting)

- 크롤링 윤리:
  - robots.txt 존중
  - 합리적인 요청 빈도 유지
  - 서버에 과도한 부하 주지 않기

## 중요 원칙 (Important)

- 최소 변경 (Minimal change)
- 안전 우선 (Safety first)
- 명확한 설명 (Clear explanation)
- 크롤링 윤리 준수 (Crawling ethics)