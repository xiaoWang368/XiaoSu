import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()

@dataclass
class ChromaConfig:
    persist_directory: str
    collection_name: str
    embedding_function: str

chroma_config = ChromaConfig(
    persist_directory=os.getenv("CHROMA_PATH", "data/chroma"),
    collection_name=os.getenv("CHROMA_COLLECTION", "kb_chunks"),
    embedding_function=os.getenv("CHROMA_EMBEDDING_FN", "default"),
)
