# Seed Data

PRD §11.3 기준 정보 시드 데이터. Alembic 마이그레이션 후 적용합니다.

## 파일

| 파일 | 내용 | 적용 순서 |
|---|---|---|
| `01_emission_factors.sql` | 차종/연료별 배출계수 (g CO2/km) | 1 |
| `02_speed_bin_factors.sql` | 평균속도 구간별 보정계수 | 2 |
| `03_vehicles_sample.sql` | 데모용 차량 7대 | 3 (FK 의존) |

## 수치 출처

배출계수는 **리서치 보고서 v1.1** 기준 한국 공인연비/전력배출계수 실측값으로 보정되었습니다 (PRD v1.0 추정치 대비 트럭 -25%, 전기차 +30%).

- 내연기관: 환경부 공인연비 측정 CO2 (2021~2023 대표 모델)
- 전기차: 환경부 2023년 전력배출계수 **0.4173 tCO2/MWh** ÷ 차종별 km/kWh
- 트럭 2.5t/5t: 공식 g/km 자료 부재로 **추정치** (운영 시 차량 실측 권장)

## 적용 방법

### 옵션 A: psql 수동 실행
```bash
psql -U elo -d elo -h localhost -f 01_emission_factors.sql
psql -U elo -d elo -h localhost -f 02_speed_bin_factors.sql
psql -U elo -d elo -h localhost -f 03_vehicles_sample.sql
```

### 옵션 B: init_db 스크립트 (권장)
```bash
python -m src.scripts.init_db
```

### 옵션 C: Docker 첫 기동
`docker-compose.yml`이 `./backend/seeds`를 `/docker-entrypoint-initdb.d`로 마운트하므로 컨테이너 최초 기동 시 자동 실행됩니다. (단, 본 프로젝트는 Alembic 마이그레이션 후 시드를 적용하므로 이 방식은 비추천)
