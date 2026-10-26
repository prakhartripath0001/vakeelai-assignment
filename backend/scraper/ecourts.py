import requests

BASE_URL = "https://services.ecourts.gov.in/ecourtindia_v6/"


class ECourtsScraper:
    def __init__(self):
        self.session = requests.Session()
        self.base_url = BASE_URL

    def get_captcha_and_token(self) -> dict:
        """Request the CAPTCHA form and read the returned app token."""

        response = self.session.post(
            self.base_url,
            data={
                "p": "casestatus/getCaptcha",
            },
            headers={
                "X-Requested-With": "XMLHttpRequest",
            },
            timeout=30,
        )
        response.raise_for_status()

        data = response.json()

        return {
            "app_token": data.get("app_token"),
            "captcha_html": data.get("div_captcha"),
        }
