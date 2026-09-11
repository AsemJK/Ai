import streamlit as st
import requests
import io

# --- Configuration ---
FASTAPI_URL = "http://localhost:8000"

# --- Page Configuration ---
st.set_page_config(page_title="Qualcomm RAG Assistant", page_icon="🧠", layout="wide")

# --- Session State Initialization ---
if "messages" not in st.session_state:
    st.session_state.messages = []

# --- Sidebar: Document Ingestion ---
with st.sidebar:
    st.header("📂 Knowledge Base Management")
    st.markdown("Upload documents to ground the AI's answers.")
    
    uploaded_file = st.file_uploader(
        "Choose a file", 
        type=["pdf", "docx", "xlsx"],
        help="Supported formats: PDF, Word, Excel"
    )
    
    doc_id = st.text_input("Document ID", value="doc_001", help="Unique identifier for this document")
    source = st.text_input("Source/Metadata", value="manual_upload", help="E.g., 'HR_Policy', 'Financial_Report'")
    
    if st.button("🚀 Ingest Document"):
        if uploaded_file is None:
            st.warning("Please select a file to upload.")
        else:
            with st.spinner(f"Processing {uploaded_file.name}..."):
                try:
                    # Prepare the multipart form data
                    files = {
                        "file": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)
                    }
                    data = {
                        "doc_id": doc_id,
                        "source": source
                    }
                    
                    # Call the FastAPI ingestion endpoint
                    response = requests.post(f"{FASTAPI_URL}/api/v1/ingest-file", files=files, data=data)
                    
                    if response.status_code == 200:
                        result = response.json()
                        st.success(f"✅ Success! Added {result['chunks_added']} chunks to the vector DB.")
                    else:
                        st.error(f"❌ Error: {response.json().get('detail', 'Unknown error')}")
                except requests.exceptions.ConnectionError:
                    st.error("❌ Cannot connect to backend. Is FastAPI running on port 8000?")

# --- Main Area: Chat Interface ---
st.title("🧠 Enterprise RAG Assistant")
st.caption("Powered by FastAPI, Qdrant, and Open Source LLMs")

# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Chat input
if prompt := st.chat_input("Ask a question about your uploaded documents..."):
    # 1. Add user message to state and display
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # 2. Generate assistant response
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        message_placeholder.markdown("🤔 *Thinking and retrieving context...*")
        
        try:
            # Call the FastAPI RAG endpoint
            payload = {
                "query": prompt,
                "max_new_tokens": 256
            }
            response = requests.post(f"{FASTAPI_URL}/api/v1/rag-query", json=payload)
            
            if response.status_code == 200:
                result = response.json()
                answer = result["generated_text"]
                processing_time = result["processing_time_ms"]
                
                # Display the answer and a small metadata footer
                message_placeholder.markdown(answer)
                st.caption(f"⏱️ Processed in {processing_time:.2f} ms | 🤖 Model: {result['model_used']}")
                
                # 3. Add assistant message to state
                st.session_state.messages.append({"role": "assistant", "content": answer})
            else:
                error_msg = response.json().get("detail", "Unknown error")
                message_placeholder.error(f"❌ API Error: {error_msg}")
                
        except requests.exceptions.ConnectionError:
            message_placeholder.error("❌ Cannot connect to backend. Is FastAPI running?")

# --- Footer ---
st.divider()
st.caption("Built for Week 2/3 of the AI Platform Engineering Roadmap.")