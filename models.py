from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


class ExtractedMetadata(BaseModel):
    document_type: str = "document"
    issuer: str | None = None
    amount: float | None = None
    currency: str | None = None
    document_date: date | None = None
    deadline: date | None = None
    reference: str | None = None
    confidence: float = Field(default=0.5, ge=0, le=1)
    language: str | None = None
    nip: str | None = None
    iban: str | None = None
    invoice_number: str | None = None
    vat_rate: str | None = None
    net_amount: float | None = None
    gross_amount: float | None = None
    warranty_until: date | None = None
    notice_period: str | None = None
    auto_renewal: bool = False


class FileAnalysis(BaseModel):
    source_name: str
    source_path: str
    sha256: str
    size_bytes: int
    extracted_text: str = ""
    metadata: ExtractedMetadata
    suggested_category: str
    suggested_filename: str
    tags: list[str] = []
    suggested_case: str | None = None
    action_required: str | None = None
    smart_structure: bool = True
    health_score: int = 100
    health_notes: list[str] = []
    sensitive: list[dict[str, str]] = []
    simhash: str | None = None
    warnings: list[str] = []


class ApplyRequest(BaseModel):
    source_path: str
    category: str
    filename: str
    mode: Literal["rename", "organize"] = "rename"
    profile: str = "Home"
    case_name: str | None = None
    action_required: str | None = None
    smart_structure: bool = True


class AppliedChange(BaseModel):
    id: str
    created_at: datetime
    action: Literal["rename", "move"] = "move"
    source: str
    destination: str
    verified: bool = True


class UndoResult(BaseModel):
    id: str
    restored_to: str
