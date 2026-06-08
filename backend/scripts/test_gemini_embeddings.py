import os
from dotenv import load_dotenv

# Load env
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(backend_dir, "backend", ".env"))

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

def test_embedding(model_name: str):
    print(f"Testing embedding model: {model_name}...")
    try:
        from langchain_google_genai import GoogleGenerativeAIEmbeddings
        embeddings = GoogleGenerativeAIEmbeddings(google_api_key=GEMINI_API_KEY, model=model_name)
        vector = embeddings.embed_query("Hello world")
        print(f"  Success! Vector length: {len(vector)}")
        return True
    except Exception as e:
        print(f"  Failed: {e}")
        return False

if __name__ == "__main__":
    models_to_try = [
        "models/text-embedding-004",
        "text-embedding-004",
        "models/embedding-001",
        "embedding-001"
    ]
    for model in models_to_try:
        if test_embedding(model):
            print(f"\n---> WORKED WITH EMBEDDING MODEL: {model} <---\n")
            break
