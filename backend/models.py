
from datetime import datetime

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


class Case(Base):
    # Each record represents one court case.
    __tablename__ = "cases"

    # CNR is the unique identifier for a case.
    cnr_number: Mapped[str] = mapped_column(
        String(16),
        primary_key=True,
    )

    # Case title, for example: Punjab National Bank vs Sunil Kumar.
    case_title: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    court_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    case_status: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    filing_date: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    # Store the full structured response as JSON text for now.
    # This preserves additional portal fields we haven't modeled yet.
    raw_data: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Track when this record was first created.
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        nullable=False,
    )

    # Track when this record was last updated.
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
