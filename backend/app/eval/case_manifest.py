"""Load and validate a case-level evaluation package (eval-cases-v0.1 format).

Unlike the passage-level manifest (manifest.py), each entry is a complete
case with multiple documents, claims and questions.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class CaseManifestError(ValueError):
    """The case package is malformed or fails integrity checks."""

    def __init__(self, problems: list[str]) -> None:
        self.problems = problems
        super().__init__("; ".join(problems))


@dataclass(frozen=True)
class CaseEvidence:
    document: str
    char_span: tuple[int, int]
    quote: str


@dataclass(frozen=True)
class CaseClaim:
    claim_id: str
    claim_text: str
    gold_label: str
    gold_evidence: tuple[CaseEvidence, ...]
    scenario: str | None = None
    trap_type: str | None = None


@dataclass(frozen=True)
class CaseQuestion:
    q_id: str
    question: str
    gold_answer: str
    answer_type: str
    gold_evidence: tuple[CaseEvidence, ...]


@dataclass(frozen=True)
class CaseDocument:
    filename: str
    path: str
    format: str
    file_hash: str
    word_count_approx: int | None = None


@dataclass
class EvalCase:
    case_id: str
    language: str
    source: str
    documents: list[CaseDocument]
    claims: list[CaseClaim]
    questions: list[CaseQuestion]
    gold_summary: str
    raw: dict[str, Any] = field(default_factory=dict, compare=False)


@dataclass
class CasePackage:
    root: Path
    manifest: dict[str, Any]
    cases: list[EvalCase]

    @property
    def name(self) -> str:
        return str(self.manifest.get("name") or self.root.name)

    @property
    def version(self) -> str:
        return str(self.manifest.get("version", ""))

    @property
    def status(self) -> str:
        return str(self.manifest.get("status", ""))

    def manifest_sha256(self) -> str:
        raw = (self.root / "manifest.json").read_bytes()
        return "sha256:" + hashlib.sha256(raw).hexdigest()


GOLD_LABELS = ("SUPPORTED", "REFUTED", "NEI")


def _file_sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _parse_evidence(items: list[dict[str, Any]]) -> tuple[CaseEvidence, ...]:
    return tuple(
        CaseEvidence(
            document=str(e["document"]),
            char_span=(int(e["char_span"][0]), int(e["char_span"][1])),
            quote=str(e["quote"]),
        )
        for e in items
    )


def _parse_claims(path: Path) -> list[CaseClaim]:
    claims: list[CaseClaim] = []
    for n, line in enumerate(path.read_text("utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
            claims.append(
                CaseClaim(
                    claim_id=str(obj["claim_id"]),
                    claim_text=str(obj["claim_text"]),
                    gold_label=str(obj["gold_label"]),
                    gold_evidence=_parse_evidence(obj.get("gold_evidence") or []),
                    scenario=obj.get("scenario"),
                    trap_type=obj.get("trap_type"),
                )
            )
        except (KeyError, ValueError, TypeError) as exc:
            raise CaseManifestError([f"{path.name}:{n}: {exc}"]) from exc
    return claims


def _parse_questions(path: Path) -> list[CaseQuestion]:
    questions: list[CaseQuestion] = []
    for n, line in enumerate(path.read_text("utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
            questions.append(
                CaseQuestion(
                    q_id=str(obj["q_id"]),
                    question=str(obj["question"]),
                    gold_answer=str(obj["gold_answer"]),
                    answer_type=str(obj["answer_type"]),
                    gold_evidence=_parse_evidence(obj.get("gold_evidence") or []),
                )
            )
        except (KeyError, ValueError, TypeError) as exc:
            raise CaseManifestError([f"{path.name}:{n}: {exc}"]) from exc
    return questions


def load_case_package(root: str | Path, *, validate: bool = True) -> CasePackage:
    """Load a case-level evaluation package from *root*."""
    root = Path(root).resolve()
    manifest_path = root / "manifest.json"
    if not manifest_path.is_file():
        raise CaseManifestError([f"manifest.json not found in {root}"])
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    cases: list[EvalCase] = []
    for c in manifest.get("cases") or []:
        documents = [
            CaseDocument(
                filename=d["filename"],
                path=d["path"],
                format=d.get("format", "txt"),
                file_hash=d.get("file_hash", ""),
                word_count_approx=d.get("word_count_approx"),
            )
            for d in c.get("documents") or []
        ]
        claims_path = root / c["claims_file"]
        questions_path = root / c["questions_file"]
        gold_summary_path = root / c["gold_summary_file"]

        claims = _parse_claims(claims_path) if claims_path.is_file() else []
        questions = _parse_questions(questions_path) if questions_path.is_file() else []
        gold_summary = (
            gold_summary_path.read_text("utf-8").strip()
            if gold_summary_path.is_file()
            else ""
        )

        cases.append(
            EvalCase(
                case_id=c["case_id"],
                language=str(c.get("language", "bg")),
                source=str(c.get("source", "")),
                documents=documents,
                claims=claims,
                questions=questions,
                gold_summary=gold_summary,
                raw=c,
            )
        )

    package = CasePackage(root=root, manifest=manifest, cases=cases)
    if validate:
        problems = validate_case_package(package)
        if problems:
            raise CaseManifestError(problems)
    return package


def validate_case_package(package: CasePackage) -> list[str]:
    """Return integrity problems (empty list means valid)."""
    problems: list[str] = []
    seen_case_ids: set[str] = set()

    for case in package.cases:
        if case.case_id in seen_case_ids:
            problems.append(f"{case.case_id}: duplicate case_id")
        seen_case_ids.add(case.case_id)

        doc_texts: dict[str, str] = {}
        for doc in case.documents:
            full_path = package.root / doc.path
            if not full_path.is_file():
                problems.append(f"{case.case_id}/{doc.filename}: file missing")
                continue
            if doc.file_hash:
                actual = _file_sha256(full_path)
                if actual != doc.file_hash:
                    problems.append(
                        f"{case.case_id}/{doc.filename}: hash mismatch "
                        f"{doc.file_hash} != {actual}"
                    )
            if doc.format == "txt":
                doc_texts[doc.filename] = full_path.read_text("utf-8")

        seen_claims: set[str] = set()
        for claim in case.claims:
            if claim.claim_id in seen_claims:
                problems.append(f"{case.case_id}/{claim.claim_id}: duplicate")
            seen_claims.add(claim.claim_id)
            if claim.gold_label not in GOLD_LABELS:
                problems.append(
                    f"{case.case_id}/{claim.claim_id}: invalid label {claim.gold_label}"
                )
            if claim.gold_label == "NEI" and claim.gold_evidence:
                problems.append(f"{case.case_id}/{claim.claim_id}: NEI with evidence")
            if claim.gold_label != "NEI" and not claim.gold_evidence:
                problems.append(
                    f"{case.case_id}/{claim.claim_id}: {claim.gold_label} "
                    f"needs evidence"
                )
            for ev in claim.gold_evidence:
                text = doc_texts.get(ev.document)
                if text is None:
                    continue
                start, end = ev.char_span
                if ev.quote not in text:
                    problems.append(
                        f"{case.case_id}/{claim.claim_id}: quote not in {ev.document}"
                    )
                elif text[start:end] != ev.quote:
                    problems.append(
                        f"{case.case_id}/{claim.claim_id}: char_span mismatch"
                    )

        seen_qs: set[str] = set()
        for q in case.questions:
            if q.q_id in seen_qs:
                problems.append(f"{case.case_id}/{q.q_id}: duplicate")
            seen_qs.add(q.q_id)
            for ev in q.gold_evidence:
                text = doc_texts.get(ev.document)
                if text is None:
                    continue
                start, end = ev.char_span
                if ev.quote not in text:
                    problems.append(
                        f"{case.case_id}/{q.q_id}: quote not in {ev.document}"
                    )
                elif text[start:end] != ev.quote:
                    problems.append(f"{case.case_id}/{q.q_id}: char_span mismatch")

    return problems
