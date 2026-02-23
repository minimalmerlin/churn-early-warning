"""
KPI Estimator: Quantifiziert den Business Impact bei Churn-Risiko.
Warum: Retention-Teams kämpfen oft gegen das Argument "Wir haben keine Zeit".
Ein konkreter, nachvollziehbarer ARR-Impact-Wert schafft den Urgency-Driver,
der Priorisierungsentscheidungen im Management erleichtert.
"""

import logging

from src.exceptions import KpiEstimationError
from src.models.playbook import KpiImpact
from src.models.risk_assessment import CustomerSegment, RiskAssessment, RiskLevel

logger = logging.getLogger(__name__)

# --- Baseline-Retention-Wahrscheinlichkeiten bei Intervention (Segment × RiskLevel) ---
# Warum: High-Value-Accounts haben bessere Retention-Chancen durch höhere Investition.
_RETENTION_PROBABILITY: dict[CustomerSegment, dict[RiskLevel, float]] = {
    CustomerSegment.HIGH_VALUE: {
        RiskLevel.CRITICAL: 0.65,
        RiskLevel.HIGH: 0.78,
        RiskLevel.MEDIUM: 0.90,
        RiskLevel.LOW: 0.97,
    },
    CustomerSegment.MID_MARKET: {
        RiskLevel.CRITICAL: 0.55,
        RiskLevel.HIGH: 0.70,
        RiskLevel.MEDIUM: 0.85,
        RiskLevel.LOW: 0.95,
    },
    CustomerSegment.SMB: {
        RiskLevel.CRITICAL: 0.45,
        RiskLevel.HIGH: 0.60,
        RiskLevel.MEDIUM: 0.78,
        RiskLevel.LOW: 0.92,
    },
}

# --- Geschätzte Payback-Perioden (Tage) für Retention-Investment ---
_PAYBACK_DAYS: dict[RiskLevel, int] = {
    RiskLevel.CRITICAL: 30,
    RiskLevel.HIGH: 60,
    RiskLevel.MEDIUM: 90,
    RiskLevel.LOW: 180,
}


class KpiEstimator:
    """
    Berechnet den geschätzten Business Impact eines Churn-Risks.

    Input:  RiskAssessment (Score, ARR, Segment, Level)
    Output: KpiImpact (ARR-at-Risk, erwarteter Save, Retention-Wahrscheinlichkeit)
    """

    def estimate(self, assessment: RiskAssessment) -> KpiImpact:
        """
        Schätzt den KPI Impact für einen at-risk Account.

        Raises:
            KpiEstimationError: Bei fehlenden Konfigurationen oder Berechnungsfehlern.
        """
        try:
            retention_prob = self._get_retention_probability(
                assessment.segment, assessment.risk_level
            )
            churn_prob_without_action = self._estimate_churn_without_action(assessment.risk_score)
            expected_arr_saved = round(assessment.arr_at_risk * retention_prob, 2)
            payback_days = _PAYBACK_DAYS.get(assessment.risk_level)

            impact = KpiImpact(
                arr_at_risk=assessment.arr_at_risk,
                estimated_retention_probability=retention_prob,
                expected_arr_saved=expected_arr_saved,
                churn_probability_without_action=churn_prob_without_action,
                payback_period_days=payback_days,
            )

            logger.debug(
                "KPI Impact '%s': ARR-at-Risk=€%.0f, Expected-Save=€%.0f, "
                "Retention-Prob=%.0f%%, Churn-Prob-ohne-Intervention=%.0f%%",
                assessment.account_id,
                assessment.arr_at_risk,
                expected_arr_saved,
                retention_prob * 100,
                churn_prob_without_action * 100,
            )
            return impact

        except KeyError as e:
            raise KpiEstimationError(
                f"Fehlende KPI-Konfiguration für Account '{assessment.account_id}': {e}"
            ) from e

    @staticmethod
    def _get_retention_probability(segment: CustomerSegment, level: RiskLevel) -> float:
        """Gibt die segement- und level-spezifische Retention-Wahrscheinlichkeit zurück."""
        segment_map = _RETENTION_PROBABILITY.get(segment)
        if segment_map is None:
            raise KeyError(f"Kein Retention-Mapping für Segment: {segment}")
        prob = segment_map.get(level)
        if prob is None:
            raise KeyError(f"Kein Retention-Mapping für Level: {level}")
        return prob

    @staticmethod
    def _estimate_churn_without_action(risk_score: float) -> float:
        """
        Schätzt die Churn-Wahrscheinlichkeit ohne Intervention.
        Warum sigmoid-ähnlich: Ein lineares Modell unterschätzt die Churn-Prob
        bei hohen Scores. Der Anstieg beschleunigt sich ab Score 50.
        Formula: P(churn) = score² / 10000
        """
        return round((risk_score ** 2) / 10_000, 4)
