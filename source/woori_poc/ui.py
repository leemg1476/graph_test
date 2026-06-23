from __future__ import annotations

import time
from typing import Any

import httpx
import streamlit as st


DEFAULT_API_URL = "http://127.0.0.1:8787"
EXAMPLE_QUESTIONS = [
    "수집된 데이터 컬렉션 목록을 보여줘.",
    "금융지주회사감독규정시행세칙의 별표/별지 목록을 찾아줘.",
    "감사원 적극행정 사례 중 계약 관련 사례를 찾아서 요약해줘.",
    "법제처 법령해석례에서 금융회사 내부통제와 관련된 질의를 찾아줘.",
    "graphify 결과에서 금융감독원 데이터의 주요 노드와 파일 관계를 설명해줘.",
    "LLM wiki 기준으로 각 컬렉션을 어떻게 탐색하면 좋은지 알려줘.",
]


def call_health(api_url: str) -> tuple[bool, str]:
    try:
        response = httpx.get(f"{api_url.rstrip('/')}/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            return True, f"API OK, model_configured={data.get('model_configured')}"
        return False, f"HTTP {response.status_code}: {response.text[:200]}"
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"


def call_chat(api_url: str, message: str) -> tuple[str, float]:
    started = time.perf_counter()
    response = httpx.post(
        f"{api_url.rstrip('/')}/chat",
        json={"message": message},
        timeout=300,
    )
    elapsed = time.perf_counter() - started
    response.raise_for_status()
    data: dict[str, Any] = response.json()
    return str(data.get("answer", "")), elapsed


def init_state() -> None:
    st.session_state.setdefault("messages", [])
    st.session_state.setdefault("api_url", DEFAULT_API_URL)


def render_sidebar() -> str:
    with st.sidebar:
        st.header("Agent")
        api_url = st.text_input("FastAPI URL", value=st.session_state.api_url)
        st.session_state.api_url = api_url

        ok, status = call_health(api_url)
        if ok:
            st.success(status)
        else:
            st.error(status)

        if st.button("대화 초기화", use_container_width=True):
            st.session_state.messages = []
            st.rerun()

        st.divider()
        st.subheader("예시 질문")
        for idx, question in enumerate(EXAMPLE_QUESTIONS):
            if st.button(question, key=f"example_{idx}", use_container_width=True):
                st.session_state.pending_question = question
                st.rerun()

        st.divider()
        st.caption("먼저 `python -m woori_poc.api`로 FastAPI agent를 실행하세요.")
    return api_url


def render_messages() -> None:
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if message.get("elapsed") is not None:
                st.caption(f"{message['elapsed']:.1f}s")


def submit(api_url: str, prompt: str) -> None:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        placeholder = st.empty()
        placeholder.markdown("응답 생성 중...")
        try:
            answer, elapsed = call_chat(api_url, prompt)
            placeholder.markdown(answer)
            st.caption(f"{elapsed:.1f}s")
            st.session_state.messages.append(
                {"role": "assistant", "content": answer, "elapsed": elapsed}
            )
        except Exception as exc:
            error = f"요청 실패: `{type(exc).__name__}`\n\n```text\n{exc}\n```"
            placeholder.markdown(error)
            st.session_state.messages.append({"role": "assistant", "content": error})


def main() -> None:
    st.set_page_config(page_title="Woori PoC Agent", page_icon="🔎", layout="wide")
    init_state()
    api_url = render_sidebar()

    st.title("Woori PoC Agent Test UI")
    st.caption("수집 데이터, graphify 결과, LLM wiki를 MCP로 탐색하는 LangGraph agent 테스트 화면입니다.")

    render_messages()

    pending = st.session_state.pop("pending_question", None)
    prompt = pending or st.chat_input("질문을 입력하세요")
    if prompt:
        submit(api_url, prompt)


if __name__ == "__main__":
    main()
