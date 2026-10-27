import logging
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal
from uuid import uuid4

import requests
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from backend.drafts import DraftRequest, generate_draft
from backend.scraper.ecourts import ECourtsScraper

logger = logging.getLogger(__name__)
SESSION_TTL_SECONDS = 15 * 60
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
FRONTEND_BUILD_DIR = FRONTEND_DIR / "dist"


@dataclass
class PortalSession:
    scraper: ECourtsScraper
    created_at: float = field(default_factory=time.monotonic)
    lock: threading.Lock = field(default_factory=threading.Lock)


class CNRSearchRequest(BaseModel):
    session_id: str = Field(min_length=1)
    cnr_number: str = Field(pattern=r"^[A-Za-z0-9]{16}$")
    captcha: str = Field(min_length=1)


class CaseNumberSearchRequest(BaseModel):
    session_id: str = Field(min_length=1)
    state_code: str = Field(min_length=1)
    district_code: str = Field(min_length=1)
    court_complex_code: str = Field(min_length=1)
    establishment_code: str = ""
    case_type: str = Field(min_length=1)
    case_number: str = Field(min_length=1)
    year: int = Field(ge=1900, le=2100)
    captcha: str = Field(min_length=1)


class CaseOptionsRequest(BaseModel):
    session_id: str = Field(min_length=1)
    scope: Literal["states", "districts", "complexes", "establishments", "case_types"]
    state_code: str | None = None
    district_code: str | None = None
    court_complex_code: str | None = None
    establishment_code: str | None = None


app = FastAPI(
    title="VakeelAI",
    description="District court case search and deterministic legal draft templates.",
    version="1.0.0",
)
app.mount(
    "/assets",
    StaticFiles(directory=FRONTEND_BUILD_DIR / "assets", check_dir=False),
    name="assets",
)
_portal_sessions: dict[str, PortalSession] = {}
_portal_sessions_lock = threading.Lock()


def _create_portal_session() -> tuple[str, PortalSession]:
    scraper = ECourtsScraper()
    scraper.get_captcha_and_token()
    session_id = str(uuid4())
    context = PortalSession(scraper=scraper)
    now = time.monotonic()
    with _portal_sessions_lock:
        expired = [
            key
            for key, value in _portal_sessions.items()
            if now - value.created_at > SESSION_TTL_SECONDS
        ]
        for key in expired:
            del _portal_sessions[key]
        _portal_sessions[session_id] = context
    return session_id, context


def _portal_session(session_id: str) -> PortalSession:
    with _portal_sessions_lock:
        context = _portal_sessions.get(session_id)
        if context is None:
            raise HTTPException(
                status_code=404,
                detail="eCourts session not found. Start a new search session.",
            )
        if time.monotonic() - context.created_at > SESSION_TTL_SECONDS:
            del _portal_sessions[session_id]
            raise HTTPException(
                status_code=410,
                detail="eCourts session expired. Start a new search session.",
            )
        return context


def _portal_error(error: Exception) -> HTTPException:
    logger.warning("eCourts request failed: %s", error)
    return HTTPException(status_code=502, detail=f"eCourts request failed: {error}")


@app.get("/", include_in_schema=False)
def home() -> FileResponse:
    entrypoint = FRONTEND_BUILD_DIR / "index.html"
    if not entrypoint.is_file():
        raise HTTPException(
            status_code=503,
            detail="React frontend is not built. Run `cd frontend && npm install && npm run build`.",
        )
    return FileResponse(entrypoint)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "healthy"}


@app.post("/api/ecourts/session")
def start_ecourts_session() -> dict[str, object]:
    try:
        session_id, context = _create_portal_session()
    except (requests.RequestException, RuntimeError, TypeError) as error:
        raise _portal_error(error) from error
    return {
        "session_id": session_id,
        "states": context.scraper.state_options,
        "captcha_image_available": bool(context.scraper.captcha_image_url),
        "expires_in_seconds": SESSION_TTL_SECONDS,
        "notice": "Enter the CAPTCHA shown by eCourts; this application does not solve it.",
    }


@app.post("/api/ecourts/options")
def get_case_search_options(request: CaseOptionsRequest) -> dict[str, object]:
    context = _portal_session(request.session_id)
    try:
        with context.lock:
            options = context.scraper.get_case_search_options(
                request.scope,
                state_code=request.state_code,
                district_code=request.district_code,
                court_complex_code=request.court_complex_code,
                establishment_code=request.establishment_code,
            )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except (requests.RequestException, RuntimeError, TypeError) as error:
        raise _portal_error(error) from error
    return {"options": options}


@app.post("/api/ecourts/session/{session_id}/captcha/refresh")
def refresh_captcha(session_id: str) -> dict[str, object]:
    context = _portal_session(session_id)
    try:
        with context.lock:
            result = context.scraper.get_captcha_and_token()
    except (requests.RequestException, RuntimeError, TypeError) as error:
        raise _portal_error(error) from error
    return {
        "captcha_image_available": bool(result["captcha_image_available"]),
    }


@app.get("/api/ecourts/session/{session_id}/captcha")
def get_captcha_image(session_id: str) -> Response:
    context = _portal_session(session_id)
    try:
        with context.lock:
            image, content_type = context.scraper.get_captcha_image()
    except (requests.RequestException, RuntimeError, TypeError) as error:
        raise _portal_error(error) from error
    return Response(content=image, media_type=content_type, headers={"Cache-Control": "no-store"})


@app.post("/api/ecourts/search/cnr")
def search_cnr(request: CNRSearchRequest) -> dict[str, object]:
    context = _portal_session(request.session_id)
    try:
        with context.lock:
            return context.scraper.search_cnr(request.cnr_number, request.captcha)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except (requests.RequestException, RuntimeError, TypeError) as error:
        raise _portal_error(error) from error


@app.post("/api/ecourts/search/case-number")
def search_case_number(request: CaseNumberSearchRequest) -> dict[str, object]:
    context = _portal_session(request.session_id)
    try:
        with context.lock:
            return context.scraper.search_case_number(
                state_code=request.state_code,
                district_code=request.district_code,
                court_complex_code=request.court_complex_code,
                establishment_code=request.establishment_code,
                case_type=request.case_type,
                case_number=request.case_number,
                year=request.year,
                captcha=request.captcha,
            )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except (requests.RequestException, RuntimeError, TypeError) as error:
        raise _portal_error(error) from error


@app.post("/api/drafts")
def create_draft(request: DraftRequest) -> dict[str, object]:
    return generate_draft(request)
