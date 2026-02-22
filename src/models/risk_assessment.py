"""
Output-Modelle für Risk Assessment und Reason Codes.
Warum: Typisierte Output-Strukturen erzwingen Konsistenz zwischen
Processing-Layer und Output-Layer (Data Contract).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class RiskLevel(str, Enum):
    """Kategorisierung des Churn-Risikos für schnelle Triage."""
    CRITICAL = "CRITICAL"   # Score >= 75
    HIGH = "HIGH"           # Score >= 50
    MEDIUM = "MEDIUM"       # Score >= 25
    LOW = "LOW"             # Score < 25


class CustomerSegment(str, Enum):
    """Kundensegment beeinflusst Playbook-Auswahl und KPI-Gewichtung."""
    HIGH_VALUE = "HIGH_VALUE"
    MID_MARKET = "MID_MARKET"
    SMB = "SMB"


@dataclass(frozen=True)
class ReasonCode:
    """
    Erklärender Grund für den Risk Score (Explainability Gate).

    Warum frozen: Reason Codes sind faktenbasierte Aussagen über
    einen Zeitpunkt – sie dürfen nicht nachträglich mutiert werden.
    """
    code: str               # Maschinenlesbarer Code, z.B. "LOGIN_DROP_CRITICAL"
    label: str              # Menschenlesbares Label (Deutsch)
    impact_score: float     # Beitrag zum Gesamt-Score (0.0 – 100.0)
    direction: str          # "negative" | "positive"


@dataclass(frozen=True)
class RiskAssessment:
    """
    Vollständiges Risk-Assessment-Ergebnis für einen Account.

    Input:  Berechnete Features eines CustomerEvent
    Output: Score, Level, Segment, Reason Codes, ARR-at-Risk
    """
    account_id: str
    account_name: str
    risk_score: float               # 0.0 (kein Risiko) bis 100.0 (maximales Risiko)
    risk_level: RiskLevel
    segment: CustomerSegment
    reason_codes: tuple[ReasonCode, ...] = field(default_factory=tuple)
    arr_at_risk: float = 0.0        # Geschätzter ARR-Verlust in Euro
    days_to_contract_end: Optional[int] = None
    confidence: float = 0.0         # Modell-Konfidenz (0.0 – 1.0)

    def __post_init__(self) -> None:
        """Post-Condition Check: Score und Konfidenz müssen in validen Ranges liegen."""
        if not (0.0 <= self.risk_score <= 100.0):
            raise ValueError(f"risk_score muss zwischen 0 und 100 liegen, ist: {self.risk_score}")
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError(f"confidence muss zwischen 0 und 1 liegen, ist: {self.confidence}")
