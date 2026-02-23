"""
FastAPI Routes: Definiert alle API-Endpunkte.
Warum separate Datei: Route-Definitionen sind I/O-Layer – sie dürfen
keine Business Logic enthalten. Separation of Concerns.
"""

import logging
import tempfile
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app.schemas.api_schemas import (
    ActionItemResponse,
    AnalyzeResponse,
    KpiImpactResponse,
    PlaybookResponse,
    RankedAccountResponse,
    ReasonCodeResponse,
    SummaryStats,
)
from config.settings import PipelineConfig
from src.exceptions import (
    ChurnPipelineError,
    DataIngestionError,
    DataLeakageDetectedError,
    DataValidationError,
    InsufficientDataError,
)
from src.pipeline import ChurnPipeline, PipelineResult

logger = logging.getLogger(__name__)

router = APIRouter()

_SAMPLE_CSV_PATH = Path("data/sample/customer_events_sample.csv")
_MAX_UPLOAD_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze(file: UploadFile) -> AnalyzeResponse:
    """
    Analysiert hochgeladene Customer-Event-CSV und gibt Risk Ranking + Playbooks zurück.

    Args:
        file: CSV-Datei mit Customer Events (multipart/form-data).

    Returns:
        AnalyzeResponse mit Ranking, Playbooks und KPI-Summary.

    Raises:
        HTTP 400: Bei ungültiger CSV oder Validierungsfehlern.
        HTTP 422: Bei Data-Leakage-Erkennung.
        HTTP 500: Bei unerwarteten internen Fehlern.
    """
    logger.info("Analyze-Request erhalten: Dateiname='%s'", file.filename)

    # Pre-Condition: Datei-Typ prüfen
    if file.content_type not in ("text/csv", "application/csv", "application/octet-stream"):
        if not (file.filename or "").endswith(".csv"):
            raise HTTPException(
                status_code=400,
                detail="Nur CSV-Dateien werden akzeptiert.",
            )

    content = await file.read()

    # Pre-Condition: Dateigröße prüfen
    if len(content) > _MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Datei zu groß. Maximum: {_MAX_UPLOAD_SIZE_BYTES // 1024 // 1024} MB.",
        )

    # Warum NamedTemporaryFile: Die Pipeline erwartet einen Dateipfad.
    # TemporaryFile ist sicherer als einen permanenten Upload-Ordner zu verwalten.
    with tempfile.NamedTemporaryFile(
        mode="wb", suffix=".csv", delete=True
    ) as tmp:
        tmp.write(content)
        tmp.flush()
        tmp_path = Path(tmp.name)

        try:
            result = _run_pipeline(tmp_path)
        except (DataIngestionError, DataValidationError, InsufficientDataError) as e:
            logger.warning("Ungültige CSV-Daten: %s", e)
            raise HTTPException(status_code=400, detail=str(e))
        except DataLeakageDetectedError as e:
            logger.error("Data Leakage erkannt: %s", e)
            raise HTTPException(status_code=422, detail=str(e))
        except ChurnPipelineError as e:
            logger.error("Pipeline-Fehler: %s", e)
            raise HTTPException(status_code=500, detail=str(e))

    return _map_result_to_response(result)


@router.get("/sample")
async def download_sample() -> FileResponse:
    """
    Gibt die Sample-CSV zum Download zurück.
    Ermöglicht Nutzern das korrekte CSV-Format zu verstehen.
    """
    if not _SAMPLE_CSV_PATH.exists():
        raise HTTPException(status_code=404, detail="Sample-Datei nicht gefunden.")

    return FileResponse(
        path=str(_SAMPLE_CSV_PATH),
        filename="customer_events_sample.csv",
        media_type="text/csv",
    )


@router.get("/health")
async def health() -> dict[str, str]:
    """Health-Check-Endpunkt für Deployment-Monitoring."""
    return {"status": "ok"}


def _run_pipeline(csv_path: Path) -> PipelineResult:
    """
    Kapselt den Pipeline-Aufruf. Isoliert I/O-Operationen von der Route-Logik.
    Raises: ChurnPipelineError und alle Unterklassen.
    """
    config = PipelineConfig(data_source_path=csv_path)  # type: ignore[call-arg]
    pipeline = ChurnPipeline(config)
    return pipeline.run()


def _map_result_to_response(result: PipelineResult) -> AnalyzeResponse:
    """
    Mappt das Domain-PipelineResult auf das API-Response-Schema.
    Warum explizites Mapping: Keine impliziten Typ-Casts zwischen Schichten.
    """
    critical = sum(1 for a in result.ranked_accounts if a.risk_level.value == "CRITICAL")
    high = sum(1 for a in result.ranked_accounts if a.risk_level.value == "HIGH")
    medium = sum(1 for a in result.ranked_accounts if a.risk_level.value == "MEDIUM")

    summary = SummaryStats(
        total_analyzed=result.total_accounts_analyzed,
        total_arr_at_risk=result.total_arr_at_risk,
        critical_count=critical,
        high_count=high,
        medium_count=medium,
        run_date=result.run_date.isoformat(),
    )

    ranked = [
        RankedAccountResponse(
            rank=a.rank,
            account_id=a.account_id,
            account_name=a.account_name,
            risk_score=a.risk_score,
            risk_level=a.risk_level.value,
            segment=a.segment,
            arr_at_risk=a.arr_at_risk,
            top_reason=a.top_reason,
            days_to_renewal=a.days_to_renewal,
        )
        for a in result.ranked_accounts
    ]

    playbooks = [_map_playbook(pb) for pb in result.playbooks]

    return AnalyzeResponse(summary=summary, ranked_accounts=ranked, playbooks=playbooks)


def _map_playbook(pb: object) -> PlaybookResponse:
    """Mappt ein Domain-Playbook-Objekt auf das API-Response-Schema."""
    from src.models.playbook import Playbook
    assert isinstance(pb, Playbook)

    kpi = None
    if pb.kpi_impact:
        kpi = KpiImpactResponse(
            arr_at_risk=pb.kpi_impact.arr_at_risk,
            estimated_retention_probability=pb.kpi_impact.estimated_retention_probability,
            expected_arr_saved=pb.kpi_impact.expected_arr_saved,
            churn_probability_without_action=pb.kpi_impact.churn_probability_without_action,
            payback_period_days=pb.kpi_impact.payback_period_days,
        )

    actions = [
        ActionItemResponse(
            priority=item.priority,
            action=item.action.value,
            title=item.title,
            description=item.description,
            recommended_owner=item.recommended_owner,
            suggested_timeline_days=item.suggested_timeline_days,
            triggered_by=item.triggered_by,
        )
        for item in pb.action_items
    ]

    return PlaybookResponse(
        account_id=pb.account_id,
        account_name=pb.account_name,
        risk_score=pb.risk_score,
        risk_level=pb.risk_level,
        segment=pb.segment,
        summary=pb.summary,
        action_items=actions,
        kpi_impact=kpi,
    )
