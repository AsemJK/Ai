import json
from langgraph.graph import StateGraph, START, END
from typing import TypedDict, Literal
from model_service import generate_text  # Your Week 1 LLM function
from agent_tools import rag_search_tool, sql_query_tool, calculator_tool
from langgraph.checkpoint.memory import MemorySaver


# 1. Define the Agent State
class AgentState(TypedDict):
    user_query: str
    tool_choice: str  # "rag", "sql", "calculator", or "direct"
    tool_input: str  # The input to pass to the chosen tool
    tool_result: str  # The output from the tool
    final_answer: str  # The synthesized response


# 2. Router Node: The LLM decides which tool to use
def router_node(state: AgentState) -> AgentState:
    """Uses the LLM to classify the user's intent and choose a tool."""

    routing_prompt = f"""You are a routing agent. Analyze the user's question and decide which tool to use.


Available tools:
- "rag": Use this for questions about documents, policies, procedures, religion, articles, or any information from uploaded files.
- "sql": Use this for questions about server inventory, GPU counts, rack status, temperatures, power usage, or data center metrics.
- "calculator": Use this for pure math questions.
- "direct": Use this for greetings, general conversation, or questions that don't need any external tool.
Respond with ONLY a JSON object in this exact format:
{{"tool": "tool_name", "input": "the specific query to send to the tool"}}
Examples:
- "What does the security policy say about passwords?" → {{"tool": "rag", "input": "security policy passwords"}}
- "ما هي سياسة كلمة المرور؟" → {{"tool": "rag", "input": "سياسة كلمة المرور"}}
- "تلخيص الوثيقة المرفقة" → {{"tool": "rag", "input": "تلخيص الوثيقة المرفقة"}}
- "كم عدد كروت الشاشة في الخادم؟" → {{"tool": "sql", "input": "SELECT hostname, gpu_model, gpu_count FROM servers"}}
- "احسب 15% من 2800" → {{"tool": "calculator", "input": "2800 * 0.15"}}
- "مرحبا" → {{"tool": "direct", "input": "مرحبا"}}

User question: {state["user_query"]}

Provide a detailed and comprehensive answer.

Requirements:
- Explain the concept clearly.
- Provide step-by-step reasoning.
- Include practical examples.
- Explain important edge cases.
- Include code examples where appropriate.
- Do not give a short summary only.
- Structure the response using headings and bullet points.

JSON response:"""

    # Call the LLM
    raw_response = generate_text(
        prompt=routing_prompt, max_new_tokens=4096, temperature=0.2
    )

    # Parse the LLM's JSON response
    try:
        # Extract JSON from the response (handle potential markdown wrapping)
        json_str = raw_response.strip()
        if "{" in json_str:
            json_str = json_str[json_str.index("{") : json_str.rindex("}") + 1]

        decision = json.loads(json_str)
        tool_choice = decision.get("tool", "direct")
        tool_input = decision.get("input", state["user_query"])
    except (json.JSONDecodeError, ValueError):
        # Fallback: keyword-based routing for small models
        query_lower = state["user_query"].lower()
    #I need to check if input start with specific set of characters to 
    #force llm to use rag tool
    # for example "rag "
    
        if query_lower.startswith("rag "):
            tool_choice = "rag"
            tool_input = state["user_query"][4:]
        elif any(
            kw in query_lower
            for kw in ["server", "gpu", "rack", "temperature", "power", "node",
            "خادم", "كرت شاشة", "رف", "درجة حرارة", "طاقة", "عقدة"
            ]
        ):
            tool_choice = "sql"
            tool_input = state["user_query"]
        elif any(
            kw in query_lower
            for kw in ["policy", "document", "procedure", "how to", "what does", "extract", "search",
            "سياسة", "وثيقة", "إجراء", "كيف", "ما هو", "استخرج", "بحث"
            ]
        ):
            tool_choice = "rag"
            tool_input = state["user_query"]
        elif any(
            kw in query_lower for kw in ["calculate", "what is", "+", "-", "*", "/",
            "احسب", "ما هو", "+", "-", "*", "/"
            ]
        ):
            tool_choice = "calculator"
            tool_input = state["user_query"]
        else:
            tool_choice = "direct"
            tool_input = state["user_query"]

    #for example "rag "
    
    return {**state, "tool_choice": tool_choice, "tool_input": tool_input}


# 3. Tool Execution Nodes
def rag_node(state: AgentState) -> AgentState:
    result = rag_search_tool(state["tool_input"])
    return {**state, "tool_result": result}


def sql_node(state: AgentState) -> AgentState:
    # For SQL, the LLM might not generate perfect SQL with a small model.
    # We use a smart fallback: convert natural language to a basic query.
    query = state["tool_input"]
    if not query.strip().upper().startswith("SELECT"):
        # Fallback: generate a reasonable query based on keywords
        query_lower = query.lower()
        if "gpu" in query_lower and "count" in query_lower:
            query = "SELECT rack_id, SUM(gpu_count) as total_gpus FROM servers GROUP BY rack_id"
        elif "temperature" in query_lower:
            query = "SELECT hostname, rack_id, temperature_c FROM servers ORDER BY temperature_c DESC"
        elif "maintenance" in query_lower or "status" in query_lower:
            query = "SELECT hostname, rack_id, status FROM servers"
        else:
            query = "SELECT hostname, rack_id, gpu_model, gpu_count, status, temperature_c FROM servers"

    result = sql_query_tool(query)
    return {**state, "tool_result": result}


def calculator_node(state: AgentState) -> AgentState:
    result = calculator_tool(state["tool_input"])
    return {**state, "tool_result": result}


def direct_node(state: AgentState) -> AgentState:
    return {**state, "tool_result": "No tool needed. Respond directly to the user."}


# 4. Generator Node: Synthesize the final answer
def generator_node(state: AgentState) -> AgentState:
    synthesis_prompt = f"""You are a helpful enterprise assistant. Use the tool result below to answer the user's question clearly and concisely.

User's original question: {state["user_query"]}
Tool used: {state["tool_choice"]}
Tool result:
{state["tool_result"]}

CRITICAL INSTRUCTIONS:
1. If the user's question is in Arabic, you MUST reply entirely in fluent Arabic.
2. If the tool result contains data, present it in a clear format.
3. If the tool result says 'No relevant documents found', politely inform the user in their language that the information was not found.

Answer:"""

    final_answer = generate_text(
        prompt=synthesis_prompt, max_new_tokens=256, temperature=0.3
    )

    return {**state, "final_answer": final_answer}


# 5. Routing Logic
def route_to_tool(state: AgentState) -> Literal["rag", "sql", "calculator", "direct"]:
    """Conditional edge: routes based on the LLM's tool choice."""
    return state["tool_choice"]


# 6. Build the Graph
def build_agent():
    graph = StateGraph(AgentState)

    # Add nodes
    graph.add_node("router", router_node)
    graph.add_node("rag", rag_node)
    graph.add_node("sql", sql_node)
    graph.add_node("calculator", calculator_node)
    graph.add_node("direct", direct_node)
    graph.add_node("generator", generator_node)

    # Add edges
    graph.add_edge(START, "router")

    # Conditional routing from router to tools
    graph.add_conditional_edges(
        "router",
        route_to_tool,
        {"rag": "rag", "sql": "sql", "calculator": "calculator", "direct": "direct"},
    )

    # All tools lead to the generator
    graph.add_edge("rag", "generator")
    graph.add_edge("sql", "generator")
    graph.add_edge("calculator", "generator")
    graph.add_edge("direct", "generator")

    # Generator leads to END
    graph.add_edge("generator", END)

    memory = MemorySaver()
    
    # Compile the graph WITH the checkpointer
    return graph.compile(checkpointer=memory)


# Singleton agent instance
agent = build_agent()


def run_agent(query: str, thread_id: str = "default_thread") -> dict:
    """Main entry point for the agent."""
    initial_state = {
        "user_query": query,
        "tool_choice": "",
        "tool_input": "",
        "tool_result": "",
        "final_answer": "",
    }

    # The config is where we pass the thread_id for multi-tenant isolation
    config = {"configurable": {"thread_id": thread_id}}
    
    # Invoke with the config
    final_state = agent.invoke(initial_state, config=config)

    return {
        "answer": final_state["final_answer"],
        "tool_used": final_state["tool_choice"],
        "tool_input": final_state["tool_input"],
        "tool_result_preview": final_state["tool_result"][
            :200
        ],  # Truncate for API response
    }
