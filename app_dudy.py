import json
import re
import time
import uuid
import random
import string
import requests
import streamlit as st


# -----------------------------
# Config
# -----------------------------
DUDY_LAMBDA_URL = "https://n6iudam7vomf747ijpiggbdyoa0gsrma.lambda-url.ap-southeast-1.on.aws/"

st.set_page_config(page_title="dudy Chatbot", page_icon="💬", layout="wide")

# Inject thinking animation CSS
st.markdown("""
<style>
@keyframes dudy-bounce {
  0%, 60%, 100% { transform: translateY(0); opacity: 0.35; }
  30% { transform: translateY(-6px); opacity: 1; }
}
.dudy-thinking {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 6px 0;
}
.dudy-dots {
  display: flex;
  gap: 5px;
  align-items: center;
}
.dudy-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #888;
  animation: dudy-bounce 1.1s ease-in-out infinite;
}
.dudy-dot:nth-child(1) { animation-delay: 0s; }
.dudy-dot:nth-child(2) { animation-delay: 0.18s; }
.dudy-dot:nth-child(3) { animation-delay: 0.36s; }
.dudy-label {
  color: #888;
  font-size: 0.88em;
  font-style: italic;
}
</style>
""", unsafe_allow_html=True)

THINKING_HTML = """
<div class="dudy-thinking">
  <div class="dudy-dots">
    <span class="dudy-dot"></span>
    <span class="dudy-dot"></span>
    <span class="dudy-dot"></span>
  </div>
  <span class="dudy-label">Thinking...</span>
</div>
"""


# -----------------------------
# Helpers
# -----------------------------
def generate_session_id():
    return str(uuid.uuid4()).replace("-", "")[:12]


def generate_en():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))


def new_chat_entry():
    return {
        "id": str(uuid.uuid4()),
        "session_id": generate_session_id(),
        "en": generate_en(),
        "messages": [],
        "title": "New Chat",
    }


def get_active_chat():
    for chat in st.session_state.chats:
        if chat["id"] == st.session_state.active_chat_id:
            return chat
    return None


# -----------------------------
# Session state init
# -----------------------------
if "chats" not in st.session_state:
    first = new_chat_entry()
    st.session_state.chats = [first]
    st.session_state.active_chat_id = first["id"]

if "password" not in st.session_state:
    st.session_state.password = ""


# -----------------------------
# Sidebar
# -----------------------------
with st.sidebar:
    st.markdown("## 💬 dudy Chatbot")

    st.session_state.password = st.text_input(
        "Password",
        value=st.session_state.password,
        type="password",
    )

    if st.button("➕ New Chat", use_container_width=True, type="primary"):
        entry = new_chat_entry()
        st.session_state.chats.insert(0, entry)
        st.session_state.active_chat_id = entry["id"]
        st.rerun()

    st.divider()
    st.markdown("**Chat History**")

    for chat in st.session_state.chats:
        is_active = chat["id"] == st.session_state.active_chat_id
        label = f"{'▶ ' if is_active else ''}{chat['title']}"
        if st.button(label, key=f"chat_{chat['id']}", use_container_width=True):
            st.session_state.active_chat_id = chat["id"]
            st.rerun()


# -----------------------------
# Main area
# -----------------------------
st.title("💬 dudy Stream Chatbot")

active = get_active_chat()

if active:
    st.caption(f"Session: `{active['session_id']}`  |  EN: `{active['en']}`")


# -----------------------------
# Validate password
# -----------------------------
if not st.session_state.password:
    st.warning("กรุณากรอก Password ใน Sidebar ก่อนเริ่มสนทนา")
    st.stop()

if not active:
    st.error("ไม่พบ chat session กรุณากด New Chat")
    st.stop()


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
def invoke_lambda_stream(user_query, username, password, session_id, lambda_url):
    payload = {
        "query": user_query,
        "en": username,
        "password": password,
        "session_id": session_id,
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
                    yield json.loads(decoded)
                except json.JSONDecodeError:
                    yield {"type": "raw", "content": decoded}
    except requests.exceptions.RequestException as e:
        yield {"type": "error", "content": f"Request error: {str(e)}"}


# -----------------------------
# Render existing messages
# -----------------------------
for message in active["messages"]:
    with st.chat_message(message["role"]):
        if message["role"] == "assistant":
            st.caption("Agent: dudy")
        render_content(message["content"])


# -----------------------------
# Chat input
# -----------------------------
prompt = st.chat_input("Type your message...")

if prompt:
    # Update chat title from first user message
    if active["title"] == "New Chat":
        active["title"] = prompt[:40] + ("..." if len(prompt) > 40 else "")

    active["messages"].append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        st.caption("Agent: dudy")
        response_placeholder = st.empty()
        info_placeholder = st.empty()
        full_response = ""

        response_placeholder.markdown(THINKING_HTML, unsafe_allow_html=True)
        start_time = time.time()

        for event in invoke_lambda_stream(
            user_query=prompt,
            username=active["en"],
            password=st.session_state.password,
            session_id=f"dudy-{active['session_id']}",
            lambda_url=DUDY_LAMBDA_URL,
        ):
            event_type = event.get("type")

            if event_type == "StatusCode":
                info_placeholder.caption(f"Status: {event.get('code')}")
            elif event_type == "token":
                full_response += event.get("content", "")
                response_placeholder.markdown(full_response + "▌")
            elif event_type in ("error", "raw"):
                prefix = "\n\n❌ " if event_type == "error" else ""
                full_response += prefix + event.get("content", "")
                response_placeholder.markdown(full_response + "▌")

        elapsed = time.time() - start_time

        if not full_response.strip():
            full_response = "_No response received_"

        response_placeholder.empty()
        render_content(full_response)
        info_placeholder.caption(f"⏱ Response time: {elapsed:.2f}s")

    active["messages"].append({
        "role": "assistant",
        "content": full_response,
        "agent_name": "dudy",
    })


# streamlit run app_audy.py
