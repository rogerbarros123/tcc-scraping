import logging
from app.modules.chat.dependencies import client, milvus_client
import logging

import datetime

log = logging.getLogger(__name__)

# Função para gerar embedding da pergunta
def emb_text(text):
    try:
        response = client.embeddings.create(input=text, model="text-embedding-3-large")
        return response.data[0].embedding
    except Exception as e:
        logging.error(f"Erro ao gerar embedding: {e}")
        raise e
    

    
def ask_question_stream(question, collection_name, context):  
    # Consultar dados no Milvus
    search_res = milvus_client.search(
        collection_name=collection_name,
        data=[emb_text(question)],
        search_params={"metric_type": "IP", "params": {"nprobe": 16}},
        limit=20,
        output_fields=["text", "file_name", "page"], 
    )

    retrieved_items = []
    for res in search_res[0]:
        entity = res["entity"]
        text = entity["text"]
        distance = res["distance"]
        file_name = entity.get("file_name", "desconhecido")
        page = entity.get("page")
        retrieved_items.append((text, distance, file_name, page))
    
    retrieved_items.sort(key=lambda x: x[1], reverse=True)

    if retrieved_items:
        top_score = retrieved_items[0][1]
        threshold = max(0.2, top_score * 0.6)
        filtered_results = [
            (text, dist, file_name, page)
            for (text, dist, file_name, page) in retrieved_items
            if dist > threshold
        ]
    else:
        filtered_results = []

    selected_contexts = []
    for text, dist, file_name, page in filtered_results:
        extra = []
        if file_name:
            extra.append(f"arquivo='{file_name}'")
        if page is not None:
            extra.append(f"página={page}")
        meta_str = ", ".join(extra)
        context_entry = f"Trecho (similaridade={dist:.4f}{', ' + meta_str if meta_str else ''}):\n{text}"
        selected_contexts.append(context_entry)

    if not selected_contexts:
        milvus_context = "Nenhum contexto relevante encontrado no banco de dados."
    else:
        milvus_context = "\n\n".join(selected_contexts)

    log.info("Contexto relevante encontrado: %s", milvus_context)

    # Criar prompt do usuário com contexto relevante
    SYSTEM_PROMPT = "Você é um assistente que só responde sobre a base de conhecimento" 
    conhecimento = f"\n\n Base de Conhecimento:\n + {milvus_context}"
    if SYSTEM_PROMPT is None:
        raise KeyError("The key 'prompt' is missing from the dictionary.")

    # Realiza a chamada ao modelo com stream=True
    response = client.chat.completions.create(
        model="gpt-4.1-mini-2025-04-14",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            *context,          
            {"role": "user", "content": question + conhecimento} ,
        ],
        stream=True,
        temperature=0.0,
    )

    # Itera sobre os chunks do stream e yield o conteúdo conforme recebido
    for chunk in response:
        # Cada chunk pode ter uma estrutura parcial na chave "delta"
        content = chunk.choices[0].delta.content
        if content:
            yield content
