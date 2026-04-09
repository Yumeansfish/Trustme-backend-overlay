from trustme_api.browser.surveys.result_csv import build_result_csv_rows as legacy_build_result_csv_rows
from trustme_api.browser.surveys.result_export import build_result_csv_rows


def test_result_csv_shim_reexports_result_export():
    assert legacy_build_result_csv_rows is build_result_csv_rows
