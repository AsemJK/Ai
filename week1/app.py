import streamlit as st
import requests
import random
import uuid
import bulk_ingest
import web_scraper_3 as web_scraper
import re
from bs4 import BeautifulSoup


# --- Configuration ---
FASTAPI_URL = "http://localhost:8070"

# --- Page Configuration ---
st.set_page_config(page_title="RAG Assistant", page_icon="🧠", layout="wide")

# --- Session State Initialization ---
if "messages" not in st.session_state:
    st.session_state.messages = []
    
# NEW: Initialize a unique thread_id for this chat session
if "thread_id" not in st.session_state:
    st.session_state.thread_id = str(uuid.uuid4())


# --- Sidebar: Document Ingestion ---
with st.sidebar:
    st.markdown("📂 Knowledge Base Management")
    
    #web scraper
    web_url = st.sidebar.text_input("Web URL")
    link_depth = st.sidebar.number_input("Link Depth", min_value=0, max_value=10, value=1, help="Number of links to follow from the main page")
    if st.sidebar.button("Scrape", use_container_width=True):
        with st.spinner("Scraping..."):
            web_scraper.scrape_and_ingest(web_url, scan_links=True,max_depth=link_depth) #scan links = True for scanning all the links of the given page and also sub-pages
    st.sidebar.divider()
    #single file ingest
    uploaded_file = st.file_uploader(
        "Choose a file",
        type=["pdf", "docx", "xlsx","txt","epub"],
        help="Supported formats: PDF, Word, Excel, TXT, EPUB",
        # accept_multiple_files=True,
        on_change=lambda: st.rerun()
    )

    doc_id = random.randint(1, 9999999)
    # source = st.text_input(
    #     "Source/Metadata",
    #     value="general",
    #     help="E.g., 'HR_Policy', 'Financial_Report'",
    # )
    source_options = st.sidebar.selectbox("Source/Metadata",["general","EA","Software Architecture","Software Engineering","API","programming","csharp","javascript","python","rust","sql","mysql","postgres","sqlite","ai","mobile","web","data","religion","health","finance","HR"])   
    ingest_button = st.button("🚀 Ingest Document")
    if ingest_button:
        if uploaded_file is None:
            st.warning("Please select a file to upload.")
        else:
            with st.spinner(f"Processing {uploaded_file.name}..."):
                try:
                    # Prepare the multipart form data
                    files = {
                        "file": (
                            uploaded_file.name,
                            uploaded_file.getvalue(),
                            uploaded_file.type,
                        )
                    }
                    st.session_state.source = source_options
                    data = {"doc_id": doc_id, "source": st.session_state.source}

                    # Call the FastAPI ingestion endpoint
                    response = requests.post(
                        f"{FASTAPI_URL}/api/v1/ingest-file", files=files, data=data
                    )

                    if response.status_code == 200:
                        result = response.json()
                        st.success(
                            f"✅ Success! Added {result['chunks_added']} chunks to the vector DB."
                        )
                        # clear the input
                        uploaded_file = None
                        # doc_id = str(random.randint(1, 9999999))
                        source = "manual_upload"
                    else:
                        st.error(
                            f"❌ Error: {response.json().get('detail', 'Unknown error')}"
                        )
                except requests.exceptions.ConnectionError:
                    st.error(
                        "❌ Cannot connect to backend. Is FastAPI running on port 8070?"
                    )
# ingest bulk
st.sidebar.divider()
st.sidebar.header("Bulk Ingestion")
folder_path = st.sidebar.text_input("Folder Path")
if folder_path:
    if st.sidebar.button("Start Bulk Ingestion", use_container_width=True):
        with st.spinner("Processing folder..."):
            bulk_ingest.ingest_folder(folder_path)

# --- Main Area: Chat Interface ---
st.markdown("<h4> 🧠 Enterprise RAG Assistant </h4>", unsafe_allow_html=True)
st.caption("Powered by FastAPI, Qdrant, and Open Source LLMs")

# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Chat input
# In app.py, replace the chat input section with:
enable_rag = st.checkbox("Force using RAG",value=True)

if prompt := st.chat_input("Ask anything about your docs, servers, or math..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
        
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        message_placeholder.markdown("🤔 *Routing to the right tool...*")

        try:
            if enable_rag:
                st.sidebar.text(f"forcing rag mode")
                payload = {"query": prompt,"thread_id": st.session_state.thread_id,"tool": "rag" }
            else:
                st.sidebar.text(f"tool auto-selecting mode")    
                payload = {"query": prompt,"thread_id": st.session_state.thread_id,"tool": "auto"}
            response = requests.post(f"{FASTAPI_URL}/api/v1/agent", json=payload)

            if response.status_code == 200:
                result = response.json()
                answer = result["answer"]
                tool = result["tool_used"]
                time_ms = result["processing_time_ms"]

                # Display answer
                message_placeholder.markdown(answer)

                # Show which tool was used (observability!)
                tool_emoji = {
                    "rag": "📚",
                    "sql": "🗄️",
                    "calculator": "🔢",
                    "direct": "💬",
                }.get(tool, "❓")
                st.caption(f"{tool_emoji} Tool: `{tool}` | ⏱️ {time_ms:.0f}ms")

                # Expandable debug info
                with st.expander("🔍 Debug: Tool Details"):
                    st.json(
                        {
                            "tool_input": result["tool_input"],
                            "tool_result_preview": result["tool_result_preview"],
                        }
                    )

                st.session_state.messages.append(
                    {"role": "assistant", "content": answer}
                )
            else:
                message_placeholder.error(f"❌ Error: {response.json().get('detail')}")
        except requests.exceptions.ConnectionError:
            message_placeholder.error("❌ Backend not reachable.")

# --- Footer ---
st.divider()
 # NEW: Chat History Controls
# st.header("💬 Chat Session")
# st.caption(f"Session ID: `{st.session_state.thread_id[:8]}...`")

def get_most_relevant_header(text):
    if not text or not text.strip():
        return ""

    text = text.strip()

    # 1. Try HTML
    if re.search(r"<(?:h[1-6]|title)\b", text, re.IGNORECASE):
        soup = BeautifulSoup(text, "html.parser")

        # Prefer H1, then H2, ... H6
        for level in range(1, 7):
            header = soup.find(f"h{level}")
            if header:
                value = header.get_text(" ", strip=True)
                if value:
                    return value[:70]

        # If there is no H1-H6, try <title>
        if soup.title:
            value = soup.title.get_text(" ", strip=True)
            if value:
                return value[:70]

        # HTML but no heading
        text = soup.get_text(" ", strip=True)

    # 2. Try Markdown
    headers = re.findall(r"^#+\s*(.+)$", text, re.MULTILINE)

    if headers:
        return headers[0].strip()[:70]

    # 3. Plain text fallback
    return text[:70].strip()
# --- Manual Ingestion Section ---
with st.sidebar.expander("📝 Inject Raw Text", expanded=False):
    with st.form("manual_ingest_form", clear_on_submit=True):
        manual_doc_id = st.text_input("Document ID", value=f"manual_{uuid.uuid4().hex[:8]}")
        manual_content = st.text_area("Document Content", height=400, placeholder="Paste your text here...")
        manual_source = st.text_input("Source Name", value=get_most_relevant_header(manual_content))
        submitted = st.form_submit_button("Ingest Text")
    if submitted:
        if not manual_content.strip():
            st.warning("Please enter content to ingest.")
        else:
            with st.spinner("Ingesting..."):
                try:
                    payload = {
                        "doc_id": manual_doc_id,
                        "text": manual_content,
                        "source": manual_source,
                    }
                    response = requests.post(f"{FASTAPI_URL}/api/v1/ingest", json=payload)
                    
                    if response.status_code == 200:
                        result = response.json()
                        st.success(f"✅ Added {result['chunks_added']} chunks.")
                    else:
                        st.error(f"❌ {response.json().get('detail', 'Error')}")
                except Exception as e:
                    st.error(f"❌ {str(e)}")

with st.sidebar:
    if st.button("🔄 Start New Chat", use_container_width=True):
        # Clear the UI history and generate a new thread_id
        st.session_state.messages = []
        st.session_state.thread_id = str(uuid.uuid4())
        st.rerun()
    st.header("💬 Chat Session")
    st.caption(f"Session ID: `{st.session_state.thread_id[:8]}...`")

st.caption("Built for Week 2/3 of the AI Platform Engineering Roadmap.")

