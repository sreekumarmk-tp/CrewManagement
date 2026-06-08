"""
SQLAlchemy ORM model for the L4 Precedent Index (placement history store).

A PlacementPrecedent is one COMPLETED placement, flattened into indexed columns so
it can be looked up cheaply by the vacancy profile (rank / grade / port). Each row
records both the vacancy that was being filled (the departing crew's attributes —
the lookup key) and the result (who was chosen + how it turned out).

When a new sign-off begins, the matching layer consults this table for the same
vacancy profile; on the 2nd+ time a given profile is filled, the lookup returns
the earlier placements. Derived from the decision_traces row at outcome time.
"""
from datetime import datetime

from sqlalchemy import Column, DateTime, Float, String

from database.db import Base


class PlacementPrecedent(Base):
    __tablename__ = "placement_precedents"

    precedent_id = Column(String, primary_key=True)         # uuid
    decision_id = Column(String, index=True)                # originating decision
    workflow_id = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    # ── Vacancy profile = the LOOKUP KEY (departing crew's attributes) ─────────
    rank = Column(String, index=True)
    grade = Column(String)
    port = Column(String, index=True)
    nationality = Column(String)

    # ── Result of that placement ───────────────────────────────────────────────
    chosen_crew_id = Column(String)
    chosen_crew_name = Column(String)
    chosen_crew_rank = Column(String)
    # Chosen crew's own profile — the LOOKUP RESULT the L4 #3 feedback loop keys
    # on: a repeat vacancy boosts candidates matching the nationality/grade that
    # previously signed on cleanly (and penalizes ones that were rejected).
    chosen_crew_nationality = Column(String)
    chosen_crew_grade = Column(String)
    confidence_score = Column(Float)
    outcome_status = Column(String)        # signed_on | rejected
    compliance_status = Column(String)
    compliance_score = Column(Float)

    def to_dict(self) -> dict:
        return {
            "precedent_id": self.precedent_id,
            "decision_id": self.decision_id,
            "workflow_id": self.workflow_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "rank": self.rank,
            "grade": self.grade,
            "port": self.port,
            "nationality": self.nationality,
            "chosen_crew_id": self.chosen_crew_id,
            "chosen_crew_name": self.chosen_crew_name,
            "chosen_crew_rank": self.chosen_crew_rank,
            "chosen_crew_nationality": self.chosen_crew_nationality,
            "chosen_crew_grade": self.chosen_crew_grade,
            "confidence_score": self.confidence_score,
            "outcome_status": self.outcome_status,
            "compliance_status": self.compliance_status,
            "compliance_score": self.compliance_score,
        }
