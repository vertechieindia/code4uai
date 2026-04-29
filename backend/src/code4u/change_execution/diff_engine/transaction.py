from __future__ import annotations
"""Transactional diff management for code4u.ai."""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional
import uuid

class DiffStatus(str, Enum):
    PENDING = "pending"
    APPLIED = "applied"
    REJECTED = "rejected"
    ROLLED_BACK = "rolled_back"

@dataclass
class FileDiff:
    file_path: str
    original_content: str
    new_content: str
    unified_diff: str
    status: DiffStatus = DiffStatus.PENDING

@dataclass
class DiffTransaction:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)
    diffs: list[FileDiff] = field(default_factory=list)
    status: DiffStatus = DiffStatus.PENDING
    metadata: Dict[str, Any] = field(default_factory=dict)

class TransactionManager:
    def __init__(self):
        self._transactions: dict[str, DiffTransaction] = {}
        self._active: Optional[str] = None
    
    def create(self, session_id: str) -> DiffTransaction:
        tx = DiffTransaction(session_id=session_id)
        self._transactions[tx.id] = tx
        self._active = tx.id
        return tx
    
    def get_active(self) -> DiffTransaction | None:
        return self._transactions.get(self._active) if self._active else None
    
    def add_diff(self, tx_id: str, file_path: str, original: str, new: str, diff: str) -> None:
        tx = self._transactions.get(tx_id)
        if tx: tx.diffs.append(FileDiff(file_path=file_path, original_content=original, new_content=new, unified_diff=diff))
    
    async def apply(self, tx_id: str) -> tuple[bool, List[str]]:
        tx = self._transactions.get(tx_id)
        if not tx: return False, ["Transaction not found"]
        errors = []
        for diff in tx.diffs:
            try:
                Path(diff.file_path).write_text(diff.new_content)
                diff.status = DiffStatus.APPLIED
            except Exception as e:
                errors.append(f"{diff.file_path}: {e}")
                diff.status = DiffStatus.ROLLED_BACK
        tx.status = DiffStatus.APPLIED if not errors else DiffStatus.ROLLED_BACK
        return not errors, errors
    
    async def rollback(self, tx_id: str) -> tuple[bool, List[str]]:
        tx = self._transactions.get(tx_id)
        if not tx: return False, ["Transaction not found"]
        errors = []
        for diff in reversed(tx.diffs):
            if diff.status == DiffStatus.APPLIED:
                try:
                    Path(diff.file_path).write_text(diff.original_content)
                    diff.status = DiffStatus.ROLLED_BACK
                except Exception as e:
                    errors.append(f"{diff.file_path}: {e}")
        tx.status = DiffStatus.ROLLED_BACK
        return not errors, errors

