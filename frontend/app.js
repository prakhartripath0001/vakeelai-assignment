const tabs = document.querySelectorAll(".tab");
const panels = document.querySelectorAll(".panel");
const caseStatus = document.querySelector("#case-status");
const draftStatus = document.querySelector("#draft-status");
const captchaBox = document.querySelector("#captcha-box");
const captchaImage = document.querySelector("#captcha-image");
const captchaMessage = document.querySelector("#captcha-message");
let portalSessionId = null;

for (const tab of tabs) {
  tab.addEventListener("click", () => {
    for (const otherTab of tabs) {
      const active = otherTab === tab;
      otherTab.classList.toggle("active", active);
      otherTab.setAttribute("aria-selected", String(active));
    }
    for (const panel of panels) {
      panel.classList.toggle("active", panel.id === tab.dataset.panel);
    }
  });
}

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

function setStatus(element, message, kind = "") {
  element.textContent = message;
  element.className = `status ${kind}`.trim();
}

function showCaptcha(available) {
  captchaBox.hidden = false;
  captchaImage.hidden = !available;
  captchaMessage.textContent = available
    ? "Enter the characters shown into the selected search form."
    : "The portal did not provide an image. Refresh or try again later.";
  if (available) {
    captchaImage.src = `/api/ecourts/session/${encodeURIComponent(portalSessionId)}/captcha?time=${Date.now()}`;
  }
}

function populateSelect(select, options, placeholder) {
  select.replaceChildren(new Option(placeholder, ""));
  for (const option of options) {
    select.add(new Option(option.label, option.value));
  }
  select.disabled = options.length === 0;
  select.value = "";
}

async function loadOptions(scope, parentValues = {}) {
  const data = await requestJson("/api/ecourts/options", {
    method: "POST",
    body: JSON.stringify({
      session_id: portalSessionId,
      scope,
      ...parentValues,
    }),
  });
  return data.options;
}

const caseForm = document.querySelector("#case-form");
const caseSelects = Object.fromEntries(
  ["state_code", "district_code", "court_complex_code", "establishment_code", "case_type"]
    .map((name) => [name, caseForm.elements[name]]),
);

function resetCaseOptions(afterName) {
  const order = Object.keys(caseSelects);
  const index = order.indexOf(afterName);
  const placeholders = [
    "Select a state",
    "Select a district",
    "Select a court complex",
    "Select an establishment",
    "Select a case type",
  ];
  for (let position = index + 1; position < order.length; position += 1) {
    const select = caseSelects[order[position]];
    populateSelect(select, [], placeholders[position]);
  }
}

caseSelects.state_code.addEventListener("change", async (event) => {
  resetCaseOptions("state_code");
  if (!event.currentTarget.value) return;
  try {
    const options = await loadOptions("districts", { state_code: event.currentTarget.value });
    populateSelect(caseSelects.district_code, options, "Select a district");
  } catch (error) {
    setStatus(caseStatus, error.message, "error");
  }
});

caseSelects.district_code.addEventListener("change", async () => {
  resetCaseOptions("district_code");
  if (!caseSelects.district_code.value) return;
  try {
    const options = await loadOptions("complexes", {
      state_code: caseSelects.state_code.value,
      district_code: caseSelects.district_code.value,
    });
    populateSelect(caseSelects.court_complex_code, options, "Select a court complex");
  } catch (error) {
    setStatus(caseStatus, error.message, "error");
  }
});

caseSelects.court_complex_code.addEventListener("change", async () => {
  resetCaseOptions("court_complex_code");
  if (!caseSelects.court_complex_code.value) return;
  try {
    const complexParts = caseSelects.court_complex_code.value.split("@");
    if (complexParts[2] !== "Y") {
      populateSelect(
        caseSelects.establishment_code,
        [],
        "Not required for this court complex",
      );
      const options = await loadOptions("case_types", {
        state_code: caseSelects.state_code.value,
        district_code: caseSelects.district_code.value,
        court_complex_code: caseSelects.court_complex_code.value,
        establishment_code: "",
      });
      populateSelect(caseSelects.case_type, options, "Select a case type");
      return;
    }
    const options = await loadOptions("establishments", {
      state_code: caseSelects.state_code.value,
      district_code: caseSelects.district_code.value,
      court_complex_code: caseSelects.court_complex_code.value,
    });
    populateSelect(caseSelects.establishment_code, options, "Select an establishment");
  } catch (error) {
    setStatus(caseStatus, error.message, "error");
  }
});

caseSelects.establishment_code.addEventListener("change", async () => {
  resetCaseOptions("establishment_code");
  if (!caseSelects.establishment_code.value) return;
  try {
    const options = await loadOptions("case_types", {
      state_code: caseSelects.state_code.value,
      district_code: caseSelects.district_code.value,
      court_complex_code: caseSelects.court_complex_code.value,
      establishment_code: caseSelects.establishment_code.value,
    });
    populateSelect(caseSelects.case_type, options, "Select a case type");
  } catch (error) {
    setStatus(caseStatus, error.message, "error");
  }
});

function renderCaseResults(data) {
  const container = document.querySelector("#case-results");
  container.replaceChildren();
  const header = document.createElement("div");
  header.className = "results-header";
  const heading = document.createElement("h3");
  heading.textContent = "eCourts response";
  header.append(heading);
  const body = document.createElement("div");
  body.className = "results-body";

  if (Array.isArray(data.links) && data.links.length) {
    const linksHeading = document.createElement("p");
    linksHeading.textContent = "Documents and portal links";
    body.append(linksHeading);
    for (const link of data.links) {
      const anchor = document.createElement("a");
      anchor.href = link.url;
      anchor.target = "_blank";
      anchor.rel = "noopener noreferrer";
      anchor.textContent = link.text || link.url;
      body.append(anchor);
    }
  }

  const details = document.createElement("pre");
  details.textContent = JSON.stringify(data, null, 2);
  body.append(details);
  container.append(header, body);
  container.hidden = false;
}

function renderDraft(data) {
  const container = document.querySelector("#draft-results");
  container.replaceChildren();
  const header = document.createElement("div");
  header.className = "results-header";
  const heading = document.createElement("h3");
  heading.textContent = data.title;
  const copy = document.createElement("button");
  copy.type = "button";
  copy.className = "button secondary";
  copy.textContent = "Copy draft";
  copy.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(data.full_text);
      setStatus(draftStatus, "Draft copied to clipboard.", "success");
    } catch (error) {
      setStatus(draftStatus, `Could not copy draft: ${error.message}`, "error");
    }
  });
  header.append(heading, copy);

  const body = document.createElement("div");
  body.className = "results-body";
  for (const section of data.sections) {
    const sectionElement = document.createElement("section");
    sectionElement.className = "draft-section";
    const sectionHeading = document.createElement("h4");
    sectionHeading.textContent = section.heading;
    const text = document.createElement("p");
    text.textContent = section.body;
    sectionElement.append(sectionHeading, text);
    body.append(sectionElement);
  }
  const disclaimer = document.createElement("p");
  disclaimer.className = "disclaimer";
  disclaimer.textContent = data.disclaimer;
  body.append(disclaimer);
  container.append(header, body);
  container.hidden = false;
}

document.querySelector("#start-session").addEventListener("click", async (event) => {
  const button = event.currentTarget;
  button.disabled = true;
  setStatus(caseStatus, "Connecting to eCourts and loading a CAPTCHA…");
  try {
    const data = await requestJson("/api/ecourts/session", { method: "POST" });
    portalSessionId = data.session_id;
    populateSelect(caseSelects.state_code, data.states, "Select a state");
    resetCaseOptions("state_code");
    showCaptcha(data.captcha_image_available);
    setStatus(caseStatus, data.notice, "success");
  } catch (error) {
    setStatus(caseStatus, error.message, "error");
  } finally {
    button.disabled = false;
  }
});

document.querySelector("#refresh-captcha").addEventListener("click", async (event) => {
  if (!portalSessionId) {
    setStatus(caseStatus, "Load a CAPTCHA session first.", "error");
    return;
  }
  const button = event.currentTarget;
  button.disabled = true;
  try {
    const data = await requestJson(
      `/api/ecourts/session/${encodeURIComponent(portalSessionId)}/captcha/refresh`,
      { method: "POST" },
    );
    showCaptcha(data.captcha_image_available);
    setStatus(caseStatus, "CAPTCHA refreshed. Enter the new characters.", "success");
  } catch (error) {
    setStatus(caseStatus, error.message, "error");
  } finally {
    button.disabled = false;
  }
});

document.querySelector("#cnr-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!portalSessionId) {
    setStatus(caseStatus, "Load a CAPTCHA session before searching.", "error");
    return;
  }
  const form = event.currentTarget;
  const submit = form.querySelector('button[type="submit"]');
  submit.disabled = true;
  setStatus(caseStatus, "Searching the eCourts portal…");
  try {
    const formData = new FormData(form);
    const data = await requestJson("/api/ecourts/search/cnr", {
      method: "POST",
      body: JSON.stringify({
        session_id: portalSessionId,
        cnr_number: formData.get("cnr_number"),
        captcha: formData.get("captcha"),
      }),
    });
    renderCaseResults(data);
    setStatus(caseStatus, "Portal response received.", "success");
    form.elements.captcha.value = "";
    if (data.links?.length) {
      setStatus(caseStatus, "Portal response received. Document links open in a new tab.", "success");
    }
    showCaptcha(Boolean(data.captcha_image_available));
  } catch (error) {
    setStatus(caseStatus, error.message, "error");
  } finally {
    submit.disabled = false;
  }
});

document.querySelector("#case-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!portalSessionId) {
    setStatus(caseStatus, "Load a CAPTCHA session before searching.", "error");
    return;
  }
  const form = event.currentTarget;
  const submit = form.querySelector('button[type="submit"]');
  submit.disabled = true;
  setStatus(caseStatus, "Searching the eCourts portal…");
  try {
    const values = Object.fromEntries(new FormData(form));
    values.year = Number(values.year);
    values.establishment_code = caseSelects.establishment_code.value;
    values.session_id = portalSessionId;
    const data = await requestJson("/api/ecourts/search/case-number", {
      method: "POST",
      body: JSON.stringify(values),
    });
    renderCaseResults(data);
    setStatus(caseStatus, "Portal response received.", "success");
    form.elements.captcha.value = "";
    showCaptcha(Boolean(data.captcha_image_available));
  } catch (error) {
    setStatus(caseStatus, error.message, "error");
  } finally {
    submit.disabled = false;
  }
});

document.querySelector("#draft-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const submit = form.querySelector('button[type="submit"]');
  submit.disabled = true;
  setStatus(draftStatus, "Generating draft from the selected template…");
  try {
    const values = Object.fromEntries(new FormData(form));
    values.notice_period_days = Number(values.notice_period_days);
    const data = await requestJson("/api/drafts", {
      method: "POST",
      body: JSON.stringify(values),
    });
    renderDraft(data);
    setStatus(draftStatus, "Draft generated. Review it with an advocate before use.", "success");
  } catch (error) {
    setStatus(draftStatus, error.message, "error");
  } finally {
    submit.disabled = false;
  }
});
