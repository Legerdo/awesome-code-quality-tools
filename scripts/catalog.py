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

게임, 앱, 웹, 서버 프로젝트에서 쓸 코드 품질 도구를 모았다. 코드 검사기부터 의존성 관리, 코드 그래프까지 개발 환경별로 찾아볼 수 있다. 라이선스 검토 부담을 줄이기 위해 MIT, Apache-2.0, BSD, ISC 계열을 우선한다.

개발 환경 {len(data['profiles'])}개를 다룬다. 일반 추천 도구 {count['permissive']}개와 엔진 및 SDK 제공 기능 {count['engine-exception']}개를 수록했고, 제외한 도구 {count['excluded']}개의 이유도 남겼다.

**자료 확인일:** {data['reviewed_on']}. 공식 문서와 라이선스 원문을 검토한 목록이다. 도구의 실제 실행, 탐지 정확도, 배포물의 전체 라이선스는 검증하지 않았다.

## 목차

- [개발 환경별 추천](#quick-start)
- [코드 그래프와 AI 탐색](#graphs)
- [공통 품질 검사와 보안 도구](#common)
- [AI 에이전트로 활용하기](#agents)
- [라이선스 선정 기준](#selection)
- [자료 관리와 검증](#verification)
- **추가 자료:** [전체 도구 목록](docs/TOOLS.md), [스택별 상세 가이드](docs/PROFILES.md), [추천 제외 이력](docs/EXCLUDED.md)

## 읽는 방법

개발 환경별 표에서 도구를 찾고, 상세 가이드에서 필요한 설정과 한계를 확인한다. 표는 모두 설치하라는 뜻이 아니다. 기존 검사와 겹치는 기능, 새로 확인할 문제를 기준으로 구성을 정한다.

코드 그래프는 구조와 참조를 찾고, 정적 검사기는 코드와 의존성의 문제를 찾는다. 실제 동작은 빌드와 테스트로 확인해야 한다. 어느 한 검사도 확인하지 않은 경로의 안전성까지 보장하지 않는다.

<a id="quick-start"></a>
## 개발 환경별 추천

각 환경의 기본 조합이다. 개발 환경 이름을 누르면 추가 도구와 설정 조건을 볼 수 있다. **(엔진/SDK 제공)** 기능은 해당 제품의 사용 조건을 따라야 한다.

"""
    readme += table(["개발 환경", "먼저 살펴볼 도구"], [
        [f"[{p['name']}](docs/PROFILES.md#{p['id']})", readme_recommendations(p)] for p in data["profiles"]
    ])
    readme += """

**Knip과 Fallow:** 두 도구를 함께 실행할 수 있다. Knip은 미사용 파일, export, 의존성 검사에 집중하고, Fallow는 미사용 분석 외에도 복잡도, 코드 중복, 순환 의존성, 아키텍처 경계를 검사한다. 중복되는 미사용 진단은 CI에서 이중 집계하지 않도록 관리하고, 자동 수정은 변경 내용을 확인한 뒤 적용한다.

Godot의 GDScript는 CodeGraph의 확인된 지원 언어에 포함되지 않는다. Godot 내장 LSP와 엔진 테스트를 활용하고, C#이나 GDExtension(C++)은 해당 언어의 도구를 따로 검토해야 한다.

<a id="graphs"></a>
## 코드 그래프와 AI 탐색

**CodeGraph**는 [colbymchenry/codegraph](https://github.com/colbymchenry/codegraph)다. CodeGraphContext와 이름은 비슷하지만 다른 프로젝트다. AI가 만든 설명을 실제 코드의 참조 관계와 같다고 보지는 않는다.

"""
    readme += compact([t for t in tools if t["category"] == "graph" and t["status"] == "permissive"])
    readme += """

<a id="common"></a>
## 공통 품질 검사와 보안 도구

여러 언어에서 중복 코드, 복잡도, 비밀정보 노출, 의존성 취약점을 검사하거나 로컬 검사를 자동화할 때 쓸 수 있다.

"""
    readme += compact([t for t in tools if t["category"] in {"common", "testing"} and t["status"] == "permissive"])
    readme += """

<a id="agents"></a>

## AI 에이전트로 활용하기

도구를 고르거나 이 목록을 관리할 때 쓸 스킬을 함께 제공한다. [AGENTS.md](AGENTS.md)에 작업 규칙을, [에이전트 안내](docs/AGENT-GUIDE.md)에 사용 예시를 정리했다.

| 스킬 | 용도 |
| --- | --- |
| [choose-quality-tools](.agents/skills/choose-quality-tools/SKILL.md) | 프로젝트 설정을 읽고 검사 도구와 검증 방법을 제안한다. |
| [maintain-quality-catalog](.agents/skills/maintain-quality-catalog/SKILL.md) | 공식 근거를 확인해 도구 정보와 추천 구성을 갱신한다. |
| [edit-korean-docs](.agents/skills/edit-korean-docs/SKILL.md) | 기능과 조건을 유지하면서 한국어 문장과 Markdown을 다듬는다. |

필요한 항목만 읽으려면 저장소 루트에서 다음 명령을 실행한다. 도구를 설치하거나 프로젝트 코드를 검사하는 명령은 아니다.

```powershell
python scripts/query_catalog.py --profile typescript-web
python scripts/query_catalog.py --tool fallow
```

<a id="selection"></a>
## 라이선스 선정 기준

- **우선 추천:** MIT, Apache-2.0, BSD, ISC 등 사용 조건이 비교적 단순한 라이선스의 도구.
- **별도 표시:** Unreal, Unity, Android에서 제공하는 엔진 및 SDK 기능. 해당 제품의 사용 조건을 따라야 한다.
- **추천 제외:** 비상업 제한, 별도 유료 계약, 구버전 유지보수 부담 등으로 기본 목록에서 뺀 도구. GPL, LGPL, AGPL도 제외한다.

**GPL, LGPL, AGPL이 상업적 사용을 금지하는 것은 아니다.** 다만 수정본 배포나 결합 방식에 따라 추가 의무가 생길 수 있어 기본 추천에서 제외했다.

Fallow는 MIT 라이선스의 정적 분석 기능, Gitleaks는 MIT 라이선스의 CLI, Graphify는 오픈소스 패키지만 포함한다. 연동 DB, 룰팩, GitHub Action, 호스팅 서비스 등은 별도 조건을 확인해야 한다.

[선정 기준과 라이선스 원문](docs/LICENSE-POLICY.md) 및 [추천 제외 사유](docs/EXCLUDED.md)에 자세히 정리했다.

<a id="verification"></a>
## 자료 관리와 검증

도구 설명과 추천 조합은 [data/catalog.json](data/catalog.json)이 원본이다. README와 상세표는 [scripts/catalog.py](scripts/catalog.py)로 만든다. 생성된 문서만 직접 고치면 다음 생성 때 덮어써지므로 원본부터 수정한다.

[라이선스 조회 기록](data/license-evidence.json)에는 파일 경로, Git blob SHA, 확인 시점을 남겼다. CI는 목록과 문서가 일치하는지, 제외한 도구가 추천에 다시 들어갔는지, 링크와 스킬 형식에 문제가 없는지 검사한다. 수록 도구의 성능이나 에이전트의 실제 행동까지 시험하지는 않는다.

```powershell
python scripts/catalog.py --write
python scripts/catalog.py --check
python scripts/check_skills.py
python -m unittest discover -s tests -v
```

Python 3.13 표준 라이브러리만 사용하며 Windows와 Ubuntu에서 CI를 실행한다. 변경 절차는 [기여 안내](CONTRIBUTING.md), 문장 편집은 [작성 기준](docs/WRITING.md), 검사 범위는 [검증 안내](docs/VERIFICATION.md)를 참고한다.

## 라이선스

이 저장소에서 작성한 문서, 데이터, 스킬과 검사 스크립트에는 [MIT 라이선스](LICENSE)를 적용한다. 소개한 도구에는 각 프로젝트의 라이선스가 적용된다. 이 목록은 법률 자문이나 개별 배포물의 라이선스 적합성 인증이 아니다.
"""

    inventory = "<!-- Generated by scripts/catalog.py. -->\n# 전체 도구 상세표\n\n- [README로 돌아가기](../README.md)\n- [라이선스 정책](LICENSE-POLICY.md)\n- [추천 제외 이력](EXCLUDED.md)\n\n"
    inventory += "공식 문서를 읽고 정리한 목록이다. 실제 실행, 성능, 오탐률은 검증하지 않았다. 라이선스를 누르면 확인한 원문을 볼 수 있다. (엔진/SDK 제공) 기능은 해당 제품의 사용 조건을 따른다.\n\n"
    for group, title in data["categories"].items():
        selected = [t for t in tools if t["category"] == group and t["status"] != "excluded"]
        if not selected:
            continue
        inventory += f"## {title}\n\n"
        rows = []
        for t in selected:
            sources = " ".join(f"[문서 {i + 1}]({url})" for i, url in enumerate(t.get("sources", [])))
            rows.append([f'<a id="{t["id"]}"></a>' + tool_link(t), license_link(t, ev), t["summary"], t["limitations"] + (" " + sources if sources else "")])
        inventory += table(["도구", "라이선스", "주요 기능", "조건과 한계"], rows) + "\n\n"
    inventory += "[라이선스 조회 기록](../data/license-evidence.json)과 [분류 원본](../data/catalog.json)을 함께 볼 수 있다. JSON의 `multi`는 여러 언어를 다룬다는 뜻이며 언어마다 지원 범위는 다를 수 있다. 도구 본체의 라이선스만으로 배포 바이너리, 간접 의존성, 모델 API, DB의 조건까지 확인한 것은 아니다.\n"

    profiles = "<!-- Generated by scripts/catalog.py. -->\n# 스택별 구성 가이드\n\n- [README로 돌아가기](../README.md)\n- [전체 도구 목록](TOOLS.md)\n\n"
    profiles += "Windows 11과 PowerShell 사용을 고려한 구성 안내다. 아래 조합의 설치와 프로젝트 호환성을 직접 시험한 것은 아니다. 기본 검사부터 확인하고 필요한 도구를 더한다. 빌드, 타입 검사, 린트, 테스트의 결과는 각각 기록한다.\n\n"
    for p in data["profiles"]:
        profiles += f'<a id="{p["id"]}"></a>\n## {p["name"]}\n\n'
        profiles += table(["역할", "후보"], [["우선 검토", links(p["base"])], ["추가 또는 대체", links(p["optional"])], ["코드 탐색", links(p["navigation"])]])
        profiles += "\n\n" + p["notes"] + "\n\n"
    profiles += "## 단계별 적용\n\n"
    profiles += table(["단계", "작업", "확인할 결과"], [
        ["1. 현재 상태 기록", "빌드와 테스트 결과, 버전, 작업 디렉터리를 남긴다.", "기존 문제와 새 검사에서 발견한 문제를 구분한다."],
        ["2. 작은 범위에서 검사", "규칙, 대상 파일, 진입점을 설정한다.", "알려진 결함을 찾고 정상적인 동적 참조는 보존한다."],
        ["3. CI 연결", "종료 코드, 예외, 기존 문제 목록인 baseline을 정한다.", "누락, 시간 초과, 일부 파일만 검사한 결과를 통과로 처리하지 않는다."],
        ["4. 구조 검사 추가", "계층, 순환 참조, 의존성 규칙을 정한다.", "규칙을 어긴 변경이 실제로 검사에 실패하는지 확인한다."],
        ["5. 코드 탐색 연결", "필요한 코드 그래프를 만든다.", "탐색 결과와 CI의 합격 판정을 구분한다."]
    ]) + "\n"

    excluded = "<!-- Generated by scripts/catalog.py. -->\n# 추천 제외 이력\n\n- [README로 돌아가기](../README.md)\n- [라이선스 선정 기준](LICENSE-POLICY.md)\n\n"
    excluded += "이 페이지에 있는 도구는 기본 추천에서 제외했다. 상업적 사용이 불법이라는 뜻은 아니다. 제외 이유와 대체 후보를 기록했으며, 대체 도구가 같은 기능이나 탐지 정확도를 보장하지는 않는다.\n\n"
    excluded += table(["도구", "라이선스와 상태", "제외 이유 및 참고 사항", "대체 후보"], [
        [tool_link(t), license_link(t, ev), t["limitations"], links(t["alternatives"]) if t.get("alternatives") else "확인한 대체 도구 없음"]
        for t in tools if t["status"] == "excluded"
    ])
    excluded += "\n\nPeriphery의 과거 MIT 코드나 Serena의 과거 MIT 릴리스, SolidLSP의 사용권이 소급 취소됐다는 뜻은 아니다. 구버전을 계속 관리해야 하는 부담도 고려해 새 프로젝트의 기본 추천에서는 뺐다.\n\n"
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
