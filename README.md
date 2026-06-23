# 100억 가계부 — MCP 서버 (개발자 인계 패키지)

카카오 **PlayMCP / AGENTIC PLAYER** 공모전 출품용 MCP 서버입니다.
AI 에이전트(카카오 AI)가 "가계부 도구"를 호출해 **말로 가계부를 기록·분석**할 수 있게 합니다.

> 코드는 완성되어 로컬에서 정상 동작 확인됨(HTTP 200). 남은 작업은 **카카오 클라우드 배포 + PlayMCP 등록**뿐입니다. 숙련 개발자 기준 **1~2시간** 예상.

---

## 1. 구성

| 파일 | 설명 |
|------|------|
| `server.py` | MCP 서버 본체 (Python, FastMCP, streamable-http). 도구 8개. |
| `requirements.txt` | 의존성 (`mcp==1.28.0`) |
| `Dockerfile` | 컨테이너 빌드 |
| `.dockerignore` | 빌드 제외 목록 |

- **전송 방식**: Streamable HTTP (MCP 표준)
- **리슨**: `0.0.0.0:8000` (환경변수 `HOST`/`PORT`로 변경 가능)
- **MCP Endpoint 경로**: **`/mcp`** → 최종 PlayMCP 등록 주소 = `https://<배포도메인>/mcp`
- **Python**: 3.10+ (Docker 이미지는 3.12)

## 2. 로컬 테스트 (선택)

```bash
# uv 사용 시
uv venv --python 3.12 && uv pip install -r requirements.txt
.venv/bin/python server.py
# → http://0.0.0.0:8000/mcp 에서 동작

# initialize 핸드셰이크 확인 (200 이면 정상)
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000/mcp \
  -X POST -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"t","version":"1"}}}'
```

## 3. Docker 빌드 & 실행

```bash
docker build -t budget100eok-mcp .
docker run -p 8000:8000 budget100eok-mcp
# 영속 저장을 원하면: docker run -p 8000:8000 -v $(pwd)/data:/data budget100eok-mcp
```

## 4. 카카오 클라우드 배포 (요지)

목표: **공개 HTTPS 주소**로 위 컨테이너를 띄우기. (PlayMCP는 https Endpoint를 요구)

일반 흐름 (카카오 클라우드 컨테이너/Kubernetes 또는 VM 기준 — 콘솔 UI는 최신 문서 참고):

1. 이미지 빌드 후 **카카오 클라우드 컨테이너 레지스트리(KCR)** 에 push
2. **컨테이너 서비스 / Kubernetes** 로 배포, 컨테이너 포트 `8000` 노출
3. **로드밸런서 + 도메인 + 인증서(HTTPS)** 연결 → `https://<도메인>` 확보
   - (대안) VM에 Docker 설치 후 실행 + Nginx 리버스 프록시 + Let's Encrypt 로 HTTPS
4. 헬스 체크: `https://<도메인>/mcp` 에 위 `curl initialize` → `200` 확인

> 참고: PlayMCP가 요구하는 건 "도달 가능한 https MCP Endpoint" 입니다. 카카오 클라우드의 어떤 서비스를 쓰든 결과만 충족하면 됩니다. 가장 간단한 길은 **VM + Docker + Nginx + 인증서** 또는 **컨테이너 매니지드 서비스**입니다.

## 5. PlayMCP 등록 (배포 후)

[playmcp.kakao.com](https://playmcp.kakao.com) → "새로운 MCP 서버 등록" (대부분 항목은 임시등록 초안에 이미 입력됨):

- **MCP Endpoint**: `https://<배포도메인>/mcp`
- **인증 방식**: 인증 사용하지 않음 (MVP) — *주의: 사용자 식별 안 됨(6번 참고)*
- **[정보 불러오기]** 클릭 → 도구 8개가 인식되는지 확인
- 이상 없으면 **[등록 및 심사 요청]**

## 6. 도구(tool) 목록

| 도구 | 기능 |
|------|------|
| `record_expense` | 지출 기록 ("점심 8천원 썼어") |
| `record_income` | 수입 기록 ("월급 300만원 들어왔어") |
| `get_summary` | 월 수입/지출/잔액 |
| `analyze_spending` | 카테고리별 + 고정/변동비 분석 |
| `set_budget` / `check_budget` | 카테고리 예산 한도/초과 경고 |
| `goal_progress` | 100억 목표 진행률 + 응원 |
| `list_transactions` | 내역 조회(분류/월 필터) |

## 7. 주의 / 향후 개선 (본선용)

- **사용자별 데이터**: 현재 `user_id` 미전달 시 단일 저장소(`demo`) 공유. 다중 사용자 서비스로 가려면 **PlayMCP 인증(OAuth) 연동 → 사용자 식별값을 각 tool의 `user_id`로 주입**하도록 수정 필요. (`server.py`의 `_uid()` 참고)
- **데이터 영속성**: SQLite 파일. 컨테이너 재시작 시 유실 방지하려면 **볼륨 마운트(`/data`)** 또는 **관리형 DB(PostgreSQL 등)** 로 전환 권장.
- **안정성**: 헬스체크/오토스케일/재시작 정책 설정 권장.

---

문의(기획/브랜딩): MC2호선 · www.hellomc.com
