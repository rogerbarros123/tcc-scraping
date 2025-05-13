from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse
from app.modules.chat.service import ask_question_stream
import json
import logging

log = logging.getLogger(__name__)

router = APIRouter()

@router.post("/ask")
async def process_web_query(request: Request):
    try:
        log.info("Recebendo solicitação de consulta da Web...")

        request = await request.json()
        
        question = request.get("question")
        collection_name = request.get("collection")

        messages = request.get("messages")
        
        if not question or not collection_name:
            log.error("Campos obrigatórios não fornecidos.")
            return JSONResponse(
                content={
                    "status": "error",
                    "message": "Os campos obrigatórios não foram fornecidos.",
                },
                status_code=400,
            )
    

        # Nome da coleção no Milvus
        collection_name = f"{collection_name}"
        log.info(f"Utilizando coleção Milvus: {collection_name}")
        
        log.info("Iniciando geração de resposta...")
        answer_generator = ask_question_stream(
            question, collection_name, messages
        )
        
        def event_generator():
            full_answer = ""
            for chunk in answer_generator:
                full_answer += chunk
                log.debug(f"Chunk recebido: {chunk}")
                yield chunk 
        
        return StreamingResponse(event_generator(), media_type="text/plain")
    
    except Exception as e:
        log.error(f"Erro ao processar a solicitação: {e}")
        return JSONResponse(
            content={
                "status": "error",
                "message": "Não foi possível processar sua solicitação.",
            },
            status_code=500,
        )