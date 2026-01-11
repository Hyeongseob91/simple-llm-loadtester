# Claude Code Configuration

llm-loadtest 프로젝트를 위한 Claude Code 설정입니다.

## 폴더 구조

```
.claude/
├── agents/                          # 전문 에이전트 정의
│   ├── loadtest-debugger.md         # 디버깅 전문가
│   ├── loadtest-tester.md           # 테스트 전문가
│   └── loadtest-code-reviewer.md    # 코드 리뷰 전문가
│
├── skills/                          # 스킬 정의
│   ├── loadtest-system/             # 프로젝트 컨텍스트
│   │   └── SKILL.md
│   ├── memory-system/               # Goal Drift 방지 메모리 시스템
│   │   └── SKILL.md
│   └── clarify/                     # 요구사항 명확화
│       ├── SKILL.md
│       └── reference/
│           └── question-templates.md
│
└── memory/                          # 작업 메모리 (작업 시 생성)
    ├── task_plan.md                 # 마스터 플랜
    ├── notes.md                     # 리서치 노트
    └── checkpoint.md                # 세션 체크포인트
```

## 에이전트 사용법

### loadtest-debugger
부하테스트 문제 진단 전문가
- 트리거: "부하테스트 실패해", "vLLM 응답이 안 와", "메트릭이 이상해"

### loadtest-tester
테스트 실행 전문가
- 트리거: "테스트 실행해줘", "pytest 돌려줘"

### loadtest-code-reviewer
코드 품질 리뷰 전문가
- 트리거: "코드 리뷰해줘", "비동기 코드 체크"

## 스킬 사용법

### loadtest-system
프로젝트 전체 컨텍스트 제공
- 아키텍처, 코드 구조, 핵심 파일 경로

### memory-system
긴 작업에서 Goal Drift 방지
- 주요 결정 전 task_plan.md 읽기
- 에러 발생 시 Error Log 기록
- 세션 종료 시 checkpoint.md 업데이트

### clarify
모호한 요구사항 명확화
- 3단계 객관식 질문을 통한 체계적 명확화
- Before/After 비교 출력

## 메모리 시스템 사용

복잡한 작업 시작 시:

```bash
# memory 폴더에 파일 생성
mkdir -p .claude/memory
# task_plan.md, notes.md, checkpoint.md 생성
```

작업 중:
1. 주요 결정 전 → task_plan.md 읽기
2. 에러 발생 → Error Log 기록
3. 세션 종료 전 → checkpoint.md 업데이트

## 핵심 구현 노트

### AI 분석 보고서 (benchmarks.py)

**Thinking 모델 지원**:
- `/no_think` 옵션: system prompt 맨 앞에 추가하여 thinking 모드 비활성화 시도
- `</think>` 태그 감지: Qwen3-VL 등 thinking 모델의 추론 과정 필터링
- 버퍼링 로직: 스트리밍 응답에서 `</think>` 이후 내용만 출력

```python
# 핵심 로직 (benchmarks.py:generate_analysis)
if think_end_tag in buffer:
    idx = buffer.find(think_end_tag)
    remaining = buffer[idx + len(think_end_tag):].lstrip()
    report_started = True
```

**프롬프트 구성** (`_build_analysis_prompt`):
- 테이블 데이터에서 요약 통계 직접 계산 (summary 필드 의존 제거)
- 전문용어 설명 규칙 포함 (TTFT, Throughput, Goodput 등)
- 마크다운 헤딩으로 구조화된 보고서 형식 지정

### 핵심 파일 경로

| Task | Start Here |
|------|------------|
| 부하테스트 로직 | `core/load_generator.py` |
| 메트릭 계산 | `core/metrics.py` |
| AI 분석 보고서 | `api/src/llm_loadtest_api/routers/benchmarks.py:analyze_result` |
| 인프라 추천 | `core/recommend.py` |

## 출처

이 구성은 soundmind-ai-system 프로젝트의 .claude 폴더 구조를 참고하여 llm-loadtest에 맞게 커스터마이징되었습니다.
