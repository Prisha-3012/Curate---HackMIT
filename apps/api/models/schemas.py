"""Source of truth for every shape crossing the API boundary.

Mirrors ARCHITECTURE.md §4. Field names are snake_case exactly as §4 prints them.
SHARED FILE — ping the group before editing. If this and §4 disagree, one of them
is a bug; say so rather than quietly bending the model.

Drift from §4 that is deliberate, and why, is marked DRIFT below.
"""

from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Rung(str, Enum):
    """The ladder, in the order the resolver walks it."""

    OWN = "OWN"
    BORROW = "BORROW"
    USED = "USED"
    NEW = "NEW"


class Category(str, Enum):
    """listings.category / needs.category, per §3."""

    TOP = "top"
    BOTTOM = "bottom"
    OUTERWEAR = "outerwear"
    FOOTWEAR = "footwear"
    OTHER = "other"


class ConfidenceBand(str, Enum):
    """§5 bands: HIGH >= 0.75 · MEDIUM 0.50-0.74 · LOW < 0.50."""

    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


#: Categories that FitCheck can actually size. POST /api/fitcheck takes
#: garment=top|bottom and the size charts cover only those, so an option outside
#: this set can never be fit-checked and must never carry needs_fitcheck=True.
FITCHECKABLE = frozenset({Category.TOP, Category.BOTTOM})

#: Rungs where the item is not already in the user's hands, so fit is a real risk.
FITCHECK_RUNGS = frozenset({Rung.USED, Rung.NEW})


def needs_fitcheck_for(category: "Category | str", rung: Rung) -> bool:
    """The single place the FitCheck gate is decided.

    DRIFT (§1/§4): §1 gates on "NEW or USED and it's apparel", and §4's worked
    example marks a USED *shoe* needs_fitcheck=True. But /api/fitcheck accepts only
    garment=top|bottom, so a flagged shoe is a promise the API cannot keep. Resolved
    with Prisha 2026-09-19: flag top/bottom only. Raise with A if footwear sizing
    lands later.
    """
    # Categories are free-form strings since 2026-09-19 (domain-agnostic goals),
    # so an unknown category is simply not fit-checkable rather than an error.
    try:
        cat = Category(category) if not isinstance(category, Category) else category
    except ValueError:
        return False
    return cat in FITCHECKABLE and rung in FITCHECK_RUNGS


class Base(BaseModel):
    """Reject unknown keys so contract drift fails loudly instead of silently."""

    model_config = ConfigDict(extra="forbid", use_enum_values=False)


# --------------------------------------------------------------------------
# POST /api/mission
# --------------------------------------------------------------------------


class MissionRequest(Base):
    user_id: str
    goal_text: str
    budget_cents: int = Field(ge=0)


class Option(Base):
    """One way to satisfy a need, on one rung."""

    listing_id: str
    rung: Rung
    title: str
    owner_label: str  # "you", "Poshmark seller", a friend's name
    price_cents: int = Field(ge=0)  # 0 for OWN and BORROW
    retail_cents: int = Field(ge=0)  # what it costs new; savings baseline
    #: DRIFT (§4): the OWN example carries image_url, the USED one omits it.
    #: Optional until §4 says otherwise.
    image_url: Optional[str] = None
    match_score: float = Field(ge=0.0, le=1.0)
    why: str
    needs_fitcheck: bool


class Need(Base):
    """One real need decomposed out of the goal.

    DRIFT (§3/§4): the needs table also has `category` and `attrs`. §4 does not
    serialize them, so they stay server-side; the resolver reads them off the row.
    Do not add them here without telling C, who renders this object.

    UNMET NEEDS (§4 extension, 2026-09-19): a need with no candidate anywhere on
    the ladder stays in the plan with `options: []`,
    `recommended_listing_id: null` and an `unmet_reason` string. Dropping it
    instead would silently shrink the plan and flatter the impact number, which
    is the one thing the impact number must never do.

    BREAKING for consumers: recommended_listing_id is now nullable. Anything
    rendering it must handle null.
    """

    need_id: str
    label: str
    rationale: str
    priority: int = Field(ge=1, le=2)  # 1 = essential, 2 = nice-to-have
    options: list[Option]
    #: null when the need is unmet. See unmet_reason.
    recommended_listing_id: Optional[str] = None
    #: Set only when options is empty. Human-readable, shown in the UI.
    unmet_reason: Optional[str] = None

    @model_validator(mode="after")
    def _unmet_needs_are_coherent(self) -> "Need":
        """The invariant, keyed on the recommendation rather than on options:

            recommended != null  -> it is one of this need's options, no reason
            recommended == null  -> unmet_reason is set; options MAY be non-empty

        Options are allowed on an unmet need because "three options exist, none
        within your budget" is materially different information from "nothing
        exists", and collapsing them would make the plan less truthful.
        """
        if self.recommended_listing_id is not None:
            if self.unmet_reason:
                raise ValueError("a met need must not carry an unmet_reason")
            ids = {o.listing_id for o in self.options}
            if self.recommended_listing_id not in ids:
                raise ValueError(
                    f"recommended_listing_id {self.recommended_listing_id} "
                    f"is not among this need's own options"
                )
        elif not self.unmet_reason:
            raise ValueError("a need with no recommendation must say why")
        return self


class Impact(Base):
    baseline_cents: int = Field(ge=0)  # cost if every need were bought NEW
    plan_cents: int = Field(ge=0)  # cost of recommended options
    saved_cents: int
    items_reused: int = Field(ge=0)
    textile_kg_avoided: float = Field(ge=0.0)
    assumptions_note: str


class Plan(Base):
    """The whole product. Frontend renders it, voice reads it, checkout eats one
    option out of it. GET /api/mission/{id} returns this same object."""

    mission_id: str
    goal_text: str
    budget_cents: int = Field(ge=0)
    needs: list[Need]
    impact: Impact


# --------------------------------------------------------------------------
# POST /api/fitcheck  — A's lane. Defined here so checkout can gate on it.
# --------------------------------------------------------------------------


class MeasurementValue(Base):
    """§4: never return a bare number. Always value + range."""

    value: float
    range: list[float] = Field(min_length=2, max_length=2)


class Measurements(Base):
    chest_cm: MeasurementValue
    shoulder_cm: MeasurementValue
    waist_cm: MeasurementValue


class SizeRecommendation(Base):
    brand: str
    size_label: str
    alternate_size: Optional[str] = None
    note: str
    return_risk: Literal["low", "medium", "high"]


class FitCheckResult(Base):
    measurement_id: str
    measurements: Measurements
    confidence: float = Field(ge=0.0, le=1.0)
    confidence_band: ConfidenceBand
    confidence_reason: str
    recommendation: SizeRecommendation


# --------------------------------------------------------------------------
# POST /api/checkout
# --------------------------------------------------------------------------


class CheckoutRequest(Base):
    user_id: str
    listing_id: str
    measurement_id: Optional[str] = None  # null if non-apparel
    size_label: Optional[str] = None


class CheckoutResponse(Base):
    #: DRIFT (§4): only "approved" is shown. Declines and gateway errors are real;
    #: C and D need to handle all three.
    status: Literal["approved", "declined", "error"]
    txn_id: str
    amount_cents: int = Field(ge=0)
    #: DRIFT (§4): Cybersource returns no receipt URL. We synthesize a local one.
    receipt_url: Optional[str] = None


# --------------------------------------------------------------------------
# Voice — §4. Backend routes are B's per 2026-09-19; frontend stays C's.
# --------------------------------------------------------------------------


class TranscribeResponse(Base):
    text: str


class SpeakRequest(Base):
    text: str
