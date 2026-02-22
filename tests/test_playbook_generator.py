"""
Unit Tests: Playbook Generator und KPI Estimator.
Proof of Work: Output-Layer liefert vollständige und valide Playbooks.
"""

from src.models.playbook import Playbook
from src.models.risk_assessment import RiskAssessment
from src.output.kpi_estimator import KpiEstimator
from src.output.playbook_generator import PlaybookGenerator


class TestPlaybookGenerator:
    """Tests für den Playbook Generator."""

    def test_playbook_is_generated_for_assessment(
        self,
        sample_risk_assessment: RiskAssessment,
        kpi_estimator: KpiEstimator,
    ) -> None:
        """Prüfe: Playbook wird für ein valides Assessment erstellt."""
        generator = PlaybookGenerator(kpi_estimator=kpi_estimator)
        playbook = generator.generate(sample_risk_assessment)
        assert isinstance(playbook, Playbook)
        assert playbook.account_id == sample_risk_assessment.account_id

    def test_playbook_has_action_items(
        self,
        sample_risk_assessment: RiskAssessment,
        kpi_estimator: KpiEstimator,
    ) -> None:
        """Prüfe: Playbook enthält mindestens eine Action."""
        generator = PlaybookGenerator(kpi_estimator=kpi_estimator)
        playbook = generator.generate(sample_risk_assessment)
        assert len(playbook.action_items) > 0

    def test_action_items_are_prioritized(
        self,
        sample_risk_assessment: RiskAssessment,
        kpi_estimator: KpiEstimator,
    ) -> None:
        """Prüfe: Action Items sind aufsteigend nach Priorität nummeriert."""
        generator = PlaybookGenerator(kpi_estimator=kpi_estimator)
        playbook = generator.generate(sample_risk_assessment)
        priorities = [item.priority for item in playbook.action_items]
        assert priorities == sorted(priorities)
        assert priorities[0] == 1

    def test_playbook_summary_is_not_empty(
        self,
        sample_risk_assessment: RiskAssessment,
        kpi_estimator: KpiEstimator,
    ) -> None:
        """Prüfe: Playbook Summary ist ausgefüllt (für Slack/Management)."""
        generator = PlaybookGenerator(kpi_estimator=kpi_estimator)
        playbook = generator.generate(sample_risk_assessment)
        assert len(playbook.summary) > 0
        assert sample_risk_assessment.account_name in playbook.summary

    def test_playbook_kpi_impact_is_populated(
        self,
        sample_risk_assessment: RiskAssessment,
        kpi_estimator: KpiEstimator,
    ) -> None:
        """Prüfe: KPI Impact wird berechnet und ist im Playbook enthalten."""
        generator = PlaybookGenerator(kpi_estimator=kpi_estimator)
        playbook = generator.generate(sample_risk_assessment)
        assert playbook.kpi_impact is not None
        assert playbook.kpi_impact.arr_at_risk > 0

    def test_no_duplicate_actions_in_playbook(
        self,
        sample_risk_assessment: RiskAssessment,
        kpi_estimator: KpiEstimator,
    ) -> None:
        """Prüfe: Jede Action-Type erscheint maximal einmal im Playbook."""
        generator = PlaybookGenerator(kpi_estimator=kpi_estimator)
        playbook = generator.generate(sample_risk_assessment)
        action_types = [item.action for item in playbook.action_items]
        assert len(action_types) == len(set(action_types))


class TestKpiEstimator:
    """Tests für den KPI Estimator."""

    def test_arr_saved_cannot_exceed_arr_at_risk(
        self,
        sample_risk_assessment: RiskAssessment,
        kpi_estimator: KpiEstimator,
    ) -> None:
        """Prüfe: Erwarteter Save kann nicht größer sein als ARR at Risk."""
        impact = kpi_estimator.estimate(sample_risk_assessment)
        assert impact.expected_arr_saved <= impact.arr_at_risk

    def test_retention_probability_is_between_0_and_1(
        self,
        sample_risk_assessment: RiskAssessment,
        kpi_estimator: KpiEstimator,
    ) -> None:
        """Prüfe: Retention-Wahrscheinlichkeit liegt im gültigen Bereich."""
        impact = kpi_estimator.estimate(sample_risk_assessment)
        assert 0.0 <= impact.estimated_retention_probability <= 1.0

    def test_churn_probability_increases_with_score(
        self,
        kpi_estimator: KpiEstimator,
    ) -> None:
        """Prüfe: Höherer Risk Score → höhere Churn-Wahrscheinlichkeit ohne Intervention."""
        from src.models.risk_assessment import RiskAssessment, RiskLevel, CustomerSegment
        low_score_assessment = RiskAssessment(
            account_id="LOW",
            account_name="Low Risk",
            risk_score=20.0,
            risk_level=RiskLevel.LOW,
            segment=CustomerSegment.SMB,
            arr_at_risk=5_000.0,
            confidence=0.5,
        )
        high_score_assessment = RiskAssessment(
            account_id="HIGH",
            account_name="High Risk",
            risk_score=80.0,
            risk_level=RiskLevel.CRITICAL,
            segment=CustomerSegment.SMB,
            arr_at_risk=50_000.0,
            confidence=0.9,
        )
        low_impact = kpi_estimator.estimate(low_score_assessment)
        high_impact = kpi_estimator.estimate(high_score_assessment)
        assert high_impact.churn_probability_without_action > low_impact.churn_probability_without_action
