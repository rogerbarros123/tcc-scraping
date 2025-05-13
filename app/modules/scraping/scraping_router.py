from fastapi import APIRouter
# from app.utils.task_wrapper import run_async_task_in_thread
from app.core.logging import logging
from app.modules.scraping.dtos.scraping_dto import ScrapingDto
from app.modules.scraping.dtos.download_files_dto import DownloadFilesDto
from app.modules.scraping.services.scraping_service import ScrapingService
from app.modules.scraping.services.download_files_service import DownloadFilesService

logger = logging.getLogger(__name__)

scraping_router = APIRouter()

scraping_service = ScrapingService()
download_files_service = DownloadFilesService()

@scraping_router.post("/scraping")
async def scraping(msg: ScrapingDto):
  logger.info("Received scraping request with the follow url: %s", msg.url)
  try:
    links_to_download = scraping_service.start_scraping(msg.url)
    logger.info("Scraping request processed successfully")
    return links_to_download
  except Exception as e:
    logger.error("Error during scraping process: %s", e, exc_info=True)
    return {"error": str(e)}

@scraping_router.post("/download_files")
def download_files(dto: DownloadFilesDto):
  logger.info("Received download files request with the follow urls: %s", dto.links)
  try:
    # Executa a tarefa de download em thread separada para não bloquear
    download_files_service.download_files(dto.downloadPage, dto.links, dto.companyId, dto.groupId)
    
    return {"message": "Started downloading files"}
  except Exception as e:
    logger.error("Error initializing download task: %s", e, exc_info=True)
    return {"error": str(e)}
