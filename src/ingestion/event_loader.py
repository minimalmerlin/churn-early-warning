"""
Ingestion Layer: Lädt und validiert Customer-Event-Daten.
Warum: Die Trennung von I/O und Business Logic ist das Fundament
von Clean Architecture – ein I/O-Fehler darf nie den internen State korrumpieren.
"""

import logging
from pathlib import Path
from typing import Generator

import pandas as pd
from pydantic import ValidationError

from src.exceptions import DataIngestionError, DataValidationError, InsufficientDataError
from src.models.customer_event import CustomerEvent

logger = logging.getLogger(__name__)

_MINIMUM_RECORDS_REQUIRED = 1


class EventLoader:
    """
    Lädt Customer-Event-Daten aus einer CSV-Datei und validiert
    jede Zeile gegen das CustomerEvent-Schema.

    Input:  Pfad zu einer CSV-Datei mit Customer Events
    Output: Generator von validierten CustomerEvent-Objekten
    """

    def __init__(self, source_path: Path) -> None:
        self._source_path = source_path
        logger.info("EventLoader initialisiert für: %s", source_path)

    def load(self) -> list[CustomerEvent]:
        """
        Lädt alle validen Records aus der CSV-Quelle.

        Gibt im Fehlerfall eine strukturierte Exception zurück,
        anstatt mit korrupten Daten weiterzuarbeiten.

        Returns:
            Liste valider CustomerEvent-Objekte.

        Raises:
            DataIngestionError: Datei nicht lesbar oder kein valider CSV.
            DataValidationError: Schwerwiegender Schema-Fehler (alle Records ungültig).
            InsufficientDataError: Zu wenige valide Records für eine Analyse.
        """
        raw_df = self._read_csv()
        events = list(self._validate_rows(raw_df))

        if len(events) < _MINIMUM_RECORDS_REQUIRED:
            raise InsufficientDataError(
                f"Zu wenige valide Records ({len(events)}) in: {self._source_path}. "
                f"Minimum: {_MINIMUM_RECORDS_REQUIRED}"
            )

        logger.info("Erfolgreich %d valide Events geladen.", len(events))
        return events

    def _read_csv(self) -> pd.DataFrame:
        """
        Liest die CSV-Datei ein. Isoliert I/O-Fehler von der Validierungslogik.

        Raises:
            DataIngestionError: Datei nicht gefunden oder nicht parsbar.
        """
        if not self._source_path.exists():
            raise DataIngestionError(f"Quelldatei nicht gefunden: {self._source_path}")

        try:
            df = pd.read_csv(
                self._source_path,
                dtype=str,  # Alles als String einlesen, Typen via Pydantic validieren
                parse_dates=False,
            )
        except Exception as e:
            raise DataIngestionError(
                f"CSV konnte nicht gelesen werden ({self._source_path}): {e}"
            ) from e

        if df.empty:
            raise DataIngestionError(f"CSV-Datei ist leer: {self._source_path}")

        logger.info("CSV gelesen: %d Zeilen, %d Spalten.", len(df), len(df.columns))
        return df

    def _validate_rows(self, df: pd.DataFrame) -> Generator[CustomerEvent, None, None]:
        """
        Validiert jede Zeile einzeln gegen das CustomerEvent-Schema.
        Ungültige Zeilen werden geloggt und übersprungen (kein Fail-Fast,
        da einzelne korrupte Records die gesamte Charge nicht blockieren sollen).

        Yields:
            Valide CustomerEvent-Objekte.
        """
        invalid_count = 0

        for idx, row in df.iterrows():
            row_dict = {k: (None if pd.isna(v) else v) for k, v in row.to_dict().items()}
            try:
                event = CustomerEvent.model_validate(row_dict)
                yield event
            except ValidationError as e:
                invalid_count += 1
                logger.warning(
                    "Zeile %d übersprungen (Validierungsfehler): %s",
                    idx,
                    e.errors(include_url=False),
                )

        if invalid_count > 0:
            logger.warning(
                "%d von %d Zeilen übersprungen aufgrund von Validierungsfehlern.",
                invalid_count,
                len(df),
            )
