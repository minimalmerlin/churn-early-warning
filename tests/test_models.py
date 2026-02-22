"""
Unit Tests: Pydantic-Modelle und Validierungslogik.
Proof of Work: Schema-Validierung funktioniert korrekt.
"""

from datetime import date

import pytest
from pydantic import ValidationError

from src.models.customer_event import CustomerEvent
from src.models.risk_assessment import RiskAssessment, RiskLevel, CustomerSegment, ReasonCode


class TestCustomerEventValidation:
    """Validiert das CustomerEvent-Schema gegen valide und invalide Inputs."""

    def test_valid_event_creates_successfully(self) -> None:
        """Prüfe: Valider Input produziert ein CustomerEvent ohne Fehler."""
        event = CustomerEvent(
            account_id="ACC-001",
            account_name="Test GmbH",
            event_date=date(2026, 1, 1),
            annual_recurring_revenue=100_000.0,
            logins_last_7d=5,
            logins_last_30d=20,
            logins_last_90d=60,
            customer_segment="HIGH_VALUE",
        )
        assert event.account_id == "ACC-001"
        assert event.customer_segment == "HIGH_VALUE"

    def test_negative_arr_is_rejected(self) -> None:
        """Prüfe: Negativer ARR wird durch Pydantic abgelehnt."""
        with pytest.raises(ValidationError) as exc_info:
            CustomerEvent(
                account_id="ACC-002",
                account_name="Invalid",
                event_date=date(2026, 1, 1),
                annual_recurring_revenue=-1000.0,
                logins_last_30d=10,
                logins_last_90d=30,
            )
        assert "annual_recurring_revenue" in str(exc_info.value)

    def test_invalid_segment_is_rejected(self) -> None:
        """Prüfe: Unbekanntes Segment löst ValidationError aus."""
        with pytest.raises(ValidationError):
            CustomerEvent(
                account_id="ACC-003",
                account_name="Invalid",
                event_date=date(2026, 1, 1),
                annual_recurring_revenue=50_000.0,
                logins_last_30d=10,
                logins_last_90d=30,
                customer_segment="UNKNOWN_SEGMENT",
            )

    def test_login_inconsistency_is_rejected(self) -> None:
        """Prüfe: logins_last_30d > logins_last_90d wird abgelehnt (Leakage-Check)."""
        with pytest.raises(ValidationError) as exc_info:
            CustomerEvent(
                account_id="ACC-004",
                account_name="Inconsistent",
                event_date=date(2026, 1, 1),
                annual_recurring_revenue=50_000.0,
                logins_last_7d=5,
                logins_last_30d=100,  # Mehr als 90d: inkonsistent
                logins_last_90d=50,
            )
        assert "Inkonsistente Login-Daten" in str(exc_info.value)

    def test_nps_out_of_range_is_rejected(self) -> None:
        """Prüfe: NPS außerhalb [-100, 100] ist ungültig."""
        with pytest.raises(ValidationError):
            CustomerEvent(
                account_id="ACC-005",
                account_name="Bad NPS",
                event_date=date(2026, 1, 1),
                annual_recurring_revenue=50_000.0,
                logins_last_30d=10,
                logins_last_90d=30,
                nps_score=150.0,  # Ungültig
            )

    def test_frozen_model_cannot_be_mutated(self, high_risk_event: "CustomerEvent") -> None:
        """
        Prüfe: CustomerEvent ist immutable (frozen=True).
        Warum ValidationError zusätzlich: Pydantic v2 kapselt Frozen-Fehler
        in ValidationError statt TypeError – beide Varianten sind korrekt.
        """
        from pydantic import ValidationError as PydanticValidationError
        with pytest.raises((TypeError, AttributeError, PydanticValidationError)):
            high_risk_event.account_id = "MUTATED"  # type: ignore[misc]


class TestRiskAssessmentValidation:
    """Validiert das RiskAssessment-Modell."""

    def test_risk_score_out_of_range_raises(self) -> None:
        """Prüfe: Risk Score > 100 wird im __post_init__ abgelehnt."""
        with pytest.raises(ValueError, match="risk_score"):
            RiskAssessment(
                account_id="TEST",
                account_name="Test",
                risk_score=150.0,  # Ungültig
                risk_level=RiskLevel.CRITICAL,
                segment=CustomerSegment.SMB,
                confidence=0.5,
            )

    def test_confidence_out_of_range_raises(self) -> None:
        """Prüfe: Konfidenz > 1.0 wird abgelehnt."""
        with pytest.raises(ValueError, match="confidence"):
            RiskAssessment(
                account_id="TEST",
                account_name="Test",
                risk_score=50.0,
                risk_level=RiskLevel.HIGH,
                segment=CustomerSegment.SMB,
                confidence=1.5,  # Ungültig
            )
