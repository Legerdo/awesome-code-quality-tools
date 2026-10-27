# 라이선스 선정 정책

[README로 돌아가기](../README.md) · [추천 제외 이력](EXCLUDED.md)

## 목적과 범위

상업용·폐쇄소스 프로젝트의 **내부 개발 도구를 고르는 과정에서 검토 부담을 줄이기 위한 보수적인 정책**이다. 도구의 기능·성능 순위나 법적 안전성 인증이 아니다.

| 분류 | 선정 기준 | 실제 도입 시 확인 |
| --- | --- | --- |
| `permissive` | MIT, Apache-2.0, BSD-2/3-Clause, ISC 및 명시적 퍼미시브 선택지 | 저작권·라이선스·NOTICE, 수정 고지, 구성요소별 조건 |
| `engine-exception` | 이미 사용하는 Unreal·Unity·Android 환경의 내장 검사 기능 | 실제 엔진/SDK/패키지 버전의 이용 조건. 독립 재배포 허용으로 해석하지 않음 |
| `excluded` | copyleft 검토 부담, 비상업 제한, 별도 구독, 유지보수 경로의 변화 | 제외 이유 및 대체안. 상업 이용 금지와 동일한 뜻이 아님 |

자동 검사의 허용 표현식과 예외 ID는 [policy.json](../data/policy.json)에 있다. 허용 목록에 없거나 라이선스가 불명확한 도구는 확인 전까지 추천에 넣지 않는다.

## GPL과 상업 사용을 혼동하지 않는다

GPL/LGPL/AGPL은 상업적 사용 자체를 금지하는 라이선스가 아니다. 단순 내부 실행, 수정·연결·재배포, 네트워크 서비스 제공은 서로 다른 검토 상황이다. 이 저장소는 범용 추천의 운영 부담을 낮추려는 이유로 copyleft 도구를 제외하며, 이를 사용한 프로젝트 코드가 자동으로 공개되어야 한다고 주장하지 않는다.

원문: [GNU GPL FAQ — 상업적 사용](https://www.gnu.org/licenses/gpl-faq.html#GPLCommercially), [내부 사용](https://www.gnu.org/licenses/gpl-faq.html#InternalDistribution), [Apache License 2.0](https://www.apache.org/licenses/LICENSE-2.0), [MIT](https://opensource.org/license/mit).

## 본체와 별도 구성요소를 구분한다

| 항목 | 이 목록의 범위 |
| --- | --- |
| CodeGraph | `colbymchenry/codegraph` MIT 본체. 별도 호스팅 상품 제외. telemetry·외부 통신 설정은 라이선스와 별도 검토 |
| Graphify | Apache-2.0 OSS 패키지. `LICENSE-MIT`·`NOTICE`가 적용되는 부분도 확인. Cloud/Enterprise 및 모델 API 계약 제외 |
| CodeGraphContext | MIT 본체. 그래프 DB·SCIP 인덱서의 라이선스는 별도. Neo4j Community를 기본 조합에 포함하지 않음 |
| Fallow | MIT 정적 코어만 포함. 유료 Runtime 제외 |
| Gitleaks | MIT CLI만 포함. `gitleaks-action`의 별도 조건 제외 |
| mypy·LLVM·Swift | 본체 외 구성요소 고지 또는 라이선스 예외를 보존. 상위 라이선스 표시는 전체 바이너리 감사 결과가 아님 |
| Android Lint | AOSP 소스 라이선스와 Android SDK 배포 이용 조건을 구분. SDK 사용 경로를 엔진 예외로 분류 |
| Unity 패키지 | 옛 GitHub 저장소의 라이선스가 현재 UPM 패키지에 동일하게 적용된다고 가정하지 않음. 설치 버전의 LICENSE 확인 |

도구를 고객용 SDK·설치 프로그램·컨테이너에 번들하거나 수정 배포·서비스화할 때는 직접 및 전이 라이선스를 따로 검토해야 한다. 이 저장소는 분석기 바이너리나 제3자 소스를 배포하지 않는다.

## 원문 근거와 변경 이력

[license-evidence.json](../data/license-evidence.json)은 GitHub 원본 파일의 경로, blob SHA, 조회 시점, 자동 인식 결과를 저장한다. SHA는 **조회한 라이선스 텍스트**의 식별자이지 전체 프로그램 버전이나 바이너리의 식별자가 아니다.

`NOASSERTION`은 라이선스가 없다는 뜻이 아니다. 자동 분류가 불명확하면 원문을 읽고 `review_note`를 남긴다. 조회 성공도 법률 검토 완료와 동일하지 않다. 외부 패키지의 최신 버전이 같은 조건을 유지하는지는 도입 시 재확인한다.

저장소 자체의 [MIT 라이선스](../LICENSE)는 큐레이션 문서·데이터·검사 스크립트에만 적용된다. 링크한 도구들의 라이선스를 대체하지 않는다.
