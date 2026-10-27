import pytest
from pydantic import ValidationError

from backend.drafts import DraftRequest, generate_draft


@pytest.mark.parametrize(
    ("document_type", "expected_heading"),
    [
        ("legal_notice", "Demand"),
        ("civil_plaint", "Material facts"),
        ("affidavit", "Verification"),
    ],
)
def test_draft_templates_are_structured_and_use_supplied_facts(
    document_type: str, expected_heading: str
):
    request = DraftRequest(
        document_type=document_type,
        court_name="District Court",
        petitioner="Asha Rao",
        respondent="Ravi Shah",
        facts="The parties entered into an agreement and the respondent did not perform.",
        relief_sought="perform the agreement",
        jurisdiction="The events took place within this court's territorial jurisdiction.",
        date="27 October 2026",
        advocate_name="Advocate Meera",
        notice_period_days=21,
    )

    draft = generate_draft(request)

    assert draft["document_type"] == document_type
    assert draft["title"]
    assert any(section["heading"] == expected_heading for section in draft["sections"])
    assert "Asha Rao" in draft["full_text"]
    assert "Advocate Meera" in draft["full_text"]
    assert "not legal advice" in draft["disclaimer"]


def test_draft_rejects_blank_party_name():
    with pytest.raises(ValidationError):
        DraftRequest(
            document_type="affidavit",
            court_name="District Court",
            petitioner=" ",
            respondent="Ravi Shah",
            facts="The parties entered into an agreement and the respondent did not perform.",
            relief_sought="perform the agreement",
            jurisdiction="The events took place within this court's territorial jurisdiction.",
            date="27 October 2026",
            advocate_name="Advocate Meera",
        )
