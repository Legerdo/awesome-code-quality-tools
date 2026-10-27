# 목록에 기여하기

도구를 추가하거나 설명을 고칠 때는 기능, 라이선스, 사용 조건의 근거를 함께 남긴다. 한국어 문장은 [작성 기준](docs/WRITING.md)을 따른다. AI 에이전트로 작업할 때는 [AGENTS.md](AGENTS.md)를 먼저 읽는다.

## 어디를 수정하나

| 바꿀 내용 | 수정할 파일 |
| --- | --- |
| 도구 정보와 개발 환경별 구성 | `data/catalog.json` |
| 라이선스 조회 기록 | `data/license-evidence.json` |
| 라이선스 허용 목록과 엔진 예외 | `data/policy.json` |
| README와 상세표의 고정 문구, 배치 | `scripts/catalog.py`의 `render()` |
| 스킬과 그 밖의 문서 | 해당 Markdown 파일 |

`README.md`, `docs/TOOLS.md`, `docs/PROFILES.md`, `docs/EXCLUDED.md`는 생성 파일이다. 이 파일만 고치면 다음 생성 때 변경이 사라진다.

## 도구 추가 또는 정보 갱신

1. 공식 저장소와 문서를 읽고 ID, 이름, 분석 대상 언어, 기능, 한계, 출처를 기록한다. 설치하거나 실행하지 않았다면 문서만 확인했다고 적는다.
2. LICENSE나 실제 사용할 패키지의 조건을 확인한다. 본체, 룰팩, DB, CI Action, 모델 API, 유료 기능을 구분한다.
3. GitHub 프로젝트는 라이선스 원문 URL, blob SHA, 조회 시점을 남긴다. 조건이 불명확하면 확인 전까지 추천에 넣지 않는다.
4. 관련 개발 환경의 목록을 갱신한다. 함께 쓸 수 있는 도구를 하나만 골라야 하는 것처럼 표시하지 않는다. 제외 도구는 추천 목록에 넣지 않는다.
5. 아래 검사를 실행하고 생성된 문서까지 확인한다. 전체 목록을 다시 검토하지 않았다면 전체 확인 날짜를 바꾸지 않는다.

```powershell
python scripts/catalog.py --write
python scripts/catalog.py --check
python scripts/check_skills.py
python -m unittest discover -s tests -v
git diff --check
```

## 라이선스 근거

GitHub에서 LICENSE를 열고 파일의 blob SHA를 확인한다. `gh api repos/OWNER/REPO/license`나 해당 파일의 Contents API를 사용할 수 있다. 루트에 LICENSE가 없으면 패키지 내부도 확인한다.

`github_detection`은 GitHub의 자동 인식 결과다. `null` 또는 `NOASSERTION`이면 원문을 읽고 `review_note`에 판단 이유를 적는다. 예외나 복수 라이선스는 원문의 선택 조건을 유지한다.

## 문장과 검사 코드

문장만 고칠 때는 도구 ID, URL, 라이선스, 지원 언어, 추천 관계, 수치, 확인 날짜를 유지한다. [edit-korean-docs 스킬](.agents/skills/edit-korean-docs/SKILL.md)에 대조할 항목을 정리했다.

정책이나 검사를 바꾸는 수정은 일반 목록 수정과 구분해서 설명한다. 테스트를 빼거나 기준을 낮춰서 통과시키지 않는다. 기존 실패 사례가 여전히 거부되는지 확인한다.

제3자 README 전체, 바이너리, 비밀정보, 개인 프로젝트 설정은 복사하지 않는다. 기여한 문서, 데이터, 스킬과 코드는 이 저장소의 [MIT 라이선스](LICENSE)로 제공되며 외부 프로젝트의 권리는 원저작자에게 남는다.
