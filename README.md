# LLM Loadtest

> LLM 서빙 서버 부하 테스트 도구

vLLM, SGLang, Ollama 등 OpenAI-compatible API 서버의 부하 테스트를 수행하고, 결과를 Web 대시보드에서 시각화합니다.

## 주요 기능

- **부하 테스트**: 다양한 동시성 레벨에서 LLM 서버 성능 측정
- **LLM 특화 메트릭**: TTFT, TPOT, ITL, Throughput, p95/p99
- **Goodput**: SLO 기반 품질 지표 (요청 중 임계값 만족 비율)
- **Web 대시보드**: 결과 시각화, 비교, 히스토리 관리
- **어댑터 패턴**: OpenAI-compatible, Triton (예정)

## 빠른 시작

### Docker Compose (권장)

```bash
# 전체 서비스 시작
docker compose up -d

# 접속
# - Web UI: http://localhost:5050
# - API: http://localhost:8085
```

### CLI 설치

```bash
cd cli
pip install -e .

# 기본 부하 테스트
llm-loadtest run \
  --server http://localhost:8000 \
  --model qwen3-14b \
  --concurrency 1,10,50 \
  --num-prompts 100 \
  --output result.json

# Goodput 측정
llm-loadtest run \
  --server http://localhost:8000 \
  --model qwen3-14b \
  --concurrency 50 \
  --goodput ttft:500,tpot:50

# 시스템 정보
llm-loadtest info
llm-loadtest gpu
```

## 프로젝트 구조

```
llm-loadtest/
├── core/                    # 핵심 로직
│   ├── load_generator.py    # asyncio 기반 부하 생성
│   ├── metrics.py           # TTFT, TPOT, Goodput 계산
│   └── models.py            # 데이터 모델
│
├── adapters/                # 서버 어댑터
│   ├── base.py              # 어댑터 인터페이스
│   └── openai_compat.py     # vLLM, SGLang, Ollama 지원
│
├── cli/                     # CLI 도구
├── api/                     # FastAPI 백엔드
├── web/                     # Next.js 대시보드
└── docker/                  # Docker 설정
```

## CLI 명령어

### `llm-loadtest run`

부하 테스트 실행

```bash
llm-loadtest run \
  --server http://localhost:8000 \    # 서버 URL
  --model qwen3-14b \                  # 모델명
  --concurrency 1,10,50,100 \          # 동시성 레벨
  --num-prompts 100 \                  # 요청 수
  --input-len 256 \                    # 입력 토큰 길이
  --output-len 128 \                   # 출력 토큰 길이
  --stream \                           # 스트리밍 모드
  --goodput ttft:500,tpot:50 \         # Goodput SLO
  --output result.json                 # 결과 파일
```

### `llm-loadtest info`

시스템 정보 출력

### `llm-loadtest gpu`

GPU 상태 확인

## API 엔드포인트

| Method | Endpoint | 설명 |
|--------|----------|------|
| POST | `/api/v1/benchmark/run` | 벤치마크 실행 |
| GET | `/api/v1/benchmark/run/:id` | 실행 상태 조회 |
| GET | `/api/v1/benchmark/result/:id` | 결과 조회 |
| GET | `/api/v1/benchmark/history` | 히스토리 목록 |
| POST | `/api/v1/benchmark/compare` | 결과 비교 |
| DELETE | `/api/v1/benchmark/run/:id` | 결과 삭제 |

## 메트릭 정의

| 메트릭 | 정의 |
|--------|------|
| **TTFT** | Time To First Token - 첫 토큰까지 시간 |
| **TPOT** | Time Per Output Token - 출력 토큰당 시간 |
| **ITL** | Inter-Token Latency - 토큰 간 지연 |
| **E2E** | End-to-End Latency - 전체 응답 시간 |
| **Throughput** | 초당 생성 토큰 수 (tokens/s) |
| **Goodput** | SLO 만족 요청 비율 (%) |

## Goodput

NVIDIA GenAI-Perf에서 제안한 개념으로, 단순 처리량이 아닌 **SLO를 만족하는 요청의 비율**을 측정합니다.

```bash
# TTFT < 500ms, TPOT < 50ms를 만족하는 요청 비율 측정
llm-loadtest run \
  --server http://localhost:8000 \
  --model qwen3-14b \
  --goodput ttft:500,tpot:50
```

출력 예시:
```
Goodput: 87.0% (87/100 requests met SLO)
  - TTFT < 500ms: 92/100
  - TPOT < 50ms: 89/100
```

## 지원 서버

| 서버 | 어댑터 | 상태 |
|------|--------|------|
| vLLM | `openai` | ✅ 지원 |
| SGLang | `openai` | ✅ 지원 |
| Ollama | `openai` | ✅ 지원 |
| LMDeploy | `openai` | ✅ 지원 |
| Triton | `triton` | 🚧 예정 |
| TensorRT-LLM | `trtllm` | 🚧 예정 |

## 개발

### 로컬 개발

```bash
# CLI 개발
cd cli
pip install -e ".[dev]"

# API 개발
cd api
pip install -e ".[dev]"
uvicorn llm_loadtest_api.main:app --reload --port 8080

# Web 개발
cd web
npm install
npm run dev
```

### 테스트

```bash
# CLI 테스트
cd cli && pytest tests/

# API 테스트
cd api && pytest tests/

# Web 테스트
cd web && npm run lint
```

## 라이선스

MIT License
