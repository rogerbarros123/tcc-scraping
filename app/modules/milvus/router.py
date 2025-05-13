import uuid
import asyncio
import logging
from fastapi import APIRouter, Depends, HTTPException
from app.modules.milvus.schemas.schemas import InsertDto
from app.modules.milvus.utils.downloader import download_links_to_temp_dir
from app.modules.milvus.utils.ocr import OCRService
from app.modules.milvus.utils.embbeding import batches_chunks, generate_doc_id, split_text, embed_texts
from app.modules.milvus.utils.milvus import prepare_milvus_collection, insert_batch_to_milvus
from app.core.dependencies import get_milvus_client  # retorna MilvusClient
from pymilvus import connections
from app.config.settings import settings
from pymilvus import MilvusClient
logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/insert")
async def insert_documents(
    dto: InsertDto,
    milvus_client=Depends(get_milvus_client),
):
    connections.connect(
        alias="default",
        host="localhost",   # ou settings.MILVUS_HOST
        port="19530"        # ou settings.MILVUS_PORT
    )
    collection_name = f"_{dto.folder_name}_"
    # 1) prepara coleção Milvus
    await prepare_milvus_collection(milvus_client, collection_name)

    # 2) baixa links e executa OCR
    paths, temp_dir = download_links_to_temp_dir(
        links=dto.links,
        folder_name=dto.folder_name
    )
    if not temp_dir:
        raise HTTPException(status_code=500, detail="Falha ao criar pasta temporária")

    ocr = OCRService()
    documents = []
    for path in paths:
        result = ocr.process_file(file_path=path)
        for page in result["pages"]:
            documents.append({
                "page_content": page["content"],
                "metadata": {"file_name": result["file_name"], "page": page["page_number"]}
            })

    # 3) pré-processa e gera chunks + metadata alinhada
    all_chunks, all_pages_metadata = [], []
    for doc in documents:
        chunks = split_text(doc["page_content"])
        if not chunks:
            logger.warning(f"Documento {doc['metadata'].get('file_name')} sem chunks.")
            continue
        all_chunks.extend(chunks)
        all_pages_metadata.extend([doc["metadata"]] * len(chunks))

    # 4) cria batches de embedding
    embedding_batches = await batches_chunks(
        all_chunks, max_tokens_per_batch=600000, tokens_per_chunk_estimate=1024
    )

    # 5) processa batches e insere em Milvus
    BATCH_SIZE = 500
    batch_counter = 0
    chunk_counter = 0
    milvus_batch = []

    for batch in embedding_batches:
        # 5a) gera embeddings localmente (sem Celery)
        embeddings = await asyncio.to_thread(embed_texts, batch)

        for idx, (chunk, vector) in enumerate(zip(batch, embeddings)):
            metadata = all_pages_metadata[chunk_counter]
            chunk_id = f"{generate_doc_id(chunk)}-{idx}"
            milvus_batch.append({
                "vector": vector,
                "text": chunk,
                "doc_id": chunk_id,
                "file_name": metadata.get("file_name"),
                "page": metadata.get("page", 1)
            })
            chunk_counter += 1

            # 5b) insere batch em Milvus quando atingir BATCH_SIZE
            if len(milvus_batch) >= BATCH_SIZE:
                ok = await insert_batch_to_milvus(milvus_client, collection_name, milvus_batch)
                if ok:
                    logger.info(f"Batch {batch_counter} inserido com sucesso.")
                else:
                    logger.error(f"Erro ao inserir o batch {batch_counter}")
                milvus_batch.clear()
                batch_counter += 1

    # 6) insere o que sobrou
    if milvus_batch:
        ok = await insert_batch_to_milvus(milvus_client, collection_name, milvus_batch)
        if ok:
            logger.info("Último batch inserido com sucesso.")
        else:
            logger.error("Erro ao inserir o último batch.")
            raise HTTPException(status_code=500, detail="Erro na inserção final")

    return {"status": "success", "collection": collection_name}



@router.get("/collections")
async def list_collections(
) -> list[str]:
    milvus_client = MilvusClient(settings.MILVUS_URL)
    """
    Retorna a lista de collections existentes no servidor Milvus.
    """
    # Dependendo da versão do pymilvus, use list_collections ou show_collections
    try:
        collections = milvus_client.list_collections()
    except AttributeError:
        # Em versões mais antigas do SDK
        collections = milvus_client.show_collections()
    return collections
