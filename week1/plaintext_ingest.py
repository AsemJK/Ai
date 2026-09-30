#injecting files content manually

import requests
import time
import json
import os
from dotenv import load_dotenv

# Load environment variables (optional, but good practice)
load_dotenv()

FASTAPI_URL = os.getenv("FASTAPI_URL", "http://localhost:8000")
COLLECTION_NAME = os.getenv("COLLECTION_NAME", "docs_fastapi")
# Add other env vars for your auth/keys if needed

def ingest_file_content(doc_id: str, content: str, source: str):
    """
    Sends raw text content directly to the /api/v1/ingest endpoint.
    
    Args:
        doc_id: Unique identifier for the document.
        content: The full text content to ingest.
        source: Name of the source (for metadata).
    """
    start_time = time.time()
    
    data = {
        "doc_id": doc_id,
        "text": content,
        "source": source,
    }
    
    try:
        response = requests.post(f"{FASTAPI_URL}/api/v1/ingest", json=data)
        
        if response.status_code == 200:
            result = response.json()
            processing_time_ms = (time.time() - start_time) * 1000
            print(f"✅ Success for {doc_id} ({source})")
            print(f"   Chunks Added: {result.get('chunks_added', 'N/A')}")
            print(f"   Time: {processing_time_ms:.1f} ms\n")
            return result
        else:
            print(f"❌ Failed for {doc_id}: {response.status_code} - {response.text}\n")
            return None
            
    except requests.exceptions.ConnectionError:
        print(f"❌ Connection Error: Is FastAPI running on {FASTAPI_URL}?")
        return None
    except Exception as e:
        print(f"❌ Error: {e}\n")
        return None


def main():
    """
    Demonstration of how to ingest raw text content directly.
    """
    print("=== Manual Content Ingestion Demo ===")
    print(f"FastAPI URL: {FASTAPI_URL}")
    print("-" * 30)

    # Example 1: A short document
    doc1_content = """The quick brown fox jumps over the lazy dog. 
This sentence contains all letters of the English alphabet (a pangram). 
It is often used for testing typefaces and keyboard layouts."""
    
    ingest_file_content(
        doc_id="doc-manual-001",
        content=doc1_content,
        source="Manual Text Example"
    )

    # Example 2: A slightly longer, structured document
    doc2_content = """
Project Alpha Technical Specification
Version 1.2
Date: 2023-10-27

1. System Architecture
   The system uses a microservices architecture with a RESTful API 
   for communication. The database is a PostgreSQL instance 
   running on port 5432.

2. Deployment
   Containers are managed using Docker and orchestrated via Kubernetes.
   CI/CD pipelines are handled by Jenkins.

3. Security
   All traffic must use HTTPS. JWT tokens are required for 
   authentication. Password hashing is done using bcrypt.
"""

    ingest_file_content(
        doc_id="doc-manual-002",
        content=doc2_content,
        source="Project Alpha Specs"
    )

if __name__ == "__main__":
    main()
