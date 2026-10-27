import { useState } from "react";

const EMPTY_CASE_OPTIONS = {
  state_code: [],
  district_code: [],
  court_complex_code: [],
  establishment_code: [],
  case_type: [],
};

const EMPTY_CASE_SELECTION = {
  state_code: "",
  district_code: "",
  court_complex_code: "",
  establishment_code: "",
  case_type: "",
};

const INITIAL_DRAFT = {
  document_type: "legal_notice",
  court_name: "",
  petitioner: "",
  respondent: "",
  facts: "",
  relief_sought: "",
  jurisdiction: "",
  date: "",
  advocate_name: "",
  notice_period_days: 15,
};

async function requestJson(url, options = {}) {
  const response = await fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options.headers,
    },
  });
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.detail || `Request failed (${response.status}).`);
  }
  return data;
}

function Status({ message, kind = "" }) {
  if (!message) return null;
  return (
    <p className={`status ${kind}`} role="status" aria-live="polite">
      {message}
    </p>
  );
}

function CaseResults({ data }) {
  if (!data) return null;
  return (
    <section className="results" aria-label="Case search results">
      <div className="results-header">
        <h3>eCourts response</h3>
      </div>
      <div className="results-body">
        {data.links?.length > 0 && (
          <div className="document-links">
            <p>Documents and portal links</p>
            {data.links.map((link, index) => (
              <a
                href={link.url}
                key={`${link.url}-${index}`}
                target="_blank"
                rel="noopener noreferrer"
              >
                {link.text || link.url}
              </a>
            ))}
          </div>
        )}
        <pre>{JSON.stringify(data, null, 2)}</pre>
      </div>
    </section>
  );
}

function DraftResults({ data, onCopy }) {
  if (!data) return null;
  return (
    <section className="results" aria-label="Generated draft">
      <div className="results-header">
        <h3>{data.title}</h3>
        <button className="button secondary" onClick={onCopy} type="button">
          Copy draft
        </button>
      </div>
      <div className="results-body">
        {data.sections.map((section) => (
          <section className="draft-section" key={section.heading}>
            <h4>{section.heading}</h4>
            <p>{section.body}</p>
          </section>
        ))}
        <p className="disclaimer">{data.disclaimer}</p>
      </div>
    </section>
  );
}

function Field({ label, children }) {
  return (
    <label>
      {label}
      {children}
    </label>
  );
}

function CaptchaChallenge({
  sessionId,
  imageAvailable,
  imageFailed,
  version,
  disabled,
  onRefresh,
  onImageError,
}) {
  if (!sessionId) return null;

  return (
    <div className="captcha-challenge">
      {imageAvailable && !imageFailed ? (
        <img
          src={`/api/ecourts/session/${encodeURIComponent(
            sessionId,
          )}/captcha?version=${version}`}
          alt="CAPTCHA challenge from eCourts"
          onError={onImageError}
        />
      ) : (
        <p role="status">
          {imageFailed
            ? "The CAPTCHA image could not be loaded. Refresh the CAPTCHA to try again."
            : "The portal did not provide a CAPTCHA image. Refresh or try again later."}
        </p>
      )}
      <button
        className="button secondary"
        disabled={disabled}
        onClick={onRefresh}
        type="button"
      >
        Refresh CAPTCHA
      </button>
    </div>
  );
}

export default function App() {
  const [activePanel, setActivePanel] = useState("cases");
  const [portalSessionId, setPortalSessionId] = useState("");
  const [caseOptions, setCaseOptions] = useState(EMPTY_CASE_OPTIONS);
  const [caseSelection, setCaseSelection] = useState(EMPTY_CASE_SELECTION);
  const [captchaImageAvailable, setCaptchaImageAvailable] = useState(false);
  const [captchaImageFailed, setCaptchaImageFailed] = useState(false);
  const [captchaVersion, setCaptchaVersion] = useState(0);
  const [caseStatus, setCaseStatus] = useState({ message: "", kind: "" });
  const [caseBusy, setCaseBusy] = useState(false);
  const [caseResults, setCaseResults] = useState(null);
  const [draftValues, setDraftValues] = useState(INITIAL_DRAFT);
  const [draftStatus, setDraftStatus] = useState({ message: "", kind: "" });
  const [draftBusy, setDraftBusy] = useState(false);
  const [draftResults, setDraftResults] = useState(null);

  const updateCaseStatus = (message, kind = "") => setCaseStatus({ message, kind });
  const updateDraftStatus = (message, kind = "") => setDraftStatus({ message, kind });

  async function loadOptions(scope, parentValues = {}) {
    const data = await requestJson("/api/ecourts/options", {
      method: "POST",
      body: JSON.stringify({ session_id: portalSessionId, scope, ...parentValues }),
    });
    return data.options;
  }

  function resetCaseOptions(afterName) {
    const names = Object.keys(EMPTY_CASE_OPTIONS);
    const start = afterName ? names.indexOf(afterName) + 1 : 0;
    setCaseOptions((current) => {
      const next = { ...current };
      for (const name of names.slice(start)) next[name] = [];
      return next;
    });
  }

  async function handleStartSession() {
    setCaseBusy(true);
    updateCaseStatus("Connecting to eCourts and loading a CAPTCHA…");
    try {
      const data = await requestJson("/api/ecourts/session", { method: "POST" });
      setPortalSessionId(data.session_id);
      setCaseOptions({
        ...EMPTY_CASE_OPTIONS,
        state_code: data.states,
      });
      setCaseSelection(EMPTY_CASE_SELECTION);
      setCaptchaImageAvailable(data.captcha_image_available);
      setCaptchaImageFailed(false);
      setCaptchaVersion((version) => version + 1);
      setCaseResults(null);
      updateCaseStatus(data.notice, "success");
    } catch (error) {
      updateCaseStatus(error.message, "error");
    } finally {
      setCaseBusy(false);
    }
  }

  async function handleRefreshCaptcha() {
    if (!portalSessionId) {
      updateCaseStatus("Load a CAPTCHA session first.", "error");
      return;
    }
    setCaseBusy(true);
    try {
      const data = await requestJson(
        `/api/ecourts/session/${encodeURIComponent(portalSessionId)}/captcha/refresh`,
        { method: "POST" },
      );
      setCaptchaImageAvailable(data.captcha_image_available);
      setCaptchaImageFailed(false);
      setCaptchaVersion((version) => version + 1);
      updateCaseStatus("CAPTCHA refreshed. Enter the new characters.", "success");
    } catch (error) {
      updateCaseStatus(error.message, "error");
    } finally {
      setCaseBusy(false);
    }
  }

  async function handleStateChange(event) {
    const stateCode = event.target.value;
    setCaseSelection({ ...EMPTY_CASE_SELECTION, state_code: stateCode });
    resetCaseOptions("state_code");
    if (!stateCode) return;
    try {
      const options = await loadOptions("districts", { state_code: stateCode });
      setCaseOptions((current) => ({ ...current, district_code: options }));
    } catch (error) {
      updateCaseStatus(error.message, "error");
    }
  }

  async function handleDistrictChange(event) {
    const districtCode = event.target.value;
    setCaseSelection((current) => ({
      ...current,
      district_code: districtCode,
      court_complex_code: "",
      establishment_code: "",
      case_type: "",
    }));
    resetCaseOptions("district_code");
    if (!districtCode) return;
    try {
      const options = await loadOptions("complexes", {
        state_code: caseSelection.state_code,
        district_code: districtCode,
      });
      setCaseOptions((current) => ({ ...current, court_complex_code: options }));
    } catch (error) {
      updateCaseStatus(error.message, "error");
    }
  }

  async function handleComplexChange(event) {
    const complexCode = event.target.value;
    setCaseSelection((current) => ({
      ...current,
      court_complex_code: complexCode,
      establishment_code: "",
      case_type: "",
    }));
    resetCaseOptions("court_complex_code");
    if (!complexCode) return;
    try {
      if (complexCode.split("@")[2] !== "Y") {
        const options = await loadOptions("case_types", {
          state_code: caseSelection.state_code,
          district_code: caseSelection.district_code,
          court_complex_code: complexCode,
          establishment_code: "",
        });
        setCaseOptions((current) => ({
          ...current,
          case_type: options,
        }));
        return;
      }
      const options = await loadOptions("establishments", {
        state_code: caseSelection.state_code,
        district_code: caseSelection.district_code,
        court_complex_code: complexCode,
      });
      setCaseOptions((current) => ({ ...current, establishment_code: options }));
    } catch (error) {
      updateCaseStatus(error.message, "error");
    }
  }

  async function handleEstablishmentChange(event) {
    const establishmentCode = event.target.value;
    setCaseSelection((current) => ({
      ...current,
      establishment_code: establishmentCode,
      case_type: "",
    }));
    resetCaseOptions("establishment_code");
    if (!establishmentCode) return;
    try {
      const options = await loadOptions("case_types", {
        state_code: caseSelection.state_code,
        district_code: caseSelection.district_code,
        court_complex_code: caseSelection.court_complex_code,
        establishment_code: establishmentCode,
      });
      setCaseOptions((current) => ({ ...current, case_type: options }));
    } catch (error) {
      updateCaseStatus(error.message, "error");
    }
  }

  function handleCaseTypeChange(event) {
    setCaseSelection((current) => ({ ...current, case_type: event.target.value }));
  }

  async function handleCnrSearch(event) {
    event.preventDefault();
    const form = event.currentTarget;
    if (!portalSessionId) {
      updateCaseStatus("Load a CAPTCHA session before searching.", "error");
      return;
    }
    const values = Object.fromEntries(new FormData(event.currentTarget));
    setCaseBusy(true);
    updateCaseStatus("Searching the eCourts portal…");
    try {
      const data = await requestJson("/api/ecourts/search/cnr", {
        method: "POST",
        body: JSON.stringify({
          cnr_number: values.cnr_number,
          captcha: values.captcha,
          session_id: portalSessionId,
        }),
      });
      setCaseResults(data);
      setCaptchaImageAvailable(Boolean(data.captcha_image_available));
      setCaptchaImageFailed(false);
      setCaptchaVersion((version) => version + 1);
      form.reset();
      updateCaseStatus("Portal response received.", "success");
    } catch (error) {
      updateCaseStatus(error.message, "error");
    } finally {
      setCaseBusy(false);
    }
  }

  async function handleCaseNumberSearch(event) {
    event.preventDefault();
    const form = event.currentTarget;
    if (!portalSessionId) {
      updateCaseStatus("Load a CAPTCHA session before searching.", "error");
      return;
    }
    const values = Object.fromEntries(new FormData(form));
    values.year = Number(values.year);
    values.establishment_code = caseSelection.establishment_code;
    values.state_code = caseSelection.state_code;
    values.district_code = caseSelection.district_code;
    values.court_complex_code = caseSelection.court_complex_code;
    values.case_type = caseSelection.case_type;
    values.session_id = portalSessionId;
    setCaseBusy(true);
    updateCaseStatus("Searching the eCourts portal…");
    try {
      const data = await requestJson("/api/ecourts/search/case-number", {
        method: "POST",
        body: JSON.stringify(values),
      });
      setCaseResults(data);
      setCaptchaImageAvailable(Boolean(data.captcha_image_available));
      setCaptchaImageFailed(false);
      setCaptchaVersion((version) => version + 1);
      form.reset();
      updateCaseStatus("Portal response received.", "success");
    } catch (error) {
      updateCaseStatus(error.message, "error");
    } finally {
      setCaseBusy(false);
    }
  }

  async function handleDraftSubmit(event) {
    event.preventDefault();
    setDraftBusy(true);
    updateDraftStatus("Generating draft from the selected template…");
    try {
      const data = await requestJson("/api/drafts", {
        method: "POST",
        body: JSON.stringify({
          ...draftValues,
          notice_period_days: Number(draftValues.notice_period_days),
        }),
      });
      setDraftResults(data);
      updateDraftStatus("Draft generated. Review it with an advocate before use.", "success");
    } catch (error) {
      updateDraftStatus(error.message, "error");
    } finally {
      setDraftBusy(false);
    }
  }

  async function handleCopyDraft() {
    try {
      await navigator.clipboard.writeText(draftResults.full_text);
      updateDraftStatus("Draft copied to clipboard.", "success");
    } catch (error) {
      updateDraftStatus(`Could not copy draft: ${error.message}`, "error");
    }
  }

  function updateDraftField(event) {
    const { name, value } = event.target;
    setDraftValues((current) => ({ ...current, [name]: value }));
  }

  function renderOptionSelect(name, placeholder, onChange, disabled = false) {
    return (
      <select
        name={name}
        required
        disabled={disabled || caseOptions[name].length === 0}
        value={caseSelection[name]}
        onChange={onChange}
      >
        <option value="">{placeholder}</option>
        {caseOptions[name].map((option) => (
          <option value={option.value} key={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    );
  }

  return (
    <>
      <header className="topbar">
        <a className="brand" href="/" aria-label="VakeelAI home">
          <span className="brand-mark">V</span>
          <span>VakeelAI</span>
        </a>
        <span className="topbar-caption">Court information &amp; document templates</span>
      </header>

      <main className="page">
        <section className="intro">
          <p className="eyebrow">DISTRICT COURT SERVICES</p>
          <h1>Practical tools for legal work</h1>
          <p>
            Search public case information on eCourts or prepare a structured draft from your
            own details.
          </p>
        </section>

        <nav className="tabs" aria-label="Tools">
          <button
            className={`tab ${activePanel === "cases" ? "active" : ""}`}
            onClick={() => setActivePanel("cases")}
            type="button"
          >
            Case search
          </button>
          <button
            className={`tab ${activePanel === "drafts" ? "active" : ""}`}
            onClick={() => setActivePanel("drafts")}
            type="button"
          >
            Draft generator
          </button>
        </nav>

        {activePanel === "cases" ? (
          <section className="panel active" aria-labelledby="case-heading">
            <div className="panel-heading">
              <div>
                <p className="eyebrow">ECourts portal</p>
                <h2 id="case-heading">Search a district court case</h2>
              </div>
              <button
                className="button secondary"
                disabled={caseBusy}
                onClick={handleStartSession}
                type="button"
              >
                {portalSessionId ? "Reload CAPTCHA" : "Load CAPTCHA"}
              </button>
            </div>
            <p className="notice">
              Load a CAPTCHA session first. Enter the characters shown in the image directly
              below the CAPTCHA field in either search form.
            </p>

            <div className="form-grid search-layout">
              <form className="card form-stack" onSubmit={handleCnrSearch}>
                <h3>Search by CNR</h3>
                <Field label="CNR number">
                  <input
                    name="cnr_number"
                    required
                    minLength="16"
                    maxLength="16"
                    pattern="[A-Za-z0-9]{16}"
                    placeholder="DLND020000602007"
                  />
                </Field>
                <Field label="CAPTCHA">
                  <input name="captcha" required autoComplete="off" placeholder="Enter characters" />
                </Field>
                <CaptchaChallenge
                  sessionId={portalSessionId}
                  imageAvailable={captchaImageAvailable}
                  imageFailed={captchaImageFailed}
                  version={captchaVersion}
                  disabled={caseBusy}
                  onRefresh={handleRefreshCaptcha}
                  onImageError={() => setCaptchaImageFailed(true)}
                />
                <button className="button" disabled={caseBusy} type="submit">
                  Search CNR
                </button>
              </form>

              <form className="card form-stack" onSubmit={handleCaseNumberSearch}>
                <h3>Search by case number</h3>
                <div className="form-grid two-columns">
                  <Field label="State">
                    {renderOptionSelect(
                      "state_code",
                      "Load CAPTCHA to load states",
                      handleStateChange,
                      !portalSessionId,
                    )}
                  </Field>
                  <Field label="District">
                    {renderOptionSelect(
                      "district_code",
                      "Select a state first",
                      handleDistrictChange,
                    )}
                  </Field>
                  <Field label="Court complex">
                    {renderOptionSelect(
                      "court_complex_code",
                      "Select a district first",
                      handleComplexChange,
                    )}
                  </Field>
                  <Field label="Establishment">
                    {renderOptionSelect(
                      "establishment_code",
                      caseSelection.court_complex_code &&
                        caseSelection.court_complex_code.split("@")[2] !== "Y"
                        ? "Not required for this court complex"
                        : "Select a court complex first",
                      handleEstablishmentChange,
                    )}
                  </Field>
                  <Field label="Case type">
                    {renderOptionSelect(
                      "case_type",
                      "Select an establishment first",
                      handleCaseTypeChange,
                    )}
                  </Field>
                  <Field label="Case number">
                    <input name="case_number" required placeholder="233" />
                  </Field>
                  <Field label="Registration year">
                    <input
                      name="year"
                      type="number"
                      min="1900"
                      max="2100"
                      required
                      placeholder="2024"
                    />
                  </Field>
                  <Field label="CAPTCHA">
                    <input
                      name="captcha"
                      required
                      autoComplete="off"
                      placeholder="Enter characters"
                    />
                  </Field>
                </div>
                <CaptchaChallenge
                  sessionId={portalSessionId}
                  imageAvailable={captchaImageAvailable}
                  imageFailed={captchaImageFailed}
                  version={captchaVersion}
                  disabled={caseBusy}
                  onRefresh={handleRefreshCaptcha}
                  onImageError={() => setCaptchaImageFailed(true)}
                />
                <button className="button" disabled={caseBusy} type="submit">
                  Search case number
                </button>
              </form>
            </div>

            <Status {...caseStatus} />
            <CaseResults data={caseResults} />
          </section>
        ) : (
          <section className="panel active" aria-labelledby="draft-heading">
            <p className="eyebrow">DETERMINISTIC PYTHON TEMPLATES</p>
            <h2 id="draft-heading">Generate a legal draft</h2>
            <p className="notice">
              The generator uses fixed templates and your supplied facts only. It does not use
              an LLM or external API.
            </p>
            <form className="card form-stack" onSubmit={handleDraftSubmit}>
              <div className="form-grid two-columns">
                <Field label="Document type">
                  <select
                    name="document_type"
                    value={draftValues.document_type}
                    onChange={updateDraftField}
                  >
                    <option value="legal_notice">Legal notice</option>
                    <option value="civil_plaint">Civil plaint</option>
                    <option value="affidavit">Affidavit</option>
                  </select>
                </Field>
                <Field label="Court / forum">
                  <input
                    name="court_name"
                    required
                    value={draftValues.court_name}
                    onChange={updateDraftField}
                    placeholder="Court name or forum"
                  />
                </Field>
                <Field label="Petitioner / sender / deponent">
                  <input
                    name="petitioner"
                    required
                    value={draftValues.petitioner}
                    onChange={updateDraftField}
                  />
                </Field>
                <Field label="Respondent / recipient">
                  <input
                    name="respondent"
                    required
                    value={draftValues.respondent}
                    onChange={updateDraftField}
                  />
                </Field>
                <Field label="Draft date">
                  <input
                    name="date"
                    required
                    value={draftValues.date}
                    onChange={updateDraftField}
                    placeholder="DD Month YYYY"
                  />
                </Field>
                <Field label="Advocate name">
                  <input
                    name="advocate_name"
                    required
                    value={draftValues.advocate_name}
                    onChange={updateDraftField}
                  />
                </Field>
                <Field label="Notice response period (days)">
                  <input
                    name="notice_period_days"
                    type="number"
                    min="1"
                    max="90"
                    required
                    value={draftValues.notice_period_days}
                    onChange={updateDraftField}
                  />
                </Field>
              </div>
              <Field label="Material facts">
                <textarea
                  name="facts"
                  rows="5"
                  minLength="20"
                  maxLength="10000"
                  required
                  value={draftValues.facts}
                  onChange={updateDraftField}
                  placeholder="Enter relevant facts in your own words."
                />
              </Field>
              <Field label="Jurisdiction / context">
                <textarea
                  name="jurisdiction"
                  rows="3"
                  required
                  value={draftValues.jurisdiction}
                  onChange={updateDraftField}
                  placeholder="Explain the forum or legal context to be reviewed by counsel."
                />
              </Field>
              <Field label="Relief / action sought">
                <textarea
                  name="relief_sought"
                  rows="3"
                  required
                  value={draftValues.relief_sought}
                  onChange={updateDraftField}
                  placeholder="Describe the requested relief or action."
                />
              </Field>
              <button className="button" disabled={draftBusy} type="submit">
                {draftBusy ? "Generating…" : "Generate draft"}
              </button>
            </form>
            <Status {...draftStatus} />
            <DraftResults data={draftResults} onCopy={handleCopyDraft} />
          </section>
        )}

        <footer>
          eCourts data is retrieved on demand from the public portal. Verify case details and
          have all draft content reviewed by an advocate before relying on or filing it.
        </footer>
      </main>
    </>
  );
}
