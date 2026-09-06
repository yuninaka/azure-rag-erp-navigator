"""RAG回答生成用のプロンプトテンプレート。"""

from src.rag.search_client import SearchHit

SYSTEM_PROMPT = """あなたはERP／基幹システム「ERPNavi」の導入・設定手順を案内するナビゲーターアシスタントです。
以下のルールを厳守してください。

- 必ず「参考情報」に記載された内容のみを根拠に回答してください。参考情報にない内容を推測で補ってはいけません。
- 参考情報だけでは回答できない場合は、正直に「提供された情報からは回答できません」と述べ、
  社内の担当部署への問い合わせを促してください。
- 回答の各主張の末尾に、根拠とした参考情報の番号を [1] のように付記してください。
- 業務担当者にも分かりやすいよう、手順は箇条書きで示してください。
"""


def _format_context_entry(index: int, hit: SearchHit) -> str:
    # section_pathは見出しパスの先頭に既にtitle(H1)を含む(chunkers.pyの設計)ため、
    # ここでhit.titleを前置するとタイトルが二重表示される。
    return f"[{index}] {hit.section_path}\n{hit.content}"


def build_user_message(query: str, hits: list[SearchHit]) -> str:
    """検索結果を番号付き参考情報として質問に付与するユーザーメッセージを組み立てる。"""
    context = "\n\n".join(_format_context_entry(i, hit) for i, hit in enumerate(hits, start=1))
    return f"### 参考情報\n{context}\n\n### 質問\n{query}"
