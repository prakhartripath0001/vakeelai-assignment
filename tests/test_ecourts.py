from unittest.mock import Mock

from backend.scraper.ecourts import ECourtsScraper


def test_get_captcha_and_token():
    scraper = ECourtsScraper()

    mock_response = Mock()
    mock_response.json.return_value = {
        "app_token": "test-token",
        "div_captcha": "<div>CAPTCHA form</div>",
    }
    mock_response.raise_for_status.return_value = None

    scraper.session.post = Mock(return_value=mock_response)

    result = scraper.get_captcha_and_token()

    assert result["app_token"] == "test-token"
    assert result["captcha_html"] == "<div>CAPTCHA form</div>"
    scraper.session.post.assert_called_once()

    print("PASS: app_token and CAPTCHA HTML parsed successfully.")
