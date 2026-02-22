"""
Pytest Fixtures für die Churn Pipeline Tests.
Zentrale Testdaten für isolierte, reproduzierbare Unit Tests.
"""

from datetime import date

import pytest

from src.models.customer_event import CustomerEvent
from src.models.risk_assessment import CustomerSegment, ReasonCode, RiskAssessment, RiskLevel
from src.processing.feature_engineer import FeatureEngineer, FeatureSet
from src.processing.reason_codes import ReasonCodeGenerator
from src.processing.risk_scorer import RiskScorer
from src.output.kpi_estimator import KpiEstimator


@pytest.fixture
def high_risk_event() -> CustomerEvent:
    """Account mit kritischem Churn-Risiko (starker Login-Drop, schlechter NPS, Renewal imminent)."""
    return CustomerEvent(
        account_id="TEST-CRITICAL-001",
        account_name="At Risk Corp",
        event_date=date(2026, 2, 22),
        annual_recurring_revenue=500_000.0,
        logins_last_7d=1,
        logins_last_30d=8,
        logins_last_90d=95,
        open_tickets=8,
        resolved_tickets_last_30d=5,
        escalated_tickets_last_90d=7,
        nps_score=-60.0,
        nps_trend=-20.0,
        feature_adoption_rate=0.20,
        active_users_last_30d=5,
        active_users_last_90d=42,
        contract_end_date=date(2026, 3, 15),
        customer_segment="HIGH_VALUE",
    )


@pytest.fixture
def low_risk_event() -> CustomerEvent:
    """Account mit niedrigem Churn-Risiko (gute Aktivität, positiver NPS)."""
    return CustomerEvent(
        account_id="TEST-LOW-001",
        account_name="Happy Customer GmbH",
        event_date=date(2026, 2, 22),
        annual_recurring_revenue=120_000.0,
        logins_last_7d=25,
        logins_last_30d=98,
        logins_last_90d=285,
        open_tickets=0,
        resolved_tickets_last_30d=12,
        escalated_tickets_last_90d=0,
        nps_score=72.0,
        nps_trend=8.0,
        feature_adoption_rate=0.88,
        active_users_last_30d=22,
        active_users_last_90d=65,
        contract_end_date=date(2026, 12, 31),
        customer_segment="MID_MARKET",
    )


@pytest.fixture
def feature_engineer() -> FeatureEngineer:
    return FeatureEngineer()


@pytest.fixture
def reason_code_generator() -> ReasonCodeGenerator:
    return ReasonCodeGenerator()


@pytest.fixture
def risk_scorer(reason_code_generator: ReasonCodeGenerator) -> RiskScorer:
    return RiskScorer(reason_code_generator=reason_code_generator)


@pytest.fixture
def kpi_estimator() -> KpiEstimator:
    return KpiEstimator()


@pytest.fixture
def sample_risk_assessment() -> RiskAssessment:
    """Minimal valides RiskAssessment für Output-Layer Tests."""
    return RiskAssessment(
        account_id="TEST-001",
        account_name="Test Account AG",
        risk_score=72.5,
        risk_level=RiskLevel.HIGH,
        segment=CustomerSegment.HIGH_VALUE,
        reason_codes=(
            ReasonCode(
                code="LOGIN_DROP_CRITICAL",
                label="Kritischer Login-Einbruch (>50%)",
                impact_score=35.0,
                direction="negative",
            ),
            ReasonCode(
                code="NPS_POOR",
                label="Niedriger NPS-Score",
                impact_score=20.0,
                direction="negative",
            ),
        ),
        arr_at_risk=180_000.0,
        days_to_contract_end=45,
        confidence=0.85,
    )
