"""
Output-Modelle für das Playbook (Action Templates + KPI Impact).
Warum: Klar typisierte Playbook-Ausgaben ermöglichen automatische
Weiterverarbeitung (z.B. CRM-Integration, Slack-Alerts).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class PlaybookAction(str, Enum):
    """
    Katalog aller verfügbaren Interventions-Actions.
    Warum Enum: Verhindert Tippfehler und ermöglicht typsichere
    Filterung im CRM/Notification-Layer.
    """
    EXECUTIVE_SPONSOR_OUTREACH = "EXECUTIVE_SPONSOR_OUTREACH"
    CS_DEEP_DIVE_CALL = "CS_DEEP_DIVE_CALL"
    FEATURE_ADOPTION_CAMPAIGN = "FEATURE_ADOPTION_CAMPAIGN"
    NPS_RECOVERY_PROGRAM = "NPS_RECOVERY_PROGRAM"
    CONTRACT_RENEWAL_NEGOTIATION = "CONTRACT_RENEWAL_NEGOTIATION"
    TECHNICAL_HEALTH_CHECK = "TECHNICAL_HEALTH_CHECK"
    EXECUTIVE_BUSINESS_REVIEW = "EXECUTIVE_BUSINESS_REVIEW"
    PROACTIVE_SUPPORT_REVIEW = "PROACTIVE_SUPPORT_REVIEW"


@dataclass(frozen=True)
class ActionItem:
    """
    Konkrete Handlungsanweisung mit Owner und Deadline-Empfehlung.

    Input:  PlaybookAction + Reason Code
    Output: Strukturierte Handlungsanweisung für CS-Team
    """
    action: PlaybookAction
    priority: int                    # 1 = höchste Priorität
    title: str
    description: str
    recommended_owner: str           # z.B. "CSM", "Account Executive", "VP Customer Success"
    suggested_timeline_days: int     # Empfohlene Bearbeitungszeit in Tagen
    triggered_by: str                # Welcher Reason Code löst diese Action aus


@dataclass(frozen=True)
class KpiImpact:
    """
    Geschätzter Business Impact bei Inaktivität vs. Intervention.

    Warum: Ohne monetäre Quantifizierung fehlt der Urgency-Driver
    für das Management – Retention "fühlt sich" weniger wichtig an.
    """
    arr_at_risk: float                      # Potenzieller ARR-Verlust (Euro)
    estimated_retention_probability: float  # Wahrscheinlichkeit der Retention bei Intervention (0-1)
    expected_arr_saved: float               # Erwarteter ARR-Save = arr_at_risk * retention_prob
    churn_probability_without_action: float # Baseline-Churn-Prob ohne Eingriff (0-1)
    payback_period_days: Optional[int]      # Geschätzte Amortisierungszeit der Intervention


@dataclass(frozen=True)
class Playbook:
    """
    Vollständiges Playbook für einen at-risk Account.

    Input:  RiskAssessment
    Output: Priorisierte Action Items + KPI Impact für Management-Report
    """
    account_id: str
    account_name: str
    risk_score: float
    risk_level: str
    segment: str
    action_items: tuple[ActionItem, ...] = field(default_factory=tuple)
    kpi_impact: Optional[KpiImpact] = None
    summary: str = ""                       # Einzeiler für Executive Summary / Slack-Alert
