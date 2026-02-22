"""
Data Leakage Checker: Quality Gate gegen Future-Data-Leakage.
Warum: Ein Churn-Modell, das versehentlich Zukunftsdaten in die
Vergangenheitsanalyse einbezieht, produziert unrealistisch gute Scores –
und total falsche Produktionsresultate. Dieser Check ist nicht optional.
"""

import logging
from datetime import date

from src.exceptions import DataLeakageDetectedError
from src.models.customer_event import CustomerEvent

logger = logging.getLogger(__name__)


class LeakageChecker:
    """
    Prüft Customer Events auf potenzielle Data-Leakage-Muster.

    Input:  Liste von CustomerEvent-Objekten + Referenzdatum
    Output: None (raises DataLeakageDetectedError bei Leakage)
    """

    def __init__(self, reference_date: date | None = None) -> None:
        """
        Args:
            reference_date: Das "heutige" Datum für den Check.
                            None = aktuelles Systemdatum.
        """
        self._reference_date = reference_date or date.today()
        logger.info("LeakageChecker initialisiert. Referenzdatum: %s", self._reference_date)

    def check(self, events: list[CustomerEvent]) -> None:
        """
        Führt alle Leakage-Checks durch.

        Raises:
            DataLeakageDetectedError: Bei erkanntem Future-Data-Leakage.
        """
        self._check_future_event_dates(events)
        self._check_future_contract_dates(events)
        logger.info("LeakageChecker: Alle %d Events bestanden den Leakage-Check.", len(events))

    def _check_future_event_dates(self, events: list[CustomerEvent]) -> None:
        """
        Event-Datum darf nicht in der Zukunft liegen.
        Warum: Ein Event mit Datum nach heute kann keine valide Beobachtung sein.
        """
        future_events = [
            e for e in events if e.event_date > self._reference_date
        ]
        if future_events:
            offending_ids = [e.account_id for e in future_events[:5]]
            raise DataLeakageDetectedError(
                f"LEAKAGE DETECTED: {len(future_events)} Events haben ein Datum "
                f"nach dem Referenzdatum ({self._reference_date}). "
                f"Betroffene Account-IDs (erste 5): {offending_ids}"
            )

    def _check_future_contract_dates(self, events: list[CustomerEvent]) -> None:
        """
        Prüft ob contract_end_date-basierte Features auf Zukunftsdaten beruhen.
        Vertragsende darf bekannt sein, aber Scoring-Features dürfen nicht
        auf zukünftigen Vertragsverlängerungen basieren.
        Warum: Nur der Status zum event_date ist eine valide Beobachtung.
        """
        inconsistent = [
            e for e in events
            if e.contract_end_date is not None
            and e.event_date > e.contract_end_date
        ]
        if inconsistent:
            offending_ids = [e.account_id for e in inconsistent[:5]]
            logger.warning(
                "INKONSISTENZ: %d Events haben event_date > contract_end_date "
                "(Vertrag bereits abgelaufen). Account-IDs: %s",
                len(inconsistent), offending_ids,
            )
            # Warnung statt Exception: Ausgelaufene Verträge können noch
            # relevant für Retention-Analyse sein (Late-Stage Churn).
