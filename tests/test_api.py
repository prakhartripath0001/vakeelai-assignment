from threading import Lock
from types import SimpleNamespace

from fastapi.testclient import TestClient

from backend import main
from backend.main import app

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_frontend_is_served():
    response = client.get("/")

    if (main.FRONTEND_BUILD_DIR / "index.html").is_file():
        assert response.status_code == 200
        assert "VakeelAI" in response.text
    else:
        assert response.status_code == 503
        assert "npm run build" in response.json()["detail"]


def test_case_search_rejects_malformed_cnr():
    response = client.post(
        "/api/ecourts/search/cnr",
        json={
            "session_id": "missing-session",
            "cnr_number": "short",
            "captcha": "abcde",
        },
    )

    assert response.status_code == 422


def test_draft_endpoint_returns_structured_template():
    response = client.post(
        "/api/drafts",
        json={
            "document_type": "legal_notice",
            "court_name": "District Court",
            "petitioner": "Asha Rao",
            "respondent": "Ravi Shah",
            "facts": "The parties entered into an agreement and the respondent did not perform.",
            "relief_sought": "perform the agreement",
            "jurisdiction": "The events took place within this court's territorial jurisdiction.",
            "date": "27 October 2026",
            "advocate_name": "Advocate Meera",
        },
    )

    assert response.status_code == 200
    result = response.json()
    assert result["title"] == "Legal Notice"
    assert isinstance(result["sections"], list)
    assert "Asha Rao" in result["full_text"]


def test_case_options_endpoint_forwards_session_and_parent_selection(monkeypatch):
    class FakeScraper:
        def get_case_search_options(self, scope, **parents):
            assert scope == "districts"
            assert parents["state_code"] == "26"
            return [{"value": "10", "label": "South"}]

    context = SimpleNamespace(scraper=FakeScraper(), lock=Lock())

    def fake_get_session(session_id):
        assert session_id == "test-session"
        return context

    monkeypatch.setattr(main, "_portal_session", fake_get_session)

    response = client.post(
        "/api/ecourts/options",
        json={"session_id": "test-session", "scope": "districts", "state_code": "26"},
    )

    assert response.status_code == 200
    assert response.json() == {"options": [{"value": "10", "label": "South"}]}
