"""
Churn Early Warning Pipeline: Haupt-Orchestrator.
Warum: Der Orchestrator verbindet alle Schichten (EVA-Prinzip) und
stellt sicher, dass Fehler in einer Schicht kontrolliert abgefangen werden,
ohne den State der anderen Schichten zu korrumpieren.

EVA-Flow:
  E (Eingabe):    EventLoader → CustomerEvent[]
  V (Verarbeitung): FeatureEngineer → RiskScorer → AccountRanker
  A (Ausgabe):    PlaybookGenerator → Report
"""

import logging
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from config.settings import PipelineConfig
from src.exceptions import (
    ChurnPipelineError,
    DataIngestionError,
    InsufficientDataError,
)
from src.ingestion.event_loader import EventLoader
from src.models.customer_event import CustomerEvent
from src.models.playbook import Playbook
from src.models.risk_assessment import RiskAssessment
from src.output.account_ranker import AccountRanker, RankedAccount
from src.output.kpi_estimator import KpiEstimator
from src.output.playbook_generator import PlaybookGenerator
from src.processing.feature_engineer import FeatureEngineer
from src.processing.leakage_checker import LeakageChecker
from src.processing.reason_codes import ReasonCodeGenerator
from src.processing.risk_scorer import RiskScorer

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PipelineResult:
    """
    Vollständiges Ergebnis eines Pipeline-Laufs.

    Output: Top-N Accounts + zugehörige Playbooks + Metadaten
    """
    ranked_accounts: tuple[RankedAccount, ...]
    playbooks: tuple[Playbook, ...]
    total_accounts_analyzed: int
    total_arr_at_risk: float
    run_date: date
    source_file: Path


class ChurnPipeline:
    """
    Haupt-Orchestrator der Churn Early Warning Pipeline.

    Orchestriert den vollständigen EVA-Flow:
    Laden → Validieren → Features → Scoring → Ranking → Playbooks → Report
    """

    def __init__(self, config: PipelineConfig) -> None:
        self._config = config
        # Dependency Injection: alle Komponenten werden hier verdrahtet
        self._event_loader = EventLoader(config.data_source_path)
        self._leakage_checker = LeakageChecker()
        self._feature_engineer = FeatureEngineer()
        self._reason_code_gen = ReasonCodeGenerator()
        self._risk_scorer = RiskScorer(reason_code_generator=self._reason_code_gen)
        self._account_ranker = AccountRanker(
            top_n=config.top_n_accounts,
            min_score=config.min_risk_score_threshold,
        )
        self._kpi_estimator = KpiEstimator()
        self._playbook_generator = PlaybookGenerator(kpi_estimator=self._kpi_estimator)

        logger.info(
            "ChurnPipeline initialisiert. Source: %s | Top-N: %d | Min-Score: %.1f",
            config.data_source_path, config.top_n_accounts, config.min_risk_score_threshold,
        )

    def run(self) -> PipelineResult:
        """
        Führt den vollständigen Pipeline-Lauf durch.

        Returns:
            PipelineResult mit allen Ergebnissen.

        Raises:
            ChurnPipelineError: Bei nicht behebbaren Fehlern in der Pipeline.
        """
        logger.info("=== CHURN PIPELINE GESTARTET ===")

        # --- E: Eingabe & Validierung ---
        events = self._load_and_validate()

        # --- Quality Gate: Leakage Check ---
        self._leakage_checker.check(events)

        # --- V: Verarbeitung ---
        assessments = self._process_events(events)

        # --- V: Ranking ---
        ranked_accounts = self._account_ranker.rank(assessments)

        # --- A: Ausgabe – Playbooks für Top-N Accounts ---
        top_assessment_ids = {a.account_id for a in ranked_accounts}
        top_assessments = [a for a in assessments if a.account_id in top_assessment_ids]
        playbooks = self._generate_playbooks(top_assessments)

        # --- Ergebnis aggregieren ---
        total_arr_at_risk = sum(a.arr_at_risk for a in assessments)

        result = PipelineResult(
            ranked_accounts=tuple(ranked_accounts),
            playbooks=tuple(playbooks),
            total_accounts_analyzed=len(events),
            total_arr_at_risk=round(total_arr_at_risk, 2),
            run_date=date.today(),
            source_file=self._config.data_source_path,
        )

        logger.info(
            "=== PIPELINE ABGESCHLOSSEN === | Accounts: %d | Top-%d at risk | "
            "Gesamt ARR at risk: EUR %s",
            result.total_accounts_analyzed,
            len(result.ranked_accounts),
            f"{result.total_arr_at_risk:,.0f}",
        )
        return result

    def _load_and_validate(self) -> list[CustomerEvent]:
        """E-Phase: Laden und Validieren der Eingabedaten."""
        try:
            events = self._event_loader.load()
            logger.info("E-Phase: %d valide Events geladen.", len(events))
            return events
        except (DataIngestionError, InsufficientDataError):
            raise
        except Exception as e:
            raise ChurnPipelineError(f"Unerwarteter Fehler in E-Phase: {e}") from e

    def _process_events(self, events: list[CustomerEvent]) -> list[RiskAssessment]:
        """
        V-Phase: Feature Engineering + Risk Scoring für alle Events.
        Fehler einzelner Accounts werden geloggt, blockieren aber nicht die gesamte Pipeline.
        """
        assessments: list[RiskAssessment] = []
        failed_count = 0

        for event in events:
            try:
                features = self._feature_engineer.transform(event)
                days_to_end = (
                    (event.contract_end_date - event.event_date).days
                    if event.contract_end_date else None
                )
                assessment = self._risk_scorer.score(
                    features=features,
                    arr=event.annual_recurring_revenue,
                    segment=event.customer_segment,
                    account_name=event.account_name,
                    days_to_contract_end=days_to_end,
                )
                assessments.append(assessment)
            except ChurnPipelineError as e:
                failed_count += 1
                logger.error(
                    "Account '%s' übersprungen: %s", event.account_id, e
                )

        if failed_count > 0:
            logger.warning(
                "V-Phase: %d von %d Accounts konnten nicht verarbeitet werden.",
                failed_count, len(events),
            )

        logger.info("V-Phase: %d Assessments berechnet.", len(assessments))
        return assessments

    def _generate_playbooks(self, assessments: list[RiskAssessment]) -> list[Playbook]:
        """A-Phase: Playbook-Generierung für Top-N at-risk Accounts."""
        playbooks: list[Playbook] = []
        failed_count = 0

        for assessment in assessments:
            try:
                playbook = self._playbook_generator.generate(assessment)
                playbooks.append(playbook)
            except ChurnPipelineError as e:
                failed_count += 1
                logger.error(
                    "Playbook für Account '%s' fehlgeschlagen: %s", assessment.account_id, e
                )

        if failed_count > 0:
            logger.warning(
                "A-Phase: %d von %d Playbooks konnten nicht erstellt werden.",
                failed_count, len(assessments),
            )

        logger.info("A-Phase: %d Playbooks erstellt.", len(playbooks))
        return playbooks
