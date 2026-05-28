# E.L.O Frontend

Next.js 15 (App Router) + React 19 + TypeScript + TailwindCSS.

## 개발 환경

```bash
npm install
cp .env.local.example .env.local
# NEXT_PUBLIC_KAKAO_MAP_KEY 입력
npm run dev                         # http://localhost:3000
```

## 스크립트

- `npm run dev` — 개발 서버
- `npm run build` — 프로덕션 빌드
- `npm run start` — 빌드 실행
- `npm run lint` — ESLint
- `npm run typecheck` — TypeScript 타입 체크

## 디렉토리

- `src/app/` — App Router 페이지/레이아웃
- `src/components/` — 재사용 UI (Phase 7 이후)
- `src/lib/` — API 클라이언트, 타입

## 환경변수

`.env.local` 파일:

```
NEXT_PUBLIC_KAKAO_MAP_KEY=...
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

`NEXT_PUBLIC_` 접두사가 있는 변수만 브라우저 번들에 포함됩니다.
