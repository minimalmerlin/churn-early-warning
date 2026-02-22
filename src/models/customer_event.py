"""
Pydantic-Modelle für eingehende Customer-Event-Daten.
Warum: Schema-Validierung am System-Eingang verhindert Silent Data
Corruption in nachgelagerten Pipeline-Stufen (Design by Contract).
"""

from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class CustomerEvent(BaseModel):
    """
    Validiertes Rohdaten-Objekt für einen Kunden-Event-Record.

    Input:  Rohdaten-Row aus CSV / API / DB
    Output: Typgesichertes, valides Datenobjekt
    """

    account_id: str = Field(..., min_length=1, description="Eindeutige Account-ID")
    account_name: str = Field(..., min_length=1)
    event_date: date = Field(..., description="Datum des Events (YYYY-MM-DD)")
    annual_recurring_revenue: float = Field(
        ..., ge=0.0, description="ARR in Euro"
    )
    # --- Login-Metriken ---
    logins_last_7d: int = Field(default=0, ge=0)
    logins_last_30d: int = Field(default=0, ge=0)
    logins_last_90d: int = Field(default=0, ge=0)
    # --- Support-Metriken ---
    open_tickets: int = Field(default=0, ge=0)
    resolved_tickets_last_30d: int = Field(default=0, ge=0)
    escalated_tickets_last_90d: int = Field(default=0, ge=0)
    # --- NPS ---
    nps_score: Optional[float] = Field(
        default=None, ge=-100.0, le=100.0,
        description="Net Promoter Score (-100 bis 100). None = kein aktueller Wert."
    )
    nps_trend: Optional[float] = Field(
        default=None,
        description="NPS-Veränderung gegenüber letzter Messung (positiv = besser)."
    )
    # --- Usage-Metriken ---
    feature_adoption_rate: float = Field(
        default=0.0, ge=0.0, le=1.0,
        description="Anteil genutzter Features (0.0 bis 1.0)."
    )
    active_users_last_30d: int = Field(default=0, ge=0)
    active_users_last_90d: int = Field(default=0, ge=0)
    # --- Vertragsdaten ---
    contract_end_date: Optional[date] = Field(default=None)
    customer_segment: str = Field(
        default="SMB",
        description="HIGH_VALUE | MID_MARKET | SMB"
    )

    @field_validator("customer_segment")
    @classmethod
    def validate_segment(cls, v: str) -> str:
        """Nur definierte Segmente sind erlaubt."""
        allowed = {"HIGH_VALUE", "MID_MARKET", "SMB"}
        if v.upper() not in allowed:
            raise ValueError(f"Ungültiges Segment '{v}'. Erlaubt: {allowed}")
        return v.upper()

    @model_validator(mode="after")
    def validate_login_consistency(self) -> "CustomerEvent":
        """
        Warum: Logins_90d < Logins_30d wäre ein Data-Leakage-Indikator
        oder ein Erfassungsfehler – beides muss abgefangen werden.
        """
        if self.logins_last_30d > self.logins_last_90d:
            raise ValueError(
                f"Inkonsistente Login-Daten für Account '{self.account_id}': "
                f"logins_last_30d ({self.logins_last_30d}) > "
                f"logins_last_90d ({self.logins_last_90d})"
            )
        return self

    model_config = {"frozen": True}  # Immutability: verhindert versteckte Mutationen
