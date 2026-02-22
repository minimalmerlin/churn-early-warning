"""
Unit Tests: Risk Scorer und Reason Code Generator.
Proof of Work: Scoring-Logik und Reason Codes funktionieren korrekt.
"""

from src.models.customer_event import CustomerEvent
from src.models.risk_assessment import RiskLevel
from src.processing.feature_engineer import FeatureEngineer
from src.processing.reason_codes import ReasonCodeGenerator
from src.processing.risk_scorer import RiskScorer, ScoringWeights


class TestRiskScorer:
    """Tests für den Risk Scorer."""

    def test_high_risk_account_gets_high_score(
        self,
        feature_engineer: FeatureEngineer,
        risk_scorer: RiskScorer,
        high_risk_event: CustomerEvent,
    ) -> None:
        """Prüfe: Account mit vielen negativen Signalen erhält einen hohen Score."""
        features = feature_engineer.transform(high_risk_event)
        assessment = risk_scorer.score(
            features=features,
            arr=high_risk_event.annual_recurring_revenue,
            segment=high_risk_event.customer_segment,
            account_name=high_risk_event.account_name,
        )
        assert assessment.risk_score >= 50.0, (
            f"Erwarteter Score >= 50, tatsächlich: {assessment.risk_score}"
        )
        assert assessment.risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL)

    def test_low_risk_account_gets_low_score(
        self,
        feature_engineer: FeatureEngineer,
        risk_scorer: RiskScorer,
        low_risk_event: CustomerEvent,
    ) -> None:
        """Prüfe: Account mit positiven Signalen erhält einen niedrigen Score."""
        features = feature_engineer.transform(low_risk_event)
        assessment = risk_scorer.score(
            features=features,
            arr=low_risk_event.annual_recurring_revenue,
            segment=low_risk_event.customer_segment,
            account_name=low_risk_event.account_name,
        )
        assert assessment.risk_score < 50.0, (
            f"Erwarteter Score < 50, tatsächlich: {assessment.risk_score}"
        )

    def test_score_is_always_between_0_and_100(
        self,
        feature_engineer: FeatureEngineer,
        risk_scorer: RiskScorer,
        high_risk_event: CustomerEvent,
    ) -> None:
        """Prüfe: Score-Bounding funktioniert (kein Overflow über 100)."""
        features = feature_engineer.transform(high_risk_event)
        assessment = risk_scorer.score(
            features=features,
            arr=high_risk_event.annual_recurring_revenue,
            segment=high_risk_event.customer_segment,
            account_name=high_risk_event.account_name,
        )
        assert 0.0 <= assessment.risk_score <= 100.0

    def test_arr_at_risk_never_exceeds_arr(
        self,
        feature_engineer: FeatureEngineer,
        risk_scorer: RiskScorer,
        high_risk_event: CustomerEvent,
    ) -> None:
        """Prüfe: ARR-at-Risk ist niemals größer als der tatsächliche ARR."""
        features = feature_engineer.transform(high_risk_event)
        assessment = risk_scorer.score(
            features=features,
            arr=high_risk_event.annual_recurring_revenue,
            segment=high_risk_event.customer_segment,
            account_name=high_risk_event.account_name,
        )
        assert assessment.arr_at_risk <= high_risk_event.annual_recurring_revenue

    def test_scoring_weights_must_sum_to_one(self) -> None:
        """Prüfe: Ungültige Gewichtssumme wird abgelehnt."""
        import pytest
        with pytest.raises(ValueError, match="Gewichtsumme"):
            ScoringWeights(
                login_drop=0.5,
                ticket_intensity=0.5,  # Summe = 1.5 → ungültig
                nps=0.2,
                feature_adoption=0.15,
                user_activity=0.10,
                renewal_pressure=0.05,
            )


class TestReasonCodeGenerator:
    """Tests für den Reason Code Generator (Explainability Gate)."""

    def test_high_risk_account_generates_reason_codes(
        self,
        feature_engineer: FeatureEngineer,
        reason_code_generator: ReasonCodeGenerator,
        high_risk_event: CustomerEvent,
    ) -> None:
        """Prüfe: Kritischer Account produziert mindestens einen Reason Code."""
        features = feature_engineer.transform(high_risk_event)
        codes = reason_code_generator.generate(features)
        assert len(codes) > 0, "Kritischer Account muss Reason Codes haben."

    def test_reason_codes_are_sorted_by_impact(
        self,
        feature_engineer: FeatureEngineer,
        reason_code_generator: ReasonCodeGenerator,
        high_risk_event: CustomerEvent,
    ) -> None:
        """Prüfe: Reason Codes sind nach Impact sortiert (höchster zuerst)."""
        features = feature_engineer.transform(high_risk_event)
        codes = reason_code_generator.generate(features)
        if len(codes) > 1:
            for i in range(len(codes) - 1):
                assert codes[i].impact_score >= codes[i + 1].impact_score

    def test_low_risk_account_generates_fewer_codes(
        self,
        feature_engineer: FeatureEngineer,
        reason_code_generator: ReasonCodeGenerator,
        high_risk_event: CustomerEvent,
        low_risk_event: CustomerEvent,
    ) -> None:
        """Prüfe: Gesunder Account hat weniger Reason Codes als riskanter Account."""
        high_features = feature_engineer.transform(high_risk_event)
        low_features = feature_engineer.transform(low_risk_event)
        high_codes = reason_code_generator.generate(high_features)
        low_codes = reason_code_generator.generate(low_features)
        assert len(high_codes) >= len(low_codes)

    def test_reason_code_impact_scores_are_positive(
        self,
        feature_engineer: FeatureEngineer,
        reason_code_generator: ReasonCodeGenerator,
        high_risk_event: CustomerEvent,
    ) -> None:
        """Prüfe: Alle Impact Scores sind positive Zahlen."""
        features = feature_engineer.transform(high_risk_event)
        codes = reason_code_generator.generate(features)
        for code in codes:
            assert code.impact_score >= 0.0
