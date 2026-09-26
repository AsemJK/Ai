from qdrant_client import QdrantClient
from qdrant_client.http import models
from sentence_transformers import SentenceTransformer
import uuid
import hashlib

# 1. Initialize Embedding Model (Downloads on first run, ~130MB)
# bge-small-en-v1.5 is optimized for retrieval tasks

# BAAI/bge-m3 is a newer, more powerful model
# EMBEDDING_MODEL = SentenceTransformer("BAAI/bge-m3")

# with 8gb vram what is the best hugging face model to use for RAG?
# bge-large-en-v1.5 is a good choice
# EMBEDDING_MODEL = SentenceTransformer("BAAI/bge-small-en-v1.5")
# EMBEDDING_MODEL = SentenceTransformer("BAAI/bge-large-en-v1.5")
EMBEDDING_MODEL = SentenceTransformer("BAAI/bge-m3")


# 2. Initialize Qdrant Client (Local Docker instance)
client = QdrantClient(url="http://localhost:6333")

COLLECTION_NAME = "asem_docs"
VECTOR_SIZE = (
    EMBEDDING_MODEL.get_sentence_embedding_dimension()
)
# 384 for bge-small-en-v1.5
# 1024 for bge-large-en-v1.5 


def setup_collection():
    """Creates the vector collection if it doesn't exist."""
    collections = client.get_collections().collections
    if not any(c.name == COLLECTION_NAME for c in collections):
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=models.VectorParams(
                size=VECTOR_SIZE, distance=models.Distance.COSINE
            ),
        )
        client.create_payload_index(
            collection_name=COLLECTION_NAME,
            field_name="content_hash",
            field_schema=models.PayloadSchemaType.KEYWORD,
        )
        client.create_payload_index(
            collection_name=COLLECTION_NAME,
            field_name="doc_id",
            field_schema=models.PayloadSchemaType.KEYWORD,
        )
        print(f"Created collection: {COLLECTION_NAME}")

def get_content_hash(text: str) -> str:
    normalized_text = text.strip()
    return hashlib.sha256(normalized_text.encode("utf-8")).hexdigest()


def ingest_document(doc_id: str, text: str, metadata: dict):
    """Ingest a document only if its content does not already exist."""

    # Generate deterministic hash from document content
    content_hash = get_content_hash(text)

    # Check whether this document content already exists
    existing = client.scroll(
        collection_name=COLLECTION_NAME,
        scroll_filter=models.Filter(
            must=[
                models.FieldCondition(
                    key="content_hash",
                    match=models.MatchValue(value=content_hash),
                )
            ]
        ),
        limit=1,
        with_payload=False,
        with_vectors=False,
    )

    existing_points, _ = existing

    if existing_points:
        print("Document already exists. Skipping ingestion.")
        return 0

    # Chunk the document
    chunks = [
        chunk.strip()
        for chunk in text.split("\n\n")
        if chunk.strip()
    ]

    points = []

    for i, chunk in enumerate(chunks):

        vector = EMBEDDING_MODEL.encode(chunk).tolist()

        points.append(
            models.PointStruct(
                id=str(uuid.uuid4()),
                vector=vector,
                payload={
                    "doc_id": doc_id,
                    "content_hash": content_hash,
                    "chunk_index": i,
                    "text": chunk,
                    **metadata,
                },
            )
        )

    client.upsert(
        collection_name=COLLECTION_NAME,
        points=points,
    )

    return len(chunks)
    
def ingest_document_old(doc_id: str, text: str, metadata: dict):
    """Chunks (simplified), embeds, and stores text in Qdrant."""
    # Simple chunking: split by paragraphs for this tutorial
    chunks = [chunk.strip() for chunk in text.split("\n\n") if chunk.strip()]
    points = []
    for i, chunk in enumerate(chunks):
        # Generate the dense vector embedding
        vector = EMBEDDING_MODEL.encode(chunk).tolist()
        points.append(
            models.PointStruct(
                id=str(uuid.uuid4()),
                vector=vector,
                payload={
                    "doc_id": doc_id,
                    "chunk_index": i,
                    "text": chunk,
                    **metadata,  # e.g., {"source": "employee_handbook.pdf"}
                },
            )
        )

    # Upsert (insert or update) into Qdrant
    client.upsert(collection_name=COLLECTION_NAME, points=points)   
    return len(chunks)

def retrieve_context(query: str, top_k: int = 15) -> list[dict]:
    """Searches Qdrant for the most relevant text chunks."""
    # 1. Embed the user's query
    query_vector = EMBEDDING_MODEL.encode(query).tolist()

    # 2. Search Qdrant
    search_response = client.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vector,
        limit=top_k,
        with_payload=True,
        score_threshold=0.65,  # 0.x means only x*100% similarity is required to return a chunk.
    )

    # 3. Format results
    context_list = []
    for result in search_response.points:
        context_list.append(
            {
                "text": result.payload["text"],
                "source": result.payload.get("source", "unknown"),
                "score": result.score,  # Cosine similarity score (0 to 1)
            }
        )

    return context_list
