import asyncio
import hashlib
from typing import List
from langchain.text_splitter import RecursiveCharacterTextSplitter
from app.config.settings import settings
from pymilvus import model

# Configura função de embeddings do OpenAI
openai_ef = model.dense.OpenAIEmbeddingFunction(
    model_name='text-embedding-3-large',  # Specify the model name
    api_key=settings.OPENAI_API_KEY,       # Provide your OpenAI API key
    dimensions=3072                        # Set the embedding dimensionality
)

# Text processing utilities
def normalize_text(text: str) -> str:
    """Normalizes text by removing extra whitespace"""
    return " ".join(text.split())

def generate_doc_id(text: str) -> str:
    """Generates a unique ID for a document using MD5 hash"""
    normalized_text = normalize_text(text)
    return hashlib.md5(normalized_text.encode("utf-8")).hexdigest()

def split_text(text: str, chunk_size: int = 1024, overlap: int = 150) -> List[str]:
    """Splits text into chunks using RecursiveCharacterTextSplitter"""
    splitter = RecursiveCharacterTextSplitter(
        separators=["\n\n", "\n", " ", ""],
        chunk_size=chunk_size,
        chunk_overlap=overlap,
    )
    return splitter.split_text(text)

async def batches_chunks(
    chunks: List[str],
    max_tokens_per_batch: int,
    tokens_per_chunk_estimate: int
) -> List[List[str]]:
    """Agrupa chunks em batches com base em estimativas de tokens."""
    chunks_per_batch = max(1, max_tokens_per_batch // tokens_per_chunk_estimate)
    return [chunks[i:i + chunks_per_batch] for i in range(0, len(chunks), chunks_per_batch)]

async def embed_batch(batch: List[str], sem: asyncio.Semaphore) -> List[List[float]]:
    """Embeds a batch of text chunks usando OpenAIEmbeddingFunction."""
    async with sem:
        if asyncio.iscoroutinefunction(openai_ef.encode_documents):
            return await openai_ef.encode_documents(batch)
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, openai_ef.encode_documents, batch)

def embed_texts(texts: List[str]) -> List[List[float]]:
    """
    Gera embeddings para uma lista de textos de forma síncrona.
    Usa o OpenAIEmbeddingFunction (pymilvus.model).
    """
    # encode_documents aceita lista de strings e retorna lista de embeddings
    return openai_ef.encode_documents(texts)
