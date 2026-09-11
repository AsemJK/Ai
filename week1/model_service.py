import torch
from transformers import pipeline, AutoTokenizer

# 1. Define the model (Swap to "HuggingFaceH4/zephyr-7b-beta" if you have a GPU)
MODEL_ID = "Qwen/Qwen2.5-0.5B-Instruct"

# 2. Determine device (GPU if available, else CPU)
device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"Loading model on: {device}")

# 3. Initialize the Hugging Face pipeline
# We use a 'text-generation' pipeline. 
# trust_remote_code=True is sometimes needed for newer architectures like Qwen.
generator = pipeline(
    "text-generation",
    model=MODEL_ID,
    device=device,
    torch_dtype=torch.float16 if device == "cuda" else torch.float32,
    trust_remote_code=True
)

def generate_text(prompt: str, max_new_tokens: int, temperature: float) -> dict:
    """
    Core inference function. 
    Note: HF pipeline is synchronous. We will handle async wrapping in FastAPI.
    """
    # Format prompt for chat models (optional but recommended for chat models)
    messages = [{"role": "user", "content": prompt}]
    
    outputs = generator(
        messages,
        max_new_tokens=max_new_tokens,
        temperature=temperature,
        do_sample=True,
        pad_token_id=generator.tokenizer.eos_token_id
    )
    
    # Extract the generated text from the nested output structure
    generated_text = outputs[0]["generated_text"][-1]["content"]
    return generated_text