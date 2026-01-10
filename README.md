# LLM Loadtest

> LLM 서빙 서버의 성능을 측정하고 최적화하기 위한 부하 테스트 도구

vLLM, SGLang, Ollama 등 OpenAI-compatible API 서버의 부하 테스트를 수행하고, 결과를 Web 대시보드에서 시각화합니다.

> **Note**: [llm-benchmark](../llm-benchmark) 프로젝트가 llm-loadtest로 통합되었습니다.
> llm-benchmark 사용자는 [마이그레이션 가이드](../llm-benchmark/README.md#마이그레이션-가이드)를 참조하세요.

## 목차

- [프로젝트 소개](#프로젝트-소개)
- [주요 기능](#주요-기능)
- [빠른 시작](#빠른-시작)
- [메트릭 상세 설명](#메트릭-상세-설명)
- [Web UI 가이드](#web-ui-가이드)
- [CLI 사용법](#cli-사용법)
- [API 레퍼런스](#api-레퍼런스)
- [설정 옵션](#설정-옵션)
- [아키텍처](#아키텍처)
- [지원 서버](#지원-서버)
- [프로젝트 구조](#프로젝트-구조)
- [개발 가이드](#개발-가이드)
- [향후 개발 방향](#향후-개발-방향)
- [FAQ](#faq)
- [라이선스](#라이선스)

---

## 프로젝트 소개

### 왜 LLM Loadtest가 필요한가?

LLM 서빙 서버의 성능을 정확히 측정하는 것은 생각보다 어렵습니다:

- **단순 처리량(Throughput)만으로는 부족합니다**: 높은 처리량이라도 지연 시간이 길면 사용자 경험이 나빠집니다.
- **LLM 특화 메트릭이 필요합니다**: 첫 토큰 응답 시간(TTFT), 토큰 생성 속도(TPOT) 등 LLM에 특화된 지표가 있습니다.
- **SLO 기반 품질 측정이 중요합니다**: Goodput 개념으로 실제 서비스 품질을 측정할 수 있습니다.

### 핵심 가치

| 가치 | 설명 |
|------|------|
| **정확한 측정** | tiktoken 기반 토큰 카운팅, LLM 특화 메트릭 (TTFT, TPOT, ITL) |
| **품질 기반 평가** | Goodput - SLO를 만족하는 요청 비율 측정 |
| **실시간 모니터링** | WebSocket 진행률, GPU 메트릭 (메모리, 활용률, 온도, 전력) |
| **시각화** | 인터랙티브 차트, 모델 비교, 결과 내보내기 |
| **확장성** | 어댑터 패턴으로 vLLM, SGLang, Ollama, Triton 등 지원 |

### 대상 사용자

- **ML Engineer**: LLM 서빙 최적화, 모델 성능 비교
- **DevOps**: SLO 기반 성능 모니터링, 용량 계획
- **연구원**: 다양한 모델/설정 성능 평가

---

## 주요 기능

| 카테고리 | 기능 | 상태 |
|---------|------|------|
| **부하 테스트** | 다중 동시성 레벨 테스트 | ✅ |
| | 요청 수 / 기간 기반 모드 | ✅ |
| | 워밍업 요청 | ✅ |
| **메트릭** | TTFT, TPOT, ITL, E2E Latency | ✅ |
| | Throughput, Request Rate | ✅ |
| | Goodput (SLO 기반) | ✅ |
| | p50/p95/p99 백분위수 | ✅ |
| **토큰** | tiktoken 정확 카운팅 | ✅ |
| | 다양한 모델 지원 (GPT, Llama, Qwen 등) | ✅ |
| **GPU** | 메모리 사용량 모니터링 | ✅ |
| | GPU 활용률, 온도, 전력 | ✅ |
| **Web UI** | 실시간 대시보드 | ✅ |
| | 벤치마크 결과 비교 | ✅ |
| | 테스트 프리셋 (Quick/Standard/Stress) | ✅ |
| | 다크모드 | ✅ |
| **내보내기** | CSV/Excel 다운로드 | ✅ |
| **보안** | API Key 인증 | ✅ |
| **운영** | 구조화된 로깅 (structlog, JSON) | ✅ |
| | 요청 ID 추적 | ✅ |
| **어댑터** | OpenAI Compatible (vLLM, SGLang, Ollama) | ✅ |
| | Triton Inference Server | 🚧 개발 중 |

---

## 빠른 시작

### Docker Compose (권장)

```bash
# 저장소 클론
git clone https://github.com/your-org/llm-loadtest.git
cd llm-loadtest

# 전체 서비스 시작
docker compose up -d

# 접속
# - Web UI: http://localhost:5050
# - API Docs: http://localhost:8085/docs
```

### CLI 설치

```bash
# 프로젝트 루트에서
pip install -e .

# 기본 부하 테스트
llm-loadtest run \
  --server http://localhost:8000 \
  --model qwen3-14b \
  --concurrency 1,10,50 \
  --num-prompts 100

# Goodput 측정 (SLO 기반)
llm-loadtest run \
  --server http://localhost:8000 \
  --model qwen3-14b \
  --concurrency 50 \
  --goodput ttft:500,tpot:50

# 결과 JSON 저장
llm-loadtest run \
  --server http://localhost:8000 \
  --model qwen3-14b \
  --output result.json
```

### 시스템 정보 확인

```bash
# 시스템 정보
llm-loadtest info

# GPU 상태
llm-loadtest gpu
```

---

## 메트릭 상세 설명

### 지연 시간 메트릭 (Latency Metrics)

#### TTFT (Time To First Token)

첫 토큰 응답 시간 - 사용자가 응답 시작을 인지하는 시간

| 항목 | 내용 |
|------|------|
| **정의** | 요청 전송 후 첫 토큰 수신까지의 시간 |
| **단위** | 밀리초 (ms) |
| **계산** | `first_token_time - request_start_time` |
| **의미** | 인터랙티브성, 사용자 대기 시간 |
| **목표** | 낮을수록 좋음 (일반적 SLO: <500ms) |
| **영향 요인** | 프롬프트 길이, 모델 크기, 서버 큐 대기 시간 |

#### TPOT (Time Per Output Token)

토큰 생성 속도 - 디코딩 성능 지표

| 항목 | 내용 |
|------|------|
| **정의** | 첫 토큰 이후 각 토큰 생성에 소요되는 평균 시간 |
| **단위** | 밀리초 (ms) |
| **계산** | `(end_time - first_token_time) / (output_tokens - 1)` |
| **의미** | 토큰 생성 처리량의 역수 |
| **목표** | 낮을수록 좋음 (SLO: <50ms) |
| **역관계** | TPOT 50ms = 초당 ~20토큰 생성 |

#### ITL (Inter-Token Latency)

토큰 간 지연 시간 - 생성 일관성 지표

| 항목 | 내용 |
|------|------|
| **정의** | 연속 토큰 간 시간 간격 |
| **단위** | 밀리초 (ms) 배열 |
| **의미** | 토큰 생성의 일관성 |
| **해석** | ITL 편차 작음 → 안정적, 편차 큼 → 불안정 |

#### E2E Latency (End-to-End)

전체 응답 시간 - 사용자가 체감하는 총 대기 시간

| 항목 | 내용 |
|------|------|
| **정의** | 요청 전송부터 완전한 응답까지 총 시간 |
| **단위** | 밀리초 (ms) |
| **공식** | `E2E = TTFT + TPOT × (output_tokens - 1)` |
| **의미** | 전체 사용자 대기 시간 |

### 처리량 메트릭 (Throughput Metrics)

#### Throughput

| 항목 | 내용 |
|------|------|
| **정의** | 초당 생성되는 토큰 수 |
| **단위** | tokens/second |
| **계산** | `total_output_tokens / duration_seconds` |
| **목표** | 높을수록 좋음 |

#### Request Rate

| 항목 | 내용 |
|------|------|
| **정의** | 초당 처리되는 요청 수 |
| **단위** | requests/second |
| **의미** | 시스템의 동시 처리 능력 |

### 백분위수 (Percentiles)

모든 지연 메트릭은 다음 통계를 제공합니다:

| 백분위수 | 의미 | 용도 |
|----------|------|------|
| **min/max** | 최솟값/최댓값 | 극단값 확인 |
| **mean** | 평균값 | 전체 경향 |
| **p50 (median)** | 50% 요청이 이 값 이하 | 일반적 성능 |
| **p95** | 95% 요청이 이 값 이하 | 높은 지연 감지 |
| **p99** | 99% 요청이 이 값 이하 | 극단 케이스 |
| **std** | 표준편차 | 변동성 |

**예시**: TTFT p95 = 2000ms → 95%의 요청이 2초 이내에 첫 토큰 수신

### Goodput (품질 기반 처리량)

**NVIDIA GenAI-Perf에서 제안한 개념**으로, 단순 처리량이 아닌 **SLO를 만족하는 요청의 비율**을 측정합니다.

#### SLO 임계값 설정

```bash
--goodput ttft:500,tpot:50,e2e:5000
# TTFT < 500ms AND TPOT < 50ms AND E2E < 5000ms
```

#### 계산 로직

**AND 조건**: 모든 활성 임계값을 동시에 만족해야 함

```
satisfied = (ttft < ttft_threshold) AND (tpot < tpot_threshold) AND (e2e < e2e_threshold)
goodput = satisfied_requests / total_requests × 100%
```

#### 결과 예시

```
Goodput: 87.0% (87/100 requests met SLO)
  - TTFT < 500ms: 92/100 (92%)
  - TPOT < 50ms: 89/100 (89%)
  - Both (AND): 87/100 (87%)  ← Final Goodput
```

#### 왜 Goodput이 중요한가?

| 시나리오 | Throughput | Goodput | 해석 |
|----------|------------|---------|------|
| A | 500 tok/s | 95% | 높은 처리량, 높은 품질 - **최적** |
| B | 800 tok/s | 60% | 높은 처리량, 낮은 품질 - **문제 있음** |
| C | 400 tok/s | 99% | 중간 처리량, 높은 품질 - **안정적** |

**결론**: 처리량이 높아도 품질이 낮으면 실제 서비스에서는 의미가 없습니다.

---

## Web UI 가이드

### 대시보드 (/)

- **전체 개요**: 총 실행 수, 완료/진행중/실패 현황
- **최근 벤치마크**: 최근 실행 목록
- **빠른 액션**: New Benchmark, Compare Results 버튼

### 새 벤치마크 (/benchmark/new)

#### 테스트 프리셋

| 프리셋 | 동시성 | 프롬프트 | Input | Output | 용도 |
|--------|--------|---------|-------|--------|------|
| **Quick** | 1, 5, 10 | 50 | 128 | 64 | 빠른 검증 |
| **Standard** | 1, 10, 50, 100 | 200 | 256 | 128 | 일반 테스트 |
| **Stress** | 10, 50, 100, 200, 500 | 500 | 512 | 256 | 스트레스 테스트 |

#### 설정 항목

- **서버 설정**: Server URL, Model Name, API Key
- **테스트 설정**: Concurrency, Number of Prompts, Input/Output Length, Streaming
- **Goodput SLO**: TTFT, TPOT, E2E 임계값 (선택)

### 결과 조회 (/benchmark/[id])

- **실시간 진행률**: WebSocket으로 진행 상황 업데이트
- **요약 카드**: Best Throughput, Best TTFT p50, Best Concurrency, Error Rate
- **Goodput 표시**: SLO 만족 비율

#### 차트

1. **Throughput & Latency 듀얼 Y축 차트**
   - 좌측 Y축: Throughput (tok/s)
   - 우측 Y축: Latency (ms)
   - **Brush**: 줌/팬 기능으로 범위 선택

2. **Error Rate & Goodput 차트**
   - 동시성별 에러율과 Goodput 비교

### 비교 (/compare)

- 최대 **5개** 벤치마크 선택 비교
- **모델 비교 테이블**: 각 벤치마크의 핵심 메트릭
- **동시성별 처리량 비교 차트**: 멀티 라인 그래프

### 히스토리 (/history)

- 모든 벤치마크 목록
- **상태 필터링**: Running (파랑), Completed (초록), Failed (빨강)
- **액션**: View (상세보기), Delete (삭제)

### 다크모드

- 사이드바 하단의 **Moon/Sun 토글 버튼**
- 시스템 설정 자동 감지
- 모든 컴포넌트 다크모드 지원

---

## CLI 사용법

### llm-loadtest run

```bash
llm-loadtest run \
  --server http://localhost:8000 \    # 필수: 서버 URL
  --model qwen3-14b \                  # 필수: 모델명
  --concurrency 1,10,50,100 \          # 동시성 레벨 (쉼표 구분)
  --num-prompts 100 \                  # 요청 수 (--duration과 택일)
  --duration 60 \                      # 기간 기반 모드 (초)
  --input-len 256 \                    # 입력 토큰 길이
  --output-len 128 \                   # 최대 출력 토큰
  --stream \                           # 스트리밍 모드 (기본값)
  --no-stream \                        # 비스트리밍 모드
  --warmup 5 \                         # 워밍업 요청 수
  --timeout 120 \                      # 요청 타임아웃 (초)
  --api-key $API_KEY \                 # API 인증 키
  --adapter openai \                   # 어댑터 (openai, triton)
  --goodput ttft:500,tpot:50 \         # Goodput SLO 임계값
  --output result.json                 # 결과 JSON 파일 저장
```

#### 옵션 상세

| 옵션 | 타입 | 기본값 | 설명 |
|------|------|--------|------|
| `--server, -s` | string | (필수) | 서버 URL |
| `--model, -m` | string | (필수) | 모델명 |
| `--concurrency, -c` | string | "1" | 동시성 레벨 (쉼표 구분) |
| `--num-prompts, -n` | int | 100 | 요청 수 |
| `--duration, -d` | int | - | 기간 기반 테스트 (초) |
| `--input-len` | int | 256 | 입력 토큰 길이 |
| `--output-len` | int | 128 | 최대 출력 토큰 |
| `--stream/--no-stream` | bool | True | 스트리밍 모드 |
| `--warmup` | int | 3 | 워밍업 요청 수 |
| `--timeout` | float | 120.0 | 요청 타임아웃 (초) |
| `--api-key` | string | - | API 인증 키 |
| `--adapter` | string | "openai" | 서버 어댑터 |
| `--goodput` | string | - | SLO 임계값 |
| `--output, -o` | path | - | 결과 파일 경로 |

### llm-loadtest info

시스템 정보 출력:
- Python 버전
- llm-loadtest 버전
- 의존성 라이브러리 버전 (httpx, numpy, pydantic)
- NVIDIA 드라이버 버전
- GPU 정보

### llm-loadtest gpu

GPU 상태 모니터링:
- Device Name
- Memory: 사용/총 메모리, 사용률
- GPU Util: GPU 활용률
- Temperature: 온도 (°C)
- Power: 전력 소비 (W)

---

## API 레퍼런스

**Base URL**: `http://localhost:8085`

### 엔드포인트

| Method | Endpoint | 설명 | 인증 |
|--------|----------|------|------|
| GET | `/health` | 헬스 체크 | - |
| GET | `/api/v1/benchmark/health` | 상세 헬스 체크 | - |
| POST | `/api/v1/benchmark/run` | 벤치마크 시작 | 필요* |
| GET | `/api/v1/benchmark/run/{run_id}` | 상태 조회 | - |
| GET | `/api/v1/benchmark/result/{run_id}` | 결과 조회 | - |
| GET | `/api/v1/benchmark/result/{run_id}/export` | 내보내기 (CSV/Excel) | - |
| GET | `/api/v1/benchmark/history` | 히스토리 목록 | - |
| POST | `/api/v1/benchmark/compare` | 결과 비교 | - |
| DELETE | `/api/v1/benchmark/run/{run_id}` | 결과 삭제 | 필요* |
| WS | `/api/v1/benchmark/ws/run/{run_id}` | 실시간 진행률 | - |
| GET | `/api/v1/benchmark/ws/stats` | WebSocket 통계 | - |

**\* 인증 필요**: `API_KEY` 환경변수 설정 시에만 활성화

### POST /api/v1/benchmark/run

벤치마크 시작

**요청 본문**:
```json
{
  "server_url": "http://localhost:8000",
  "model": "qwen3-14b",
  "adapter": "openai",
  "concurrency": [1, 10, 50],
  "num_prompts": 100,
  "input_len": 256,
  "output_len": 128,
  "stream": true,
  "warmup": 3,
  "timeout": 120.0,
  "api_key": "optional-key",
  "goodput_thresholds": {
    "ttft_ms": 500,
    "tpot_ms": 50,
    "e2e_ms": 3000
  }
}
```

**응답**:
```json
{
  "run_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "started"
}
```

### GET /api/v1/benchmark/result/{run_id}/export

결과 내보내기

**파라미터**:
- `format`: `csv` (기본) 또는 `xlsx`

**응답**: 파일 다운로드
- Content-Type: `text/csv` 또는 `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`

---

## 설정 옵션

### 환경변수

| 변수 | 설명 | 기본값 |
|------|------|--------|
| `API_KEY` | API 인증 키 (설정 시 인증 활성화) | (없음) |
| `DATABASE_PATH` | SQLite DB 경로 | `/data/benchmarks.db` |
| `LOG_LEVEL` | 로그 레벨 | `INFO` |
| `PORT` | API 서버 포트 | `8085` |

### 인증 설정

```bash
# 인증 없이 실행 (기본)
docker compose up -d

# 인증 활성화
API_KEY=your-secret-key docker compose up -d

# API 호출 시 헤더 추가
curl -X POST http://localhost:8085/api/v1/benchmark/run \
  -H "X-API-Key: your-secret-key" \
  -H "Content-Type: application/json" \
  -d '{"server_url": "...", "model": "..."}'
```

### 로깅 형식

구조화된 JSON 로그 (structlog):

```json
{
  "event": "request_started",
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "method": "POST",
  "path": "/api/v1/benchmark/run",
  "client_ip": "172.17.0.1",
  "timestamp": "2026-01-10T12:00:00.123456Z",
  "level": "info"
}
```

---

## 아키텍처

```
┌─────────────────────────────────────────────────────────────┐
│                        사용자                                │
│              CLI / Web UI (Next.js)                         │
└─────────────────┬───────────────────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────────────────┐
│                    API Server (FastAPI)                      │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │ REST Routes │  │  WebSocket  │  │ Auth Middleware     │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
│  ┌─────────────┐  ┌─────────────┐                           │
│  │  Database   │  │  Structlog  │                           │
│  │  (SQLite)   │  │   Logging   │                           │
│  └─────────────┘  └─────────────┘                           │
└─────────────────┬───────────────────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────────────────┐
│                    Benchmark Engine                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐   │
│  │LoadGenerator │  │MetricsCalc   │  │ TokenCounter     │   │
│  │ (asyncio)    │  │              │  │ (tiktoken)       │   │
│  └──────────────┘  └──────────────┘  └──────────────────┘   │
│  ┌──────────────┐  ┌──────────────┐                         │
│  │ GPU Monitor  │  │GoodputCalc   │                         │
│  │ (pynvml)     │  │              │                         │
│  └──────────────┘  └──────────────┘                         │
└─────────────────┬───────────────────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────────────────┐
│                    Server Adapters                           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐   │
│  │OpenAI Compat │  │   Triton     │  │   (확장 가능)    │   │
│  │(vLLM,SGLang, │  │ (TensorRT)   │  │                  │   │
│  │ Ollama)      │  │              │  │                  │   │
│  └──────────────┘  └──────────────┘  └──────────────────┘   │
└─────────────────┬───────────────────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────────────────┐
│                    LLM Serving Server                        │
│           vLLM / SGLang / Ollama / LMDeploy / Triton        │
└─────────────────────────────────────────────────────────────┘
```

### 데이터 흐름

1. **요청 시작**: CLI/Web → API Server → Benchmark Engine
2. **부하 생성**: LoadGenerator가 asyncio.Semaphore로 동시성 제어하며 요청 전송
3. **메트릭 수집**: 각 요청의 TTFT, TPOT, ITL, E2E 측정
4. **토큰 카운팅**: tiktoken으로 정확한 토큰 수 계산
5. **집계**: MetricsCalculator가 통계(p50/p95/p99) 및 Goodput 계산
6. **저장/반환**: SQLite에 저장, WebSocket으로 실시간 전송

---

## 지원 서버

| 서버 | 어댑터 | 상태 | 비고 |
|------|--------|------|------|
| **vLLM** | openai | ✅ 지원 | OpenAI-compatible API |
| **SGLang** | openai | ✅ 지원 | OpenAI-compatible API |
| **Ollama** | openai | ✅ 지원 | OpenAI-compatible API |
| **LMDeploy** | openai | ✅ 지원 | OpenAI-compatible API |
| **Triton** | triton | 🚧 개발 중 | Triton HTTP API |
| **TensorRT-LLM** | trtllm | 📋 예정 | - |

### 어댑터 선택

```bash
# OpenAI-compatible (기본값)
llm-loadtest run --adapter openai --server http://localhost:8000 ...

# Triton
llm-loadtest run --adapter triton --server http://localhost:8000 ...
```

---

## 프로젝트 구조

```
llm-loadtest/
├── core/                      # 핵심 로직
│   ├── load_generator.py      # asyncio 기반 부하 생성
│   ├── metrics.py             # TTFT, TPOT, Goodput 계산
│   ├── models.py              # Pydantic 데이터 모델
│   ├── tokenizer.py           # tiktoken 토큰 카운팅
│   └── gpu_monitor.py         # GPU 메트릭 수집
│
├── adapters/                  # 서버 어댑터
│   ├── base.py                # 추상 어댑터 인터페이스
│   ├── openai_compat.py       # vLLM, SGLang, Ollama
│   └── triton.py              # Triton Inference Server
│
├── cli/                       # CLI 도구
│   └── src/llm_loadtest/
│       ├── main.py            # typer 기반 CLI
│       └── commands/          # run, info, gpu 명령어
│
├── api/                       # FastAPI 백엔드
│   └── src/llm_loadtest_api/
│       ├── main.py            # FastAPI 앱
│       ├── routers/           # REST/WebSocket 라우터
│       ├── services/          # 비즈니스 로직
│       ├── database.py        # SQLite 연결
│       ├── auth.py            # API Key 인증
│       └── logging_config.py  # structlog 설정
│
├── web/                       # Next.js 대시보드
│   └── src/
│       ├── app/               # App Router 페이지
│       ├── components/        # React 컴포넌트
│       ├── hooks/             # 커스텀 훅
│       └── lib/               # API 클라이언트
│
├── docker/                    # Docker 설정
│   ├── Dockerfile.api
│   ├── Dockerfile.web
│   └── docker-compose.yml
│
└── pyproject.toml             # 패키지 설정
```

---

## 개발 가이드

### 로컬 개발

```bash
# CLI 개발
pip install -e ".[dev]"
llm-loadtest --help

# API 개발
cd api
pip install -e ".[dev]"
PYTHONPATH=../. uvicorn llm_loadtest_api.main:app --reload --port 8085

# Web 개발
cd web
npm install
npm run dev
```

### 테스트

```bash
# CLI 테스트
pytest tests/

# API 테스트
cd api && pytest tests/

# Web 린트
cd web && npm run lint
```

### Docker 빌드

```bash
# 전체 빌드
docker compose build

# API만 빌드
docker compose build api

# Web만 빌드
docker compose build web
```

---

## 향후 개발 방향

### Phase 5: 인프라 추천 기능 (진행 예정)

> **"이 서버가 동시 500명을 버티는가? 버티려면 H100 몇 장이 필요한가?"**

```bash
llm-loadtest recommend \
  --server http://localhost:8000 \
  --model qwen3-14b \
  --peak-concurrency 500 \
  --goodput-target 95

# 출력: "NVIDIA H100 5장 필요합니다"
```

상세 PRD: [docs/prd-phase5-infra-recommend.md](docs/prd-phase5-infra-recommend.md)

### 단기 목표

- [ ] Triton 어댑터 완성
- [ ] Redis 캐싱 통합
- [ ] Rate Limiting
- [ ] **인프라 추천 기능** (Phase 5)

### 중기 목표

- [ ] TensorRT-LLM 어댑터
- [ ] 분산 부하 테스트 (다중 클라이언트)
- [ ] Prometheus 메트릭 내보내기
- [ ] Grafana 대시보드 템플릿

### 장기 목표

- [ ] Kubernetes Operator
- [ ] CI/CD 통합 (GitHub Actions)
- [ ] 성능 회귀 자동 감지
- [ ] A/B 테스트 지원

---

## FAQ

### Q: TTFT와 E2E Latency의 차이는?

**A**:
- **TTFT**: 첫 토큰까지의 시간 (응답 시작)
- **E2E**: 전체 응답 완료까지의 시간

스트리밍 환경에서 TTFT가 빠르면 사용자는 빠른 응답을 인지하지만, 전체 응답은 더 오래 걸릴 수 있습니다.

### Q: Goodput이 낮은 이유는?

**A**:
1. **SLO 임계값이 너무 엄격함**: 더 여유 있는 값으로 조정
2. **동시성이 서버 용량 초과**: 동시성 레벨 감소
3. **서버 리소스 부족**: GPU 메모리, CPU 확인

### Q: GPU 모니터링이 안 되는 경우?

**A**:
1. **pynvml 설치 필요**: `pip install nvidia-ml-py`
2. **NVIDIA GPU만 지원**: AMD GPU는 미지원
3. **드라이버 확인**: NVIDIA 드라이버가 설치되어 있어야 함

### Q: 토큰 카운팅이 부정확한 경우?

**A**:
1. **tiktoken 미설치**: `pip install tiktoken` 후 재시작
2. **특수 모델**: OpenAI 토크나이저 기반이므로 다른 모델은 근사치
3. **한국어/특수문자**: 일부 언어에서 오차 발생 가능

### Q: 스트리밍 vs 비스트리밍?

**A**:
- **스트리밍** (`--stream`): TTFT, TPOT, ITL 개별 측정 가능
- **비스트리밍** (`--no-stream`): E2E만 정확, TTFT = E2E

정확한 LLM 메트릭을 위해 **스트리밍 모드를 권장**합니다.

### Q: 동시성 레벨 선택 가이드?

**A**:
| 목적 | 권장 동시성 |
|------|------------|
| 기본선 측정 | 1 |
| 일반 사용 시뮬레이션 | 10-50 |
| 피크 부하 테스트 | 100+ |
| 한계 테스트 | 서버 용량까지 점진적 증가 |

여러 동시성 레벨로 테스트하여 성능 변화 곡선을 파악하세요.

---

## 라이선스

MIT License

---

## 기여

버그 리포트, 기능 제안, PR을 환영합니다!

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request
