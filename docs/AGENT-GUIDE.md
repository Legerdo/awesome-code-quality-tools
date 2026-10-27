# AI 에이전트로 활용하기

[README](../README.md) / [작업 규칙](../AGENTS.md)

이 저장소에는 도구 목록을 읽는 스킬, 목록을 관리하는 스킬, 한국어 문서를 다듬는 스킬이 있다. 분석기를 자동으로 설치하는 묶음은 아니다. 필요한 작업부터 지정한다.

## 제공하는 스킬

| 스킬 | 맡는 작업 | 하지 않는 일 |
| --- | --- | --- |
| [choose-quality-tools](../.agents/skills/choose-quality-tools/SKILL.md) | 프로젝트 설정을 확인하고 검사 도구와 검증 방법을 제안한다. | 추천만 요청했는데 패키지를 설치하거나 코드를 삭제하지 않는다. |
| [maintain-quality-catalog](../.agents/skills/maintain-quality-catalog/SKILL.md) | 공식 근거를 확인하고 JSON, 문서, 테스트를 갱신한다. | 근거 없이 라이선스 정책을 바꾸지 않는다. |
| [edit-korean-docs](../.agents/skills/edit-korean-docs/SKILL.md) | 문장과 Markdown을 다듬고 원래 의미를 대조한다. | 글을 줄이면서 조건, 수치, 지원 범위를 바꾸지 않는다. |

스킬은 이 저장소의 데이터와 문서를 참조한다. 스킬 폴더만 다른 프로젝트에 복사하면 상대 경로가 깨질 수 있으므로 저장소 전체를 두고 사용한다. 대상 프로젝트와 이 저장소의 경로를 에이전트에게 각각 알려 준다.

## 에이전트에서 읽는 방법

| 환경 | 이 저장소의 구성 |
| --- | --- |
| Codex | 스킬을 `.agents/skills/`에 둔다. 공식 문서에 안내된 프로젝트 스킬 경로다. |
| Claude Code | `CLAUDE.md`가 `AGENTS.md`를 가져온다. 작업에 맞는 스킬 파일을 경로로 읽도록 요청한다. `.claude/skills/`에 등록한 슬래시 명령은 제공하지 않는다. |
| 그 밖의 에이전트 | `AGENTS.md`와 필요한 `SKILL.md` 경로를 명시해서 읽도록 요청한다. 자동 발견 여부는 제품별로 확인한다. |

파일 구조는 공식 규격에 맞춰 작성했다. 각 에이전트에서 자동 발견과 실제 작업 수행을 시험한 결과는 아니다. 처음 사용할 때 에이전트가 읽은 파일 경로와 적용할 절차를 확인한다. 스킬 지침은 도구 권한을 강제로 제한하는 보안 설정도 아니다.

## 요청 예시

Codex에서 이 저장소를 연 상태라면 다음과 같이 요청할 수 있다. 아래 경로는 대상 프로젝트의 실제 경로로 바꾼다.

```text
$choose-quality-tools 대상 프로젝트는 C:\work\my-app이다.
기존 검사 설정을 먼저 읽고 미사용 의존성과 순환 참조를 확인할 도구를 제안해 줘.
아직 설치하거나 파일을 수정하지 마.
```

직접 파일을 읽게 하는 방식은 다음과 같다.

```text
AGENTS.md와 .agents/skills/maintain-quality-catalog/SKILL.md를 읽어 줘.
Fallow의 공식 문서에서 기능과 라이선스를 확인하고 바뀐 내용만 목록에 반영해 줘.
검사 결과와 아직 확인하지 못한 항목도 남겨 줘.
```

```text
.agents/skills/edit-korean-docs/SKILL.md를 읽고 README와 상세표를 다듬어 줘.
도구 정보와 추천 관계는 유지하고 생성기와 JSON 원본부터 수정해 줘.
```

## 필요한 항목만 JSON으로 조회

저장소 루트에서 실행한다. 외부 패키지는 필요하지 않다.

```powershell
python scripts/query_catalog.py --list-profiles
python scripts/query_catalog.py --profile typescript-web
python scripts/query_catalog.py --tool fallow
```

`--list-profiles`는 개발 환경별 ID와 이름을 보여준다. `--profile`과 `--tool` 결과에는 자료 확인일, 검증 상태, 도구 설명, 라이선스 근거가 포함된다. `--profile`은 기본 목록과 선택 목록, 코드 탐색 도구를 구분한다. `--tool`로 제외된 항목을 조회할 수도 있지만 `status: excluded`를 추천으로 해석하지 않는다.

이 명령은 로컬 목록만 읽는다. 네트워크에 접속하거나 대상 프로젝트를 스캔하지 않으며, 도구를 설치하거나 설정을 바꾸지도 않는다.

## 실제 도입 결과 남기기

[검증 안내](VERIFICATION.md)를 읽고 [결과 기록 양식](templates/QUALITY-CHECK.md)을 사용한다. 설치 여부, 분석기 실행 결과, 프로젝트의 합격 기준을 구분한다. 명령이 실행됐더라도 일부 파일이 누락됐거나 분석기가 오류로 종료됐다면 통과로 기록하지 않는다.

## 참고한 공식 자료

아래 자료는 2026-10-28에 확인했다. 설치 경로나 호출 방식은 제품 버전에 따라 달라질 수 있다.

| 자료 | 확인한 내용 |
| --- | --- |
| [Agent Skills 규격](https://agentskills.io/specification) | `SKILL.md` 필수 필드, 이름 규칙, 관련 파일 참조 |
| [AGENTS.md](https://agents.md/) | 프로젝트별 에이전트 작업 안내 형식 |
| [OpenAI 스킬 안내](https://developers.openai.com/codex/skills) | `.agents/skills/` 경로와 스킬 호출 |
| [Claude Code 메모리 안내](https://code.claude.com/docs/en/memory) | `CLAUDE.md`에서 `AGENTS.md` 가져오기 |
| [Claude Code 스킬 안내](https://code.claude.com/docs/en/skills) | `.claude/skills/` 등록과 파일 참조의 차이 |
| [AI Slop Thresher](https://github.com/Burntgogi/ai-slop-thresher) | 의미를 보존하면서 한국어 문장을 다듬는 기준 |
