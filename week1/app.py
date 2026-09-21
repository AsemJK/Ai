import streamlit as st
import requests
import random
import uuid
import bulk_ingest
import web_scraper_3 as web_scraper

# --- Configuration ---
FASTAPI_URL = "http://localhost:8000"

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
    st.header("📂 Knowledge Base Management")
    
    #web scraper
    st.sidebar.header("Web Scraper")
    web_url = st.sidebar.text_input("Web URL")
    if st.sidebar.button("Scrape", use_container_width=True):
        with st.spinner("Scraping..."):
            web_scraper.scrape_and_ingest(web_url, scan_links=True) #scan links = True for scanning all the links of the given page and also sub-pages
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
                        "❌ Cannot connect to backend. Is FastAPI running on port 8000?"
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
st.title("🧠 Enterprise RAG Assistant")
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
    
    if enable_rag:
        prompt = "rag " + prompt
        st.sidebar.text(f"forcing rag mode")
    else:
        st.sidebar.text(f"tool auto-selecting mode")    
        
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        message_placeholder.markdown("🤔 *Routing to the right tool...*")

        try:
            payload = {"query": prompt,"thread_id": st.session_state.thread_id}
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

with st.sidebar:
    if st.button("🔄 Start New Chat", use_container_width=True):
        # Clear the UI history and generate a new thread_id
        st.session_state.messages = []
        st.session_state.thread_id = str(uuid.uuid4())
        st.rerun()
    st.header("💬 Chat Session")
    st.caption(f"Session ID: `{st.session_state.thread_id[:8]}...`")

st.caption("Built for Week 2/3 of the AI Platform Engineering Roadmap.")

