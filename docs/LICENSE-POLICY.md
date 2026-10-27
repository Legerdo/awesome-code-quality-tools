# 라이선스 선정 기준

[README](../README.md) / [추천 제외 이력](EXCLUDED.md)

상업용 또는 비공개 프로젝트에서 내부 개발 도구를 고를 때 검토할 조건을 줄이기 위한 기준이다. 기능이나 성능의 순위가 아니며, 법적 안전성을 인증하는 목록도 아니다.

## 분류

| 분류 | 목록에 넣는 기준 | 도입 전에 확인할 것 |
| --- | --- | --- |
| `permissive` | MIT, Apache-2.0, BSD-2/3-Clause, ISC 또는 명시적인 퍼미시브 라이선스 선택지가 있다. | 저작권과 라이선스 고지, NOTICE, 수정 사실 고지, 개별 구성요소의 조건 |
| `engine-exception` | Unreal, Unity, Android 환경에서 제공하는 검사 기능이다. | 사용할 엔진, SDK, 패키지 버전의 조건. 독립 재배포 권한으로 해석하지 않는다. |
| `excluded` | 카피레프트 검토 부담, 비상업 제한, 별도 구독, 유지보수 변화 등을 이유로 기본 추천에서 뺐다. | 제외 이유와 대체 후보. 상업적 사용 금지와 같은 뜻은 아니다. |

자동 검사에 쓰는 라이선스 표현식과 엔진 예외 ID는 [policy.json](../data/policy.json)에 있다. 목록에 없는 라이선스나 불명확한 조건은 원문을 확인한 뒤 판단한다.

## GPL과 상업적 사용

GPL, LGPL, AGPL은 상업적 사용 자체를 금지하지 않는다. 내부에서 실행할 때와 수정본을 배포하거나 다른 코드에 연결할 때 확인할 조건이 다르다. 네트워크 서비스로 제공하는 경우도 별도로 검토해야 한다.

이 저장소는 관리 부담을 줄이기 위해 카피레프트 도구를 기본 추천에서 제외한다. 해당 도구를 실행했다는 이유만으로 검사 대상 프로젝트의 코드를 공개해야 한다는 뜻은 아니다.

근거는 [GNU GPL FAQ의 상업적 사용 설명](https://www.gnu.org/licenses/gpl-faq.html#GPLCommercially)과 [내부 사용 설명](https://www.gnu.org/licenses/gpl-faq.html#InternalDistribution)을 참고한다. [Apache License 2.0](https://www.apache.org/licenses/LICENSE-2.0)과 [MIT](https://opensource.org/license/mit)도 각각 원문을 확인한다.

## 본체와 별도 기능

| 도구 | 이 목록에서 확인한 범위 |
| --- | --- |
| CodeGraph | `colbymchenry/codegraph`의 MIT 본체다. 호스팅 상품은 포함하지 않는다. 사용 통계 수집과 외부 통신 설정도 별도로 확인한다. |
| Graphify | Apache-2.0 오픈소스 패키지를 다룬다. `LICENSE-MIT`과 `NOTICE`가 적용되는 부분도 확인한다. Cloud/Enterprise와 모델 API 계약은 포함하지 않는다. |
| CodeGraphContext | MIT 표기는 본체에 적용한다. 그래프 DB와 SCIP 인덱서의 조건은 별도이며 Neo4j Community는 기본 조합에 넣지 않는다. |
| Fallow | MIT 정적 분석 기능을 다룬다. 유료 Runtime은 포함하지 않는다. |
| Gitleaks | MIT CLI를 다룬다. `gitleaks-action`의 별도 이용 조건은 포함하지 않는다. |
| mypy, LLVM, Swift | 개별 구성요소의 고지와 라이선스 예외를 보존한다. 본체 라이선스만 확인한 것을 전체 바이너리 감사로 표시하지 않는다. |
| Android Lint | AOSP 소스와 Android SDK 배포물의 조건을 구분한다. SDK로 사용하는 경로는 엔진 예외로 분류한다. |
| Unity 패키지 | 옛 GitHub 저장소와 현재 UPM 패키지에 같은 조건이 적용된다고 가정하지 않는다. 설치할 버전의 LICENSE를 읽는다. |

고객용 SDK, 설치 프로그램, 컨테이너에 도구를 포함하거나 수정 배포, 서비스 제공을 할 때는 직접 의존성과 간접 의존성을 함께 검토한다. 이 저장소는 분석기 바이너리나 제3자 소스코드를 배포하지 않는다.

## 조회 기록

[license-evidence.json](../data/license-evidence.json)에는 GitHub 원문 경로, blob SHA, 조회 시점, 자동 인식 결과가 있다. blob SHA는 조회한 라이선스 파일을 식별하며 전체 프로그램 버전이나 바이너리를 식별하지는 않는다.

`NOASSERTION`은 라이선스가 없다는 뜻이 아니다. 자동 인식으로 판단하기 어려우면 원문을 읽고 `review_note`에 이유를 적는다. 도입할 버전이 같은 조건을 유지하는지는 다시 확인해야 한다.

이 저장소의 [MIT 라이선스](../LICENSE)는 직접 작성한 문서, 데이터, 스킬과 검사 코드에 적용한다. 소개한 도구의 라이선스를 대체하지 않는다.
