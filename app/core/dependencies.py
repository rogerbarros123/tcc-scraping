from fastapi import Depends
from pymilvus import MilvusClient
from app.config.settings import settings

def get_milvus_client() -> MilvusClient:
    """
    Cria (ou recupera) a instância de MilvusClient,
    apontando para a URL configurada em settings.MILVUS_URL.
    """
    # settings.MILVUS_URL pode ser algo como "tcp://localhost:19530"
    client = MilvusClient(uri=settings.MILVUS_URL)
    return client