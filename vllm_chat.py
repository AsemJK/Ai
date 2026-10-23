
from openai import OpenAI

# vLLM OpenAI-compatible API
client = OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="EMPTY",  # vLLM does not require a key by default
)

def get_model():
    """Retrieve the model served by vLLM."""
    models = client.models.list().data

    if not models:
        raise RuntimeError("No models found on the vLLM server.")

    print("\nAvailable models:")
    for index, model in enumerate(models, start=1):
        print(f"{index}. {model.id}")

    return models[0].id


def chat():
    try:
        model = get_model()
        print(f"\nConnected to vLLM model: {model}")
        print("Type 'exit' or 'quit' to stop.\n")

        messages = [
            {
                "role": "system",
                "content": "You are a helpful AI assistant."
            }
        ]

        while True:
            user_input = input("You: ").strip()

            if user_input.lower() in {"exit", "quit"}:
                print("Chat ended.")
                break

            if not user_input:
                continue

            messages.append({
                "role": "user",
                "content": user_input
            })

            try:
                response = client.chat.completions.create(
                    model=model,
                    messages=messages,
                    max_tokens=256,
                    temperature=0.7,
                    stream=False,
                )

                answer = response.choices[0].message.content or ""
                print(f"\nAssistant: {answer}\n")

                messages.append({
                    "role": "assistant",
                    "content": answer
                })

            except Exception as error:
                # Remove the failed user message so it can be retried.
                messages.pop()
                print(f"\nRequest failed: {error}\n")

    except Exception as error:
        print(f"Connection error: {error}")
        print("Check that vLLM is running and the URL is correct.")


if __name__ == "__main__":
    chat()
