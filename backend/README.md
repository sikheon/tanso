# E.L.O Backend

FastAPI + OR-Tools + Gemini 기반 경로 최적화 백엔드.

## 개발 환경

```bash
python -m venv .venv
.venv\Scripts\activate              # Windows
# source .venv/bin/activate         # macOS/Linux

pip install -e ".[dev]"
```

## 실행

```bash
python -m src.main                  # http://localhost:8000
# OpenAPI docs: http://localhost:8000/docs
```

## 헬스체크

```bash
curl http://localhost:8000/health
# {"status":"ok","version":"0.1.0"}
```

## 디렉토리

- `src/api/` — REST 엔드포인트
- `src/llm/` — Gemini 오케스트레이터
- `src/routing/` — Kakao / ORS 어댑터
- `src/eco/` — CO₂ 계산
- `src/vrp/` — OR-Tools 래퍼
- `src/models/` — SQLAlchemy ORM
- `src/core/` — 설정, DB, 로깅

## 환경변수

루트의 `../.env` 파일 참조. 누락 시 기본값 사용 (외부 API 호출은 실패).
