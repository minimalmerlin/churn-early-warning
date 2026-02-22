"""
Feature Engineering: Berechnet abgeleitete Features aus CustomerEvents.
Warum: Rohe Event-Counts sind wenig aussagekräftig – relative Veränderungen
(z.B. Login-Drop-Rate, Ticket-Intensität) haben deutlich höhere Prädiktionskraft.
"""

import logging
from dataclasses import dataclass
from typing import Optional

from src.exceptions import FeatureEngineeringError
from src.models.customer_event import CustomerEvent

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FeatureSet:
    """
    Abgeleitete Feature-Werte für einen Account.
    Alle Werte sind normalisiert und interpretierbar (kein raw count).

    Input:  CustomerEvent
    Output: Numerische Features für den Risk Scorer
    """
    account_id: str
    # Login-Features
    login_drop_rate_7_to_30d: float     # Wie stark sind Logins in 7d vs. 30d-Durchschnitt gefallen?
    login_intensity_30d: float          # Logins/Tag in den letzten 30 Tagen (normalisiert)
    login_trend_score: float            # -1.0 (stark fallend) bis +1.0 (stark steigend)
    # Support-Features
    ticket_intensity: float             # Eskalierte Tickets / Gesamttickets (0-1)
    open_ticket_load: float             # Offene Tickets als Stressfaktor (normalisiert)
    # NPS-Features
    nps_normalized: float               # NPS auf 0-1 normalisiert (0 = schlecht, 1 = sehr gut)
    nps_declining: bool                 # True = NPS-Trend negativ
    # Usage-Features
    feature_adoption_rate: float        # Direkt aus dem Event (0-1)
    user_activity_drop_rate: float      # Active Users 30d vs. 90d-Durchschnitt
    # Vertragsdaten-Features
    days_to_renewal_normalized: float   # 0 = morgen, 1 = >365 Tage (kein Druck)
    is_in_renewal_window: bool          # True = Vertrag endet in <90 Tagen


class FeatureEngineer:
    """
    Transformiert valide CustomerEvent-Objekte in normalisierte Feature-Sets.

    Input:  CustomerEvent (validiert)
    Output: FeatureSet (für Risk Scorer)
    """

    _RENEWAL_WINDOW_DAYS: int = 90
    _MAX_RENEWAL_DAYS: int = 365

    def transform(self, event: CustomerEvent) -> FeatureSet:
        """
        Berechnet alle Features für einen einzelnen Account.

        Raises:
            FeatureEngineeringError: Bei unerwarteten Berechnungsfehlern.
        """
        try:
            return FeatureSet(
                account_id=event.account_id,
                login_drop_rate_7_to_30d=self._calc_login_drop_rate(event),
                login_intensity_30d=self._calc_login_intensity(event),
                login_trend_score=self._calc_login_trend(event),
                ticket_intensity=self._calc_ticket_intensity(event),
                open_ticket_load=self._calc_open_ticket_load(event),
                nps_normalized=self._calc_nps_normalized(event),
                nps_declining=self._is_nps_declining(event),
                feature_adoption_rate=event.feature_adoption_rate,
                user_activity_drop_rate=self._calc_user_activity_drop(event),
                days_to_renewal_normalized=self._calc_days_to_renewal(event),
                is_in_renewal_window=self._check_renewal_window(event),
            )
        except Exception as e:
            raise FeatureEngineeringError(
                f"Feature-Berechnung für Account '{event.account_id}' fehlgeschlagen: {e}"
            ) from e

    def _calc_login_drop_rate(self, event: CustomerEvent) -> float:
        """
        Warum: Ein starker Rückgang der Logins in 7d vs. dem 30d-Durchschnitt
        ist ein früher, zuverlässiger Churn-Indikator.
        Positiver Wert = Rückgang (schlecht), negativer = Anstieg (gut).
        """
        avg_logins_per_7d_from_30d = event.logins_last_30d / 4.0
        if avg_logins_per_7d_from_30d == 0:
            return 1.0 if event.logins_last_7d == 0 else 0.0
        drop_rate = (avg_logins_per_7d_from_30d - event.logins_last_7d) / avg_logins_per_7d_from_30d
        return max(-1.0, min(1.0, drop_rate))

    def _calc_login_intensity(self, event: CustomerEvent) -> float:
        """
        Logins pro Tag (normalisiert auf 0-1, Cap bei 10 Logins/Tag = 1.0).
        Warum: Absolute Zahlen sind irreführend – relative Aktivität ist der KPI.
        """
        intensity = event.logins_last_30d / 30.0
        return min(1.0, intensity / 10.0)

    def _calc_login_trend(self, event: CustomerEvent) -> float:
        """
        Vergleicht 7d-Fenster mit 90d-Fenster für Langzeit-Trend.
        -1.0 = maximaler Rückgang, +1.0 = maximaler Anstieg.
        """
        avg_per_7d_from_90d = event.logins_last_90d / 12.0
        avg_per_7d_from_30d = event.logins_last_30d / 4.0

        if avg_per_7d_from_90d == 0:
            return 0.0

        trend = (avg_per_7d_from_30d - avg_per_7d_from_90d) / avg_per_7d_from_90d
        return max(-1.0, min(1.0, trend))

    def _calc_ticket_intensity(self, event: CustomerEvent) -> float:
        """
        Anteil eskalierter an allen bearbeiteten Tickets.
        Warum: Eskalationen sind ein Proxy für tiefe Unzufriedenheit.
        """
        total = event.resolved_tickets_last_30d + event.escalated_tickets_last_90d
        if total == 0:
            return 0.0
        return min(1.0, event.escalated_tickets_last_90d / total)

    def _calc_open_ticket_load(self, event: CustomerEvent) -> float:
        """Normalisierter Open-Ticket-Load (Cap bei 10 offenen Tickets = 1.0)."""
        return min(1.0, event.open_tickets / 10.0)

    def _calc_nps_normalized(self, event: CustomerEvent) -> float:
        """
        Normalisiert NPS von (-100, 100) auf (0, 1).
        None-Werte (keine Messung) werden neutral behandelt (0.5).
        Warum: Neutral, nicht gut – fehlende NPS-Daten sind ein Signal für
        mangelndes Engagement, nicht für Zufriedenheit.
        """
        if event.nps_score is None:
            return 0.5
        return (event.nps_score + 100) / 200.0

    def _is_nps_declining(self, event: CustomerEvent) -> bool:
        """True wenn NPS-Trend negativ (Wert sinkend)."""
        if event.nps_trend is None:
            return False
        return event.nps_trend < 0

    def _calc_user_activity_drop(self, event: CustomerEvent) -> float:
        """
        Rückgang aktiver User: 30d vs. 90d-Durchschnitt.
        Positiv = Rückgang (Risiko), negativ = Wachstum.
        """
        avg_90d_per_month = event.active_users_last_90d / 3.0
        if avg_90d_per_month == 0:
            return 1.0 if event.active_users_last_30d == 0 else 0.0
        drop = (avg_90d_per_month - event.active_users_last_30d) / avg_90d_per_month
        return max(-1.0, min(1.0, drop))

    def _calc_days_to_renewal(self, event: CustomerEvent) -> float:
        """
        Normalisiert die verbleibenden Tage bis Vertragsende auf 0-1.
        0 = unmittelbar bevorstehend (höchstes Risiko), 1 = >365 Tage.
        """
        if event.contract_end_date is None:
            return 1.0  # Kein bekanntes Enddatum = kein Renewal-Druck
        days_remaining = (event.contract_end_date - event.event_date).days
        if days_remaining <= 0:
            return 0.0
        return min(1.0, days_remaining / self._MAX_RENEWAL_DAYS)

    def _check_renewal_window(self, event: CustomerEvent) -> bool:
        """True wenn Vertragsende in <90 Tagen."""
        if event.contract_end_date is None:
            return False
        days_remaining = (event.contract_end_date - event.event_date).days
        return 0 <= days_remaining <= self._RENEWAL_WINDOW_DAYS
