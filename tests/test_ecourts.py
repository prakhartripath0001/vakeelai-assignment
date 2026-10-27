import os
from unittest.mock import Mock

import pytest

from backend.scraper.ecourts import ECourtsScraper

AJAX_HELPER = """
function ajaxCall(jsonobj) {
    var delimeter="current-test-value";
    $.ajax({
        headers: {
            "delimeter": delimeter,
            "CurrentPortalHeader": delimeter
        }
    });
}
function ajaxCallNormal(jsonobj) {}
"""


def mock_bootstrap_responses(scraper, captcha_response):
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
        '<select id="sess_state_code"><option value="26">Delhi</option></select>'
        '<script src="/ecourtindia_v6/js/components.js?v=1"></script>'
    )
    mock_case_status_response.raise_for_status.return_value = None
    mock_script_response = Mock()
    mock_script_response.text = AJAX_HELPER
    mock_script_response.raise_for_status.return_value = None

    scraper.session.get = Mock(
        side_effect=[
            mock_home_response,
            mock_case_status_response,
            mock_script_response,
        ]
    )
    scraper.session.post = Mock(return_value=captcha_response)
    return mock_home_response, mock_case_status_response


def test_portal_rejection_is_reported():
    scraper = ECourtsScraper()
    mock_response = Mock()
    mock_response.raise_for_status.return_value = None
    mock_response.headers = {"Content-Type": "text/html; charset=utf-8"}
    mock_response.json.return_value = {"errormsg": "Invalid Request"}

    mock_bootstrap_responses(scraper, mock_response)

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
    _, mock_case_status_response = mock_bootstrap_responses(
        scraper, mock_response
    )

    result = scraper.get_captcha_and_token()

    assert result["app_token"] == "test-token"
    assert result["captcha_html"] == "<div>CAPTCHA form</div>"
    assert result["captcha_image_available"] is False
    assert scraper.session.get.call_count == 3
    assert scraper.session.get.call_args_list[0].args == (scraper.base_url,)
    assert scraper.session.get.call_args_list[1].args == (
        mock_case_status_response.url,
    )
    scraper.session.post.assert_called_once()
    headers = scraper.session.post.call_args.kwargs["headers"]
    assert headers["delimeter"] == "current-test-value"
    assert headers["CurrentPortalHeader"] == "current-test-value"
    assert scraper.session.post.call_args.kwargs["data"]["app_token"] == "test-token"

    print("PASS: app_token and CAPTCHA HTML parsed successfully.")


def test_search_by_cnr_uses_portal_ajax_contract():
    scraper = ECourtsScraper()
    scraper.app_token = "session-token"
    scraper.ajax_headers = {
        "delimeter": "current-test-value",
        "CurrentPortalHeader": "current-test-value",
    }
    scraper.case_status_url = (
        f"{scraper.base_url}?p=casestatus/index&app_token=session-token"
    )
    response = Mock()
    response.json.return_value = {
        "status": 1,
        "casetype_list": (
            "<table><tr><th>Case title</th><th>Status</th></tr>"
            "<tr><td>Punjab National Bank vs Sunil Kumar</td>"
            "<td>Pending</td></tr></table>"
            '<a href="/orders/order.pdf">Order dated 01-01-2025</a>'
        ),
    }
    response.raise_for_status.return_value = None
    response.headers = {"Content-Type": "application/json"}
    scraper.session.post = Mock(return_value=response)

    result = scraper.search_cnr("DLND020000602007", "abcde")

    request = scraper.session.post.call_args
    assert request.kwargs["params"] == {"p": "cnr_status/searchByCNR/"}
    assert request.kwargs["data"] == {
        "cino": "DLND020000602007",
        "fcaptcha_code": "abcde",
        "ajax_req": "true",
        "app_token": "session-token",
    }
    assert request.kwargs["headers"]["delimeter"] == "current-test-value"
    assert request.kwargs["headers"]["CurrentPortalHeader"] == "current-test-value"
    assert request.kwargs["headers"]["Referer"] == scraper.case_status_url
    assert result["status"] == 1
    assert result["casetype_list"]["tables"][0][1][0] == (
        "Punjab National Bank vs Sunil Kumar"
    )
    assert result["links"][0]["url"] == (
        "https://services.ecourts.gov.in/orders/order.pdf"
    )


def test_search_by_case_number_posts_selected_portal_values():
    scraper = ECourtsScraper()
    scraper.app_token = "session-token"
    scraper.ajax_headers = {"delimeter": "test", "Header": "test"}
    response = Mock()
    response.json.return_value = {"status": 0, "case_data": ""}
    response.raise_for_status.return_value = None
    response.headers = {"Content-Type": "application/json"}
    scraper.session.post = Mock(return_value=response)

    scraper.search_case_number(
        state_code="26",
        district_code="district-code",
        court_complex_code="1260011@1,2,3,4@Y",
        establishment_code="1",
        case_type="CS(COMM)",
        case_number="233",
        year=2024,
        captcha="abcde",
    )

    request = scraper.session.post.call_args
    assert request.kwargs["params"] == {"p": "casestatus/submitCaseNo"}
    assert request.kwargs["data"] == {
        "state_code": "26",
        "dist_code": "district-code",
        "court_complex_code": "1260011",
        "est_code": "1",
        "case_type": "CS(COMM)",
        "case_no": "233",
        "rgyear": "2024",
        "case_captcha_code": "abcde",
        "ajax_req": "true",
        "app_token": "session-token",
    }


def test_search_by_case_number_allows_complex_without_establishment():
    scraper = ECourtsScraper()
    scraper.app_token = "session-token"
    scraper.ajax_headers = {"delimeter": "test", "Header": "test"}
    response = Mock()
    response.json.return_value = {"status": 0}
    response.raise_for_status.return_value = None
    response.headers = {"Content-Type": "application/json"}
    scraper.session.post = Mock(return_value=response)

    scraper.search_case_number(
        state_code="26",
        district_code="10",
        court_complex_code="1260011@1,2,3,4@N",
        establishment_code="",
        case_type="CS",
        case_number="233",
        year=2024,
        captcha="abcde",
    )

    assert scraper.session.post.call_args.kwargs["data"]["est_code"] == ""
    assert scraper.session.post.call_args.kwargs["data"]["court_complex_code"] == "1260011"


def test_case_search_district_options_use_portal_ajax_contract():
    scraper = ECourtsScraper()
    scraper.app_token = "session-token"
    scraper.ajax_headers = {"delimeter": "test", "Header": "test"}
    response = Mock()
    response.json.return_value = {
        "status": 1,
        "dist_list": '<option value="10">South</option>',
    }
    response.raise_for_status.return_value = None
    response.headers = {"Content-Type": "application/json"}
    scraper.session.post = Mock(return_value=response)

    options = scraper.get_case_search_options("districts", state_code="26")

    assert options == [{"value": "10", "label": "South"}]
    request = scraper.session.post.call_args
    assert request.kwargs["params"] == {"p": "casestatus/fillDistrict"}
    assert request.kwargs["data"] == {
        "state_code": "26",
        "ajax_req": "true",
        "app_token": "session-token",
    }


def test_cnr_requires_exactly_16_alphanumeric_characters():
    scraper = ECourtsScraper()

    with pytest.raises(ValueError, match="exactly 16"):
        scraper.search_cnr("not-a-cnr", "abcde")


@pytest.mark.skipif(
    os.getenv("RUN_ECOURTS_LIVE_TEST") != "1",
    reason="Set RUN_ECOURTS_LIVE_TEST=1 to query the external eCourts portal.",
)
def test_live_captcha_request():
    scraper = ECourtsScraper()

    result = scraper.get_captcha_and_token()
    image, content_type = scraper.get_captcha_image()

    assert result["app_token"], "Portal did not return an app_token"
    assert result["captcha_html"], "Portal did not return CAPTCHA HTML"
    assert result["captcha_image_available"], "Portal did not provide a CAPTCHA image"
    assert image, "Portal CAPTCHA image was empty"
    assert content_type.startswith("image/"), "Portal did not return image content"

    print("PASS: Live portal returned an app_token.")
    print("PASS: CAPTCHA HTML received.")