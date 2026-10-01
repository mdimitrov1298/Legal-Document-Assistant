"""JSON-backed case and document metadata with uploads on local disk.

Case lifecycle (`status`):
    empty -(upload)-> uploaded -(ingest)-> ingested -(upload/delete doc)-> stale
    stale -(ingest)-> ingested; deleting the last document -> empty.
"""

from __future__ import annotations

import copy
import hashlib
import json
import logging
import os
import shutil
import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock
from typing import Any

from app.core.config import Settings, get_settings
from app.core.errors import CaseNotFoundError, DocumentNotFoundError

logger = logging.getLogger(__name__)

STATUS_EMPTY = "empty"
STATUS_UPLOADED = "uploaded"
STATUS_INGESTED = "ingested"
STATUS_STALE = "stale"

_UNSET: Any = object()


def _now() -> str:
    return datetime.now(UTC).isoformat()


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _normalise_case(case: dict) -> dict:
    """Fill fields missing from index files written by older versions."""
    docs = case.setdefault("documents", [])
    case.setdefault("description", None)
    case.setdefault("updated_at", case.get("created_at") or _now())
    case.setdefault("chunk_count", 0)
    case.setdefault("ingested_at", None)
    if "status" not in case:
        if not docs:
            case["status"] = STATUS_EMPTY
        elif case.get("ingested"):
            case["status"] = STATUS_INGESTED
        else:
            case["status"] = STATUS_UPLOADED
    case.pop("ingested", None)
    for doc in docs:
        doc.setdefault("sha256", None)
    return case


class CaseStore:
    """Thread-safe case index persisted atomically to `cases_index.json`."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._lock = RLock()
        self.root = Path(self.settings.data_dir)
        self.upload_dir = Path(self.settings.upload_dir)
        self.root.mkdir(parents=True, exist_ok=True)
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self._meta_path = self.root / "cases_index.json"
        self._cases: dict[str, dict] = self._load()

    def _load(self) -> dict[str, dict]:
        if not self._meta_path.exists():
            return {}
        raw = json.loads(self._meta_path.read_text(encoding="utf-8"))
        return {cid: _normalise_case(case) for cid, case in raw.items()}

    def _save(self) -> None:
        """Write to a temp file in the same directory, then atomically replace."""
        self.root.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(
            prefix=".cases_index.", suffix=".tmp", dir=str(self.root)
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(self._cases, fh, indent=2, ensure_ascii=False, default=str)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp, self._meta_path)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise

    def _case(self, case_id: str) -> dict:
        case = self._cases.get(case_id)
        if case is None:
            raise CaseNotFoundError(details={"case_id": case_id})
        return case

    # Cases

    def create_case(self, title: str, description: str | None = None) -> dict:
        with self._lock:
            now = _now()
            case = {
                "id": str(uuid.uuid4()),
                "title": title,
                "description": description,
                "created_at": now,
                "updated_at": now,
                "documents": [],
                "status": STATUS_EMPTY,
                "chunk_count": 0,
                "ingested_at": None,
            }
            self._cases[case["id"]] = case
            self._save()
            return copy.deepcopy(case)

    def get_case(self, case_id: str) -> dict | None:
        with self._lock:
            case = self._cases.get(case_id)
            return copy.deepcopy(case) if case is not None else None

    def require_case(self, case_id: str) -> dict:
        with self._lock:
            return copy.deepcopy(self._case(case_id))

    def list_cases(self, skip: int = 0, limit: int | None = None) -> list[dict]:
        with self._lock:
            cases = sorted(
                self._cases.values(), key=lambda c: c["created_at"], reverse=True
            )
            end = None if limit is None else skip + limit
            return copy.deepcopy(cases[skip:end])

    def update_case(
        self, case_id: str, *, title: str | None = None, description: Any = _UNSET
    ) -> dict:
        with self._lock:
            case = self._case(case_id)
            if title is not None:
                case["title"] = title
            if description is not _UNSET:
                case["description"] = description
            case["updated_at"] = _now()
            self._save()
            return copy.deepcopy(case)

    def delete_case(self, case_id: str) -> None:
        with self._lock:
            self._case(case_id)
            del self._cases[case_id]
            self._save()
        shutil.rmtree(self.upload_dir / case_id, ignore_errors=True)

    # Documents

    def add_document(
        self, case_id: str, filename: str, content_type: str, data: bytes
    ) -> dict:
        with self._lock:
            case = self._case(case_id)
            doc_id = str(uuid.uuid4())
            dest_dir = self.upload_dir / case_id
            dest_dir.mkdir(parents=True, exist_ok=True)
            # Keep the original extension so extraction can detect the type
            safe_name = Path(filename.replace("\\", "/")).name or "upload.bin"
            dest = dest_dir / f"{doc_id}_{safe_name}"
            dest.write_bytes(data)
            now = _now()
            doc = {
                "id": doc_id,
                "case_id": case_id,
                "filename": safe_name,
                "content_type": content_type,
                "size_bytes": len(data),
                "sha256": sha256_hex(data),
                "path": str(dest),
                "uploaded_at": now,
            }
            case["documents"].append(doc)
            if case["status"] in (STATUS_INGESTED, STATUS_STALE):
                case["status"] = STATUS_STALE
            else:
                case["status"] = STATUS_UPLOADED
            case["updated_at"] = now
            self._save()
            return copy.deepcopy(doc)

    def list_documents(self, case_id: str) -> list[dict]:
        with self._lock:
            return copy.deepcopy(self._case(case_id)["documents"])

    def require_document(self, case_id: str, document_id: str) -> dict:
        with self._lock:
            for doc in self._case(case_id)["documents"]:
                if doc["id"] == document_id:
                    return copy.deepcopy(doc)
        raise DocumentNotFoundError(
            details={"case_id": case_id, "document_id": document_id}
        )

    def delete_document(
        self, case_id: str, document_id: str, *, remaining_chunks: int | None = None
    ) -> dict:
        """Remove a document; returns the updated case."""
        with self._lock:
            case = self._case(case_id)
            doc = next((d for d in case["documents"] if d["id"] == document_id), None)
            if doc is None:
                raise DocumentNotFoundError(
                    details={"case_id": case_id, "document_id": document_id}
                )
            case["documents"].remove(doc)
            if not case["documents"]:
                case["status"] = STATUS_EMPTY
                case["chunk_count"] = 0
                case["ingested_at"] = None
            elif case["status"] in (STATUS_INGESTED, STATUS_STALE):
                case["status"] = STATUS_STALE
                if remaining_chunks is not None:
                    case["chunk_count"] = remaining_chunks
            case["updated_at"] = _now()
            self._save()
        Path(doc["path"]).unlink(missing_ok=True)
        return copy.deepcopy(case)

    def mark_ingested(
        self,
        case_id: str,
        chunk_count: int,
        *,
        embedding_backend: str | None = None,
        embedding_model: str | None = None,
    ) -> dict:
        with self._lock:
            case = self._case(case_id)
            now = _now()
            case["status"] = STATUS_INGESTED
            case["chunk_count"] = chunk_count
            case["ingested_at"] = now
            case["embedding_backend"] = embedding_backend
            case["embedding_model"] = embedding_model
            case["updated_at"] = now
            self._save()
            return copy.deepcopy(case)


_store: CaseStore | None = None


def get_store() -> CaseStore:
    global _store
    if _store is None:
        _store = CaseStore()
    return _store


def reset_store(store: CaseStore | None = None) -> None:
    global _store
    _store = store
