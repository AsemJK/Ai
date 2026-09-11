import sqlite3
from rag_service import retrieve_context  # Your Week 2 RAG function


def rag_search_tool(query: str) -> str:
    """Searches the knowledge base for document-based answers."""
    results = retrieve_context(query, top_k=3)
    if not results:
        return "No relevant documents found in the knowledge base."

    context = "\n\n".join([f"[Source: {r['source']}] {r['text']}" for r in results])
    return context


def sql_query_tool(query: str) -> str:
    """
    Executes a read-only SQL query against the data center inventory.
    Available table: servers (id, hostname, rack_id, gpu_model, gpu_count, status, temperature_c, power_watts)
    """
    try:
        conn = sqlite3.connect("datacenter.db")
        cursor = conn.cursor()

        # Security: Only allow SELECT statements
        if not query.strip().upper().startswith("SELECT"):
            return "Error: Only SELECT queries are allowed."

        cursor.execute(query)
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        conn.close()

        if not rows:
            return "No results found."

        # Format as readable text for the LLM
        result_lines = [", ".join(columns)]
        for row in rows:
            result_lines.append(", ".join(str(val) for val in row))

        return "\n".join(result_lines)

    except Exception as e:
        return f"SQL Error: {str(e)}"


def calculator_tool(expression: str) -> str:
    """Evaluates a mathematical expression."""
    try:
        # Security: Only allow safe math operations
        allowed_chars = set("0123456789+-*/.() ")
        if not all(c in allowed_chars for c in expression):
            return "Error: Invalid characters in expression."

        result = eval(expression)  # Safe because we filtered characters
        return f"{expression} = {result}"
    except Exception as e:
        return f"Calculation Error: {str(e)}"
