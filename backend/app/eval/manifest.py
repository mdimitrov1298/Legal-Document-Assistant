"""Load and validate an evaluation package (manifest, passages, claims)."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

GOLD_LABELS = ("SUPPORTED", "REFUTED", "NEI")
VERDICT_TO_LABEL = {
    "supported": "SUPPORTED",
    "denied": "REFUTED",
    "inconclusive": "NEI",
}


class ManifestError(ValueError):
    """The package is malformed or fails integrity checks."""

    def __init__(self, problems: list[str]) -> None:
        self.problems = problems
        super().__init__("; ".join(problems))


@dataclass(frozen=True)
class Evidence:
    passage_id: str
    char_span: tuple[int, int]
    quote: str


@dataclass(frozen=True)
class Claim:
    claim_id: str
    passage_id: str
    scenario: str | None
    language: str
    claim_text: str
    gold_label: str
    gold_evidence: tuple[Evidence, ...]
    trap_type: str | None = None
    annotator_notes: str | None = None


@dataclass(frozen=True)
class Passage:
    id: str
    status: str
    path: str | None
    language: str
    file_hash: str | None
    companion_passages: tuple[str, ...] = ()
    scenarios: tuple[str, ...] = ()
    tasks: tuple[str, ...] = ()
    raw: dict[str, Any] = field(default_factory=dict, compare=False)

    @property
    def is_pending(self) -> bool:
        return self.status == "pending" or not self.path


@dataclass
class Package:
    root: Path
    manifest: dict[str, Any]
    passages: dict[str, Passage]
    claims: list[Claim]

    @property
    def name(self) -> str:
        return str(self.manifest.get("name") or self.root.name)

    @property
    def version(self) -> str:
        return str(self.manifest.get("version", ""))

    @property
    def status(self) -> str:
        return str(self.manifest.get("status", ""))

    def passage_path(self, passage_id: str) -> Path:
        passage = self.passages[passage_id]
        if passage.is_pending:
            raise ManifestError([f"passage {passage_id} is pending and has no file"])
        return self.root / str(passage.path)

    def read_passage(self, passage_id: str) -> str:
        return self.passage_path(passage_id).read_bytes().decode("utf-8")

    def runnable_passages(self) -> list[Passage]:
        return [p for p in self.passages.values() if not p.is_pending]

    def claims_for(self, passage_id: str) -> list[Claim]:
        return [c for c in self.claims if c.passage_id == passage_id]

    def manifest_sha256(self) -> str:
        raw = (self.root / "manifest.json").read_bytes()
        return "sha256:" + hashlib.sha256(raw).hexdigest()


def file_sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _parse_claim(obj: dict[str, Any]) -> Claim:
    evidence = tuple(
        Evidence(
            passage_id=str(e.get("passage_id") or obj["passage_id"]),
            char_span=(int(e["char_span"][0]), int(e["char_span"][1])),
            quote=str(e["quote"]),
        )
        for e in obj.get("gold_evidence") or []
    )
    return Claim(
        claim_id=str(obj["claim_id"]),
        passage_id=str(obj["passage_id"]),
        scenario=obj.get("scenario"),
        language=str(obj.get("language", "bg")),
        claim_text=str(obj["claim_text"]),
        gold_label=str(obj["gold_label"]),
        gold_evidence=evidence,
        trap_type=obj.get("trap_type"),
        annotator_notes=obj.get("annotator_notes"),
    )


def load_package(root: str | Path, *, validate: bool = True) -> Package:
    root = Path(root).resolve()
    manifest_path = root / "manifest.json"
    if not manifest_path.is_file():
        raise ManifestError([f"manifest.json not found in {root}"])
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    passages: dict[str, Passage] = {}
    for p in manifest.get("passages") or []:
        passages[p["id"]] = Passage(
            id=p["id"],
            status=str(p.get("status", "draft")),
            path=p.get("path"),
            language=str(p.get("language", "bg")),
            file_hash=p.get("file_hash"),
            companion_passages=tuple(p.get("companion_passages") or ()),
            scenarios=tuple(p.get("scenarios") or ()),
            tasks=tuple(p.get("tasks") or ()),
            raw=p,
        )

    claims_path = root / manifest.get("claims_file", "claims/claims.jsonl")
    claims: list[Claim] = []
    if claims_path.is_file():
        for n, line in enumerate(claims_path.read_text("utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                claims.append(_parse_claim(json.loads(line)))
            except (KeyError, ValueError, TypeError) as exc:
                raise ManifestError([f"{claims_path.name}:{n}: {exc}"]) from exc

    package = Package(root=root, manifest=manifest, passages=passages, claims=claims)
    if validate:
        problems = validate_package(package)
        if problems:
            raise ManifestError(problems)
    return package


def validate_package(package: Package) -> list[str]:
    """Return a list of integrity problems (empty when the package is valid)."""
    problems: list[str] = []
    texts: dict[str, str] = {}

    for pid, passage in package.passages.items():
        if passage.is_pending:
            continue
        path = package.root / str(passage.path)
        if not path.is_file():
            problems.append(f"{pid}: file {passage.path} is missing")
            continue
        actual = file_sha256(path)
        if passage.file_hash != actual:
            problems.append(f"{pid}: file_hash {passage.file_hash} != {actual}")
        texts[pid] = path.read_bytes().decode("utf-8")
        for companion in passage.companion_passages:
            if companion not in package.passages:
                problems.append(f"{pid}: unknown companion passage {companion}")

    seen: set[str] = set()
    for claim in package.claims:
        cid = claim.claim_id
        if cid in seen:
            problems.append(f"{cid}: duplicate claim_id")
        seen.add(cid)
        if claim.gold_label not in GOLD_LABELS:
            problems.append(f"{cid}: invalid gold_label {claim.gold_label}")
        passage = package.passages.get(claim.passage_id)
        if passage is None or passage.is_pending:
            problems.append(f"{cid}: passage {claim.passage_id} is missing or pending")
        if claim.gold_label == "NEI" and claim.gold_evidence:
            problems.append(f"{cid}: NEI claims must not have gold evidence")
        if claim.gold_label != "NEI" and not claim.gold_evidence:
            problems.append(f"{cid}: {claim.gold_label} claim needs gold evidence")
        for ev in claim.gold_evidence:
            text = texts.get(ev.passage_id)
            if text is None:
                problems.append(f"{cid}: evidence passage {ev.passage_id} unavailable")
                continue
            start, end = ev.char_span
            if ev.quote not in text:
                problems.append(f"{cid}: quote is not a substring of {ev.passage_id}")
            elif text[start:end] != ev.quote:
                problems.append(f"{cid}: char_span {ev.char_span} does not match quote")
    return problems
