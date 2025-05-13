import asyncio
from typing import List, Dict, Any
from app.core.logging import logging
from pymilvus import FieldSchema, CollectionSchema, DataType, Collection, utility
import json
logger = logging.getLogger(__name__)


BATCH_SIZE = 500
# Milvus operations
async def prepare_milvus_collection(
    milvus_client,
    collection_name: str,
    shard_num: int = 2,
) -> bool:
    """
    Garante que exista uma coleção Milvus pronta para uso:
      - cria esquema (com auto_id se desejado)
      - cria índice vetor
      - carrega a coleção na memória
    Retorna True se criou a coleção do zero; False se ela já existia.
    """
    exists = await asyncio.to_thread(
        milvus_client.has_collection, collection_name
    )
    if exists:
        return False

    logger.info(f"Collection '{collection_name}' não existe. Criando...")

    # 1) Define o schema
    fields = [
        FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
        FieldSchema(name="vector", dtype=DataType.FLOAT_VECTOR, dim=3072),
        FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=65535),
        FieldSchema(name="doc_id", dtype=DataType.VARCHAR, max_length=512),
        FieldSchema(name="file_name", dtype=DataType.VARCHAR, max_length=512),
        FieldSchema(name="page", dtype=DataType.INT64),
    ]
    schema = CollectionSchema(fields, description="Chat embeddings com metadata")

    # 2) Cria a collection
    await asyncio.to_thread(
        milvus_client.create_collection,
        collection_name = collection_name,
        schema =schema,
        shard_num =shard_num,
        consistency_level="Strong",
    )
    logger.info(f"Collection '{collection_name}' criada com sucesso.")

    # 3) Cria o índice vetorial
    col = Collection(name=collection_name)
    await asyncio.to_thread(
        col.create_index,
        field_name="vector",
        index_params={
            "index_type": "IVF_FLAT",
            "metric_type": "IP",
            "params": {"nlist": 1024},
        },
        index_name="vector_idx",
    )
    logger.info(f"Índice 'vector_idx' criado em '{collection_name}'.")

    # 4) Carrega a coleção na memória
    await asyncio.to_thread(col.load)
    logger.info(f"Collection '{collection_name}' carregada na memória.")

    return True
    
async def get_existing_documents(
    milvus_client,
    collection_name: str
) -> Dict[str, List[str]]:
    """
    Recupera todos os chunks existentes na coleção e agrupa por file_name,
    retornando file_name -> lista de id (seu MD5).
    """
    col = Collection(name=collection_name)
    await asyncio.to_thread(col.load)

    # iterator buscando id e file_name
    it = col.query_iterator(
        batch_size=BATCH_SIZE,
        limit=-1,
        expr=None,
        output_fields=["id", "file_name"]
    )

    existing_doc_map: Dict[str, List[str]] = {}
    while True:
        batch = await asyncio.to_thread(it.next)
        if not batch:
            break
        for hit in batch:
            fn = hit.get("file_name")
            mid = hit.get("id")
            if fn and mid:
                existing_doc_map.setdefault(fn, []).append(mid)

    return existing_doc_map


async def delete_removed_documents(
    milvus_client,
    collection_name: str,
    existing_doc_map: Dict[str, List[int]],
    vetorizados: List[str],
) -> Dict[str, int]:
    """
    Deleta por id inteiro (PK INT64) os chunks cujos arquivos
    não estejam mais em 'vetorizados'. Retorna mapping file_name -> quantidade removida.
    """
    vetorizados_set = set(vetorizados or [])
    removed_files = set(existing_doc_map) - vetorizados_set
    if not removed_files:
        logger.info("Nenhum Arquivo para remoção")
        return {}

    # prepara a coleção para deletes por filtro
    col = Collection(name=collection_name)
    await asyncio.to_thread(col.load)

    results: Dict[str, int] = {}
    for fname in removed_files:

        logger.info(f"Arquivo :{fname} Removido do milvus ")
        # 1) coleta todos os ids INT de cada file_name
        it = col.query_iterator(
            batch_size=BATCH_SIZE,
            limit=-1,
            expr=f'file_name == "{fname}"',
            output_fields=["id"]
        )

        all_ids: List[int] = []
        while True:
            batch = await asyncio.to_thread(it.next)
            if not batch:
                break
            for hit in batch:
                id_val = hit.get("id")
                if isinstance(id_val, int):
                    all_ids.append(id_val)

        count = len(all_ids)
        if count == 0:
            continue
        
        # 2) delete em batches, sem aspas nos números
        for i in range(0, count, BATCH_SIZE):
            batch_ids = all_ids[i : i + BATCH_SIZE]
            ids_list = ", ".join(str(mid) for mid in batch_ids)
            expr = f'id in [{ids_list}]'
            await asyncio.to_thread(
                milvus_client.delete,
                collection_name=collection_name,
                filter=expr
            )

        results[fname] = count

    return results

async def insert_batch_to_milvus(milvus_client, collection_name: str, batch: List[Dict[str, Any]]):
    """Inserts a batch of data into a Milvus collection"""
    try:
        await asyncio.to_thread(milvus_client.insert, collection_name=collection_name, data=batch)
        return True
    except Exception as e:
        logger.error(f"Error inserting batch: {e}")
        return False


