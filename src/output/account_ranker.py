"""
Account Ranker: Erstellt die "Top N Accounts at Risk"-Liste.
Warum: CS-Teams brauchen einen klaren, priorisierten Fokus – nicht eine
ungeordnete Liste aller Risk Scores. Der Ranker kombiniert Score und ARR,
damit High-Value-Accounts bei gleichem Score höher gewichtet werden.
"""

import logging
from dataclasses import dataclass

from src.exceptions import InsufficientDataError
from src.models.risk_assessment import RiskAssessment, RiskLevel

logger = logging.getLogger(__name__)

_MINIMUM_SCORE_FOR_ALERT = 25.0  # Nur Accounts mit Score > 25 kommen ins Ranking


@dataclass(frozen=True)
class RankedAccount:
    """
    Ein Account im priorisierten Risk Ranking.

    Input:  RiskAssessment
    Output: Rang-Position + zusammengefasste Key Metrics
    """
    rank: int
    account_id: str
    account_name: str
    risk_score: float
    risk_level: RiskLevel
    segment: str
    arr_at_risk: float
    top_reason: str         # Wichtigster Reason Code (Label) für Quick-View
    days_to_renewal: int | None
    composite_score: float  # Für interne Sortierung (Score × ARR-Gewichtung)


class AccountRanker:
    """
    Sortiert und filtert RiskAssessments für den Management-Report.

    Input:  Liste von RiskAssessments
    Output: Priorisierte Liste von RankedAccounts (Top N)
    """

    def __init__(self, top_n: int = 20, min_score: float = _MINIMUM_SCORE_FOR_ALERT) -> None:
        """
        Args:
            top_n:      Maximale Anzahl Accounts im Report (Standard: 20).
            min_score:  Minimaler Risk Score für Aufnahme ins Ranking.
        """
        self._top_n = top_n
        self._min_score = min_score

    def rank(self, assessments: list[RiskAssessment]) -> list[RankedAccount]:
        """
        Erstellt das priorisierte Risk Ranking.

        Args:
            assessments: Alle berechneten RiskAssessments.

        Returns:
            Liste der Top-N at-risk Accounts, sortiert nach Priorität.

        Raises:
            InsufficientDataError: Wenn keine Assessments über dem Mindestschwellenwert.
        """
        # Filtere Accounts unter dem Mindestschwellenwert
        eligible = [a for a in assessments if a.risk_score >= self._min_score]

        if not eligible:
            raise InsufficientDataError(
                f"Kein Account erreicht den Mindest-Risk-Score von {self._min_score}. "
                "Möglicherweise sind alle Accounts in gutem Zustand."
            )

        # Composite Score: Risk Score wird mit ARR-Log-Gewichtung kombiniert.
        # Warum: Ein 60er-Score bei €500k ARR ist kritischer als bei €10k ARR.
        scored = [
            (a, self._calculate_composite_score(a)) for a in eligible
        ]

        # Sortierung: Composite Score (descending)
        scored.sort(key=lambda x: x[1], reverse=True)

        top_accounts = scored[:self._top_n]
        ranked = [
            self._create_ranked_account(rank=i + 1, assessment=a, composite=c)
            for i, (a, c) in enumerate(top_accounts)
        ]

        logger.info(
            "Ranking erstellt: %d Accounts qualifiziert, %d im Report (Top %d).",
            len(eligible), len(ranked), self._top_n,
        )
        return ranked

    @staticmethod
    def _calculate_composite_score(assessment: RiskAssessment) -> float:
        """
        Kombiniert Risk Score und ARR für finale Sortierung.
        Formula: composite = risk_score * (1 + log10(arr) / 10)
        Warum: ARR-Normalisierung via Log verhindert, dass Mega-Accounts
        niedrig-kritische Scores übertreiben.
        """
        import math
        arr_weight = 1.0 + (math.log10(max(assessment.arr_at_risk, 1.0)) / 10.0)
        return round(assessment.risk_score * arr_weight, 4)

    @staticmethod
    def _create_ranked_account(
        rank: int, assessment: RiskAssessment, composite: float
    ) -> RankedAccount:
        """Erstellt ein RankedAccount-Objekt aus einem RiskAssessment."""
        top_reason = (
            assessment.reason_codes[0].label
            if assessment.reason_codes
            else "Kein spezifisches Signal identifiziert"
        )

        return RankedAccount(
            rank=rank,
            account_id=assessment.account_id,
            account_name=assessment.account_name,
            risk_score=assessment.risk_score,
            risk_level=assessment.risk_level,
            segment=assessment.segment.value,
            arr_at_risk=assessment.arr_at_risk,
            top_reason=top_reason,
            days_to_renewal=assessment.days_to_contract_end,
            composite_score=composite,
        )
