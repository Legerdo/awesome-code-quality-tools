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
    return errors


def cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def table(headers: list[str], rows: list[list[str]]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    lines.extend("| " + " | ".join(cell(value) for value in row) + " |" for row in rows)
    return "\n".join(lines)


def tool_link(t: dict) -> str:
    url = t.get("homepage") or "https://github.com/" + t["repo"]
    prefix = "[E] " if t["status"] == "engine-exception" else ""
    return f"{prefix}[{t['name']}]({url})"


def license_link(t: dict, evidence: dict) -> str:
    url = evidence.get(t["id"], {}).get("url") or t.get("license_sources", [None])[0]
    return f"[{t['license']}]({url})" if url else t["license"]


def render(data: dict, evidence: list) -> dict[str, str]:
    tools = data["tools"]
    lookup = {t["id"]: t for t in tools}
    ev = {e["id"]: e for e in evidence}
    count = Counter(t["status"] for t in tools)

    def links(ids: list[str]) -> str:
        return " · ".join(tool_link(lookup[i]) for i in ids) or "—"

    def compact(items: list[dict]) -> str:
        return table(["도구", "라이선스 원문", "주요 역할"], [[tool_link(t), license_link(t, ev), t["summary"]] for t in items])

    root_url = "https://github.com/" + data["repository"]
    readme = f"""<!-- Generated by scripts/catalog.py. Edit data/catalog.json instead. -->
# Awesome Code Quality Tools

[![Catalog CI]({root_url}/actions/workflows/catalog.yml/badge.svg)]({root_url}/actions/workflows/catalog.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

**상업용 내부 개발에서 라이선스 검토 부담이 낮은 코드 품질·코드 그래프 도구 모음.**

A permissive-license-first catalog for game engines, apps, web, backend, and AI-assisted code navigation.

**{len(data['profiles'])}개 스택 · 퍼미시브 후보 {count['permissive']}개 · 엔진/SDK 조건부 예외 {count['engine-exception']}개 · 추천 제외 이력 {count['excluded']}개**

자료 기준: **{data['reviewed_on']}**. 도구 실행·정확도·전이 라이선스 전수 감사는 미수행.

## 찾아보기

[스택별 시작 조합](#quick-start) · [범용 코드 그래프](#graphs) · [공통 품질 도구](#common) · [전체 도구 상세표](docs/TOOLS.md) · [스택별 상세](docs/PROFILES.md) · [제외 도구](docs/EXCLUDED.md) · [라이선스 정책](docs/LICENSE-POLICY.md) · [기여 방법](CONTRIBUTING.md)

## 이 목록을 읽는 기준

| 구분 | 답하는 질문 | 대체하지 않는 것 |
| --- | --- | --- |
| 코드 그래프·탐색 | 어떤 심볼·호출·의존 관계가 있는가? | 실제 사용 여부와 변경 안전성의 증명 |
| 품질·의존성·아키텍처 검사 | 정해 둔 규칙을 위반했는가? | 빌드·엔진 에셋·실행 결과 검증 |
| 빌드·테스트·엔진 검사 | 지정한 구성과 입력에서 동작하는가? | 미검사 경로까지의 정확성 보장 |

추천은 **설치 후보**이지 검증된 만능 조합이 아니다. 선택 도구를 전부 설치하기보다 역할별로 하나씩 선정한다.
`[E]`는 해당 엔진/SDK의 조건을 따르는 예외다. 일반 퍼미시브 OSS로 계산하지 않는다.

<a id="quick-start"></a>
## 스택별 시작 조합

"기본"은 시작 예시이며 기존 빌드·테스트를 대체하지 않는다. Knip/Fallow, Pyright/mypy, GUT/gdUnit4는 프로젝트에 맞춰 선택한다.

"""
    readme += table(["스택", "기본 후보", "추가 검사·교체 후보"], [
        [f"[{p['name']}](docs/PROFILES.md#{p['id']})", links(p["base"]), links(p["optional"])] for p in data["profiles"]
    ])
    readme += "\n\nGDScript용 범용 그래프 추천은 비워 두었다. Godot 내장 LSP와 엔진 테스트를 활용하고, C#/GDExtension C++은 해당 언어 도구를 따로 검토한다.\n"
    readme += '\n<a id="graphs"></a>\n## 범용 코드 그래프·AI 탐색\n\n'
    readme += "**CodeGraph는 [colbymchenry/codegraph](https://github.com/colbymchenry/codegraph)를 뜻한다.** CodeGraphContext와 별개다. 설명·추론·시각화와 정적 분석 근거를 구분한다.\n\n"
    readme += compact([t for t in tools if t["category"] == "graph" and t["status"] == "permissive"])
    readme += '\n\n<a id="common"></a>\n## 공통 품질·보안·실행 도구\n\n'
    readme += compact([t for t in tools if t["category"] in {"common", "testing"} and t["status"] == "permissive"])
    readme += "\n\n## 라이선스와 선정 범위\n\n"
    readme += "MIT·Apache-2.0·BSD·ISC 계열을 우선한다. **GPL/LGPL/AGPL은 상업 사용 금지가 아니다.** 여기서는 검토·수정 배포 관리 부담을 줄이기 위해 보수적으로 제외한다. 비상업 제한, 별도 구독, 유지보수 중단 후 상용 전환도 별도 이력으로 남긴다.\n\n"
    readme += "Fallow는 MIT 정적 코어, Gitleaks는 MIT CLI, Graphify는 OSS 패키지만 포함한다. DB·룰팩·플러그인·GitHub Action·호스팅 서비스의 조건은 본체 라이선스와 별개다. 엔진 예외의 실제 패키지 조건도 확인해야 한다.\n\n"
    readme += "자세한 기준과 원문: [라이선스 정책](docs/LICENSE-POLICY.md) · [제외 사유 및 대체 후보](docs/EXCLUDED.md). 제외 이력은 추천 목록이 아니다.\n\n"
    readme += "## 유지보수와 검증\n\n"
    readme += "[data/catalog.json](data/catalog.json)이 표의 원본이다. [라이선스 근거](data/license-evidence.json)에는 조회한 파일 경로·blob SHA·시점이 있다. CI는 허용 라이선스, 제외 도구의 추천 재유입, 언어 범위 불일치, 내부 링크, JSON과 생성 문서의 불일치를 검사한다. 외부 링크의 가용성이나 수록 도구의 성능은 검사하지 않는다.\n\n"
    readme += "```powershell\npython scripts/catalog.py --check\npython -m unittest discover -s tests -v\n```\n\n"
    readme += "문서 수정은 [CONTRIBUTING.md](CONTRIBUTING.md), 실행 검증 기준은 [VERIFICATION.md](docs/VERIFICATION.md)를 따른다. Python 3.13 표준 라이브러리만 사용하며 Windows/Ubuntu CI에서 검사한다.\n\n"
    readme += "## 라이선스\n\n이 저장소의 큐레이션 문서·데이터·검사 스크립트는 [MIT](LICENSE)다. 링크한 프로젝트는 각자의 라이선스를 유지한다. 이 목록은 법률 자문이나 특정 배포물의 라이선스 적합성 인증이 아니다.\n"

    inventory = "<!-- Generated by scripts/catalog.py. -->\n# 전체 도구 상세표\n\n[README로 돌아가기](../README.md) · [라이선스 정책](LICENSE-POLICY.md) · [추천 제외 이력](EXCLUDED.md)\n\n"
    inventory += "**문서 기반 후보 목록. 실행·성능·오탐률 미검증.** `multi`는 여러 언어를 다룬다는 뜻이며 모든 언어의 동일한 지원을 보장하지 않는다. `[E]`는 엔진/SDK 종속 예외다. 라이선스 셀은 확인한 상위 원문으로 연결한다.\n\n"
    for group, title in data["categories"].items():
        selected = [t for t in tools if t["category"] == group and t["status"] != "excluded"]
        if not selected:
            continue
        inventory += f"## {title}\n\n"
        rows = []
        for t in selected:
            sources = " ".join(f"[문서 {i + 1}]({url})" for i, url in enumerate(t.get("sources", [])))
            rows.append([f'<a id="{t["id"]}"></a>' + tool_link(t), license_link(t, ev), t["summary"], t["limitations"] + (" " + sources if sources else "")])
        inventory += table(["도구", "상위 라이선스·원문", "주요 기능", "범위·도입 조건"], rows) + "\n\n"
    inventory += "라이선스 원문 조회 기록은 [license-evidence.json](../data/license-evidence.json), 분류 원본은 [catalog.json](../data/catalog.json)에 있다. 메인 라이선스만으로 바이너리·전이 의존성·모델 API·DB까지 허용됐다고 판단하지 않는다.\n"

    profiles = "<!-- Generated by scripts/catalog.py. -->\n# 스택별 구성 가이드\n\n[README로 돌아가기](../README.md) · [전체 도구](TOOLS.md)\n\n"
    profiles += "Windows 11 + PowerShell을 기본 작업 환경으로 고려한다. 이 문서는 특정 버전의 설치 스크립트가 아니다. 빌드·타입 검사·린트·테스트 상태를 각각 기록하고, 선택 도구는 중복 역할과 프로젝트 호환성을 확인한 뒤 추가한다.\n\n"
    for p in data["profiles"]:
        profiles += f'<a id="{p["id"]}"></a>\n## {p["name"]}\n\n'
        profiles += table(["역할", "후보"], [["기본", links(p["base"])], ["선택·교체", links(p["optional"])], ["탐색·그래프", links(p["navigation"])]])
        profiles += "\n\n" + p["notes"] + "\n\n"
    profiles += "## 단계별 적용\n\n"
    profiles += table(["단계", "작업", "확인할 결과"], [
        ["1. 기존 기준 확보", "현재 빌드·테스트와 버전·작업 디렉터리 기록", "기존 실패와 새 검사 실패 구분"],
        ["2. 검사기 하나 도입", "기본 규칙·범위·진입점 설정", "알려진 결함을 잡고 정상 동적 경로는 보존"],
        ["3. CI 연결", "도구별 종료 코드·예외·baseline 명시", "누락·timeout·partial을 PASS로 처리하지 않음"],
        ["4. 구조 검사 추가", "계층·순환·의존성 정책 정의", "규칙 위반을 재현 가능한 실패로 판정"],
        ["5. 탐색 도구 추가", "필요한 그래프만 인덱싱", "탐색 결과와 품질 게이트의 책임 분리"]
    ]) + "\n"

    excluded = "<!-- Generated by scripts/catalog.py. -->\n# 추천 제외 이력\n\n[README로 돌아가기](../README.md) · [선정 정책](LICENSE-POLICY.md)\n\n"
    excluded += "여기의 항목은 **설치 추천이 아니다.** 상업 사용이 불법이라는 판정도 아니다. 보수적인 라이선스·유지보수 정책에 따른 제외 이유와 기능 공백을 기록한다. 대체 후보가 동일한 탐지 기능·정확도를 보장하지는 않는다.\n\n"
    excluded += table(["도구", "라이선스·상태", "제외 이유·주의", "대체 후보"], [
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
