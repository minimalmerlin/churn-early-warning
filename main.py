"""
Churn Early Warning + Playbook Generator
Einstiegspunkt der Applikation.

Usage:
    python main.py
    CHURN_TOP_N_ACCOUNTS=10 python main.py
    CHURN_DATA_SOURCE=data/my_events.csv python main.py
"""

import sys

from config.settings import PipelineConfig, setup_logging
from src.exceptions import ChurnPipelineError
from src.pipeline import ChurnPipeline
from src.reporting.console_reporter import ConsoleReporter


def main() -> int:
    """
    Startet die Pipeline und gibt den Exit-Code zurück.

    Returns:
        0 bei Erfolg, 1 bei Fehler.
    """
    config = PipelineConfig()
    setup_logging(config)

    import logging
    logger = logging.getLogger(__name__)

    try:
        pipeline = ChurnPipeline(config)
        result = pipeline.run()

        reporter = ConsoleReporter()
        reporter.report(result)

        return 0

    except ChurnPipelineError as e:
        import logging
        logging.getLogger(__name__).critical(
            "PIPELINE FEHLGESCHLAGEN: %s", e, exc_info=True
        )
        return 1
    except Exception as e:
        import logging
        logging.getLogger(__name__).critical(
            "UNERWARTETER FEHLER: %s", e, exc_info=True
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
