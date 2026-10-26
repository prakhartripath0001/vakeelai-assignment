from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://services.ecourts.gov.in/ecourtindia_v6/"


class ECourtsScraper:
    def __init__(self):
        self.session = requests.Session()
        self.base_url = BASE_URL

    def get_captcha_and_token(self) -> dict:
        """Request the CAPTCHA form and read the returned app token."""

        page_response = self.session.get(self.base_url, timeout=30)
        page_response.raise_for_status()
        page = BeautifulSoup(page_response.text, "html.parser")
        case_status_link = page.find("a", id="leftPaneMenuCS")

        if case_status_link is None or not case_status_link.get("href"):
            raise RuntimeError("The eCourts page does not contain the Case Status link.")

        base_url_parts = urlparse(self.base_url)
        case_status_url = urljoin(page_response.url, case_status_link["href"])
        if urlparse(case_status_url).netloc != base_url_parts.netloc:
            raise RuntimeError("The eCourts Case Status link points to an unexpected host.")

        case_status_response = self.session.get(case_status_url, timeout=30)
        case_status_response.raise_for_status()
        case_status_page = BeautifulSoup(case_status_response.text, "html.parser")
        token_input = case_status_page.find("input", id="app_token")

        if token_input is None or not token_input.get("value"):
            raise RuntimeError("The eCourts Case Status page does not contain app_token.")

        response = self.session.post(
            self.base_url,
            params={
                "p": "casestatus/getCaptcha",
            },
            data={
                "ajax_req": "true",
                "app_token": token_input["value"],
            },
            headers={
                "X-Requested-With": "XMLHttpRequest",
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "Referer": case_status_response.url,
                "Origin": f"{base_url_parts.scheme}://{base_url_parts.netloc}",
                "delimeter": "wehf735ytf",
                "K98923rh": "wehf735ytf",
            },
            timeout=30,
        )

        response.raise_for_status()

        content_type = response.headers.get("Content-Type", "")
        try:
            data = response.json()
        except requests.exceptions.JSONDecodeError:
            if "application/json" not in content_type.lower():
                raise RuntimeError(
                    "Expected JSON from eCourts, but received "
                    f"Content-Type: {content_type}. "
                    "The portal returned a non-JSON response."
                ) from None
            raise RuntimeError("eCourts returned invalid JSON.") from None

        if not isinstance(data, dict):
            raise RuntimeError("Unexpected eCourts response structure.")

        if data.get("errormsg"):
            error_message = BeautifulSoup(str(data["errormsg"]), "html.parser").get_text(
                " ", strip=True
            )
            raise RuntimeError(f"eCourts rejected the CAPTCHA request: {error_message}")

        if not data.get("app_token"):
            raise RuntimeError("The response does not contain app_token.")

        return {
            "app_token": data.get("app_token"),
            "captcha_html": data.get("div_captcha"),
        }
