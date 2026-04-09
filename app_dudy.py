import json
import re
import time
import requests
import streamlit as st


# -----------------------------
# Config
# -----------------------------
DUDY_LAMBDA_URL = "https://n6iudam7vomf747ijpiggbdyoa0gsrma.lambda-url.ap-southeast-1.on.aws/"

st.set_page_config(page_title="Dudy Chatbot", page_icon="💬", layout="wide")
st.title("💬 Dudy Stream Chatbot")

# -----------------------------
# Session state
# -----------------------------
if "messages" not in st.session_state:
    st.session_state.messages = []

if "session_id" not in st.session_state:
    st.session_state.session_id = "test-final-01"

if "username" not in st.session_state:
    st.session_state.username = ""

if "password" not in st.session_state:
    st.session_state.password = ""


# -----------------------------
# Sidebar
# -----------------------------
with st.sidebar:
    st.header("Settings")

    st.session_state.username = st.text_input(
        "Username (EN)",
        value=st.session_state.username
    )

    st.session_state.password = st.text_input(
        "Password",
        value=st.session_state.password,
        type="password"
    )

    st.session_state.session_id = st.text_input(
        "Session ID",
        value=st.session_state.session_id
    )

    if st.button("Clear chat"):
        st.session_state.messages = []
        st.rerun()


# -----------------------------
# Render helper
# -----------------------------
_URL_RE = re.compile(r'(https?://\S+)')

def render_content(text: str):
    parts = _URL_RE.split(text)
    for part in parts:
        if _URL_RE.fullmatch(part):
            st.image(part)
        elif part:
            st.markdown(part)


# -----------------------------
# Stream function
# -----------------------------
def invoke_lambda_stream(user_query: str, username: str, password: str, session_id: str, lambda_url: str):
    payload = {
        "query": user_query,
        "en": username,
        "password": password,
        "session_id": session_id
    }

    try:
        with requests.post(
            lambda_url,
            json=payload,
            headers={"Content-Type": "application/json"},
            stream=True,
            timeout=300,
        ) as response:
            response.raise_for_status()

            for line in response.iter_lines():
                if not line:
                    continue

                decoded = line.decode("utf-8").strip()

                try:
                    data = json.loads(decoded)
                    yield data
                except json.JSONDecodeError:
                    yield {"type": "raw", "content": decoded}

    except requests.exceptions.RequestException as e:
        yield {"type": "error", "content": f"Request error: {str(e)}"}


# -----------------------------
# Validate required fields
# -----------------------------
if not st.session_state.username or not st.session_state.password:
    st.warning("กรุณากรอก Username และ Password ใน Sidebar ก่อนเริ่มสนทนา")
    st.stop()


# -----------------------------
# Render old chat
# -----------------------------
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        if message["role"] == "assistant":
            st.caption("Agent: Dudy")
        render_content(message["content"])


# -----------------------------
# Input box
# -----------------------------
prompt = st.chat_input("Type your message...")

if prompt:
    # show user message
    st.session_state.messages.append({
        "role": "user",
        "content": prompt,
    })
    with st.chat_message("user"):
        st.markdown(prompt)

    # show assistant streaming area
    with st.chat_message("assistant"):
        st.caption("Agent: Dudy")
        response_placeholder = st.empty()
        info_placeholder = st.empty()
        full_response = ""
        first_token_received = False

        response_placeholder.markdown("_Thinking..._")

        start_time = time.time()

        for event in invoke_lambda_stream(
            user_query=prompt,
            username=st.session_state.username,
            password=st.session_state.password,
            session_id=f"dudy-{st.session_state.session_id}",
            lambda_url=DUDY_LAMBDA_URL,
        ):
            event_type = event.get("type")

            if event_type == "StatusCode":
                info_placeholder.caption(f"Status: {event.get('code')}")

            elif event_type == "token":
                first_token_received = True
                token = event.get("content", "")
                full_response += token
                response_placeholder.markdown(full_response + "▌")

            elif event_type == "error":
                first_token_received = True
                full_response += f"\n\n❌ {event.get('content', '')}"
                response_placeholder.markdown(full_response)

            elif event_type == "raw":
                first_token_received = True
                raw_text = event.get("content", "")
                full_response += raw_text
                response_placeholder.markdown(full_response + "▌")

        elapsed = time.time() - start_time

        if not full_response.strip():
            full_response = "_No response received_"

        response_placeholder.empty()
        render_content(full_response)
        info_placeholder.caption(f"⏱ Response time: {elapsed:.2f}s")

    st.session_state.messages.append({
        "role": "assistant",
        "content": full_response,
        "agent_name": "Dudy",
    })


# streamlit run app_dudy.py
