# VakeelAI assignment

A React/Vite frontend connected to a Python/FastAPI backend, with two tools:

1. A district-court eCourts scraper for CNR and Case Number searches.
2. A deterministic legal-draft template generator for legal notices, civil plaints and affidavits.

The React application lives in `frontend/`; FastAPI serves its production build and provides the JSON API. Draft generation uses local Python templates only; it does not call an LLM or an external API.

## Requirements

- Python 3.10 or newer
- Node.js 20.19+ or 22.12+ with npm
- Network access to `services.ecourts.gov.in` for case searches

## Run locally in development

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Start the Python API in one terminal:

```bash
uvicorn backend.main:app --reload
```

In another terminal, install the React app dependencies and start Vite:

```bash
cd frontend
npm install
npm run dev
```

Open the Vite URL (normally [http://localhost:5173](http://localhost:5173)). Vite proxies `/api` requests to FastAPI on port `8000`. FastAPI's interactive API documentation remains at [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).

## Production build

Build React before running the production FastAPI app:

```bash
cd frontend
npm install
npm run build
cd ..
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

FastAPI serves the generated `frontend/dist` application at `/` and its bundled assets at `/assets`. The build output and `node_modules` are ignored by Git.

No database or environment file is required. Portal sessions are held in memory for 15 minutes; restarting the server expires them.

## Docker

Docker and Docker Compose are supported. The root image is a multi-stage build that compiles React and packages the result with FastAPI:

```bash
docker build -t vakeelai .
docker run --rm -p 8000:8000 vakeelai
```

Open [http://localhost:8000](http://localhost:8000); the API docs are at [http://localhost:8000/docs](http://localhost:8000/docs).

To run the frontend and backend as separate containers, from the repository root run:

```bash
docker compose up --build
```

Open [http://localhost:8080](http://localhost:8080). Nginx serves the frontend and proxies `/api` and `/health` to FastAPI. The standalone frontend image can use a different backend host by setting `BACKEND_HOST` to `hostname:port`. The standalone API image can be built with `docker build -f backend/Dockerfile -t vakeelai-backend .`; it serves the API and `/docs` (the React app is served only by the root combined image or the separate frontend container).

Each image runs as a non-root user where applicable and includes a health check. Docker build contexts exclude `.env` files; pass any future runtime secrets through the deployment platform instead of baking them into an image. Backend container dependencies are kept in `backend/requirements.txt`, separate from the broader development environment in `requirements.txt`.

## Case scraper

Click **Load CAPTCHA** to create a cookie-bearing eCourts session. The app obtains the portal's current token and CAPTCHA image, then exposes the eCourts' own state, district, complex, establishment and case-type options. Enter the CAPTCHA shown and search by:

- **CNR**: 16 alphanumeric characters, such as `DLND020000602007`.
- **Case Number**: select the court hierarchy and provide the case number, registration year and CAPTCHA.

The scraper follows the portal's AJAX request flow: it keeps the same `requests.Session` cookies, carries the current `app_token`, reads the portal's current AJAX headers from its loaded helper script rather than relying on stale hard-coded values, and posts to `cnr_status/searchByCNR/` or `casestatus/submitCaseNo`. It also calls the portal's `fillDistrict`, `fillcomplex`, `fillCourtEstablishment` and `fillCaseType` endpoints for the dependent selections. Portal HTML is returned as structured text, tables and safe HTTP(S) links rather than executable markup.

CAPTCHA challenges are intentional portal protections. The application displays and submits the user's answer; it does not recognize, solve or bypass CAPTCHA. Public portal availability, CAPTCHA validation and the completeness of case/order records remain controlled by eCourts.

### Case API flow

1. `POST /api/ecourts/session` creates a portal session and returns a session ID and state list.
2. `POST /api/ecourts/options` returns the next level of court-search options.
3. `GET /api/ecourts/session/{session_id}/captcha` proxies the image through that same portal session.
4. `POST /api/ecourts/search/cnr` or `/api/ecourts/search/case-number` performs the search.

Use `POST /api/ecourts/session/{session_id}/captcha/refresh` to get a new challenge. The in-memory session design avoids persisting portal cookies or CAPTCHA answers; it is intended for a single application process and does not provide cross-worker session sharing.

## Draft generator

Select a deterministic template, supply parties, forum, facts, jurisdiction, relief, date and advocate name, and choose **Generate draft**. The API returns structured sections plus full text. It makes no legal conclusions and does not validate statutory requirements, limitation, evidence or forum jurisdiction. A qualified advocate should review all generated text before use or filing.

API: `POST /api/drafts`.

## Tests

```bash
pytest -q
```

For a clean developer/CI install, use `python -m pip install -r requirements-dev.txt`.

The unit tests mock eCourts responses and require no network connection. An optional live CAPTCHA smoke test is available with:

```bash
RUN_ECOURTS_LIVE_TEST=1 pytest -q tests/test_ecourts.py::test_live_captcha_request
```

The live test only checks whether eCourts returns a session token and CAPTCHA markup; it does not submit a CAPTCHA or perform a case search.

## Design choices and trade-offs

- **Requests session per user flow:** keeps portal cookies and rotating tokens together without a database. Sessions are short-lived and process-local; a distributed deployment would need a secure shared session store.
- **Portal-supplied hierarchy options:** avoids stale hard-coded court codes and display-name mappings, at the cost of depending on the live portal's current option endpoints.
- **Human-entered CAPTCHA:** respects the portal's challenge and avoids unreliable or prohibited automation.
- **Structured extraction instead of raw HTML rendering:** retains portal table text and document links while avoiding executable portal markup in the frontend.
- **Fixed Python templates:** yields repeatable output and keeps the draft generator offline, but does not replace legal review or jurisdiction-specific drafting.

## Deployment

Build the React frontend during deployment with `cd frontend && npm ci && npm run build`, then start FastAPI with `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`. Configure outbound HTTPS access to eCourts. Use a single application worker unless a shared session store is added; the portal session registry is in process memory.

GitHub Actions in `.github/workflows/ci-cd.yml` runs Python tests and linting on Python 3.10 and 3.13, builds the frontend, and verifies all three Docker images for pull requests. Pushes to `main` and version tags (`v*`) publish the combined, backend, and frontend images to GitHub Container Registry (GHCR). Enable package publishing for the repository if required by its GitHub organization settings. This workflow publishes deployable images; automatic rollout to a hosting provider requires that provider and deployment credentials to be configured separately.
