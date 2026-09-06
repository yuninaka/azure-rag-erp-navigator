from eval.metrics import keyword_coverage


def test_keyword_coverage_all_keywords_present() -> None:
    assert (
        keyword_coverage("テナント発行コードと会社名が必要です。", ["テナント発行コード", "会社名"])
        == 1.0
    )


def test_keyword_coverage_partial_match() -> None:
    one_of_two_keywords_matched = 0.5
    assert (
        keyword_coverage("テナント発行コードが必要です。", ["テナント発行コード", "会社名"])
        == one_of_two_keywords_matched
    )


def test_keyword_coverage_no_match() -> None:
    assert keyword_coverage("分かりません。", ["テナント発行コード", "会社名"]) == 0.0


def test_keyword_coverage_with_no_expected_keywords_returns_zero() -> None:
    assert keyword_coverage("何かの回答", []) == 0.0
