"""ERPNavi サポートナビゲーター: 簡易チャットUI(Streamlit)。"""

import logging
import uuid

import streamlit as st
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from openai import AzureOpenAI

from src.app.formatting import format_citations_markdown
from src.config import load_azure_cosmos_config, load_azure_openai_config, load_azure_search_config
from src.rag.generator import RagAnswer, generate_answer
from src.session.cosmos_client import get_sessions_container
from src.session.history_manager import SessionHistoryManager

logger = logging.getLogger(__name__)

# 業務担当者が「何を聞けるか分からない」まま離脱しないよう、代表的な質問例を
# サイドバーにワンクリックで試せる形で提示する。
EXAMPLE_QUESTIONS = [
    "ERPNaviの初期設定はどこから始めればいいですか？",
    "在庫の発注点アラートが届かない場合はどうすればいいですか？",
    "月次締め処理ができないときの原因は何ですか？",
]

# 例外の詳細(Azure SDKのエラーメッセージ等)を業務担当者向け画面にそのまま出さないための
# 固定文言。詳細はlogger.exceptionでサーバー側ログにのみ残す。
USER_FACING_ERROR_MESSAGE = "エラーが発生しました。担当部署にお問い合わせください。"

st.set_page_config(page_title="ERPNavi サポートナビゲーター", page_icon="🧭")


@st.cache_resource
def _load_clients():
    openai_config = load_azure_openai_config()
    search_config = load_azure_search_config()
    cosmos_config = load_azure_cosmos_config()

    openai_client = AzureOpenAI(
        azure_endpoint=openai_config.endpoint,
        api_key=openai_config.api_key,
        api_version=openai_config.api_version,
    )
    search_client = SearchClient(
        search_config.endpoint, search_config.index_name, AzureKeyCredential(search_config.api_key)
    )
    history_manager = SessionHistoryManager(get_sessions_container(cosmos_config))
    return openai_client, openai_config, search_client, history_manager


def _new_session_id() -> str:
    return f"streamlit-{uuid.uuid4().hex[:8]}"


def _init_session_state() -> None:
    if "session_id" not in st.session_state:
        st.session_state.session_id = _new_session_id()
    if "messages" not in st.session_state:
        st.session_state.messages = []


def _render_sidebar() -> None:
    with st.sidebar:
        st.header("ERPNavi サポートナビゲーター")
        st.caption(f"セッションID: {st.session_state.session_id}")
        if st.button("新しい会話を始める"):
            st.session_state.session_id = _new_session_id()
            st.session_state.messages = []
            st.rerun()
        st.divider()
        st.subheader("よくある質問例")
        for question in EXAMPLE_QUESTIONS:
            if st.button(question, key=f"example-{question}"):
                st.session_state.pending_question = question


def _render_history() -> None:
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if message.get("citations_markdown"):
                with st.expander("引用元を表示"):
                    st.markdown(message["citations_markdown"])


def _generate_answer_safely(
    *, query: str, session_id: str, generate_answer_fn=generate_answer, **kwargs
) -> RagAnswer | None:
    """`generate_answer`を呼び出し、失敗時は詳細をログにのみ残してNoneを返す。

    Streamlitの描画呼び出し(`st.*`)を含まないため、`generate_answer_fn`を差し替えれば
    実際のAzure接続なしに例外処理の分岐だけを単体テストできる。
    """
    try:
        return generate_answer_fn(query=query, session_id=session_id, **kwargs)
    except Exception:
        logger.exception("RAG回答生成に失敗しました (session_id=%s)", session_id)
        return None


def _handle_query(query: str) -> None:
    openai_client, openai_config, search_client, history_manager = _load_clients()

    st.session_state.messages.append({"role": "user", "content": query})
    with st.chat_message("user"):
        st.markdown(query)

    with st.chat_message("assistant"), st.spinner("回答を生成しています..."):
        result = _generate_answer_safely(
            query=query,
            session_id=st.session_state.session_id,
            openai_client=openai_client,
            embedding_deployment=openai_config.embedding_deployment,
            chat_deployment=openai_config.chat_deployment,
            search_client=search_client,
            history_manager=history_manager,
        )
        if result is None:
            st.error(USER_FACING_ERROR_MESSAGE)
            st.session_state.messages.append(
                {"role": "assistant", "content": USER_FACING_ERROR_MESSAGE}
            )
            return

        citations_markdown = format_citations_markdown(result.citations)
        st.markdown(result.answer)
        if citations_markdown:
            with st.expander("引用元を表示"):
                st.markdown(citations_markdown)
        st.session_state.messages.append(
            {
                "role": "assistant",
                "content": result.answer,
                "citations_markdown": citations_markdown,
            }
        )


def main() -> None:
    _init_session_state()
    _render_sidebar()

    st.title("🧭 ERPNavi サポートナビゲーター")
    st.caption(
        "ERP導入・設定手順について質問できます。回答は参考情報に基づき、引用元を明示します。"
    )

    _render_history()

    pending_question = st.session_state.pop("pending_question", None)
    query = st.chat_input("質問を入力してください") or pending_question
    if query:
        _handle_query(query)


if __name__ == "__main__":
    # Streamlitはスクリプトを常に __main__ として実行するため、このガードは
    # `streamlit run` 経由の実行では機能しつつ、pytestからの通常importでは
    # main()を実行させない(_generate_answer_safely等を副作用なく単体テストできる)。
    main()
