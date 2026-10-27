# 검증 상태와 도구 도입 기준

[README로 돌아가기](../README.md)

## 이 저장소에서 검사하는 것

| 검사 | 통과가 의미하는 것 | 의미하지 않는 것 |
| --- | --- | --- |
| 카탈로그·정책 검사 | ID·참조·언어 범위·선정 정책이 데이터상 일치 | 라이선스 적합성의 법적 인증 |
| 생성 문서 비교 | JSON과 Markdown 표가 일치 | 기재한 외부 기능의 실동작 |
| 내부 링크 검사 | 저장소 내부 파일·명시적 anchor가 존재 | 외부 사이트의 가용성 |
| negative fixture | 잘못된 라이선스·제외 도구 재유입 등의 예제를 검증기가 거부 | 모든 잘못된 설명을 자동 탐지 |

수록된 분석기를 프로젝트에 설치·실행하거나, 정확도·성능·오탐률을 측정하지 않았다. 모든 도구의 전이 의존성, 배포 바이너리, 룰팩, 플러그인을 전수 감사한 것도 아니다.

## 실제 도입 시 남길 기록

```text
OS / architecture:
engine / runtime / compiler version:
tool version or commit:
working directory / command / configuration:
target files / entrypoints / build flags:
expected diagnostic / actual diagnostic:
execution_status: succeeded | failed | skipped | timeout | partial
policy_status: pass | fail | not_evaluated
raw log / test artifact:
known limitations / exceptions:
```

실행 실패·미설치·파싱 실패·일부 파일만 검사된 상태를 PASS로 바꾸지 않는다. 진단 발견에 따른 non-zero 종료와 분석기 자체 오류도 구분한다. JSON/SARIF 출력 및 종료 코드의 계약은 사용 버전에서 확인한다.

## 최소 fixture

| 종류 | 예시 |
| --- | --- |
| 반드시 탐지 | 미사용 직접 의존성, 금지 계층 import, 순환 의존, 의도적으로 삽입한 버그 패턴 |
| 반드시 보존 | Unreal 리플렉션·Blueprint 참조, Unity 직렬화·씬 콜백, Godot 시그널, 프레임워크 등록·플러그인 진입점 |
| 실패 상태 | 잘못된 설정, 파서 실패, 누락된 도구, timeout, 일부만 분석된 결과 |

검사기의 삭제 후보를 곧바로 안전 삭제 목록으로 취급하지 않는다. 실제 타깃 빌드·관련 테스트·엔진 에셋 검사와 함께 판단한다. 그래프의 연결 부재는 런타임 사용 부재의 증명이 아니다.

## 재현 명령

Python 3.13, 외부 패키지 불필요. 저장소 루트에서 실행한다.

```powershell
python scripts/catalog.py --check
python -m unittest discover -s tests -v
```

CI는 Windows와 Ubuntu에서 같은 명령을 실행한다. 검사 기준을 바꾸는 수정과 목록을 추가하는 수정은 영향이 드러나게 분리해 검토한다. CI 통과와 브랜치 보호 설정은 별개이며, 워크플로 파일만으로 병합 차단이 강제되지는 않는다.
