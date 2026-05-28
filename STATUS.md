# E.L.O — 현재 진행 상황 및 다음 단계

> **자리비움 중 자율 진행한 작업 요약** (2026-05-26)

---

## ✅ 완료 (Phase 0 + Phase 1 코드 작업)

### Phase 0 — 환경 셋업
- 디렉토리 구조 (`backend/`, `frontend/`, `docs/`, `seeds/`)
- `docs/PRD.md` v1.1 (리서치 반영)
- `docs/setup-api-keys.md` (Kakao/ORS/Gemini 발급 가이드)
- 루트 설정 (`.gitignore`, `.env.example`, `README.md`, `docker-compose.yml`)
- 백엔드 스캐폴드 (FastAPI + pyproject.toml + structlog + async SQLAlchemy)
- 프론트엔드 스캐폴드 (Next.js 15 + React 19 + Tailwind + 타입/API 클라이언트)
- **백엔드 venv 생성 + 의존성 설치 완료** (`backend/.venv`)

### Phase 1 — DB 스키마 + 시드
- 7개 ORM 모델 (`emission_factors`, `vehicles`, `speed_bin_factors`, `runs`, `jobs`, `routes`, `route_segments`)
- Alembic 초기화 + 최초 마이그레이션 `0001_initial_schema.py`
- 시드 SQL 3개:
  - `01_emission_factors.sql` — **v1.1 리서치 보정값** (트럭 215, 전기 79 등)
  - `02_speed_bin_factors.sql` — COPERT 간소화 8구간
  - `03_vehicles_sample.sql` — 데모 차량 7대
- `verify_db.py` — DB 연결 + PostGIS + 시드 카운트 확인
- `init_db.py` — DB 생성 + 마이그레이션 + 시드 일괄 적용
- `/health` 엔드포인트 확장 (DB + PostGIS ping, graceful degradation)
- **Windows psycopg async 호환 fix** (`asyncio_compat.py` — ProactorEventLoop 문제 해결)

### 리서치 결과 반영 (PRD v1.1)
- ✅ 배출계수 한국 실측 보정 (트럭 286→215, 전기 60→79)
- ✅ 다목적 가중합 정규화 = **Min-Max (Ideal-Nadir)** 명시 (Demir et al. 2014 EJOR)
- ✅ OR-Tools N≤20/GLS/10초 한계 검증됨
- ✅ LLM 통합 시간 재추정 6h → 14~23h, 전체 36h → 46~55h

### 검증 통과 항목
- 12+ Python 파일 syntax 검증
- Frontend JSON config 3개 valid
- Alembic `heads` / `history` / dry-run SQL 정상
- `from src.models import *` 정상 (7 테이블 metadata 등록)
- FastAPI 부팅 + `/`, `/health` 응답 (DB 없이도 graceful degraded)
- psycopg async 드라이버 정상 로드 → PostgreSQL 까지 연결 시도 도달

---

## ⏸️ 사용자 입력 대기

### PostgreSQL 비밀번호 필요

현재 로컬에 PostgreSQL 16 + PostGIS가 설치되어 실행 중이지만, `postgres` 슈퍼유저 비밀번호를 모릅니다.

**돌아오시면 다음 한 줄만 실행하면 Phase 1 전체 검증 완료**:

```powershell
cd C:\Users\hs\tanso\backend
.\.venv\Scripts\Activate.ps1
$env:PGPASSWORD = "여기에_postgres_슈퍼유저_비밀번호"
python -m src.scripts.init_db
```

이 스크립트는:
1. `elo` role + `elo` database 생성
2. PostGIS extension 활성화
3. Alembic 마이그레이션 적용 (7개 테이블)
4. 시드 데이터 INSERT (배출계수 15건, 속도구간 8건, 차량 7대)

완료 후 검증:
```powershell
python -m src.scripts.verify_db
# 기대 출력:
# [OK] Postgres: PostgreSQL 16.x...
# [OK] PostGIS:  3.x.x...
# Seed counts: emission_factors=15, speed_bin_factors=8, vehicles=7
# Sample (electric/sedan): 79.00 g/km — 환경부 2023 전력배출계수...
# [OK] All checks passed.
```

### API 키 4종 (Phase 2~5 시작 전 필요)

`docs/setup-api-keys.md` 따라 발급 후 `.env`에 입력:
- `KAKAO_REST_API_KEY` (Kakao Mobility — Phase 2)
- `ORS_API_KEY` (OpenRouteService — Phase 2)
- `GEMINI_API_KEY` (Phase 5)
- `frontend/.env.local` 의 `NEXT_PUBLIC_KAKAO_MAP_KEY` (Phase 7)

---

## ⏭️ 다음 단계 (Phase 2 — Routing Adapter)

비밀번호 입력 후 바로 시작 가능한 작업:

1. `src/routing/base.py` — `RoutingProvider` abstract 인터페이스
2. `src/routing/kakao.py` — Kakao Mobility 클라이언트 + 응답 정규화
3. `src/routing/ors.py` — OpenRouteService 클라이언트 + 응답 정규화
4. `src/routing/normalizer.py` — 공통 `Route`/`Segment` 스키마
5. 단위 테스트 (httpx mock + 실제 API 호출 통합 테스트)

---

## ⚠️ 알려진 이슈 / 메모

- Docker가 설치되어 있지 않아 `docker-compose up postgres`는 사용 불가. **로컬 PostgreSQL 16 사용**으로 대체.
- 트럭 2.5톤/5톤 배출계수는 **추정치** (공식 g/km 자료 부재). 시연 시 차종 선택을 1톤·승용 위주로 권장.
- `next-env.d.ts`는 첫 `npm run dev` 시 Next.js가 덮어쓸 수 있음 (정상).
- 백엔드 venv는 `backend/.venv` 에 생성됨. 활성화: `.\.venv\Scripts\Activate.ps1`
