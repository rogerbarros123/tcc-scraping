from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.logging import configure_logging
import app.modules.chat.router as chat
from app.modules.scraping.scraping_router import scraping_router
from app.modules.milvus.router import router as milvus_router
app = FastAPI(docs_url=None, redoc_url=None)

# Configure logging
configure_logging()


app.include_router(chat.router, prefix="/chat")
app.include_router(scraping_router)
app.include_router(milvus_router, prefix="/milvus")
