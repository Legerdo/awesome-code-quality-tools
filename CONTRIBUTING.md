# 기여 방법

이 저장소는 도구 수보다 **정확한 역할·근거·도입 조건**을 우선한다. 한국어 설명을 기본으로 하며 제품명과 공식 기술 용어는 원문을 유지한다.

## 도구 추가·수정

1. `data/catalog.json`에 ID, 이름, 언어, 분류, 본체 라이선스, 기능, 한계, 공식 출처를 기록한다. 설치·실행하지 않은 도구를 실동작 검증 완료로 표시하지 않는다.
2. 실제 LICENSE 또는 해당 패키지 조건을 확인한다. GitHub 배지나 `NOASSERTION`만으로 판정하지 않는다. 본체·룰팩·DB·Action·모델 API는 별도다.
3. GitHub 프로젝트는 `data/license-evidence.json`에 원문 URL, blob SHA, 조회 시점 및 필요할 경우 `review_note`를 남긴다. 새 도구의 라이선스가 불명확하면 추천에 넣지 않는다.
4. 관련 프로필에 추가하되 지원 언어를 과장하지 않는다. 같은 역할의 대안을 모두 필수로 두지 않는다. 제외 도구는 프로필에 참조할 수 없다.
5. 기준일을 갱신하고 아래 명령을 실행한다. 생성 파일을 직접 고치지 않는다.

```powershell
python scripts/catalog.py --write
python scripts/catalog.py --check
python -m unittest discover -s tests -v
```

## 원문 기록 방법

GitHub에서 원하는 LICENSE를 열고 해당 파일의 blob SHA를 확인한다. `gh api repos/OWNER/REPO/license` 또는 정확한 파일의 Contents API를 사용할 수 있다. 기본 LICENSE가 없는 프로젝트는 패키지 내부의 파일을 찾아야 한다.

`github_detection`은 GitHub의 자동 인식 결과일 뿐이다. null/NOASSERTION인 경우 직접 읽은 결과를 `review_note`로 기록한다. 라이선스 예외·복수 라이선스는 원문 표현을 확인하고 선택한 도입 범위를 설명한다.

## 정책·검증기 변경

`data/policy.json`, `scripts/`, `tests/`, `.github/workflows/` 변경은 통과시키기 위한 우회가 아니어야 한다. 변경 이유와 영향, 기존 negative fixture가 계속 실패하는지를 PR에 적는다. 기준 완화와 도구 추가를 한 문장으로 숨기지 않는다.

외부 링크를 가리키는 목록을 유지하며, 제3자 README 전체·바이너리·비밀정보·개인 프로젝트 설정을 복사하지 않는다. 기여한 문서·데이터·코드는 이 저장소의 [MIT 라이선스](LICENSE)로 제공된다. 링크한 프로젝트의 권리는 원저작자에게 남는다.
