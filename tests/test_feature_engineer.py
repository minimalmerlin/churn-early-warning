"""
Unit Tests: Feature Engineer.
Proof of Work: Feature-Berechnungen liefern korrekte Werte.
"""

from src.models.customer_event import CustomerEvent
from src.processing.feature_engineer import FeatureEngineer, FeatureSet


class TestFeatureEngineer:
    """Tests für alle Feature-Berechnungen."""

    def test_high_risk_event_produces_high_drop_rate(
        self, feature_engineer: FeatureEngineer, high_risk_event: CustomerEvent
    ) -> None:
        """Prüfe: Account mit starkem Login-Rückgang hat hohe drop_rate."""
        features = feature_engineer.transform(high_risk_event)
        # 2 Logins in 7d vs. 8/4 = 2.0 Erwartung → 0% Drop (tatsächlich gleich)
        # Tatsächlicher Test: logins_7d=1, 30d-Avg=8/4=2 → drop = (2-1)/2 = 0.5
        assert features.login_drop_rate_7_to_30d >= 0.4
        assert isinstance(features, FeatureSet)

    def test_low_risk_event_produces_low_drop_rate(
        self, feature_engineer: FeatureEngineer, low_risk_event: CustomerEvent
    ) -> None:
        """Prüfe: Aktiver Account hat niedrige oder negative drop_rate."""
        features = feature_engineer.transform(low_risk_event)
        # logins_7d=25, 30d-Avg=98/4=24.5 → drop = (24.5-25)/24.5 ≈ -0.02
        assert features.login_drop_rate_7_to_30d < 0.1

    def test_nps_none_returns_neutral_score(
        self, feature_engineer: FeatureEngineer
    ) -> None:
        """Prüfe: Fehlender NPS wird mit neutralem Wert 0.5 behandelt."""
        from datetime import date
        event = CustomerEvent(
            account_id="NPS-NONE-TEST",
            account_name="No NPS",
            event_date=date(2026, 2, 22),
            annual_recurring_revenue=50_000.0,
            logins_last_30d=20,
            logins_last_90d=60,
            nps_score=None,
        )
        features = feature_engineer.transform(event)
        assert features.nps_normalized == 0.5

    def test_nps_max_score_normalized_to_one(
        self, feature_engineer: FeatureEngineer
    ) -> None:
        """Prüfe: NPS = 100 wird korrekt auf 1.0 normalisiert."""
        from datetime import date
        event = CustomerEvent(
            account_id="NPS-MAX-TEST",
            account_name="Perfect NPS",
            event_date=date(2026, 2, 22),
            annual_recurring_revenue=50_000.0,
            logins_last_30d=20,
            logins_last_90d=60,
            nps_score=100.0,
        )
        features = feature_engineer.transform(event)
        assert features.nps_normalized == 1.0

    def test_nps_min_score_normalized_to_zero(
        self, feature_engineer: FeatureEngineer
    ) -> None:
        """Prüfe: NPS = -100 wird korrekt auf 0.0 normalisiert."""
        from datetime import date
        event = CustomerEvent(
            account_id="NPS-MIN-TEST",
            account_name="Worst NPS",
            event_date=date(2026, 2, 22),
            annual_recurring_revenue=50_000.0,
            logins_last_30d=20,
            logins_last_90d=60,
            nps_score=-100.0,
        )
        features = feature_engineer.transform(event)
        assert features.nps_normalized == 0.0

    def test_renewal_window_detected_correctly(
        self, feature_engineer: FeatureEngineer, high_risk_event: CustomerEvent
    ) -> None:
        """Prüfe: Account mit Vertragsende <90 Tagen ist im Renewal-Window."""
        features = feature_engineer.transform(high_risk_event)
        # high_risk_event.contract_end_date = 2026-03-15, event_date = 2026-02-22 → 21 Tage
        assert features.is_in_renewal_window is True

    def test_no_contract_end_date_not_in_renewal_window(
        self, feature_engineer: FeatureEngineer
    ) -> None:
        """Prüfe: Account ohne bekanntes Vertragsende ist nicht im Renewal-Window."""
        from datetime import date
        event = CustomerEvent(
            account_id="NO-CONTRACT",
            account_name="No End Date",
            event_date=date(2026, 2, 22),
            annual_recurring_revenue=50_000.0,
            logins_last_30d=20,
            logins_last_90d=60,
            contract_end_date=None,
        )
        features = feature_engineer.transform(event)
        assert features.is_in_renewal_window is False
        assert features.days_to_renewal_normalized == 1.0

    def test_all_features_within_valid_ranges(
        self, feature_engineer: FeatureEngineer, high_risk_event: CustomerEvent
    ) -> None:
        """Prüfe: Alle normalisierten Features liegen in gültigen Ranges."""
        features = feature_engineer.transform(high_risk_event)
        assert -1.0 <= features.login_drop_rate_7_to_30d <= 1.0
        assert 0.0 <= features.login_intensity_30d <= 1.0
        assert -1.0 <= features.login_trend_score <= 1.0
        assert 0.0 <= features.ticket_intensity <= 1.0
        assert 0.0 <= features.open_ticket_load <= 1.0
        assert 0.0 <= features.nps_normalized <= 1.0
        assert 0.0 <= features.feature_adoption_rate <= 1.0
        assert -1.0 <= features.user_activity_drop_rate <= 1.0
        assert 0.0 <= features.days_to_renewal_normalized <= 1.0
