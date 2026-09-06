from pathlib import Path

from eval.dataset import load_golden_qa

GOLDEN_QA_PATH = Path(__file__).resolve().parent.parent / "eval" / "golden_qa.jsonl"


def test_load_golden_qa_loads_all_cases_with_required_fields():
    cases = load_golden_qa(GOLDEN_QA_PATH)

    assert len(cases) == 18
    for case in cases:
        assert case["id"]
        assert case["category"]
        assert case["question"]
        assert len(case["expected_keywords"]) >= 1


def test_load_golden_qa_has_unique_ids():
    cases = load_golden_qa(GOLDEN_QA_PATH)
    ids = [case["id"] for case in cases]

    assert len(ids) == len(set(ids))
