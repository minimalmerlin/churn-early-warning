"""
Zentrale Konfiguration via Environment Variables.
Warum: Zero Hardcoded Credentials. Alle konfigurierbaren Werte
kommen aus der Umgebung – das ermöglicht sicheres Multi-Environment-Deployment.
"""

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PipelineConfig:
    """
    Vollständige Laufzeit-Konfiguration der Churn-Pipeline.
    Alle Werte werden aus Environment Variables gelesen.

    Input:  Umgebungsvariablen (via os.getenv)
    Output: Typisiertes, valides Konfigurationsobjekt
    """

    # --- Datenquellen ---
    data_source_path: Path = field(
        default_factory=lambda: Path(
            os.getenv("CHURN_DATA_SOURCE", "data/sample/customer_events_sample.csv")
        )
    )

    # --- Report-Konfiguration ---
    top_n_accounts: int = field(
        default_factory=lambda: int(os.getenv("CHURN_TOP_N_ACCOUNTS", "20"))
    )
    min_risk_score_threshold: float = field(
        default_factory=lambda: float(os.getenv("CHURN_MIN_SCORE_THRESHOLD", "25.0"))
    )

    # --- Logging ---
    log_level: str = field(
        default_factory=lambda: os.getenv("CHURN_LOG_LEVEL", "INFO").upper()
    )
    log_file: Path | None = field(
        default_factory=lambda: (
            Path(os.getenv("CHURN_LOG_FILE")) if os.getenv("CHURN_LOG_FILE") else None
        )
    )

    # --- Output ---
    output_dir: Path = field(
        default_factory=lambda: Path(os.getenv("CHURN_OUTPUT_DIR", "output"))
    )

    def __post_init__(self) -> None:
        """Post-Condition: Validierung der geladenen Konfiguration."""
        valid_log_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if self.log_level not in valid_log_levels:
            raise ValueError(
                f"Ungültiger Log-Level: '{self.log_level}'. Erlaubt: {valid_log_levels}"
            )
        if not (1 <= self.top_n_accounts <= 1000):
            raise ValueError(
                f"top_n_accounts muss zwischen 1 und 1000 liegen, ist: {self.top_n_accounts}"
            )
        if not (0.0 <= self.min_risk_score_threshold <= 100.0):
            raise ValueError(
                f"min_risk_score_threshold muss 0-100 sein, ist: {self.min_risk_score_threshold}"
            )


def setup_logging(config: PipelineConfig) -> None:
    """
    Konfiguriert das strukturierte Logging für die gesamte Pipeline.
    Warum: Zentralisiertes Logging-Setup stellt sicher, dass alle Module
    dasselbe Format und Level verwenden – keine inkonsistenten print()-Aufrufe.
    """
    log_format = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    handlers: list[logging.Handler] = [logging.StreamHandler()]

    if config.log_file is not None:
        config.log_file.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(config.log_file, encoding="utf-8"))

    logging.basicConfig(
        level=getattr(logging, config.log_level),
        format=log_format,
        datefmt=date_format,
        handlers=handlers,
    )
    logger.info("Logging konfiguriert: Level=%s", config.log_level)
