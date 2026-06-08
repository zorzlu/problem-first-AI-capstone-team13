"""Preload and report the local catalyst-dedup embedding engine."""
from backend import memory


def main() -> None:
    active = memory.is_embedding_active()
    print(f"embeddingProvider={'local_fastembed' if active else 'local_lexical'}")
    print(f"embeddingModel={memory.EMBEDDING_MODEL_NAME if active else 'tf-cosine + jaccard'}")
    print(f"embeddingCacheDir={memory.EMBEDDING_CACHE_DIR}")
    print(f"isFallbackActive={not active}")


if __name__ == "__main__":
    main()
