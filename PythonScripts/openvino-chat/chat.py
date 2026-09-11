#!/usr/bin/env python3
"""
Chat client for OpenVINO/Qwen3-8B-int4-ov
Endpoint: http://localhost:8000/v3
"""

BASE_URL = "http://localhost:8000/v3"
MODEL = "OpenVINO/Qwen3-8B-int4-ov"


# --- Alternative: Pure requests (no openai package needed) ---
def chat_with_requests():
    import requests

    url = f"{BASE_URL}/chat/completions"
    headers = {"Content-Type": "application/json"}
    messages = []

    print(f"🤖 Chat with {MODEL} (requests version)")
    print(f"🔗 Endpoint: {url}")
    print("Type 'quit', 'exit', or press Ctrl+C to stop.\n")

    while True:
        try:
            user_input = input("You: ").strip()
        except (KeyboardInterrupt, EOFError):
            break

        if user_input.lower() in ("quit", "exit"):
            break

        if not user_input:
            continue

        if not messages:
            messages.append({"role": "system", "content": "You are a helpful assistant."})
        messages.append({"role": "user", "content": user_input})

        payload = {
            "model": MODEL,
            "messages": messages,
            "stream": True,
            "max_tokens": 2048,
            "temperature": 0.7,
            "enable_thinking": False,
        }

        try:
            print("Assistant: ", end="", flush=True)
            response = requests.post(url, headers=headers, json=payload, stream=True)
            response.raise_for_status()

            full_response = ""
            for line in response.iter_lines():
                if line:
                    line = line.decode("utf-8")
                    if line.startswith("data: "):
                        data = line[6:]
                        if data == "[DONE]":
                            break
                        import json
                        try:
                            chunk = json.loads(data)
                            content = chunk["choices"][0]["delta"].get("content", "")
                            if content:
                                print(content, end="", flush=True)
                                full_response += content
                        except Exception:
                            pass

            print()
            messages.append({"role": "assistant", "content": full_response})

        except Exception as e:
            print(f"\n❌ Error: {e}")

    print("\n👋 Goodbye!")


if __name__ == "__main__":
    # Use OpenAI client by default; switch to chat_with_requests() if preferred
    chat_with_requests()
    # chat_with_openai()