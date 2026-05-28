# API 키 발급 가이드

E.L.O 실행에 필요한 4종 외부 API 키 발급 절차입니다. 모두 무료 한도로 데모/개발 가능합니다.

> 발급한 모든 키는 `.env` (백엔드)와 `.env.local` (프론트엔드)에 저장하며, **절대 git에 커밋하지 마세요**. (`.gitignore`에 등록되어 있음)

---

## 1. Kakao Mobility REST API (경로 탐색 — 백엔드)

### 발급 절차

1. https://developers.kakao.com 접속 → 카카오 계정 로그인
2. 우측 상단 **"내 애플리케이션"** 클릭 → **"애플리케이션 추가하기"**
3. 정보 입력:
   - 앱 이름: `E.L.O`
   - 사업자명: 개인 이름 또는 학교명
4. 생성된 앱 클릭 → 좌측 메뉴 **"앱 키"**
5. **REST API 키** 복사 (예: `abc123...`)
6. 좌측 메뉴 **"카카오 모빌리티"** 또는 **"제품 설정 > Kakao Mobility"** → **"활성화"** ON

### 환경변수 등록

`.env` (백엔드)에 추가:
```
KAKAO_REST_API_KEY=발급받은_REST_API_키
```

### 무료 한도
- **일 300,000건** (REST API 전체 합산)
- 데모용으로 충분

### 주의사항
- Kakao Mobility의 Directions API는 **CORS 미지원** → 반드시 백엔드에서 호출
- 요청 시 헤더: `Authorization: KakaoAK {REST_API_KEY}`

---

## 2. Kakao Maps JS SDK (지도 렌더링 — 프론트엔드)

### 발급 절차

1. **1번 발급한 같은 앱**을 사용 (별도 앱 만들 필요 없음)
2. 앱 페이지 좌측 메뉴 **"앱 키"** 에서 **JavaScript 키** 복사
3. 좌측 **"플랫폼"** 메뉴 → **"Web 플랫폼 등록"**:
   - 사이트 도메인: `http://localhost:3000` (Next.js 기본 포트)
   - 배포 시: `https://your-domain.com` 추가
4. 좌측 **"카카오 맵"** 또는 **"제품 설정 > Kakao Map"** → **"활성화"** ON

### 환경변수 등록

`.env.local` (프론트엔드)에 추가:
```
NEXT_PUBLIC_KAKAO_MAP_KEY=발급받은_JavaScript_키
```

> `NEXT_PUBLIC_` 접두사가 있어야 프론트엔드 번들에 포함됨. 도메인 제한이 걸려있으므로 노출되어도 다른 도메인에서 사용 불가.

### 무료 한도
- **일 300,000건**

### 주의사항
- 등록한 도메인에서만 작동 — 로컬 개발은 반드시 `http://localhost:3000` 등록
- HTTPS 배포 시 `https://` 별도 등록

---

## 3. OpenRouteService API (벤치마크 경로 — 백엔드)

### 발급 절차

1. https://openrouteservice.org/dev/#/signup 접속
2. 이메일로 가입 (구글/깃허브 OAuth도 지원)
3. 로그인 후 https://openrouteservice.org/dev/#/home 이동
4. **"Request a token"** 클릭
   - Token type: **Standard (Free)**
   - Token name: `E.L.O`
5. **"CREATE TOKEN"** → 생성된 토큰 복사

### 환경변수 등록

`.env` (백엔드)에 추가:
```
ORS_API_KEY=발급받은_토큰
```

### 무료 한도
- **일 2,000건 (Directions API)**
- 분당 40건 (Rate Limit)
- 개인 개발자용으로 충분

### 주의사항
- 한국 도로 데이터는 **OpenStreetMap 기반**이라 Kakao보다 매칭 정확도가 낮음 → 본 프로젝트에서는 벤치마크/교차검증 용도
- 요청 헤더: `Authorization: {API_KEY}` (Bearer 접두사 없음)

---

## 4. Google Gemini API (LLM 에이전트 — 백엔드)

### 발급 절차

1. https://aistudio.google.com 접속 → 구글 계정 로그인
2. 좌측 메뉴 또는 우측 상단 **"Get API key"** 클릭
3. **"Create API key"** → 프로젝트 선택 (없으면 새 프로젝트)
4. 생성된 키 복사 (예: `AIza...`)

### 환경변수 등록

`.env` (백엔드)에 추가:
```
GEMINI_API_KEY=발급받은_API_키
GEMINI_MODEL=gemini-2.0-flash-exp
```

### 무료 한도 (Gemini 2.0 Flash 기준)
- **분당 15회 (RPM)**
- **일 1,500회 (RPD)**
- **토큰 100만/분 (TPM)**

### 주의사항
- 무료 티어 사용 시 입력 데이터가 모델 개선에 사용될 수 있음 (운영 시 유료 전환 검토)
- E.L.O는 회당 LLM 4회 호출 → 무료 한도로 일 약 **375회 시뮬레이션 가능**
- 데모 직전에 캐싱하면 RPM 제한 회피 가능

---

## 5. 발급 후 체크리스트

`.env` 파일에 다음 4개 키가 모두 설정되었는지 확인:

```bash
# 백엔드 .env
KAKAO_REST_API_KEY=...
ORS_API_KEY=...
GEMINI_API_KEY=...
GEMINI_MODEL=gemini-2.0-flash-exp

# DB (docker-compose 기본값과 동일하면 그대로)
DATABASE_URL=postgresql+psycopg://elo:elo_password@localhost:5432/elo

# 프론트엔드 frontend/.env.local
NEXT_PUBLIC_KAKAO_MAP_KEY=...
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

### 동작 확인 명령

백엔드 셋업 완료 후 다음 명령으로 키 유효성 검증 가능:

```bash
cd backend
python -m src.scripts.verify_keys
```

(이 스크립트는 Phase 2에서 추가)

---

## 6. 비용 추정 (모두 무료 한도 내)

| 서비스 | 본 프로젝트 회당 호출 | 일일 시뮬레이션 가능 횟수 |
|---|---|---|
| Kakao Mobility | 1~2회 (alternatives) | ~150,000회 |
| Kakao Maps JS | 페이지당 1~3회 | ~100,000회 |
| OpenRouteService | 1~2회 | **~1,000회** ← 가장 빠듯 |
| Gemini Flash | 4회 (Planner/Weight/Constraint/Narrative) | **~375회** ← 가장 빠듯 |

→ **Gemini와 ORS가 병목**. 데모 직전 시나리오는 결과 캐싱 권장.

---

## 7. 문제 해결

| 증상 | 원인 | 해결 |
|---|---|---|
| Kakao 401 Unauthorized | REST API 키 오타 또는 모빌리티 미활성화 | 앱 페이지에서 "카카오 모빌리티" 활성화 확인 |
| Kakao Maps 화면 빈 페이지 | 도메인 미등록 | 앱 페이지 → 플랫폼 → Web에 localhost:3000 추가 |
| ORS 403 Forbidden | 토큰 오타 또는 만료 | 새 토큰 발급 |
| ORS 한국 좌표 응답 없음 | OSM 데이터 갭 | 정상 동작 — 백엔드가 Kakao 단독 결과로 fallback |
| Gemini 429 Too Many Requests | RPM 15 초과 | 호출 간 sleep 또는 캐싱 활용 |
| Gemini 응답이 빈 객체 | function calling 미설정 | `tool_config.function_calling_config.mode = "ANY"` 확인 |

---

**문서 끝.**
