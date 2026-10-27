"""Validate the curated catalog and render its Markdown tables. Standard library only."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import date, datetime
import json
from pathlib import Path
import re
import sys
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
GENERATED = ("README.md", "docs/TOOLS.md", "docs/PROFILES.md", "docs/EXCLUDED.md")


def load(root: Path = ROOT) -> tuple[dict, list, dict]:
    def read(name: str):
        return json.loads((root / name).read_text(encoding="utf-8"))
    return read("data/catalog.json"), read("data/license-evidence.json"), read("data/policy.json")


def secure_url(value: object) -> bool:
    if not isinstance(value, str):
        return False
    parsed = urlsplit(value)
    return parsed.scheme == "https" and bool(parsed.hostname) and not parsed.username and not parsed.password


def validate(data: dict, evidence: list, policy: dict) -> list[str]:
    """Return all catalog errors; do not fetch URLs or execute listed tools."""
    errors: list[str] = []

    def require(ok: bool, message: str) -> None:
        if not ok:
            errors.append(message)

    require(data.get("schema_version") == 1, "unsupported schema_version")
    try:
        require(date.fromisoformat(data["reviewed_on"]) <= date.today(), "review date is in the future")
    except (KeyError, ValueError, TypeError):
        errors.append("invalid review date")
    for key in ("tools_executed", "accuracy_benchmarked", "transitive_licenses_audited"):
        require(data.get("verification", {}).get(key) is False, f"unsupported verification claim: {key}")

    tools = data.get("tools", [])
    require(bool(tools), "empty tools")
    ids = [t.get("id") for t in tools]
    require(len(ids) == len(set(ids)), "duplicate tool id")
    lookup = {t["id"]: t for t in tools if "id" in t}
    evidence_ids = [e.get("id") for e in evidence]
    require(len(evidence_ids) == len(set(evidence_ids)), "duplicate evidence id")
    ev = {e["id"]: e for e in evidence if "id" in e}
    for item in evidence:
        ident = item.get("id", "?")
        require(ident in lookup, f"orphan evidence: {ident}")
        require("error" not in item, f"unresolved evidence fetch: {ident}")
        require(bool(re.fullmatch(r"[0-9a-f]{40}", item.get("blob_sha", ""))), f"invalid license blob SHA: {ident}")
        require(secure_url(item.get("url")), f"invalid evidence URL: {ident}")
        require(secure_url(item.get("immutable_blob_url")), f"invalid immutable evidence URL: {ident}")
        try:
            datetime.fromisoformat(item["retrieved_on"])
        except (ValueError, KeyError, TypeError):
            errors.append(f"invalid evidence timestamp: {ident}")
        if ident in lookup:
            require(item.get("repository") == lookup[ident].get("repo"), f"evidence repository mismatch: {ident}")
        if item.get("github_detection") in (None, "NOASSERTION"):
            require(bool(item.get("review_note")), f"manual license note required: {ident}")

    for t in tools:
        ident = t.get("id", "?")
        require(bool(re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", ident)), f"invalid tool id: {ident}")
        for key in ("name", "license", "summary", "limitations"):
            require(isinstance(t.get(key), str) and bool(t[key].strip()), f"missing {key}: {ident}")
        require(t.get("category") in data.get("categories", {}), f"unknown category: {ident}")
        require(t.get("status") in {"permissive", "engine-exception", "excluded"}, f"unknown status: {ident}")
        require(bool(t.get("languages")), f"missing languages: {ident}")
        require(set(t.get("languages", [])) <= set(policy["languages"]), f"unknown language: {ident}")
        if t.get("repo"):
            require(bool(re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", t["repo"])), f"invalid repository: {ident}")
            require(ident in ev, f"missing repository license evidence: {ident}")
        else:
            require(secure_url(t.get("homepage")), f"missing homepage: {ident}")
            require(bool(t.get("license_sources")), f"missing license source: {ident}")
        for url in t.get("sources", []) + t.get("license_sources", []) + ([t["homepage"]] if t.get("homepage") else []):
            require(secure_url(url), f"invalid source URL: {ident}")
        if t.get("status") == "permissive":
            require(t.get("license") in policy["permissive_expressions"], f"non-permissive license in active catalog: {ident}")
            detected = ev.get(ident, {}).get("github_detection")
            if detected and detected != "NOASSERTION":
                require(detected in t.get("license", ""), f"license evidence mismatch: {ident}")
        if t.get("status") == "engine-exception":
            require(ident in policy["engine_exception_ids"], f"unapproved engine exception: {ident}")
        for alt in t.get("alternatives", []):
            require(alt in lookup and lookup[alt].get("status") != "excluded", f"invalid alternative: {ident} -> {alt}")

    profiles = data.get("profiles", [])
    profile_ids = [p.get("id") for p in profiles]
    require(len(profile_ids) == len(set(profile_ids)), "duplicate profile id")
    for p in profiles:
        pid = p.get("id", "?")
        require(bool(p.get("base")), f"empty profile base: {pid}")
        require(bool(p.get("languages")), f"missing profile languages: {pid}")
        require(bool(p.get("notes")), f"missing profile notes: {pid}")
        all_refs: list[str] = []
        for role in ("base", "optional", "navigation"):
            all_refs.extend(p.get(role, []))
            for ident in p.get(role, []):
                if ident not in lookup:
                    errors.append(f"unknown profile tool: {pid} -> {ident}")
                    continue
                t = lookup[ident]
                require(t.get("status") != "excluded", f"excluded tool in profile: {pid} -> {ident}")
                langs = set(t.get("languages", []))
                require(bool(langs & set(p.get("languages", []))) or bool(langs & {"multi", "agnostic"}),
                        f"language mismatch: {pid} -> {ident}")
                if role == "navigation":
                    require(t.get("category") == "graph", f"non-graph navigation tool: {pid} -> {ident}")
        require(len(all_refs) == len(set(all_refs)), f"duplicate tool within profile: {pid}")
        require("featured_alternatives" not in p, f"deprecated mutually exclusive alternatives: {pid}")
        featured = p.get("featured_optional", [])
        require(isinstance(featured, list), f"invalid featured optional tools: {pid}")
        if isinstance(featured, list):
            require(all(isinstance(candidate, str) for candidate in featured),
                    f"invalid featured optional tool id: {pid}")
            if all(isinstance(candidate, str) for candidate in featured):
                require(len(featured) == len(set(featured)), f"duplicate featured optional tools: {pid}")
                for candidate in featured:
                    require(candidate in p.get("optional", []),
                            f"featured optional tool must be optional: {pid} -> {candidate}")
    return errors


def cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def table(headers: list[str], rows: list[list[str]]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    lines.extend("| " + " | ".join(cell(value) for value in row) + " |" for row in rows)
    return "\n".join(lines)


def tool_link(t: dict) -> str:
    url = t.get("homepage") or "https://github.com/" + t["repo"]
    label = f"[{t['name']}]({url})"
    return label + (" (엔진/SDK 제공)" if t["status"] == "engine-exception" else "")


def license_link(t: dict, evidence: dict) -> str:
    url = evidence.get(t["id"], {}).get("url") or t.get("license_sources", [None])[0]
    return f"[{t['license']}]({url})" if url else t["license"]


def render(data: dict, evidence: list) -> dict[str, str]:
    tools = data["tools"]
    lookup = {t["id"]: t for t in tools}
    ev = {e["id"]: e for e in evidence}
    count = Counter(t["status"] for t in tools)

    def links(ids: list[str]) -> str:
        return ", ".join(tool_link(lookup[i]) for i in ids) or "없음"

    def readme_recommendations(profile: dict) -> str:
        """Show useful optional tools without presenting them as mutually exclusive."""
        parts = [tool_link(lookup[ident]) for ident in profile["base"]]
        featured = profile.get("featured_optional", [])
        if featured:
            parts.append(", ".join(tool_link(lookup[ident]) for ident in featured) + " (병행 사용 가능)")
        return ", ".join(parts)

    def compact(items: list[dict]) -> str:
        return table(["도구", "주요 기능", "라이선스"], [[tool_link(t), t["summary"], license_link(t, ev)] for t in items])

    root_url = "https://github.com/" + data["repository"]
    readme = f"""<!-- Generated by scripts/catalog.py. Edit the generator for layout and data/catalog.json for entries. -->
# Awesome Code Quality Tools

[![Catalog CI]({root_url}/actions/workflows/catalog.yml/badge.svg)]({root_url}/actions/workflows/catalog.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

상업용 프로젝트에 사용할 코드 품질 검사기와 코드 탐색 도구를 개발 환경별로 정리한 목록이다. MIT, Apache-2.0, BSD, ISC처럼 라이선스 조건이 비교적 단순한 오픈소스를 우선 소개한다.

**수록 범위:** 개발 환경 {len(data['profiles'])}개, 일반 추천 도구 {count['permissive']}개, 엔진 및 SDK 제공 기능 {count['engine-exception']}개. 추천에서 제외한 도구 {count['excluded']}개도 이유와 대안을 기록했다.

**자료 확인일:** {data['reviewed_on']}. 공식 문서와 라이선스 원문을 검토한 목록이다. 도구의 실제 실행, 탐지 정확도, 배포물의 전체 라이선스는 검증하지 않았다.

## 목차

- [개발 환경별 추천](#quick-start)
- [코드 그래프와 AI 탐색](#graphs)
- [공통 품질 검사와 보안 도구](#common)
- [라이선스 선정 기준](#selection)
- [자료 관리와 검증](#verification)
- **추가 자료:** [전체 도구 목록](docs/TOOLS.md), [스택별 상세 가이드](docs/PROFILES.md), [추천 제외 이력](docs/EXCLUDED.md)

## 도구 선택 전에

코드 탐색 도구와 품질 검사기는 역할이 다르다.

- **코드 그래프:** 심볼, 호출 관계, 변경 영향을 탐색한다. 코드가 실제로 사용되는지 또는 수정이 안전한지를 단독으로 증명하지는 못한다.
- **정적 검사:** 미사용 코드와 의존성, 코딩 규칙, 아키텍처 위반 등을 찾는다. 빌드나 실행 테스트를 대신하지 않는다.
- **빌드 및 테스트:** 지정된 설정과 입력에서 동작을 확인한다. 실행하지 않은 경로까지 검증한 것은 아니다.

표에 나온 도구는 **도입 후보**다. 같은 역할의 도구를 모두 설치하기보다 프로젝트에 맞는 것부터 선택하는 편이 낫다.

<a id="quick-start"></a>
## 개발 환경별 추천

먼저 검토할 도구만 추렸다. 추가 검사기와 대체 도구, 엔진별 주의사항은 각 개발 환경의 링크에서 확인할 수 있다. 이름 뒤의 **(엔진/SDK 제공)** 표시는 일반 오픈소스와 사용 조건이 다를 수 있다는 뜻이다.

"""
    readme += table(["개발 환경", "먼저 살펴볼 도구"], [
        [f"[{p['name']}](docs/PROFILES.md#{p['id']})", readme_recommendations(p)] for p in data["profiles"]
    ])
    readme += """

**Knip과 Fallow:** 두 도구를 함께 실행할 수 있다. Knip은 미사용 파일, export, 의존성 검사에 집중하고, Fallow는 미사용 분석 외에도 복잡도, 코드 중복, 순환 의존성, 아키텍처 경계를 검사한다. 중복되는 미사용 진단은 CI에서 이중 집계하지 않도록 관리하고, 자동 수정은 변경 내용을 확인한 뒤 적용한다.

Godot의 GDScript는 CodeGraph의 확인된 지원 언어에 포함되지 않는다. Godot 내장 LSP와 엔진 테스트를 활용하고, C#이나 GDExtension(C++)은 해당 언어의 도구를 따로 검토해야 한다.

<a id="graphs"></a>
## 코드 그래프와 AI 탐색

이 목록에서 **CodeGraph**는 [colbymchenry/codegraph](https://github.com/colbymchenry/codegraph)를 가리킨다. CodeGraphContext는 다른 프로젝트다. 그래프 조회 결과와 AI가 생성한 설명은 구분해서 확인해야 한다.

"""
    readme += compact([t for t in tools if t["category"] == "graph" and t["status"] == "permissive"])
    readme += """

<a id="common"></a>
## 공통 품질 검사와 보안 도구

여러 언어에서 중복 코드, 복잡도, 비밀정보 노출, 의존성 취약점을 검사하거나 로컬 검사를 자동화할 때 쓸 수 있다.

"""
    readme += compact([t for t in tools if t["category"] in {"common", "testing"} and t["status"] == "permissive"])
    readme += """

<a id="selection"></a>
## 라이선스 선정 기준

- **우선 추천:** MIT, Apache-2.0, BSD, ISC 등 사용 조건이 비교적 단순한 라이선스의 도구.
- **별도 표시:** Unreal, Unity, Android에서 제공하는 엔진 및 SDK 기능. 해당 제품의 사용 조건을 따라야 한다.
- **추천 제외:** 비상업 용도로 제한되거나, 별도 유료 계약이 필요하거나, 현재 유지보수 상태가 달라진 도구. GPL, LGPL, AGPL 도구도 보수적으로 제외한다.

**GPL, LGPL, AGPL이 상업적 사용을 금지하는 것은 아니다.** 다만 수정본 배포나 결합 방식에 따라 추가 의무가 생길 수 있어 기본 추천에서 제외했다.

Fallow는 MIT 라이선스의 정적 분석 코어, Gitleaks는 MIT 라이선스의 CLI, Graphify는 오픈소스 패키지만 포함한다. 연동 DB, 룰팩, GitHub Action, 호스팅 서비스 등은 별도 조건을 확인해야 한다.

[선정 기준과 라이선스 원문](docs/LICENSE-POLICY.md) 및 [추천 제외 사유](docs/EXCLUDED.md)에 자세히 정리했다.

<a id="verification"></a>
## 자료 관리와 검증

도구 정보와 추천 조합은 [data/catalog.json](data/catalog.json)에서 관리한다. README와 상세 문서는 [scripts/catalog.py](scripts/catalog.py)로 생성한다. 문서의 문구나 배치를 바꾸려면 생성기를 수정해야 한다.

[라이선스 근거 기록](data/license-evidence.json)에는 확인한 파일 경로, Git blob SHA, 조회 시점을 남겼다. CI는 라이선스 분류, 제외 도구의 재유입, 언어별 추천, 내부 링크, 생성 문서와 데이터의 일치 여부를 검사한다. 외부 링크의 가용성과 수록 도구의 실행 성능은 검사하지 않는다.

```powershell
python scripts/catalog.py --write
python scripts/catalog.py --check
python -m unittest discover -s tests -v
```

수정 및 추가 방법은 [기여 안내](CONTRIBUTING.md), 검증 범위는 [검증 안내](docs/VERIFICATION.md)를 참고하면 된다. 생성 및 검사는 Python 3.13 표준 라이브러리만 사용하며 Windows와 Ubuntu에서 CI를 실행한다.

## 라이선스

이 저장소에서 작성한 문서, 데이터, 검사 스크립트에는 [MIT 라이선스](LICENSE)를 적용한다. 소개한 도구에는 각 프로젝트의 라이선스가 적용된다. 이 목록은 법률 자문이나 개별 배포물의 라이선스 적합성 인증이 아니다.
"""

    inventory = "<!-- Generated by scripts/catalog.py. -->\n# 전체 도구 상세표\n\n- [README로 돌아가기](../README.md)\n- [라이선스 정책](LICENSE-POLICY.md)\n- [추천 제외 이력](EXCLUDED.md)\n\n"
    inventory += "공식 문서를 바탕으로 선정한 후보이며 실제 실행, 성능, 오탐률은 검증하지 않았다. `multi`는 여러 언어를 지원한다는 뜻이지 모든 언어를 같은 수준으로 분석한다는 뜻은 아니다. 이름 뒤의 (엔진/SDK 제공) 표시는 제품별 사용 조건이 적용되는 기능이다. 라이선스 링크는 확인한 상위 원문으로 연결한다.\n\n"
    for group, title in data["categories"].items():
        selected = [t for t in tools if t["category"] == group and t["status"] != "excluded"]
        if not selected:
            continue
        inventory += f"## {title}\n\n"
        rows = []
        for t in selected:
            sources = " ".join(f"[문서 {i + 1}]({url})" for i, url in enumerate(t.get("sources", [])))
            rows.append([f'<a id="{t["id"]}"></a>' + tool_link(t), license_link(t, ev), t["summary"], t["limitations"] + (" " + sources if sources else "")])
        inventory += table(["도구", "라이선스 원문", "주요 기능", "적용 범위 및 주의사항"], rows) + "\n\n"
    inventory += "라이선스 원문 조회 기록은 [license-evidence.json](../data/license-evidence.json), 분류 원본은 [catalog.json](../data/catalog.json)에 있다. 메인 라이선스만으로 바이너리·전이 의존성·모델 API·DB까지 허용됐다고 판단하지 않는다.\n"

    profiles = "<!-- Generated by scripts/catalog.py. -->\n# 스택별 구성 가이드\n\n- [README로 돌아가기](../README.md)\n- [전체 도구 목록](TOOLS.md)\n\n"
    profiles += "Windows 11과 PowerShell을 기준으로 정리했다. 설치 명령은 특정 버전에서 검증한 것이 아니다. 빌드, 타입 검사, 린트, 테스트를 각각 기록하고 프로젝트 호환성과 기능 중복을 확인한 뒤 도구를 추가한다.\n\n"
    for p in data["profiles"]:
        profiles += f'<a id="{p["id"]}"></a>\n## {p["name"]}\n\n'
        profiles += table(["역할", "후보"], [["우선 검토", links(p["base"])], ["추가 또는 대체", links(p["optional"])], ["코드 탐색", links(p["navigation"])]])
        profiles += "\n\n" + p["notes"] + "\n\n"
    profiles += "## 단계별 적용\n\n"
    profiles += table(["단계", "작업", "확인할 결과"], [
        ["1. 기존 기준 확보", "현재 빌드·테스트와 버전·작업 디렉터리 기록", "기존 실패와 새 검사 실패 구분"],
        ["2. 검사기 하나 도입", "기본 규칙·범위·진입점 설정", "알려진 결함을 잡고 정상 동적 경로는 보존"],
        ["3. CI 연결", "도구별 종료 코드·예외·baseline 명시", "누락·timeout·partial을 PASS로 처리하지 않음"],
        ["4. 구조 검사 추가", "계층·순환·의존성 정책 정의", "규칙 위반을 재현 가능한 실패로 판정"],
        ["5. 탐색 도구 추가", "필요한 그래프만 인덱싱", "탐색 결과와 품질 게이트의 책임 분리"]
    ]) + "\n"

    excluded = "<!-- Generated by scripts/catalog.py. -->\n# 추천 제외 이력\n\n- [README로 돌아가기](../README.md)\n- [라이선스 선정 기준](LICENSE-POLICY.md)\n\n"
    excluded += "이 페이지에 있는 도구는 기본 추천에서 제외했다. 상업적 사용이 불법이라는 뜻은 아니다. 제외 이유와 대체 후보를 기록했으며, 대체 도구가 같은 기능이나 탐지 정확도를 보장하지는 않는다.\n\n"
    excluded += table(["도구", "라이선스와 상태", "제외 이유 및 참고 사항", "대체 후보"], [
        [tool_link(t), license_link(t, ev), t["limitations"], links(t.get("alternatives", [])) or "동등한 대체 미확인"]
        for t in tools if t["status"] == "excluded"
    ])
    excluded += "\n\nPeriphery의 과거 MIT 코드와 Serena의 과거 MIT 릴리스/SolidLSP는 사용권이 소급 취소됐다는 의미가 아니다. 이 저장소는 과거 버전을 대신 유지보수하는 운영 부담까지 고려해 새 기본 조합에서는 제외했다.\n\n"
    excluded += "## 주요 정책 원문\n\n"
    for t in tools:
        if t["status"] == "excluded":
            for url in t.get("sources", []) + t.get("license_sources", []):
                excluded += f"- [{t['name']} 공식 안내]({url})\n"
    return dict(zip(GENERATED, (readme, inventory, profiles, excluded)))


def check_internal_links(root: Path) -> list[str]:
    errors: list[str] = []
    for path in root.rglob("*.md"):
        if ".git" in path.parts:
            continue
        for target in re.findall(r"\]\(([^\s)]+)\)", path.read_text(encoding="utf-8")):
            parsed = urlsplit(target)
            if parsed.scheme or parsed.netloc:
                continue
            resolved = (path.parent / unquote(parsed.path)).resolve() if parsed.path else path.resolve()
            try:
                resolved.relative_to(root.resolve())
            except ValueError:
                errors.append(f"link escapes repository: {path.name} -> {target}")
                continue
            if not resolved.exists():
                errors.append(f"broken internal link: {path.name} -> {target}")
            elif parsed.fragment and resolved.suffix == ".md":
                text = resolved.read_text(encoding="utf-8")
                if f'id="{unquote(parsed.fragment)}"' not in text:
                    errors.append(f"missing explicit anchor: {path.name} -> {target}")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="Validate metadata and generated Markdown without rewriting")
    mode.add_argument("--write", action="store_true", help="Validate metadata, then regenerate Markdown")
    args = parser.parse_args(argv)
    try:
        data, evidence, policy = load()
        errors = validate(data, evidence, policy)
        if errors:
            raise ValueError("\n".join(errors))
        for relative, content in render(data, evidence).items():
            path = ROOT / relative
            if args.write:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8", newline="\n")
            elif not path.exists() or path.read_text(encoding="utf-8") != content:
                errors.append(f"generated file is stale: {relative}; run --write")
        errors.extend(check_internal_links(ROOT))
        if errors:
            raise ValueError("\n".join(errors))
        counts = Counter(t["status"] for t in data["tools"])
        print(f"PASS: {len(data['tools'])} catalog entries; {len(data['profiles'])} profiles; {dict(counts)}")
        print("Scope: catalog integrity only; listed tools were not executed.")
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
