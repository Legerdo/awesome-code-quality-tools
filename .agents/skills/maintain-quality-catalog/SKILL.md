---
name: maintain-quality-catalog
description: 이 Awesome 저장소에 도구를 추가하거나 기능, 지원 언어, 라이선스, 추천 구성을 갱신한다. 공식 근거를 기록하고 JSON에서 문서를 다시 생성해 검사할 때 사용한다. 대상 프로젝트의 소스코드 수정에는 사용하지 않는다.
license: MIT
compatibility: 이 저장소 전체와 Git, Python 3.13이 필요하다. 외부 정보를 갱신할 때는 공식 원문에 접근할 수 있어야 한다.
---

# 도구 목록 관리

## 변경 전

`git status --short`로 기존 수정 사항을 확인한다. [기여 안내](../../../CONTRIBUTING.md), [라이선스 기준](../../../docs/LICENSE-POLICY.md), 수정할 도구와 프로필을 읽는다. 저장소 이름이 비슷한 다른 프로젝트를 같은 도구로 취급하지 않는다.

## 근거 확인

공식 README, 기능 문서, 해당 버전의 LICENSE를 확인한다. 구현 언어와 분석 대상 언어를 구분하고, 엔진 특화 기능을 일반 언어 지원만으로 추정하지 않는다.

`data/license-evidence.json`에는 원문 경로, blob SHA, 조회 시점을 기록한다. GitHub의 `NOASSERTION`은 원문을 읽어 판단하고 `review_note`를 남긴다. 조회가 막히면 기존 근거를 보존하고 미확인 상태를 보고한다.

도구 본체의 라이선스를 유료 기능, 룰팩, DB, 모델 서비스까지 확대하지 않는다. 라이선스나 기능을 바꾸는 수정과 문장만 다듬는 수정을 구분한다. 전체 목록을 다시 조사하지 않았다면 전체 확인 날짜를 새 날짜로 바꾸지 않는다.

## 수정

[catalog.json](../../../data/catalog.json)의 해당 항목과 관련 프로필만 수정한다. 이름, 언어, 기능, 한계, 공식 출처를 빠뜨리지 않는다. 같은 역할의 도구를 모두 필수로 지정하거나, 함께 쓸 수 있는 도구를 상호 배타적으로 묶지 않는다.

README나 상세표의 배치를 바꿀 때는 [문서 생성기](../../../scripts/catalog.py)를 수정한다. 생성 파일에만 패치를 넣지 않는다. 한국어 설명은 [문서 작성 기준](../../../docs/WRITING.md)을 따른다.

## 검사

저장소 루트에서 실행한다.

```powershell
python scripts/catalog.py --write
python scripts/catalog.py --check
python scripts/check_skills.py
python -m unittest discover -s tests -v
git diff --check
```

diff에서 도구 ID, 라이선스, 제외 상태, 언어, URL, 추천 관계가 의도대로 바뀌었는지 확인한다. README에서 상세 문서와 스킬까지 링크가 이어지는지도 확인한다.

검사 기준을 수정했다면 이유와 영향을 기록하고 정상 사례와 실패 사례를 모두 실행한다. 실패하는 테스트를 제거하거나 정책을 완화해서 목록을 통과시키지 않는다.

## 완료 보고

변경한 항목, 공식 출처, 실행한 검사, 미확인 부분을 보고한다. 커밋과 푸시는 요청받은 경우에만 한다. CI 실행을 확인하지 않았다면 로컬 검사 결과만 보고한다.
