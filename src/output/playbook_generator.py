"""
Playbook Generator: Erstellt priorisierte Action Items aus Risk Assessments.
Warum: Der Pain Point ist nicht das Fehlen von Signalen, sondern dass
niemand weiß, WAS er tun soll. Der Playbook Generator mappt Reason Codes
auf konkrete, segment-spezifische Handlungsanweisungen.
"""

import logging
from typing import Callable

from src.exceptions import PlaybookGenerationError
from src.models.playbook import ActionItem, PlaybookAction, Playbook
from src.models.risk_assessment import CustomerSegment, RiskAssessment, RiskLevel
from src.output.kpi_estimator import KpiEstimator

logger = logging.getLogger(__name__)

# --- Action-Mapping: Reason Code → PlaybookAction ---
# Warum als Dict statt If-Else-Kette: Erweiterbar ohne Code-Änderungen
_REASON_TO_ACTION: dict[str, PlaybookAction] = {
    "LOGIN_DROP_CRITICAL": PlaybookAction.EXECUTIVE_SPONSOR_OUTREACH,
    "LOGIN_DROP_MODERATE": PlaybookAction.CS_DEEP_DIVE_CALL,
    "LOGIN_TREND_NEGATIVE": PlaybookAction.FEATURE_ADOPTION_CAMPAIGN,
    "HIGH_ESCALATION_RATE": PlaybookAction.PROACTIVE_SUPPORT_REVIEW,
    "HIGH_OPEN_TICKET_LOAD": PlaybookAction.TECHNICAL_HEALTH_CHECK,
    "NPS_POOR": PlaybookAction.NPS_RECOVERY_PROGRAM,
    "NPS_DECLINING": PlaybookAction.NPS_RECOVERY_PROGRAM,
    "LOW_FEATURE_ADOPTION": PlaybookAction.FEATURE_ADOPTION_CAMPAIGN,
    "USER_ACTIVITY_DROP": PlaybookAction.CS_DEEP_DIVE_CALL,
    "CONTRACT_RENEWAL_IMMINENT": PlaybookAction.CONTRACT_RENEWAL_NEGOTIATION,
}

# --- Action-Templates: segment-spezifische Beschreibungen ---
ActionTemplate = dict[str, str | int]

_ACTION_TEMPLATES: dict[PlaybookAction, dict[CustomerSegment, ActionTemplate]] = {
    PlaybookAction.EXECUTIVE_SPONSOR_OUTREACH: {
        CustomerSegment.HIGH_VALUE: {
            "title": "Executive Sponsor Call (VP-Level)",
            "description": (
                "Sofortiger Anruf durch VP Customer Success oder CRO mit dem "
                "Executive Sponsor des Accounts. Agenda: QBR vorziehen, "
                "Roadmap-Preview, strategische Wertdemonstration."
            ),
            "owner": "VP Customer Success",
            "timeline_days": 3,
        },
        CustomerSegment.MID_MARKET: {
            "title": "Executive Sponsor Outreach",
            "description": (
                "Persönlicher Anruf durch Senior CSM beim Executive Sponsor. "
                "Fokus: Kurzfristiger Health Check und Commitment-Renewal."
            ),
            "owner": "Senior CSM",
            "timeline_days": 5,
        },
        CustomerSegment.SMB: {
            "title": "Account Health Call",
            "description": (
                "CSM-geführter Health-Check-Call. Kurz-QBR, "
                "Value-Recap der letzten 90 Tage."
            ),
            "owner": "CSM",
            "timeline_days": 7,
        },
    },
    PlaybookAction.CS_DEEP_DIVE_CALL: {
        CustomerSegment.HIGH_VALUE: {
            "title": "CS Deep Dive (strukturiertes Gespräch)",
            "description": (
                "2h-strukturiertes Interview mit Key-User-Gruppe: "
                "Workflow-Analyse, Blocker-Identifikation, Feedback-Loop."
            ),
            "owner": "Senior CSM + Solutions Engineer",
            "timeline_days": 5,
        },
        CustomerSegment.MID_MARKET: {
            "title": "CS Deep Dive Call",
            "description": (
                "60-minütiger strukturierter Call: Nutzungsbarrieren identifizieren, "
                "Use-Case-Review, Next Steps definieren."
            ),
            "owner": "CSM",
            "timeline_days": 7,
        },
        CustomerSegment.SMB: {
            "title": "User-Check-in Call",
            "description": "30-minütiger Check-in: Feedback und Blocker erfragen.",
            "owner": "CSM",
            "timeline_days": 10,
        },
    },
    PlaybookAction.FEATURE_ADOPTION_CAMPAIGN: {
        CustomerSegment.HIGH_VALUE: {
            "title": "Personalisierte Adoption-Campaign",
            "description": (
                "Maßgeschneidertes Enablement-Programm: Dedizierte Onboarding-Sessions "
                "für nicht genutzte High-Value-Features, 1:1-Training."
            ),
            "owner": "CSM + Customer Education",
            "timeline_days": 14,
        },
        CustomerSegment.MID_MARKET: {
            "title": "Feature Adoption Workshop",
            "description": (
                "Gruppen-Webinar: Top-3 ungenutzten Features präsentieren, "
                "Use Cases zeigen, Q&A."
            ),
            "owner": "CSM",
            "timeline_days": 14,
        },
        CustomerSegment.SMB: {
            "title": "Feature-Tipp-E-Mail-Serie",
            "description": "Automatisierte 3-teilige E-Mail-Serie zu ungenutzten Features.",
            "owner": "CSM (triggert Automation)",
            "timeline_days": 21,
        },
    },
    PlaybookAction.NPS_RECOVERY_PROGRAM: {
        CustomerSegment.HIGH_VALUE: {
            "title": "NPS Recovery: Executive-Led Save",
            "description": (
                "Detractor-Recovery-Programm: Executive-Sponsor-Call, "
                "dedizierter Issue-Backlog, monatlicher Progress-Report."
            ),
            "owner": "VP Customer Success + CSM",
            "timeline_days": 7,
        },
        CustomerSegment.MID_MARKET: {
            "title": "NPS Recovery: Root Cause Call",
            "description": (
                "Strukturierter Root-Cause-Call: Top 3 Beschwerden erfassen, "
                "Lösungsplan präsentieren, Follow-up in 30 Tagen."
            ),
            "owner": "CSM",
            "timeline_days": 7,
        },
        CustomerSegment.SMB: {
            "title": "NPS Recovery: Feedback-Call",
            "description": "15-minütiger Feedback-Call mit konkretem Action Item.",
            "owner": "CSM",
            "timeline_days": 10,
        },
    },
    PlaybookAction.CONTRACT_RENEWAL_NEGOTIATION: {
        CustomerSegment.HIGH_VALUE: {
            "title": "Strategic Renewal Review (Executive-Level)",
            "description": (
                "Multi-Stakeholder-Meeting: QBR + Renewal-Proposal + "
                "Executive Sponsor Alignment. Ziel: Verlängerung + Upsell."
            ),
            "owner": "Account Executive + VP CS",
            "timeline_days": 14,
        },
        CustomerSegment.MID_MARKET: {
            "title": "Renewal Discovery Call",
            "description": (
                "Discovery-Gespräch zu Verlängerungsoptionen: "
                "Bedürfnisanalyse, Angebotspräsentation."
            ),
            "owner": "Account Executive",
            "timeline_days": 14,
        },
        CustomerSegment.SMB: {
            "title": "Renewal-Angebot versenden",
            "description": "Renewal-Angebot mit Early-Bird-Incentive per E-Mail.",
            "owner": "Account Executive",
            "timeline_days": 21,
        },
    },
    PlaybookAction.TECHNICAL_HEALTH_CHECK: {
        CustomerSegment.HIGH_VALUE: {
            "title": "Technical Health Audit",
            "description": (
                "Vollständiger technischer Audit: Integration-Health, "
                "Performance-Metrics, Custom-Config-Review."
            ),
            "owner": "Solutions Engineer",
            "timeline_days": 10,
        },
        CustomerSegment.MID_MARKET: {
            "title": "Technical Health Check",
            "description": "Integration- und Konfigurationscheck, Optimierungsempfehlungen.",
            "owner": "CSM + Support",
            "timeline_days": 14,
        },
        CustomerSegment.SMB: {
            "title": "Support Health Review",
            "description": "Review aller offenen Tickets, Priorisierung und Eskalation.",
            "owner": "Support Lead",
            "timeline_days": 5,
        },
    },
    PlaybookAction.PROACTIVE_SUPPORT_REVIEW: {
        CustomerSegment.HIGH_VALUE: {
            "title": "Proaktiver Support-Eskalations-Review",
            "description": (
                "Sofortige Eskalation aller offenen Tickets auf Senior-Support-Level. "
                "Tägliches Status-Update an CSM."
            ),
            "owner": "Senior Support + CSM",
            "timeline_days": 2,
        },
        CustomerSegment.MID_MARKET: {
            "title": "Support-Issue-Prioritisierung",
            "description": "Review aller Tickets, SLA-Prüfung, Priorisierung kritischer Issues.",
            "owner": "Support Lead",
            "timeline_days": 3,
        },
        CustomerSegment.SMB: {
            "title": "Ticket-Follow-up",
            "description": "Proaktiver Anruf zum Status der offenen Tickets.",
            "owner": "Support",
            "timeline_days": 5,
        },
    },
    PlaybookAction.EXECUTIVE_BUSINESS_REVIEW: {
        CustomerSegment.HIGH_VALUE: {
            "title": "Emergency QBR (vorgezogen)",
            "description": (
                "Vorgezogenes Quarterly Business Review mit C-Level-Beteiligung. "
                "ROI-Präsentation, Roadmap-Alignment."
            ),
            "owner": "VP Customer Success",
            "timeline_days": 7,
        },
        CustomerSegment.MID_MARKET: {
            "title": "Business Review Call",
            "description": "Executive-Summary-Präsentation: Ergebnisse der letzten 90 Tage.",
            "owner": "Senior CSM",
            "timeline_days": 14,
        },
        CustomerSegment.SMB: {
            "title": "Value-Check E-Mail",
            "description": "Automatisierte Value-Recap-E-Mail mit Key-Metriken.",
            "owner": "CSM (triggert Automation)",
            "timeline_days": 21,
        },
    },
}


class PlaybookGenerator:
    """
    Generiert priorisierte Playbooks für at-risk Accounts.

    Input:  RiskAssessment
    Output: Playbook mit ActionItems und KPI Impact
    """

    def __init__(self, kpi_estimator: KpiEstimator) -> None:
        self._kpi_estimator = kpi_estimator

    def generate(self, assessment: RiskAssessment) -> Playbook:
        """
        Erstellt ein vollständiges Playbook für einen Account.

        Raises:
            PlaybookGenerationError: Bei unerwarteten Fehlern.
        """
        try:
            action_items = self._build_action_items(assessment)
            kpi_impact = self._kpi_estimator.estimate(assessment)
            summary = self._generate_summary(assessment, action_items)

            playbook = Playbook(
                account_id=assessment.account_id,
                account_name=assessment.account_name,
                risk_score=assessment.risk_score,
                risk_level=assessment.risk_level.value,
                segment=assessment.segment.value,
                action_items=tuple(action_items),
                kpi_impact=kpi_impact,
                summary=summary,
            )

            logger.info(
                "Playbook für '%s' erstellt: %d Actions, ARR-at-Risk=€%.0f",
                assessment.account_id, len(action_items), assessment.arr_at_risk,
            )
            return playbook

        except Exception as e:
            raise PlaybookGenerationError(
                f"Playbook-Generierung für Account '{assessment.account_id}' fehlgeschlagen: {e}"
            ) from e

    def _build_action_items(self, assessment: RiskAssessment) -> list[ActionItem]:
        """
        Mappt Reason Codes auf Actions und dedupliziert (gleiche Action nur einmal).
        Sortierung: nach Reason-Code-Impact (höchster Impact → höchste Priorität).
        """
        seen_actions: set[PlaybookAction] = set()
        items: list[ActionItem] = []
        priority = 1

        for reason in assessment.reason_codes:
            action_type = _REASON_TO_ACTION.get(reason.code)
            if action_type is None or action_type in seen_actions:
                continue

            template = self._get_template(action_type, assessment.segment)
            if template is None:
                logger.warning(
                    "Kein Template für Action '%s' / Segment '%s'.",
                    action_type.value, assessment.segment.value,
                )
                continue

            items.append(ActionItem(
                action=action_type,
                priority=priority,
                title=str(template["title"]),
                description=str(template["description"]),
                recommended_owner=str(template["owner"]),
                suggested_timeline_days=int(template["timeline_days"]),
                triggered_by=reason.code,
            ))
            seen_actions.add(action_type)
            priority += 1

        # Kritische Accounts (CRITICAL) immer mit EBR ergänzen
        if (
            assessment.risk_level == RiskLevel.CRITICAL
            and PlaybookAction.EXECUTIVE_BUSINESS_REVIEW not in seen_actions
        ):
            template = self._get_template(
                PlaybookAction.EXECUTIVE_BUSINESS_REVIEW, assessment.segment
            )
            if template:
                items.append(ActionItem(
                    action=PlaybookAction.EXECUTIVE_BUSINESS_REVIEW,
                    priority=priority,
                    title=str(template["title"]),
                    description=str(template["description"]),
                    recommended_owner=str(template["owner"]),
                    suggested_timeline_days=int(template["timeline_days"]),
                    triggered_by="CRITICAL_RISK_AUTO",
                ))

        return items

    @staticmethod
    def _get_template(
        action: PlaybookAction, segment: CustomerSegment
    ) -> ActionTemplate | None:
        """Gibt das segment-spezifische Template zurück, Fallback auf SMB."""
        action_templates = _ACTION_TEMPLATES.get(action)
        if not action_templates:
            return None
        return action_templates.get(segment) or action_templates.get(CustomerSegment.SMB)

    @staticmethod
    def _generate_summary(assessment: RiskAssessment, actions: list[ActionItem]) -> str:
        """Einzeiler für Executive Summary und Slack-Alert."""
        top_reason = (
            assessment.reason_codes[0].label
            if assessment.reason_codes
            else "Mehrere Signale"
        )
        first_action = actions[0].title if actions else "Manuelle Prüfung"
        return (
            f"[{assessment.risk_level.value}] {assessment.account_name} "
            f"(Score: {assessment.risk_score:.0f}, €{assessment.arr_at_risk:,.0f} at risk) – "
            f"Hauptsignal: {top_reason}. Empfehlung: {first_action}."
        )
