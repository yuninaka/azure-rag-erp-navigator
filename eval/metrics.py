"""golden_qa評価の指標計算（Streamlit/Azure非依存の純粋ロジック）。

キーワード網羅率は、過去のNeo4jグラフRAG検証と同じ手法（想定回答に含まれるべき
キーワード群のうち、実際の回答に何割含まれるかを見る）を採用し、直接比較できるようにしている。
"""


def keyword_coverage(answer: str, expected_keywords: list[str]) -> float:
    """回答テキストに、期待キーワードが何割含まれるかを返す（0.0〜1.0）。"""
    if not expected_keywords:
        return 0.0
    hits = sum(1 for keyword in expected_keywords if keyword in answer)
    return hits / len(expected_keywords)
