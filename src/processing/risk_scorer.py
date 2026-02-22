"""
Risk Scorer: Berechnet den Churn-Risk-Score (0-100) aus dem Feature Set.
Warum gewichtetes Scoring statt Black-Box-ML: Für ein Frühwarnsystem ist
Transparenz entscheidend. CS-Teams müssen dem Score vertrauen können –
und das erfordert Nachvollziehbarkeit. Das Gewichtungsmodell ist
konfigurierbar und auditierbar.
"""

import logging
from dataclasses import dataclass

from src.exceptions import RiskScoringError
from src.models.risk_assessment import ReasonCode, RiskAssessment, RiskLevel, CustomerSegment
from src.processing.feature_engineer import FeatureSet
from src.processing.reason_codes import ReasonCodeGenerator

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ScoringWeights:
    """
    Konfigurierbare Gewichtungen für den Risk Score.
    Summe aller Gewichte sollte 1.0 ergeben.
    Warum als Dataclass: Ermöglicht A/B-Tests mit verschiedenen Weight-Sets.
    """
    login_drop: float = 0.30
    ticket_intensity: float = 0.20
    nps: float = 0.20
    feature_adoption: float = 0.15
    user_activity: float = 0.10
    renewal_pressure: float = 0.05

    def __post_init__(self) -> None:
        total = (
            self.login_drop + self.ticket_intensity + self.nps
            + self.feature_adoption + self.user_activity + self.renewal_pressure
        )
        if not (0.99 <= total <= 1.01):
            raise ValueError(f"Gewichtsumme muss 1.0 sein, ist: {total:.3f}")


class RiskScorer:
    """
    Berechnet den Churn-Risk-Score für einen Account via gewichtetem Feature Scoring.

    Input:  FeatureSet + ARR des Accounts
    Output: RiskAssessment (Score, Level, Reason Codes, ARR-at-Risk)
    """

    _DEFAULT_WEIGHTS = ScoringWeights()

    def __init__(
        self,
        reason_code_generator: ReasonCodeGenerator,
        weights: ScoringWeights | None = None,
    ) -> None:
        self._reason_gen = reason_code_generator
        self._weights = weights or self._DEFAULT_WEIGHTS

    def score(
        self,
        features: FeatureSet,
        arr: float,
        segment: str,
        account_name: str,
        days_to_contract_end: int | None = None,
    ) -> RiskAssessment:
        """
        Berechnet das vollständige Risk Assessment für einen Account.

        Args:
            features:              Berechnetes FeatureSet des Accounts.
            arr:                   Annual Recurring Revenue (Euro).
            segment:               Kundensegment (HIGH_VALUE | MID_MARKET | SMB).
            account_name:          Anzeigename des Accounts.
            days_to_contract_end:  Verbleibende Tage bis Vertragsende (optional).

        Returns:
            RiskAssessment mit Score, Level und Reason Codes.

        Raises:
            RiskScoringError: Bei unerwarteten Berechnungsfehlern.
        """
        try:
            raw_score = self._calculate_weighted_score(features)
            risk_score = round(min(100.0, max(0.0, raw_score)), 2)
            risk_level = self._classify_risk_level(risk_score)
            reason_codes = self._reason_gen.generate(features)
            arr_at_risk = self._estimate_arr_at_risk(risk_score, arr)
            confidence = self._calculate_confidence(features, reason_codes)
            customer_segment = CustomerSegment(segment)

            assessment = RiskAssessment(
                account_id=features.account_id,
                account_name=account_name,
                risk_score=risk_score,
                risk_level=risk_level,
                segment=customer_segment,
                reason_codes=reason_codes,
                arr_at_risk=arr_at_risk,
                days_to_contract_end=days_to_contract_end,
                confidence=confidence,
            )

            logger.info(
                "Account '%s': Score=%.1f (%s), ARR-at-Risk=€%.0f",
                features.account_id, risk_score, risk_level.value, arr_at_risk,
            )
            return assessment

        except (ValueError, KeyError) as e:
            raise RiskScoringError(
                f"Scoring für Account '{features.account_id}' fehlgeschlagen: {e}"
            ) from e

    def _calculate_weighted_score(self, f: FeatureSet) -> float:
        """
        Berechnet den gewichteten Raw Score (0-100).
        Jede Dimension liefert einen Beitrag zwischen 0 und ihrem Maximalgewicht.
        """
        w = self._weights

        # Login-Score: drop_rate ist positiv bei Rückgang (0-1)
        login_score = max(0.0, f.login_drop_rate_7_to_30d) * w.login_drop * 100

        # Ticket-Score: hohe Eskalationsrate + hohe Last = schlechter
        ticket_score = (
            (f.ticket_intensity * 0.7 + f.open_ticket_load * 0.3) * w.ticket_intensity * 100
        )

        # NPS-Score: invertiert, da niedrige nps_normalized = hohes Risiko
        nps_score = (1.0 - f.nps_normalized) * w.nps * 100

        # Feature Adoption: niedrige Adoption = hohes Risiko
        adoption_score = (1.0 - f.feature_adoption_rate) * w.feature_adoption * 100

        # User Activity: Rückgang = Risiko (nur positiver Drop zählt)
        activity_score = max(0.0, f.user_activity_drop_rate) * w.user_activity * 100

        # Renewal Pressure: je näher Vertragsende, desto höher (nur im Window)
        renewal_score = (
            (1.0 - f.days_to_renewal_normalized) * w.renewal_pressure * 100
            if f.is_in_renewal_window else 0.0
        )

        total = login_score + ticket_score + nps_score + adoption_score + activity_score + renewal_score
        logger.debug(
            "Score-Breakdown '%s': Login=%.1f Ticket=%.1f NPS=%.1f "
            "Adoption=%.1f Activity=%.1f Renewal=%.1f → Total=%.1f",
            f.account_id, login_score, ticket_score, nps_score,
            adoption_score, activity_score, renewal_score, total,
        )
        return total

    @staticmethod
    def _classify_risk_level(score: float) -> RiskLevel:
        """Klassifiziert den Score in ein diskretes Risk Level."""
        if score >= 75:
            return RiskLevel.CRITICAL
        if score >= 50:
            return RiskLevel.HIGH
        if score >= 25:
            return RiskLevel.MEDIUM
        return RiskLevel.LOW

    @staticmethod
    def _estimate_arr_at_risk(risk_score: float, arr: float) -> float:
        """
        Schätzt den gefährdeten ARR-Anteil.
        Warum lineare Näherung: Eine exponentielle Kurve wäre genauer,
        aber für ein Frühwarnsystem ist Konsistenz und Erklärbarkeit wichtiger.
        Formel: arr_at_risk = arr * (risk_score / 100) ^ 1.5
        """
        risk_factor = (risk_score / 100.0) ** 1.5
        return round(arr * risk_factor, 2)

    @staticmethod
    def _calculate_confidence(features: FeatureSet, reason_codes: tuple[ReasonCode, ...]) -> float:
        """
        Konfidenzschätzung basierend auf Datenvollständigkeit und Signal-Konsistenz.
        Mehr übereinstimmende Signale = höhere Konfidenz.
        """
        # Basis-Konfidenz: Anzahl der Reason Codes (mehr Signale = mehr Sicherheit)
        signal_confidence = min(1.0, len(reason_codes) / 4.0)

        # Abzug wenn NPS fehlt (wichtiger Datenpunkt)
        data_completeness = 0.8 if features.nps_normalized == 0.5 else 1.0

        return round(signal_confidence * data_completeness, 3)
