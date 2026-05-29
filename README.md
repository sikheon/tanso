# E.L.O — Eco Logistics Optimizer

> **친환경 물류 경로 추천 시스템** — LLM 에이전트 기반 멀티엔진 라우팅 + CO₂ 정량 최적화

Kakao Mobility(주)와 OpenRouteService(벤치마크) 두 라우팅 엔진의 결과를 비교하고, 차량별 CO₂ 배출량을 정량 계산하여 환경 친화적인 경로를 추천하는 웹 기반 의사결정 지원 시스템입니다. Gemini 기반 LLM 에이전트가 단순 리포트 생성을 넘어 **워크플로우 컨트롤러**로 동작합니다 (Planner / Weight Composer / Constraint Extractor / Narrative Generator).

---

## ✨ 핵심 기능

- **멀티엔진 비교** — Kakao Mobility (주) + OpenRouteService (벤치마크)
- **차종·연료·속도구간별 CO₂ 정량 계산** — 환경부/IPCC 배출계수 + COPERT 간소화 속도 보정
- **다목적 VRP 최적화** — OR-Tools CP-SAT, `min(distance) / min(duration) / min(CO₂)` 3가지 목적함수 동시 비교
- **LLM-Native 의사결정** — Gemini 2.0 Flash 함수 호출로 가중치·제약 동적 생성
- **What-if 시뮬레이션** — 차종 변경 시 라우팅 재호출 없이 즉시 CO₂ 재계산

---

## 🏗️ 기술 스택

| Layer | Stack |
|---|---|
| Frontend | Next.js 14 (App Router) + TypeScript + TailwindCSS + Kakao Maps SDK |
| Backend | Python 3.12 + FastAPI + SQLAlchemy + Alembic |
| Solver | Google OR-Tools (VRP CP-SAT) |
| LLM | Google Gemini 2.0 Flash (Function Calling) |
| DB | PostgreSQL 16 + PostGIS |
| Container | Docker Compose |

---

## 📂 디렉토리 구조

```
tanso/
├── docs/                        # PRD, API 가이드, 아키텍처
│   ├── PRD.md
│   └── setup-api-keys.md
├── backend/                     # FastAPI + OR-Tools + LLM
│   ├── pyproject.toml
│   ├── src/
│   │   ├── main.py
│   │   ├── api/                 # REST 엔드포인트
│   │   ├── llm/                 # Gemini 오케스트레이터
│   │   ├── routing/             # Kakao / ORS 어댑터
│   │   ├── eco/                 # CO₂ 계산
│   │   ├── vrp/                 # OR-Tools 래퍼
│   │   ├── models/              # SQLAlchemy ORM
│   │   └── core/                # 설정, DB, 로깅
│   ├── alembic/                 # DB 마이그레이션
│   └── seeds/                   # 배출계수, 속도구간 시드
├── frontend/                    # Next.js + Tailwind
│   └── src/
│       ├── app/
│       ├── components/
│       └── lib/
├── docker-compose.yml           # PostgreSQL + PostGIS
├── .env.example                 # 백엔드 환경변수 템플릿
└── README.md
```

---

## 🚀 빠른 시작

### 0. 사전 요구사항

- **Python 3.12+**
- **Node.js 20+**
- **Docker Desktop** (PostgreSQL+PostGIS 컨테이너용)
- **Git**

### 1. 저장소 클론

```bash
git clone <repo-url> tanso
cd tanso
```

### ⚡ Windows 자동 설치 (한 줄)

Windows 10/11이라면 아래로 끝납니다 (아래 §2~§6 수동 절차 모두 생략):

```cmd
setup.bat                        :: Python/Node/Docker 자동 설치(winget) + venv + 의존성
                                 ::  + Postgres 컨테이너 + 마이그레이션 + 시드
:: .env / frontend\.env.local 열어서 API 키 입력
start.bat                        :: 백엔드 8000 + 프론트 3000 동시 기동
start.bat 8000 8010              :: 프론트를 8010으로 띄우려면 인자로 전달
stop.bat                         :: 종료
```

**setup.bat은 winget을 사용해서 Python 3.12 / Node.js LTS / Docker Desktop이 없으면 자동으로 설치합니다.** UAC(관리자 권한 승인) 팝업이 한 번 뜨고, Docker Desktop 첫 설치 시 WSL2 활성화로 재부팅이 필요할 수 있습니다 — 그 경우 재부팅 후 setup.bat을 한 번 더 실행하면 됩니다.

> macOS/Linux는 아래 §2~§6 수동 절차 따라주세요.

### 2. API 키 발급

[`docs/setup-api-keys.md`](docs/setup-api-keys.md) 가이드 따라 4종 키 발급:
- Kakao Mobility REST API
- Kakao Maps JS SDK
- OpenRouteService
- Google Gemini API

### 3. 환경 변수 설정

```bash
# 백엔드
cp .env.example .env
# 편집기로 .env 열어서 API 키 입력

# 프론트엔드
cp frontend/.env.local.example frontend/.env.local
# NEXT_PUBLIC_KAKAO_MAP_KEY 입력
```

### 4. 데이터베이스 기동

```bash
docker compose up -d postgres
```

PostGIS 확장 포함 PostgreSQL 16이 5432 포트에서 동작합니다.

### 5. 백엔드 실행

```bash
cd backend
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install -e .
alembic upgrade head            # DB 스키마 적용 (Phase 1 이후)
python -m src.main              # http://localhost:8000
```

### 6. 프론트엔드 실행

```bash
cd frontend
npm install
npm run dev                     # http://localhost:3000
```

---

## 📖 문서

- **[PRD](docs/PRD.md)** — 제품 요구사항 정의 (전체 스펙)
- **[API 키 발급 가이드](docs/setup-api-keys.md)** — 외부 서비스 가입/설정 절차
- API 명세 — Phase 6 이후 `/docs` (Swagger UI) 자동 생성

---

## 🛣️ 개발 로드맵

전체 Phase는 [PRD §20](docs/PRD.md#20-마일스톤-개발-로드맵) 참조.

- [x] **Phase 0** — 환경 셋업, repo 초기화, API 키 가이드
- [ ] **Phase 1** — DB 스키마 + 기준 정보 시드
- [ ] **Phase 2** — Routing Adapter (Kakao + ORS)
- [ ] **Phase 3** — Eco-Analyzer (속도구간 보정)
- [ ] **Phase 4** — VRP Solver (OR-Tools)
- [ ] **Phase 5** — LLM Agent (4종 호출 + 검증)
- [ ] **Phase 6** — 백엔드 REST API
- [ ] **Phase 7** — 프론트 입력/지도/카드
- [ ] **Phase 8** — 프론트 내러티브/What-if/PDF
- [ ] **Phase 9** — 통합 테스트 + 시연 영상
- [ ] **Phase 10** — 발표 자료

---

## 📜 라이선스

(미정 — 학술/포트폴리오 용도)

---

## 🙋 문의

- 본 프로젝트는 졸업 작품 / 학회 포스터용 데모로 제작되었습니다.
- 배출계수 출처: 환경부 「교통수단별 온실가스 배출계수」 2023, IPCC 2006 Guidelines, 한국전력공사 전력사용 간접배출계수 2024
