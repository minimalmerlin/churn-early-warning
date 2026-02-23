"""
API-Response-Schemas für den FastAPI-Layer.
Warum eigene Schemas: Domain-Modelle (dataclasses, frozen) sind nicht direkt
JSON-serialisierbar. Die API-Schemas sind die explizite Grenze zwischen
interner Business Logic und externem HTTP-Contract.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class ReasonCodeResponse(BaseModel):
    code: str
    label: str
    impact_score: float
    direction: str


class ActionItemResponse(BaseModel):
    priority: int
    action: str
    title: str
    description: str
    recommended_owner: str
    suggested_timeline_days: int
    triggered_by: str


class KpiImpactResponse(BaseModel):
    arr_at_risk: float
    estimated_retention_probability: float
    expected_arr_saved: float
    churn_probability_without_action: float
    payback_period_days: Optional[int]


class PlaybookResponse(BaseModel):
    account_id: str
    account_name: str
    risk_score: float
    risk_level: str
    segment: str
    summary: str
    action_items: list[ActionItemResponse]
    kpi_impact: Optional[KpiImpactResponse]


class RankedAccountResponse(BaseModel):
    rank: int
    account_id: str
    account_name: str
    risk_score: float
    risk_level: str
    segment: str
    arr_at_risk: float
    top_reason: str
    days_to_renewal: Optional[int]


class SummaryStats(BaseModel):
    total_analyzed: int
    total_arr_at_risk: float
    critical_count: int
    high_count: int
    medium_count: int
    run_date: str


class AnalyzeResponse(BaseModel):
    """
    Vollständige API-Antwort auf POST /api/analyze.

    Enthält alle Daten, die das Frontend benötigt – in einem einzigen Call.
    Warum: Vermeidet mehrere Round-Trips und vereinfacht den Frontend-Code.
    """
    summary: SummaryStats
    ranked_accounts: list[RankedAccountResponse]
    playbooks: list[PlaybookResponse]


class ErrorResponse(BaseModel):
    """Standardisierte Fehlerantwort für alle API-Fehler."""
    error: str
    detail: str
