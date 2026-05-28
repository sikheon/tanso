# E.L.O — API 계약 및 UI 명세 (Phase 6/7 입력)

> PRD §13/§15를 실제 구현 직전 수준으로 구체화한 작업 명세.
> 본 문서가 백엔드 엔드포인트와 프론트 컴포넌트의 **단일 진실 소스**.

---

## 0. 의사결정 요약 (확정)

| 항목 | 결정 |
|---|---|
| 입력 모드 우선순위 | **폼 우선** (일반 사용자), 자연어는 VRP 토글 시 |
| 결과 화면 주역 | **지도 중심 (네비 스타일)** — 60% 영역 |
| VRP 입력 방식 | **자연어 + 폼 하이브리드** (LLM 파싱 → 폼 편집) |
| 이력/계정 | **계정 없음**, 단 **서버측 Run 이력은 영구 저장** (분석/재생용) |
| CRUD 대상 | **Run / Job / Vehicle** (EmissionFactor는 관리자 영역, 차후) |
| Run 활용 | **재생 중심** + 데이터 누적 (향후 통계·RAG로 업그레이드 여지) |

---

## 1. API 엔드포인트 전체 목록

### Action endpoints (작업 실행)
| Method | Path | 설명 |
|---|---|---|
| POST | `/api/v1/routes/p2p` | P2P 경로 추천 (멀티엔진 + Eco + Narrative) — Run 생성 |
| POST | `/api/v1/routes/vrp` | VRP 최적화 (3 목적함수) — Run 생성 |
| POST | `/api/v1/parse` | 자연어 → 구조화된 VRP 요청 (LLM Planner+Extractor) |
| POST | `/api/v1/runs/{run_id}/recalculate` | What-if 재계산 (차종 변경) |

### CRUD endpoints
| Method | Path | 설명 |
|---|---|---|
| GET | `/api/v1/runs` | Run 목록 (페이지·필터) |
| GET | `/api/v1/runs/{id}` | Run 상세 (routes + segments 포함) |
| PATCH | `/api/v1/runs/{id}` | Run 메타 수정 (label, notes) |
| DELETE | `/api/v1/runs/{id}` | Run 삭제 (cascade: jobs, routes, segments) |
| GET | `/api/v1/runs/{id}/jobs` | Run의 배송지 목록 |
| PATCH | `/api/v1/jobs/{id}` | Job 수정 (label, time_window) |
| GET | `/api/v1/vehicles` | 차량 목록 (시드 + 사용자 추가) |
| POST | `/api/v1/vehicles` | 차량 추가 |
| GET | `/api/v1/vehicles/{id}` | 차량 상세 |
| PATCH | `/api/v1/vehicles/{id}` | 차량 수정 |
| DELETE | `/api/v1/vehicles/{id}` | 차량 hard delete (Run에는 스냅샷이 남으므로 안전) |

### Meta endpoints
| Method | Path | 설명 |
|---|---|---|
| GET | `/health` | 헬스체크 (DB + PostGIS ping) — 이미 구현 |
| GET | `/api/v1/emission-factors` | 배출계수 목록 (read-only) |
| GET | `/api/v1/stats/summary` | 누적 통계 (Run 수, CO₂ 절감 합계 등) — 차후 확장 여지 |

---

## 2. 상세 명세

### 2.1 POST /api/v1/routes/p2p

**Request**:
```json
{
  "origin":      { "lat": 37.5547, "lng": 126.972, "address": "서울역" },
  "destination": { "lat": 35.1147, "lng": 129.0413, "address": "부산역" },
  "vehicle_id":  1,
  "options": {
    "engines": ["kakao", "ors"],
    "alternatives_per_engine": 2,
    "weights": { "distance": 0.1, "duration": 0.3, "co2": 0.6 },
    "generate_narrative": true
  }
}
```

**Response 200**:
```json
{
  "run_id": 123,
  "status": "done",
  "mode": "p2p",
  "vehicle": { "id": 1, "model": "쏘나타 (가솔린)", "fuel_type": "gasoline", "vehicle_class": "sedan" },
  "weights": { "distance": 0.1, "duration": 0.3, "co2": 0.6 },
  "routes": [
    {
      "id": 456,
      "engine": "ors",
      "objective": "recommend",
      "total_distance_m": 398444,
      "total_duration_s": 16140,
      "total_co2_g": 60489,
      "is_recommended": true,
      "score": 0.001,
      "polyline": [[lat, lng], ...],
      "segments": [
        { "seq": 0, "from": {"lat":..,"lng":..}, "to": {...}, "distance_m": 1200, "duration_s": 60, "avg_speed_kmh": 72.0, "co2_g": 174.3, "road_type": "..." }
      ]
    },
    { "id": 457, "engine": "kakao", "objective": "recommend", "...": "..." }
  ],
  "narrative": "## E.L.O 추천 경로...",
  "warnings": [],
  "created_at": "2026-05-27T10:00:00Z"
}
```

**Errors**:
- `400`: invalid coordinates / vehicle not found
- `503`: all routing engines failed (rare)

### 2.2 POST /api/v1/routes/vrp

**Request**:
```json
{
  "depot": { "lat": 37.5172, "lng": 127.0473, "address": "강남구청" },
  "jobs": [
    {
      "label": "고객A",
      "location": { "lat": 37.5006, "lng": 127.0367 },
      "address": "역삼동 ...",
      "time_window": ["09:00", "12:00"],
      "service_time_min": 10,
      "constraints": []
    }
  ],
  "vehicle_id": 2,
  "options": {
    "matrix_engine": "ors",
    "objectives": ["distance", "duration", "co2"],
    "solver_time_limit_s": 10,
    "weights": null,
    "generate_narrative": true
  }
}
```

**Response 200**:
```json
{
  "run_id": 124,
  "status": "done",
  "mode": "vrp",
  "depot": {...},
  "jobs": [ { "id": 7, "seq": 0, "label": "고객A", ... } ],
  "results": [
    {
      "objective": "co2",
      "visit_order_job_ids": [9, 11, 8, 7, 10],
      "visit_order_polyline": [[lat,lng], ...],
      "total_distance_m": 13760,
      "total_duration_s": 1140,
      "total_co2_g": 3023,
      "is_recommended": true,
      "solve_ms": 5000,
      "feasible": true
    },
    { "objective": "distance", "...": "..." },
    { "objective": "duration", "...": "..." }
  ],
  "narrative": "...",
  "solver": { "time_limit_s": 10, "metaheuristic": "GUIDED_LOCAL_SEARCH" },
  "created_at": "..."
}
```

### 2.3 POST /api/v1/parse (자연어 → 구조화)

**Request**:
```json
{ "text": "내일 오전 8시 강남 차고지 출발, 1톤 디젤 트럭으로 송파 3곳, 강동 2곳 배송, 12시까지 복귀. 강남 2번은 12-13시 받지 못함, 송파 1번은 후문 진입." }
```

**Response 200**:
```json
{
  "mode": "vrp",
  "vehicle_hint": { "fuel_type": "diesel", "vehicle_class": "truck_1t" },
  "depot_hint": "강남",
  "jobs_outline": [
    { "label": "송파-1", "raw": "송파 1곳" },
    { "label": "송파-2", "raw": "송파 2곳" },
    { "label": "송파-3", "raw": "송파 3곳" },
    { "label": "강동-1", "raw": "강동 1곳" },
    { "label": "강동-2", "raw": "강동 2곳" }
  ],
  "deadline_hint": "12:00",
  "weights": { "distance": 0.1, "duration": 0.5, "co2": 0.4 },
  "constraints": [
    { "site_id": "강남-2", "type": "time_window_exclusion", "range": "12:00-13:00" },
    { "site_id": "송파-1", "type": "access_note", "value": "후문 진입" }
  ],
  "llm_trace": { "planner_ms": 1505, "constraint_ms": 1603, "weights_ms": 1162 }
}
```

> 주의: `jobs_outline`은 **placeholder**. 사용자가 폼에서 좌표를 채워줘야 실제 VRP 실행 가능. 프론트에서 Kakao 주소검색 위젯과 연결.

### 2.4 POST /api/v1/runs/{run_id}/recalculate

차종만 변경해서 라우팅 재호출 없이 CO₂만 다시 계산.

**Request**:
```json
{ "vehicle_id": 5 }
```

**Response 200**:
```json
{
  "original_run_id": 123,
  "new_run_id": 130,
  "vehicle": { "id": 5, "...": "..." },
  "routes": [ { "id": 478, "total_co2_g": 33083, "...": "..." } ],
  "savings_vs_original_g": 27606,
  "narrative": "..."
}
```

### 2.5 GET /api/v1/runs (목록)

**Query params**: `limit=50&offset=0&mode=p2p|vrp&vehicle_id=&from=&to=&label=`

**Response 200**:
```json
{
  "items": [
    {
      "id": 123,
      "mode": "p2p",
      "label": null,
      "vehicle": { "id": 1, "model": "쏘나타 (가솔린)" },
      "summary": { "distance_km": 398.4, "duration_min": 269, "co2_g": 60489 },
      "status": "done",
      "created_at": "2026-05-27T10:00:00Z"
    }
  ],
  "total": 47,
  "limit": 50,
  "offset": 0
}
```

### 2.6 GET /api/v1/runs/{id} (상세)

전체 Run 데이터를 P2P/VRP response와 동일 구조로 반환 (재생용).

### 2.7 PATCH /api/v1/runs/{id}

**Request**:
```json
{ "label": "주말 인천공항 배송", "notes": "교통 좋음" }
```

### 2.8 GET/POST/PATCH/DELETE /api/v1/vehicles

표준 CRUD. **DELETE는 hard delete** — Run에 차종 스냅샷(`vehicle_snapshot`)이 저장되므로 외래키 깨져도 안전. `runs.vehicle_id`는 nullable + ON DELETE SET NULL.

POST body:
```json
{
  "plate": "12가3456",
  "model": "그랜저 HEV",
  "fuel_type": "hybrid",
  "vehicle_class": "sedan",
  "year_produced": 2024
}
```

→ 백엔드가 `emission_factor_id`는 자동 매핑 (fuel_type + vehicle_class 조합으로).

**Run 생성 시 vehicle_snapshot 자동 저장 예**:
```json
"vehicle_snapshot": {
  "id": 2,
  "model": "봉고3 1톤 (디젤)",
  "fuel_type": "diesel",
  "vehicle_class": "truck_1t",
  "year_produced": 2023,
  "emission_factor_g_per_km": 215.0,
  "emission_factor_source": "환경부 공인연비 2021 (봉고3 221, 포터2 204)"
}
```

→ 차량이 나중에 삭제돼도 Run 재생/분석 시 당시 차종 정보 그대로 사용.

### 2.9 GET /api/v1/stats/summary (확장 여지)

```json
{
  "total_runs": 47,
  "total_distance_km": 8420.3,
  "total_co2_kg": 1240.5,
  "total_co2_saved_kg": 124.7,
  "by_vehicle_class": [
    { "vehicle_class": "sedan", "runs": 30, "avg_co2_g_per_km": 144.2 }
  ],
  "by_engine": [
    { "engine": "kakao", "recommended_count": 28 },
    { "engine": "ors", "recommended_count": 19 }
  ]
}
```

---

## 3. DB 변경사항 (Phase 1 → Phase 6 추가)

기존 7테이블에 **컬럼 추가** (마이그레이션 `0002_run_user_metadata_and_vehicle_snapshot.py`):

```sql
-- runs
ALTER TABLE runs ADD COLUMN label VARCHAR(200);
ALTER TABLE runs ADD COLUMN notes TEXT;
ALTER TABLE runs ADD COLUMN vehicle_snapshot JSONB;
-- Allow vehicle to be deleted without orphaning runs
ALTER TABLE runs DROP CONSTRAINT runs_vehicle_id_fkey;
ALTER TABLE runs ADD CONSTRAINT runs_vehicle_id_fkey
    FOREIGN KEY (vehicle_id) REFERENCES vehicles(id) ON DELETE SET NULL;
```

새 테이블 없음. `vehicles`는 손대지 않음(`is_active` 추가하지 않음, hard delete 그대로 사용).

---

## 4. 프론트 UI 와이어프레임

### 4.1 메인 화면 (P2P 폼 모드, default)

```
┌──────────────────────────────────────────────────────────────────────┐
│  E.L.O — 친환경 물류 경로                          [📜이력]  [⚙ 설정] │
├──────────────────────────┬───────────────────────────────────────────┤
│                          │                                           │
│  ◉ P2P    ○ VRP 자연어   │                                           │
│                          │                                           │
│  ┌─────────────────────┐ │                                           │
│  │ 🔍 출발지            │ │                                           │
│  │ "서울역"            │ │                                           │
│  └─────────────────────┘ │           ┌───────────────────┐           │
│  ┌─────────────────────┐ │           │                   │           │
│  │ 🏁 도착지            │ │           │   [Kakao 지도]    │           │
│  │ "부산역"            │ │           │                   │           │
│  └─────────────────────┘ │           │  경로 폴리라인     │           │
│  ┌─────────────────────┐ │           │  마커 (출발/도착)  │           │
│  │ 🚗 차종              ▼│ │           │                   │           │
│  │ 휘발유 중형 sedan    │ │           └───────────────────┘           │
│  └─────────────────────┘ │                                           │
│                          │                                           │
│  ┌─────────────────────┐ │                                           │
│  │ 🌱 친환경 경로 찾기  │ │                                           │
│  └─────────────────────┘ │                                           │
│                          │                                           │
├──────────────────────────┴───────────────────────────────────────────┤
│  [경로 비교 카드 가로 스크롤 — 추천에 🌱 배지]                        │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐                            │
│  │ORS recommend🌱│ │Kakao recommend│ │Kakao alt│                    │
│  │398.4km / 269분│ │398.4km / 280분│ │405.5km/ │                    │
│  │60,489 g CO₂  │ │60,679 g CO₂   │ │62,593 g │                    │
│  └──────────┘ └──────────┘ └──────────┘                            │
├──────────────────────────────────────────────────────────────────────┤
│  [내러티브 패널 — 마크다운]                       [📋복사] [🔄재생성]│
│  ## E.L.O 추천 경로                                                  │
│  ORS 경로는 269분 만에 주파... 60,489g CO₂... 소나무 116.9일치       │
└──────────────────────────────────────────────────────────────────────┘
```

### 4.2 VRP 자연어 입력 모드

```
┌──────────────────────────┬───────────────────────────────────────────┐
│  ○ P2P    ◉ VRP 자연어    │                                           │
│                          │                                           │
│  ┌─────────────────────┐ │                                           │
│  │ ✏ 배송 요청 (자연어)│ │           [지도 + 배송지 마커]            │
│  │                     │ │           (좌표 채워질 때마다 추가)        │
│  │ "내일 오전 8시 강남  │ │                                           │
│  │  차고지 출발..."     │ │                                           │
│  │                     │ │                                           │
│  └─────────────────────┘ │                                           │
│                          │                                           │
│  [🤖 AI 파싱]            │                                           │
│                          │                                           │
│  ── 파싱 결과 (편집 가능) ──                                          │
│  📍 차고지: [강남구청       🔍]                                       │
│  📦 배송지:                                                          │
│   1. [송파-1   🔍] [TW 없음▼] [메모: 후문 진입]                      │
│   2. [송파-2   🔍] [TW 없음▼]                                        │
│   3. [강남-2   🔍] [TW 09:00-12:00 ▼] [메모: 점심 12-13시 ✗]        │
│   ...                                                                │
│  🚛 [디젤 1톤 트럭▼]                                                  │
│  ⚖ 가중치: [거리 0.1] [시간 0.5] [CO₂ 0.4]  (AI 자동, 수동 조정 OK)  │
│                                                                      │
│  [🌱 최적 경로 계산]                                                  │
└──────────────────────────────────────────────────────────────────────┘
```

### 4.3 이력 패널 (사이드 슬라이드)

```
┌─ 📜 최근 실행 ─────────────────────────────────┐
│  필터: [모든 모드▼] [모든 차종▼] [날짜 범위 ▼]│
│                                              │
│  ┌────────────────────────────────────────┐  │
│  │ 💡 #123  서울→부산 (가솔린 sedan)         │  │
│  │     398.4km · 269분 · 60.5kg CO₂        │  │
│  │     2026-05-27 10:00                    │  │
│  │     [재생] [What-if 차종변경] [삭제]    │  │
│  └────────────────────────────────────────┘  │
│  ┌────────────────────────────────────────┐  │
│  │ 🚛 #124  강남 5곳 VRP (디젤 1톤)         │  │
│  │     13.8km · 19분 · 3.0kg CO₂           │  │
│  │     2026-05-27 11:30                    │  │
│  └────────────────────────────────────────┘  │
│                                              │
│  📊 [통계 보기]                              │
└──────────────────────────────────────────────┘
```

### 4.4 인터랙션 룰

| 이벤트 | 동작 |
|---|---|
| 폼 입력 후 "경로 찾기" 클릭 | POST /routes/p2p → 결과로 지도/카드/내러티브 갱신 |
| 차종 드롭다운 변경 (결과 있는 상태) | POST /runs/{id}/recalculate → CO₂만 갱신 |
| 이력 패널 Run 클릭 → "재생" | GET /runs/{id} → 화면 복원 |
| 이력 Run → "What-if 차종변경" | 모달 → 차종 선택 → recalculate |
| VRP 자연어 입력 → AI 파싱 | POST /parse → 폼에 결과 자동 채움 |
| 경로 카드 hover | 지도 폴리라인 굵기 ↑, 나머지 dim |
| 내러티브 "재생성" 클릭 | LLM 다시 호출 (run.narrative 업데이트) |

---

## 5. 작업 분해 (Phase 6 백엔드)

```
[ ] 6.1 DB 마이그레이션 0002 (runs.label, notes / vehicles.is_active)
[ ] 6.2 API schemas (Pydantic): RoutesP2PRequest/Response, RoutesVRPRequest/Response,
        ParseRequest/Response, RunSummary, VehicleCreate/Update
[ ] 6.3 Service layer
    [ ] services/routing_service.py — RoutingAdapter + Eco + Normalizer 조합
    [ ] services/vrp_service.py     — Matrix + Solver + Eco 통합
    [ ] services/parse_service.py   — LLM Planner + Constraint + Weight
    [ ] services/recalc_service.py  — 차종만 변경 What-if
    [ ] services/run_service.py     — CRUD + Run 영속화
    [ ] services/vehicle_service.py — CRUD
[ ] 6.4 Routers
    [ ] api/routes/p2p.py
    [ ] api/routes/vrp.py
    [ ] api/parse.py
    [ ] api/runs.py    — CRUD + recalculate
    [ ] api/vehicles.py
    [ ] api/emission_factors.py (read-only)
    [ ] api/stats.py (read-only, optional)
[ ] 6.5 main.py에 router 등록 + OpenAPI 메타데이터
[ ] 6.6 통합 테스트 (tests/test_api_*.py) — httpx ASGI client
```

## 6. 작업 분해 (Phase 7 프론트 — 차후)

```
[ ] 7.1 Zustand store (mode toggle, currentRun, history cache)
[ ] 7.2 Kakao Maps 컴포넌트 + 폴리라인 렌더
[ ] 7.3 InputPanelP2P (출발/도착 자동완성 + 차종)
[ ] 7.4 InputPanelVRP (자연어 입력 + 파싱 결과 편집 폼)
[ ] 7.5 RouteCards (가로 스크롤 + 추천 배지)
[ ] 7.6 NarrativePanel (마크다운 + 복사/재생성)
[ ] 7.7 HistorySidePanel (Run list + 재생/What-if/삭제)
[ ] 7.8 VehicleSelector (드롭다운 + 추가 모달 — 추후)
```

---

**End of spec — confirm 후 Phase 6 구현 착수.**
