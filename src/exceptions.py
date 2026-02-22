"""
Domain-spezifische Exception-Hierarchie.
Warum: Generische `except Exception`-Blöcke verbergen Fehlerursachen.
Jede Schicht der Pipeline hat eigene, semantisch korrekte Fehlertypen,
die gezieltes Logging und kontrollierte Fallbacks ermöglichen.
"""


class ChurnPipelineError(Exception):
    """Basis-Exception für alle Fehler in der Churn-Pipeline."""
    pass


# --- Ingestion Layer ---

class DataIngestionError(ChurnPipelineError):
    """Fehler beim Laden von Rohdaten aus einer Quelle."""
    pass


class DataValidationError(ChurnPipelineError):
    """Schema-Verletzung oder ungültige Eingabedaten (Pydantic/Pandera)."""
    pass


# --- Processing Layer ---

class FeatureEngineeringError(ChurnPipelineError):
    """Fehler während der Feature-Berechnung (z.B. fehlende Zeitreihen)."""
    pass


class RiskScoringError(ChurnPipelineError):
    """Fehler beim Berechnen des Churn-Risk-Scores."""
    pass


class SegmentationError(ChurnPipelineError):
    """Fehler bei der Kundensegmentierung."""
    pass


class ReasonCodeError(ChurnPipelineError):
    """Fehler beim Generieren von Explainability-Reason-Codes."""
    pass


# --- Output Layer ---

class PlaybookGenerationError(ChurnPipelineError):
    """Fehler beim Erstellen des Handlungs-Playbooks für einen Account."""
    pass


class KpiEstimationError(ChurnPipelineError):
    """Fehler bei der KPI-Impact-Schätzung (z.B. ARR-Berechnung)."""
    pass


# --- Quality Gate ---

class DataLeakageDetectedError(ChurnPipelineError):
    """
    Kritischer Fehler: Future-Data-Leakage wurde erkannt.
    Warum als eigene Exception: Ein Data-Leakage invalidiert das gesamte
    Modell und muss als CRITICAL-Event behandelt werden, das die Pipeline
    sofort stoppt.
    """
    pass


class InsufficientDataError(ChurnPipelineError):
    """Zu wenige Datenpunkte für eine statistisch valide Aussage."""
    pass
