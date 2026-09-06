from eval.metrics import keyword_coverage


def test_keyword_coverage_all_keywords_present():
    assert (
        keyword_coverage("テナント発行コードと会社名が必要です。", ["テナント発行コード", "会社名"])
        == 1.0
    )


def test_keyword_coverage_partial_match():
    assert (
        keyword_coverage("テナント発行コードが必要です。", ["テナント発行コード", "会社名"]) == 0.5
    )


def test_keyword_coverage_no_match():
    assert keyword_coverage("分かりません。", ["テナント発行コード", "会社名"]) == 0.0


def test_keyword_coverage_with_no_expected_keywords_returns_zero():
    assert keyword_coverage("何かの回答", []) == 0.0
