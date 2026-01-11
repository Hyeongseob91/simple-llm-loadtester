# llm-loadtest - Claude Code Instructions

## Project Overview

vLLM 등 LLM 서버의 성능을 측정하는 부하테스트 도구입니다.

| Component | Location | Description |
|-----------|----------|-------------|
| CLI | `cli/` | Click 기반 CLI 명령어 |
| API | `api/` | FastAPI 백엔드 서버 |
| Core | `core/` | 부하 생성, 메트릭 계산 핵심 로직 |
| Web | `web/` | Next.js 대시보드 |
| Adapters | `adapters/` | vLLM, Triton 등 백엔드 어댑터 |

---

## Memory System (Goal Drift 방지)

> **복잡한 멀티스텝 작업 시 반드시 메모리 시스템을 활성화하세요.**

### 활성화 조건

다음 조건 중 하나라도 해당되면 메모리 시스템을 사용합니다:
- 3단계 이상의 작업
- 여러 파일 수정이 필요한 작업
- 리팩토링, 기능 추가 등 복잡한 작업
- 에러 해결이 3회 이상 실패한 경우

### CRITICAL RULES

#### Rule 1: READ BEFORE DECIDE

```
┌─────────────────────────────────────────────────────────────────┐
│  주요 결정 전, 반드시 .claude/memory/task_plan.md 읽기          │
└─────────────────────────────────────────────────────────────────┘
```

**적용 시점:**
- 새로운 파일 생성 전
- 아키텍처 결정 전
- 구현 방향 변경 전
- 에러 해결 방식 결정 전

#### Rule 2: LOG ALL ERRORS

```
┌─────────────────────────────────────────────────────────────────┐
│  에러 발생 시 task_plan.md의 Error Log에 반드시 기록            │
└─────────────────────────────────────────────────────────────────┘
```

**3회 반복 규칙:** 동일 에러 3회 반복 시 접근 방식 변경 필수

#### Rule 3: UPDATE CHECKPOINT

```
┌─────────────────────────────────────────────────────────────────┐
│  세션 종료 전 .claude/memory/checkpoint.md 업데이트 필수        │
└─────────────────────────────────────────────────────────────────┘
```

---

## Memory Files

```
.claude/memory/
├── task_plan.md      # Master Plan - 목표, 단계, 에러 로그
├── notes.md          # Research Notes - 발견 사항, 코드 참조
└── checkpoint.md     # Session State - 진행 상황, 다음 단계
```

### 작업 시작 시 초기화

복잡한 작업 시작 시 아래 명령으로 메모리 파일을 생성합니다:

```bash
mkdir -p .claude/memory
```

그리고 아래 템플릿으로 각 파일을 생성합니다.

---

## File Templates

### task_plan.md

```markdown
# [TASK_NAME] - Task Plan

> **Created**: YYYY-MM-DD
> **Status**: In Progress

---

## Objective

[한 문장으로 목표 정의]

---

## Success Criteria

- [ ] [완료 기준 1]
- [ ] [완료 기준 2]
- [ ] [완료 기준 3]

---

## Phases

### Phase 1: [단계명]

- [ ] Step 1.1: [설명]
- [ ] Step 1.2: [설명]

### Phase 2: [단계명]

- [ ] Step 2.1: [설명]
- [ ] Step 2.2: [설명]

---

## Current Status

| Field | Value |
|-------|-------|
| **Phase** | 1 |
| **Step** | 1.1 |
| **State** | Not Started |

---

## Error Log

| Date | Phase | Error | Attempted Solution | Result |
|------|-------|-------|-------------------|--------|
| | | | | |

---

## Error Patterns (3회 이상 반복)

| Pattern | Count | Root Cause | Resolution |
|---------|-------|------------|------------|
| | | | |

---

## Decisions Log

| Date | Decision | Rationale | Impact |
|------|----------|-----------|--------|
| | | | |
```

### notes.md

```markdown
# [TASK_NAME] - Research Notes

> **Last Updated**: YYYY-MM-DD

---

## Key Findings

### [Topic 1]
- [발견 사항]

---

## Code References

| File | Line | Description |
|------|------|-------------|
| | | |

---

## Ideas & Alternatives

- [대안 1]
- [대안 2]
```

### checkpoint.md

```markdown
# [TASK_NAME] - Session Checkpoint

> **Last Session**: YYYY-MM-DD
> **Progress**: 0%

---

## What Was Accomplished

- [완료 항목]

## What's In Progress

- [진행 중 항목]

## Files Modified

| File | Change | Description |
|------|--------|-------------|
| | | |

## Immediate Next Steps

1. [다음 단계 1]
2. [다음 단계 2]

---

## Quick Resume Checklist

- [ ] checkpoint.md 읽기 (현재 파일)
- [ ] task_plan.md Current Status 확인
- [ ] notes.md 관련 정보 스캔
```

---

## Workflow

### 1. 작업 시작

```
1. 복잡한 작업인가? → YES → 메모리 시스템 활성화
                    → NO  → 일반 작업 진행

2. .claude/memory/ 폴더 생성
3. task_plan.md 작성 (Objective, Success Criteria, Phases)
4. 작업 시작
```

### 2. 작업 중

```
┌─────────────────┐
│   작업 수행     │
└────────┬────────┘
         │
         ▼
    ┌─────────┐     YES    ┌──────────────────┐
    │ 주요    │───────────▶│ task_plan.md     │
    │ 결정?   │            │ READ             │
    └────┬────┘            └──────────────────┘
         │ NO
         ▼
    ┌─────────┐     YES    ┌──────────────────┐
    │ 에러    │───────────▶│ Error Log        │
    │ 발생?   │            │ WRITE            │
    └────┬────┘            └──────────────────┘
         │ NO
         ▼
    ┌─────────┐     YES    ┌──────────────────┐
    │ 발견    │───────────▶│ notes.md         │
    │ 사항?   │            │ APPEND           │
    └────┬────┘            └──────────────────┘
         │ NO
         ▼
    ┌─────────────────┐
    │   계속 작업     │
    └─────────────────┘
```

### 3. 단계 완료

```
1. task_plan.md 체크박스 업데이트 `- [x]`
2. Current Status 섹션 업데이트
3. Decisions Log에 주요 결정 기록
```

### 4. 세션 종료

```
1. checkpoint.md 업데이트
   - What Was Accomplished
   - Files Modified
   - Immediate Next Steps
```

### 5. 세션 재개

```
1. checkpoint.md READ
2. task_plan.md Current Status 확인
3. notes.md SCAN
4. 작업 재개
```

---

## Pre-Decision Checklist

주요 결정 전 확인:

- [ ] task_plan.md의 Objective와 일치하는가?
- [ ] Error Log에서 관련 실패 사례를 확인했는가?
- [ ] notes.md에 관련 리서치 결과가 있는가?
- [ ] 이 결정이 다른 Phase에 영향을 주는가?
- [ ] Success Criteria를 만족하는 방향인가?

---

## Post-Error Protocol

에러 발생 시:

1. [ ] Error Log에 즉시 기록
2. [ ] 동일 에러 이력 확인 (3회 규칙)
3. [ ] 3회 이상 반복 시:
   - Error Patterns에 기록
   - 접근 방식 변경 검토
   - notes.md에 대안 기록
4. [ ] 해결 후 Result 컬럼 업데이트

---

## Project-Specific Guidelines

### 핵심 파일 경로

| Task | Start Here |
|------|------------|
| 부하테스트 로직 | `core/load_generator.py` |
| 메트릭 계산 | `core/metrics.py` |
| GPU 모니터링 | `core/gpu_monitor.py` |
| 새 어댑터 추가 | `adapters/base.py` |
| CLI 명령어 | `cli/src/llm_loadtest/commands/` |
| API 엔드포인트 | `api/src/llm_loadtest_api/routers/` |
| AI 분석 보고서 | `api/src/llm_loadtest_api/routers/benchmarks.py:analyze_result` |
| 인프라 추천 | `core/recommend.py` |

### AI 분석 보고서 구현 노트

**Thinking 모델 지원** (`benchmarks.py:generate_analysis`):
- `/no_think` 옵션: system prompt 맨 앞에 추가
- `</think>` 태그 감지: Qwen3-VL 등 thinking 모델의 추론 과정 필터링
- 버퍼링: 스트리밍 응답에서 `</think>` 이후 내용만 출력

**프롬프트** (`_build_analysis_prompt`):
- 테이블 데이터에서 요약 통계 직접 계산
- 전문용어 설명 규칙 (TTFT, Throughput, Goodput 등)
- 마크다운 헤딩으로 구조화

### 코드 스타일

- Python: asyncio/aiohttp 비동기 패턴
- Type hints 필수
- docstring 작성
- 에러는 명시적 예외 처리

### 테스트

```bash
# 테스트 실행
pytest tests/ -v

# 커버리지 포함
pytest tests/ -v --cov=core --cov-report=term-missing
```

---

## Related Resources

- `.claude/skills/memory-system/SKILL.md` - 메모리 시스템 상세
- `.claude/skills/loadtest-system/SKILL.md` - 프로젝트 컨텍스트
- `.claude/skills/clarify/SKILL.md` - 요구사항 명확화
- `.claude/agents/` - 전문 에이전트들
