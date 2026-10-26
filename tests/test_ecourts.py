import os
from unittest.mock import Mock

import pytest

from backend.scraper.ecourts import ECourtsScraper


def test_portal_rejection_is_reported():
    scraper = ECourtsScraper()
    mock_home_response = Mock()
    mock_home_response.url = scraper.base_url
    mock_home_response.text = (
        '<a id="leftPaneMenuCS" '
        'href="/ecourtindia_v6/?p=casestatus/index&app_token=test-token"></a>'
    )
    mock_home_response.raise_for_status.return_value = None
    mock_case_status_response = Mock()
    mock_case_status_response.url = (
        f"{scraper.base_url}?p=casestatus/index&app_token=test-token"
    )
    mock_case_status_response.text = (
        '<input id="app_token" name="app_token" value="test-token">'
    )
    mock_case_status_response.raise_for_status.return_value = None
    mock_response = Mock()
    mock_response.raise_for_status.return_value = None
    mock_response.headers = {"Content-Type": "text/html; charset=utf-8"}
    mock_response.json.return_value = {"errormsg": "Invalid Request"}

    scraper.session.get = Mock(
        side_effect=[mock_home_response, mock_case_status_response]
    )
    scraper.session.post = Mock(return_value=mock_response)

    with pytest.raises(
        RuntimeError, match="rejected the CAPTCHA request: Invalid Request"
    ):
        scraper.get_captcha_and_token()


def test_get_captcha_and_token():
    scraper = ECourtsScraper()

    mock_response = Mock()
    mock_response.json.return_value = {
        "app_token": "test-token",
        "div_captcha": "<div>CAPTCHA form</div>",
    }
    mock_response.raise_for_status.return_value = None

    mock_response.headers = {
        "Content-Type": "application/json; charset=utf-8"
    }
    mock_home_response = Mock()
    mock_home_response.url = scraper.base_url
    mock_home_response.text = (
        '<a id="leftPaneMenuCS" '
        'href="/ecourtindia_v6/?p=casestatus/index&app_token=test-token"></a>'
    )
    mock_home_response.raise_for_status.return_value = None
    mock_case_status_response = Mock()
    mock_case_status_response.url = (
        f"{scraper.base_url}?p=casestatus/index&app_token=test-token"
    )
    mock_case_status_response.text = (
        '<input id="app_token" name="app_token" value="test-token">'
    )
    mock_case_status_response.raise_for_status.return_value = None

    scraper.session.get = Mock(
        side_effect=[mock_home_response, mock_case_status_response]
    )
    scraper.session.post = Mock(return_value=mock_response)

    result = scraper.get_captcha_and_token()

    assert result["app_token"] == "test-token"
    assert result["captcha_html"] == "<div>CAPTCHA form</div>"
    assert scraper.session.get.call_count == 2
    assert scraper.session.get.call_args_list[0].args == (scraper.base_url,)
    assert scraper.session.get.call_args_list[1].args == (
        mock_case_status_response.url,
    )
    scraper.session.post.assert_called_once()
    headers = scraper.session.post.call_args.kwargs["headers"]
    assert headers["delimeter"] == "wehf735ytf"
    assert headers["K98923rh"] == "wehf735ytf"
    assert scraper.session.post.call_args.kwargs["data"]["app_token"] == "test-token"

    print("PASS: app_token and CAPTCHA HTML parsed successfully.")


@pytest.mark.skipif(
    os.getenv("RUN_ECOURTS_LIVE_TEST") != "1",
    reason="Set RUN_ECOURTS_LIVE_TEST=1 to query the external eCourts portal.",
)
def test_live_captcha_request():
    scraper = ECourtsScraper()

    result = scraper.get_captcha_and_token()

    assert result["app_token"], "Portal did not return an app_token"
    assert result["captcha_html"], "Portal did not return CAPTCHA HTML"

    print("PASS: Live portal returned an app_token.")
    print("PASS: CAPTCHA HTML received.")