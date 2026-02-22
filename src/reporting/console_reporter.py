"""
Console Reporter: Formatiert den Pipeline-Output für die Konsole.
Warum separate Klasse: I/O-Operationen (Reporting) müssen von
Business Logic (Scoring/Ranking) getrennt sein (Clean Architecture).

Warum f-Strings statt %-Formatierung: Das Python-Logging-Modul unterstützt
kein '%,' als Tausendertrennzeichen – f-Strings als pre-formatierter String
umgehen dieses Limit ohne Qualitätsverlust.
"""

import logging

from src.models.playbook import Playbook
from src.output.account_ranker import RankedAccount
from src.pipeline import PipelineResult

logger = logging.getLogger(__name__)

_SEPARATOR = "=" * 80
_SECTION_SEP = "-" * 80


class ConsoleReporter:
    """
    Gibt das Pipeline-Ergebnis strukturiert auf der Konsole aus.

    Input:  PipelineResult
    Output: Formatierter Text-Report (stdout via logging)
    """

    def report(self, result: PipelineResult) -> None:
        """Gibt den vollständigen Report aus."""
        self._print_header(result)
        self._print_ranking(result.ranked_accounts)
        self._print_playbooks(result.playbooks)
        self._print_summary(result)

    def _print_header(self, result: PipelineResult) -> None:
        logger.info(_SEPARATOR)
        logger.info("  CHURN EARLY WARNING REPORT | %s", result.run_date.isoformat())
        logger.info("  Quelle: %s", result.source_file)
        logger.info(
            "  Analysierte Accounts: %d | Gesamt ARR at risk: €%s",
            result.total_accounts_analyzed,
            f"{result.total_arr_at_risk:,.0f}",
        )
        logger.info(_SEPARATOR)

    def _print_ranking(self, ranked: tuple[RankedAccount, ...]) -> None:
        logger.info("TOP %d ACCOUNTS AT RISK", len(ranked))
        logger.info(_SECTION_SEP)
        logger.info(
            "%-4s %-30s %-12s %-10s %-14s %-10s %s",
            "Rang", "Account", "Segment", "Score", "ARR at Risk", "Renewal", "Hauptsignal",
        )
        logger.info(_SECTION_SEP)

        for acc in ranked:
            renewal_info = (
                f"{acc.days_to_renewal}d" if acc.days_to_renewal is not None else "-"
            )
            row = (
                f"#{acc.rank:<3d} {acc.account_name[:29]:<30s} {acc.segment:<12s} "
                f"{acc.risk_score:<10.1f} €{acc.arr_at_risk:>12,.0f} "
                f"{renewal_info:<10s} {acc.top_reason[:60]}"
            )
            logger.info(row)

    def _print_playbooks(self, playbooks: tuple[Playbook, ...]) -> None:
        logger.info("")
        logger.info("PLAYBOOKS FUER TOP ACCOUNTS")
        logger.info(_SECTION_SEP)

        for pb in playbooks:
            logger.info("")
            logger.info(
                "Account: %s | Score: %.1f | %s",
                pb.account_name, pb.risk_score, pb.risk_level,
            )
            logger.info("Summary: %s", pb.summary)

            if pb.kpi_impact:
                logger.info(
                    "KPI Impact: ARR at Risk=€%s | Expected Save=€%s | "
                    "Retention-Prob=%.0f%% | Churn-Prob ohne Intervention=%.0f%%",
                    f"{pb.kpi_impact.arr_at_risk:,.0f}",
                    f"{pb.kpi_impact.expected_arr_saved:,.0f}",
                    pb.kpi_impact.estimated_retention_probability * 100,
                    pb.kpi_impact.churn_probability_without_action * 100,
                )

            logger.info("Empfohlene Actions:")
            for item in pb.action_items:
                logger.info(
                    "  [P%d] %s | Owner: %s | Timeline: %dd | Trigger: %s",
                    item.priority,
                    item.title,
                    item.recommended_owner,
                    item.suggested_timeline_days,
                    item.triggered_by,
                )
            logger.info(_SECTION_SEP)

    def _print_summary(self, result: PipelineResult) -> None:
        logger.info("")
        logger.info("EXECUTIVE SUMMARY")
        logger.info(_SECTION_SEP)
        critical = sum(1 for a in result.ranked_accounts if a.risk_level.value == "CRITICAL")
        high = sum(1 for a in result.ranked_accounts if a.risk_level.value == "HIGH")
        logger.info(
            "CRITICAL: %d | HIGH: %d | Gesamt im Report: %d",
            critical, high, len(result.ranked_accounts),
        )
        logger.info("Gesamt ARR at Risk: EUR %s", f"{result.total_arr_at_risk:,.0f}")
        logger.info(_SEPARATOR)
