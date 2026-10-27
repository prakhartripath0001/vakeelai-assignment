from typing import Literal

from pydantic import BaseModel, Field, field_validator

DraftType = Literal["legal_notice", "civil_plaint", "affidavit"]


class DraftRequest(BaseModel):
    document_type: DraftType
    court_name: str = Field(min_length=1, max_length=300)
    petitioner: str = Field(min_length=1, max_length=300)
    respondent: str = Field(min_length=1, max_length=300)
    facts: str = Field(min_length=20, max_length=10000)
    relief_sought: str = Field(min_length=1, max_length=3000)
    jurisdiction: str = Field(min_length=1, max_length=3000)
    date: str = Field(min_length=1, max_length=100)
    advocate_name: str = Field(min_length=1, max_length=300)
    notice_period_days: int = Field(default=15, ge=1, le=90)

    @field_validator(
        "court_name",
        "petitioner",
        "respondent",
        "facts",
        "relief_sought",
        "jurisdiction",
        "date",
        "advocate_name",
    )
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("This field must not be blank.")
        return cleaned


def generate_draft(request: DraftRequest) -> dict[str, object]:
    """Render a deterministic template; no model or external service is involved."""
    data = request.model_dump()
    if request.document_type == "legal_notice":
        sections = [
            ("From", f"{data['petitioner']}, through {data['advocate_name']}"),
            ("To", data["respondent"]),
            (
                "Subject",
                f"Legal notice concerning {data['relief_sought']}",
            ),
            ("Statement of facts", data["facts"]),
            (
                "Demand",
                (
                    f"You are called upon to {data['relief_sought']} within "
                    f"{data['notice_period_days']} days of receipt of this notice."
                ),
            ),
            (
                "Reservation of rights",
                (
                    "If you do not comply within the period stated above, my client "
                    "may pursue remedies available under applicable law, at your risk "
                    "as to costs and consequences."
                ),
            ),
            ("Date", data["date"]),
            ("Counsel", data["advocate_name"]),
        ]
        title = "Legal Notice"
    elif request.document_type == "civil_plaint":
        sections = [
            ("Court", data["court_name"]),
            ("Cause title", f"{data['petitioner']} v. {data['respondent']}"),
            ("Parties", f"Plaintiff: {data['petitioner']}\nDefendant: {data['respondent']}"),
            ("Material facts", data["facts"]),
            ("Jurisdiction", data["jurisdiction"]),
            ("Relief sought", data["relief_sought"]),
            (
                "Verification",
                (
                    f"I, {data['petitioner']}, verify that the statements made above "
                    "are true to my knowledge and belief.\n"
                    f"Place: ____________________    Date: {data['date']}\n"
                    "Plaintiff"
                ),
            ),
            ("Counsel", data["advocate_name"]),
        ]
        title = "Civil Plaint"
    else:
        sections = [
            ("Court", data["court_name"]),
            ("Title", "Affidavit"),
            (
                "Deponent",
                (
                    f"I, {data['petitioner']}, state on oath in the matter concerning "
                    f"{data['respondent']}:"
                ),
            ),
            ("Statement", data["facts"]),
            ("Jurisdiction / context", data["jurisdiction"]),
            (
                "Verification",
                (
                    f"I verify that the contents above are true to my knowledge and "
                    f"belief. Verified at ____________________ on {data['date']}.\n"
                    "Deponent"
                ),
            ),
            ("Counsel", data["advocate_name"]),
        ]
        title = "Affidavit"

    rendered_sections = [
        {"heading": heading, "body": body} for heading, body in sections
    ]
    full_text = "\n\n".join(
        f"{section['heading'].upper()}\n{section['body']}"
        for section in rendered_sections
    )
    return {
        "document_type": request.document_type,
        "title": title,
        "sections": rendered_sections,
        "full_text": full_text,
        "disclaimer": (
            "This is a general template generated from the supplied information, "
            "not legal advice. Have an advocate verify facts, law, forum, limitation, "
            "and filing requirements before use."
        ),
    }
