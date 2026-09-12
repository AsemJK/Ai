import time
import asyncio
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from document_parser import parse_document
from rag_service import setup_collection, ingest_document, retrieve_context
from schemas import GenerationRequest, GenerationResponse
from model_service import generate_text, MODEL_ID
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from agent_graph import run_agent


app = FastAPI(
    title="AI Inference API",
    description="Week 1 Capstone: Async LLM Serving",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "*"
    ],  # allow all origins: Streamlit's default port ["http://localhost:8501", "*"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/api/v1/generate", response_model=GenerationResponse)
async def generate_endpoint(request: GenerationRequest):
    start_time = time.time()

    try:
        # Run the blocking CPU/GPU task in a separate thread
        # to keep the FastAPI event loop free for other requests.
        generated_text = await asyncio.to_thread(
            generate_text,
            prompt=request.prompt,
            max_new_tokens=request.max_new_tokens,
            temperature=request.temperature,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Inference failed: {str(e)}")

    processing_time_ms = (time.time() - start_time) * 1000

    # Estimate tokens generated (rough approximation for logging)
    estimated_tokens = len(generated_text.split())

    return GenerationResponse(
        generated_text=generated_text,
        model_used=MODEL_ID,
        tokens_generated=estimated_tokens,
        processing_time_ms=round(processing_time_ms, 2),
    )


@app.get("/health")
async def health_check():
    return {"status": "healthy", "model": MODEL_ID}


# Initialize Qdrant collection on startup
@app.on_event("startup")
def startup_event():
    setup_collection()


class IngestRequest(BaseModel):
    doc_id: str
    text: str
    source: str


@app.post("/api/v1/ingest")
async def ingest_endpoint(request: IngestRequest):
    """Ingests a document into the vector database."""
    try:
        chunks_added = ingest_document(
            doc_id=request.doc_id,
            text=request.text,
            metadata={"source": request.source},
        )
        return {"status": "success", "chunks_added": chunks_added}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class RAGRequest(BaseModel):
    query: str
    max_new_tokens: int = 150


@app.post("/api/v1/rag-query", response_model=GenerationResponse)
async def rag_query_endpoint(request: RAGRequest):
    """Retrieves context and generates an answer based STRICTLY on that context."""
    import time
    import asyncio

    start_time = time.time()

    # 1. Retrieve relevant context
    context_results = retrieve_context(request.query, top_k=3)

    if not context_results:
        raise HTTPException(status_code=404, detail="No relevant documents found.")

    # 2. Format the context with clear source attribution
    context_text = "\n\n".join(
        [f"[Source: {r['source']}] {r['text']}" for r in context_results]
    )

    # 3. THE FIX: Strict Prompt with XML tags and negative constraints
    grounded_prompt = f"""You are a strict enterprise assistant. You must answer the user's question using ONLY the information provided inside the <context> tags.

CRITICAL RULES:
1. Do NOT use your pre-trained knowledge.
2. If the answer is not explicitly stated in the <context>, you must reply with exactly: "I do not have enough information in the provided documents to answer that."
3. Do not make up facts.

<context>
{context_text}
</context>

Question: {request.query}
Answer:"""

    # 4. Generate response
    try:
        generated_text = await asyncio.to_thread(
            generate_text,
            prompt=grounded_prompt,
            max_new_tokens=request.max_new_tokens,
            temperature=0.1,  # <-- FIX: Lowered temperature for strict factual adherence
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Inference failed: {str(e)}")

    processing_time_ms = (time.time() - start_time) * 1000

    return GenerationResponse(
        generated_text=generated_text,
        model_used=MODEL_ID,
        tokens_generated=len(generated_text.split()),
        processing_time_ms=round(processing_time_ms, 2),
    )


@app.post("/api/v1/rag-query-old", response_model=GenerationResponse)
async def rag_query_endpoint_old(request: RAGRequest):
    """Retrieves context and generates an answer based ONLY on that context."""
    import time
    import asyncio

    start_time = time.time()

    # 1. Retrieve relevant context
    context_results = retrieve_context(request.query, top_k=3)

    if not context_results:
        raise HTTPException(status_code=404, detail="No relevant documents found.")

    # 2. Format the context into a prompt
    context_text = "\n\n".join(
        [f"[Source: {r['source']}] {r['text']}" for r in context_results]
    )

    # 3. Construct a strict, grounded prompt (Prompt Engineering)
    grounded_prompt = f"""You are a helpful assistant. Answer the user's question using ONLY the provided context. 
If the answer is not in the context, say "I do not have enough information to answer that."

Context:
{context_text}

Question: {request.query}
Answer:"""

    # 4. Generate response (using our async thread wrapper from Week 1)
    try:
        generated_text = await asyncio.to_thread(
            generate_text,
            prompt=grounded_prompt,
            max_new_tokens=request.max_new_tokens,
            temperature=0.3,  # Lower temperature for factual RAG responses
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Inference failed: {str(e)}")

    processing_time_ms = (time.time() - start_time) * 1000

    return GenerationResponse(
        generated_text=generated_text,
        model_used=MODEL_ID,
        tokens_generated=len(generated_text.split()),
        processing_time_ms=round(processing_time_ms, 2),
    )


@app.post("/api/v1/ingest-file")
async def ingest_file_endpoint(
    file: UploadFile = File(
        ..., description="The document to ingest (PDF, DOCX, XLSX)"
    ),
    doc_id: str = Form(..., description="Unique identifier for the document"),
    source: str = Form(default="uploaded_file", description="Source metadata"),
):
    """
    Accepts a file upload, parses it, chunks it, and stores it in Qdrant.
    """
    try:
        # 1. Read the file bytes in memory
        file_bytes = await file.read()

        # 2. Parse the document into raw text
        extracted_text = parse_document(file.filename, file_bytes)

        if not extracted_text.strip():
            raise HTTPException(
                status_code=400,
                detail="Extracted text is empty. Is the file corrupted or image-based?",
            )

        # 3. Ingest into Vector DB (reusing our Week 2 logic)
        chunks_added = ingest_document(
            doc_id=doc_id,
            text=extracted_text,
            metadata={"source": source, "filename": file.filename},
        )

        return {
            "status": "success",
            "filename": file.filename,
            "chunks_added": chunks_added,
            "message": f"Successfully processed and indexed {file.filename}",
        }

    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")


class AgentRequest(BaseModel):
    query: str
    thread_id: str


class AgentResponse(BaseModel):
    answer: str
    tool_used: str
    tool_input: str
    tool_result_preview: str
    processing_time_ms: float


@app.post("/api/v1/agent", response_model=AgentResponse)
async def agent_endpoint(request: AgentRequest):
    """The main agentic endpoint. Routes to the right tool automatically."""
    import time

    start_time = time.time()

    try:
        result = await asyncio.to_thread(run_agent, query=request.query, thread_id=request.thread_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent failed: {str(e)}")

    processing_time_ms = (time.time() - start_time) * 1000

    return AgentResponse(
        answer=result["answer"],
        tool_used=result["tool_used"],
        tool_input=result["tool_input"],
        tool_result_preview=result["tool_result_preview"],
        processing_time_ms=round(processing_time_ms, 2),
    )
