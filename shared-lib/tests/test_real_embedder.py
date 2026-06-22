# scratch/test_real_embedder.py
import asyncio

from shared.embeddings import Embedder

print("Instantiating Embedder client...")
embedder = Embedder()

text = "This is a test document to embed."
print(f"Sending text to Bedrock model '{embedder.model_id}'...")


async def main():
    try:
        vector = await embedder.embed_query(text)
        print("\n--- Success! ---")
        print(f"Vector dimensions returned: {len(vector)}")
        print(f"Sample values (first 5 elements): {vector[:5]}")
    except Exception as e:
        print(f"\nFailed to embed: {e}")


if __name__ == "__main__":
    asyncio.run(main())
