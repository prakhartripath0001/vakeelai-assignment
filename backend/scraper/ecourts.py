import re
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://services.ecourts.gov.in/ecourtindia_v6/"


class ECourtsScraper:
    """Keep the portal's cookies and rotating token together for one search."""

    def __init__(self) -> None:
        self.session = requests.Session()
        self.base_url = BASE_URL
        self.case_status_url: str | None = None
        self.app_token: str | None = None
        self.captcha_image_url: str | None = None
        self.ajax_headers: dict[str, str] = {}
        self.state_options: list[dict[str, str]] = []

    def get_captcha_and_token(self) -> dict[str, str | bool | None]:
        """Create a portal session and request its CAPTCHA without solving it."""
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
        self.case_status_url = case_status_response.url
        case_status_page = BeautifulSoup(case_status_response.text, "html.parser")
        self.ajax_headers = self._get_ajax_headers(
            case_status_page, case_status_response.url
        )
        self.state_options = self._parse_options(
            str(case_status_page.select_one("#sess_state_code") or "")
        )
        if not self.state_options:
            raise RuntimeError("The eCourts Case Status page does not contain state options.")
        token_input = case_status_page.find("input", id="app_token")

        if token_input is None or not token_input.get("value"):
            raise RuntimeError("The eCourts Case Status page does not contain app_token.")

        base_url_parts = urlparse(self.base_url)
        response = self.session.post(
            self.base_url,
            params={"p": "casestatus/getCaptcha"},
            data={
                "ajax_req": "true",
                "app_token": token_input["value"],
            },
            headers={
                "X-Requested-With": "XMLHttpRequest",
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "Referer": case_status_response.url,
                "Origin": f"{base_url_parts.scheme}://{base_url_parts.netloc}",
                **self.ajax_headers,
            },
            timeout=30,
        )
        response.raise_for_status()
        data = self._read_json(response)
        self._raise_for_portal_error(data, subject="CAPTCHA")

        token = data.get("app_token")
        if not isinstance(token, str) or not token:
            raise RuntimeError("The response does not contain app_token.")

        self.app_token = token
        captcha_html = data.get("div_captcha")
        self.captcha_image_url = self._captcha_image_url(captcha_html, case_status_response.url)
        return {
            "app_token": token,
            "captcha_html": captcha_html if isinstance(captcha_html, str) else None,
            "captcha_image_available": bool(self.captcha_image_url),
        }

    def get_captcha_image(self) -> tuple[bytes, str]:
        """Fetch the CAPTCHA image through the same cookie-bearing session."""
        if self.captcha_image_url is None:
            raise RuntimeError("The portal response did not contain a CAPTCHA image.")

        response = self.session.get(
            self.captcha_image_url,
            headers={"Referer": self.case_status_url or self.base_url},
            timeout=30,
        )
        response.raise_for_status()
        content_type = response.headers.get("Content-Type", "").split(";", 1)[0].strip()
        if not content_type.startswith("image/"):
            raise RuntimeError("The eCourts CAPTCHA endpoint did not return an image.")
        return response.content, content_type

    def search_cnr(self, cnr_number: str, captcha: str) -> dict[str, object]:
        if not re.fullmatch(r"[A-Za-z0-9]{16}", cnr_number):
            raise ValueError("CNR number must contain exactly 16 letters or digits.")
        if not captcha.strip():
            raise ValueError("CAPTCHA is required.")

        return self._submit_search(
            "cnr_status/searchByCNR/",
            {
                "cino": cnr_number.strip(),
                "fcaptcha_code": captcha.strip(),
            },
        )

    def search_case_number(
        self,
        *,
        state_code: str,
        district_code: str,
        court_complex_code: str,
        establishment_code: str,
        case_type: str,
        case_number: str,
        year: int,
        captcha: str,
    ) -> dict[str, object]:
        fields = {
            "state_code": state_code.strip(),
            "dist_code": district_code.strip(),
            "court_complex_code": court_complex_code.split("@", 1)[0].strip(),
            "est_code": establishment_code.strip(),
            "case_type": case_type.strip(),
            "case_no": case_number.strip(),
            "rgyear": str(year),
            "case_captcha_code": captcha.strip(),
        }
        if any(not fields[key].strip() for key in fields if key != "est_code"):
            raise ValueError("All required case number search fields are required.")

        return self._submit_search("casestatus/submitCaseNo", fields)

    def get_case_search_options(
        self,
        scope: str,
        *,
        state_code: str | None = None,
        district_code: str | None = None,
        court_complex_code: str | None = None,
        establishment_code: str | None = None,
    ) -> list[dict[str, str]]:
        if scope == "states":
            return self.state_options

        if scope == "districts" and state_code:
            endpoint = "casestatus/fillDistrict"
            fields = {"state_code": state_code}
            response_key = "dist_list"
        elif scope == "complexes" and state_code and district_code:
            endpoint = "casestatus/fillcomplex"
            fields = {"state_code": state_code, "dist_code": district_code}
            response_key = "complex_list"
        elif (
            scope == "establishments"
            and state_code
            and district_code
            and court_complex_code
        ):
            endpoint = "casestatus/fillCourtEstablishment"
            fields = {
                "state_code": state_code,
                "dist_code": district_code,
                "court_complex_code": court_complex_code.split("@", 1)[0],
            }
            response_key = "establishment_list"
        elif (
            scope == "case_types"
            and state_code
            and district_code
            and court_complex_code
            and establishment_code is not None
        ):
            endpoint = "casestatus/fillCaseType"
            fields = {
                "state_code": state_code,
                "dist_code": district_code,
                "court_complex_code": court_complex_code.split("@", 1)[0],
                "est_code": establishment_code,
                "search_type": "c_no",
            }
            response_key = "casetype_list"
        else:
            raise ValueError(f"Missing parent selection for {scope} options.")

        data = self._post_ajax(endpoint, fields)
        if str(data.get("status")) != "1":
            raise RuntimeError(f"eCourts did not return {scope} options.")
        markup = data.get(response_key)
        if not isinstance(markup, str):
            raise TypeError(f"eCourts response does not contain {scope} options.")
        return self._parse_options(markup)

    def _submit_search(self, endpoint: str, fields: dict[str, str]) -> dict[str, object]:
        data = self._post_ajax(endpoint, fields)
        if "div_captcha" in data:
            self._update_captcha_image(data["div_captcha"])
        result = self._structure_response(data)
        result["captcha_image_available"] = bool(self.captcha_image_url)
        return result

    def _post_ajax(self, endpoint: str, fields: dict[str, str]) -> dict[str, object]:
        if self.app_token is None:
            raise RuntimeError("Start an eCourts session before making a portal request.")
        if not self.ajax_headers:
            raise RuntimeError("The eCourts AJAX request headers were not initialized.")

        base_url_parts = urlparse(self.base_url)
        response = self.session.post(
            self.base_url,
            params={"p": endpoint},
            data={
                **fields,
                "ajax_req": "true",
                "app_token": self.app_token,
            },
            headers={
                "X-Requested-With": "XMLHttpRequest",
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "Referer": self.case_status_url or urljoin(
                    self.base_url, "?p=casestatus/index"
                ),
                "Origin": f"{base_url_parts.scheme}://{base_url_parts.netloc}",
                **self.ajax_headers,
            },
            timeout=30,
        )
        response.raise_for_status()
        data = self._read_json(response)
        self._raise_for_portal_error(data, subject="search")

        rotated_token = data.get("app_token")
        if isinstance(rotated_token, str) and rotated_token:
            self.app_token = rotated_token
        return data

    def _get_ajax_headers(
        self, page: BeautifulSoup, page_url: str
    ) -> dict[str, str]:
        """Read the portal's per-page AJAX header values from its loaded helper."""
        script_tag = page.select_one('script[src*="components.js"]')
        if script_tag is None or not script_tag.get("src"):
            raise RuntimeError("The eCourts page does not load its AJAX helper script.")

        script_url = urljoin(page_url, script_tag["src"])
        if urlparse(script_url).netloc != urlparse(self.base_url).netloc:
            raise RuntimeError("The eCourts AJAX helper points to an unexpected host.")
        response = self.session.get(
            script_url,
            headers={"Referer": page_url},
            timeout=30,
        )
        response.raise_for_status()
        helper_source = response.text
        helper_start = helper_source.find("function ajaxCall(")
        helper_end = helper_source.find("function ajaxCallNormal", helper_start)
        if helper_start < 0:
            raise RuntimeError("The eCourts AJAX helper does not define ajaxCall.")
        ajax_call_source = helper_source[
            helper_start : helper_end if helper_end > helper_start else None
        ]
        delimiter_match = re.search(
            r"""var\s+delimeter\s*=\s*["']([^"']+)["']""",
            ajax_call_source,
        )
        header_names = re.findall(
            r"""["']([A-Za-z0-9]+)["']\s*:\s*delimeter""",
            ajax_call_source,
        )
        if (
            delimiter_match is None
            or len(header_names) < 2
            or header_names[0].lower() != "delimeter"
        ):
            raise RuntimeError("The eCourts AJAX helper has an unsupported header format.")

        delimiter = delimiter_match.group(1)
        return {
            "delimeter": delimiter,
            header_names[1]: delimiter,
        }

    def _update_captcha_image(self, captcha_html: object) -> None:
        self.captcha_image_url = self._captcha_image_url(captcha_html, self.base_url)

    def _captcha_image_url(self, markup: object, page_url: str) -> str | None:
        if not isinstance(markup, str):
            return None
        image = BeautifulSoup(markup, "html.parser").find("img", src=True)
        if image is None:
            return None
        image_url = urljoin(page_url, image["src"])
        if urlparse(image_url).netloc != urlparse(self.base_url).netloc:
            raise RuntimeError("The CAPTCHA image points to an unexpected host.")
        return image_url

    @staticmethod
    def _read_json(response: requests.Response) -> dict[str, object]:
        try:
            data = response.json()
        except requests.exceptions.JSONDecodeError:
            content_type = response.headers.get("Content-Type", "")
            raise RuntimeError(
                "Expected a JSON response from eCourts, but received "
                f"Content-Type: {content_type or 'unknown'}."
            ) from None
        if not isinstance(data, dict):
            raise TypeError("Unexpected eCourts response structure.")
        return data

    @staticmethod
    def _raise_for_portal_error(data: dict[str, object], subject: str) -> None:
        if data.get("errormsg"):
            error_message = BeautifulSoup(str(data["errormsg"]), "html.parser").get_text(
                " ", strip=True
            )
            raise RuntimeError(f"eCourts rejected the {subject} request: {error_message}")

    def _structure_response(self, data: dict[str, object]) -> dict[str, object]:
        """Convert portal HTML fragments to safe text, table and link data."""
        result: dict[str, object] = {}
        excluded = {"app_token", "div_captcha"}
        html_keys = {
            key
            for key, value in data.items()
            if isinstance(value, str) and ("<" in value or key.endswith("_data"))
        }

        all_links: list[dict[str, str]] = []
        for key, value in data.items():
            if key in excluded:
                continue
            if key in html_keys:
                structured = self._parse_html(value)
                result[key] = structured
                all_links.extend(structured["links"])
            else:
                result[key] = value
        result["links"] = all_links
        return result

    def _parse_html(self, markup: str) -> dict[str, object]:
        soup = BeautifulSoup(markup, "html.parser")
        for element in soup(["script", "style", "noscript"]):
            element.decompose()

        tables: list[list[list[str]]] = []
        for table in soup.find_all("table"):
            rows = [
                [cell.get_text(" ", strip=True) for cell in row.find_all(["th", "td"])]
                for row in table.find_all("tr")
            ]
            rows = [row for row in rows if any(row)]
            if rows:
                tables.append(rows)

        links: list[dict[str, str]] = []
        for anchor in soup.find_all("a", href=True):
            href = urljoin(self.base_url, anchor["href"].strip())
            if urlparse(href).scheme in {"http", "https"}:
                links.append(
                    {
                        "text": anchor.get_text(" ", strip=True),
                        "url": href,
                    }
                )

        return {
            "text": soup.get_text(" ", strip=True),
            "tables": tables,
            "links": links,
        }

    @staticmethod
    def _parse_options(markup: str) -> list[dict[str, str]]:
        soup = BeautifulSoup(markup, "html.parser")
        return [
            {"value": option["value"].strip(), "label": option.get_text(" ", strip=True)}
            for option in soup.find_all("option", value=True)
            if option["value"].strip() not in {"", "0", "Select case type"}
        ]
