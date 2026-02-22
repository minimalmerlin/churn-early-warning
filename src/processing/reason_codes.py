"""
Reason Code Generator: Explainability Quality Gate.
Warum: Ohne erklärbare Reason Codes ist ein Risk Score für CS-Teams
nutzlos – sie wissen nicht, WAS sie tun sollen. Explainability ist
kein Nice-to-Have, sondern ein Quality Gate.
"""

import logging
from dataclasses import dataclass

from src.models.risk_assessment import ReasonCode
from src.processing.feature_engineer import FeatureSet

logger = logging.getLogger(__name__)

# --- Schwellenwerte für Reason Code Triggerung ---
_LOGIN_DROP_CRITICAL = 0.5      # >50% Login-Rückgang = kritisch
_LOGIN_DROP_MODERATE = 0.25     # >25% Rückgang = moderat
_TICKET_INTENSITY_HIGH = 0.3    # >30% Eskalationsrate = hoch
_NPS_POOR_THRESHOLD = 0.35      # NPS normalisiert <0.35 ≈ NPS < -30
_ADOPTION_LOW_THRESHOLD = 0.4   # <40% Feature Adoption = gering
_USER_DROP_CRITICAL = 0.4       # >40% User-Rückgang = kritisch


@dataclass(frozen=True)
class _RuleDefinition:
    """Interne Struktur für eine Reason-Code-Regel."""
    code: str
    label: str
    max_impact: float
    direction: str = "negative"


class ReasonCodeGenerator:
    """
    Regelbasierter Reason Code Generator.

    Warum regelbasiert statt SHAP: Regelbasierte Systeme sind vollständig
    transparent, deterministisch und auditierbar. Für ein Business-System,
    das CS-Teams als Handlungsanweisung dient, ist interpretierbare Einfachheit
    wertvoller als ML-Komplexität.

    Input:  FeatureSet eines Accounts
    Output: Tuple von ReasonCode-Objekten (sortiert nach Impact)
    """

    def generate(self, features: FeatureSet) -> tuple[ReasonCode, ...]:
        """
        Generiert alle zutreffenden Reason Codes für einen Account.

        Returns:
            Tuple von ReasonCodes, sortiert nach Impact (höchster zuerst).
        """
        codes: list[ReasonCode] = []

        codes.extend(self._check_login_signals(features))
        codes.extend(self._check_support_signals(features))
        codes.extend(self._check_nps_signals(features))
        codes.extend(self._check_usage_signals(features))
        codes.extend(self._check_renewal_signals(features))

        # Sortierung nach Impact: höchster Impact erscheint zuerst im Report
        sorted_codes = tuple(sorted(codes, key=lambda c: c.impact_score, reverse=True))

        logger.debug(
            "Account '%s': %d Reason Codes generiert.", features.account_id, len(sorted_codes)
        )
        return sorted_codes

    def _check_login_signals(self, f: FeatureSet) -> list[ReasonCode]:
        """Prüft Login-basierte Churn-Signale."""
        codes: list[ReasonCode] = []

        if f.login_drop_rate_7_to_30d >= _LOGIN_DROP_CRITICAL:
            codes.append(ReasonCode(
                code="LOGIN_DROP_CRITICAL",
                label="Kritischer Login-Einbruch (>50% in 7 Tagen)",
                impact_score=round(f.login_drop_rate_7_to_30d * 40.0, 2),
                direction="negative",
            ))
        elif f.login_drop_rate_7_to_30d >= _LOGIN_DROP_MODERATE:
            codes.append(ReasonCode(
                code="LOGIN_DROP_MODERATE",
                label="Moderater Login-Rückgang (25-50%)",
                impact_score=round(f.login_drop_rate_7_to_30d * 20.0, 2),
                direction="negative",
            ))

        if f.login_trend_score < -0.3:
            codes.append(ReasonCode(
                code="LOGIN_TREND_NEGATIVE",
                label="Negativer Login-Langzeittrend (90d)",
                impact_score=round(abs(f.login_trend_score) * 15.0, 2),
                direction="negative",
            ))

        return codes

    def _check_support_signals(self, f: FeatureSet) -> list[ReasonCode]:
        """Prüft Support-basierte Churn-Signale."""
        codes: list[ReasonCode] = []

        if f.ticket_intensity >= _TICKET_INTENSITY_HIGH:
            codes.append(ReasonCode(
                code="HIGH_ESCALATION_RATE",
                label="Hohe Eskalationsrate im Support (>30%)",
                impact_score=round(f.ticket_intensity * 25.0, 2),
                direction="negative",
            ))

        if f.open_ticket_load >= 0.5:
            codes.append(ReasonCode(
                code="HIGH_OPEN_TICKET_LOAD",
                label="Hohe Anzahl offener Support-Tickets",
                impact_score=round(f.open_ticket_load * 15.0, 2),
                direction="negative",
            ))

        return codes

    def _check_nps_signals(self, f: FeatureSet) -> list[ReasonCode]:
        """Prüft NPS-basierte Churn-Signale."""
        codes: list[ReasonCode] = []

        if f.nps_normalized < _NPS_POOR_THRESHOLD:
            codes.append(ReasonCode(
                code="NPS_POOR",
                label="Niedriger NPS-Score (Detractor-Bereich)",
                impact_score=round((1.0 - f.nps_normalized) * 30.0, 2),
                direction="negative",
            ))

        if f.nps_declining:
            codes.append(ReasonCode(
                code="NPS_DECLINING",
                label="NPS-Trend negativ (Zufriedenheit sinkt)",
                impact_score=10.0,
                direction="negative",
            ))

        return codes

    def _check_usage_signals(self, f: FeatureSet) -> list[ReasonCode]:
        """Prüft Usage-basierte Churn-Signale."""
        codes: list[ReasonCode] = []

        if f.feature_adoption_rate < _ADOPTION_LOW_THRESHOLD:
            codes.append(ReasonCode(
                code="LOW_FEATURE_ADOPTION",
                label="Geringe Feature-Adoption (<40% genutzte Features)",
                impact_score=round((1.0 - f.feature_adoption_rate) * 20.0, 2),
                direction="negative",
            ))

        if f.user_activity_drop_rate >= _USER_DROP_CRITICAL:
            codes.append(ReasonCode(
                code="USER_ACTIVITY_DROP",
                label="Signifikanter Rückgang aktiver User (>40%)",
                impact_score=round(f.user_activity_drop_rate * 20.0, 2),
                direction="negative",
            ))

        return codes

    def _check_renewal_signals(self, f: FeatureSet) -> list[ReasonCode]:
        """Prüft Vertragserneuerungs-Signale."""
        codes: list[ReasonCode] = []

        if f.is_in_renewal_window:
            impact = round((1.0 - f.days_to_renewal_normalized) * 20.0, 2)
            codes.append(ReasonCode(
                code="CONTRACT_RENEWAL_IMMINENT",
                label="Vertragsende in <90 Tagen (kritisches Renewal-Fenster)",
                impact_score=impact,
                direction="negative",
            ))

        return codes
