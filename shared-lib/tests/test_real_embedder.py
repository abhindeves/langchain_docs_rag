# scratch/test_real_embedder.py
import asyncio
import time

from rag_shared.embeddings import Embedder

print("Instantiating Embedder client...")
embedder = Embedder()

text = "This is a test document to embed."
print(f"Sending text to Bedrock model '{embedder.model_id}'...")

# Override the semaphore to 3 to easily demonstrate queuing in action
CONCURRENCY_LIMIT = 3
local_semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)


async def track_task(i, doc_text):
    start_wait = time.time()

    # Calculate active calls based on semaphore's internal counter
    active_calls = CONCURRENCY_LIMIT - local_semaphore._value
    print(
        f"[Task {i:02d}] Requesting semaphore... "
        f"(Active Bedrock calls: {active_calls}/{CONCURRENCY_LIMIT})"
    )

    # Calling embed_query, wrapped by local_semaphore
    async with local_semaphore:
        vector = await embedder.embed_query(doc_text)

    elapsed = time.time() - start_wait
    print(f"[Task {i:02d}] Finished! Took {elapsed:.2f} seconds.")
    return vector


async def main():
    try:
        # Create 9 parallel tasks. With a semaphore limit of 3,
        # they should run in 3 distinct batches of 3.
        num_docs = 9
        texts = [text] * num_docs

        print(
            f"\n--- Launching {num_docs} Parallel Requests"
            f" (Semaphore Cap: {CONCURRENCY_LIMIT}) ---"
        )
        start_total = time.time()

        tasks = [track_task(i, t) for i, t in enumerate(texts, 1)]
        vectors = await asyncio.gather(*tasks)

        total_time = time.time() - start_total
        print("\n--- Success! ---")
        print(f"Total time for {num_docs} embeddings: {total_time:.2f}s")
        print(f"Vector dimensions returned: {len(vectors[0])}")
        print(f"Number of docs embedded: {len(vectors)}")

    except Exception as e:
        print(f"\nFailed to embed: {e}")


if __name__ == "__main__":
    asyncio.run(main())
