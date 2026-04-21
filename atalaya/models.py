"""Dominio de Atalaya: oferta, perfil, candidatura y desglose de score."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


def _utcnow() -> datetime:
    return datetime.now(UTC)


class ApplicationStatus(StrEnum):
    NEW = "new"
    DRAFTED = "drafted"
    APPLIED = "applied"
    REJECTED = "rejected"
    INTERVIEW = "interview"


class Offer(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    id: int | None = None
    source: str
    title: str
    company: str
    location: str
    remote: bool
    stack: list[str] = Field(default_factory=list)
    url: str
    description: str = ""
    posted_at: datetime | None = None
    scraped_at: datetime = Field(default_factory=_utcnow)
    salary_min: int | None = None
    salary_max: int | None = None
    seniority: str | None = None
    raw_html_hash: str = ""


class Profile(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str
    email: str
    stack_core: list[str]
    stack_extra: list[str] = Field(default_factory=list)
    location: str
    seniority: str
    availability: str
    modes: list[str]
    languages: list[str]
    portfolio_url: HttpUrl | None = None
    github_url: HttpUrl | None = None


class Application(BaseModel):
    offer_id: int
    status: ApplicationStatus = ApplicationStatus.NEW
    letter_md: str = ""
    cv_variant_md: str = ""
    applied_at: datetime | None = None
    notes: str = ""


class ScoreBreakdown(BaseModel):
    total: int = Field(ge=0, le=100)
    stack_match: int = Field(ge=0, le=100)
    remote_match: int = Field(ge=0, le=100)
    seniority_match: int = Field(ge=0, le=100)
    language_match: int = Field(ge=0, le=100)
