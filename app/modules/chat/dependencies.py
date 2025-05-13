from pymilvus import MilvusClient
from openai import OpenAI
from app.config.settings import settings

# Initialize Milvus and OpenAI Clients using Config
milvus_client = MilvusClient(settings.MILVUS_URL)
client = OpenAI(api_key=settings.OPENAI_API_KEY)