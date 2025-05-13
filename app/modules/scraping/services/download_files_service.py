import os
import uuid
import base64
import requests
import html2text
from urllib.parse import urlparse, unquote

from app.core.logging import logging
from app.config.settings import settings

logger = logging.getLogger(__name__)

OUT_DIR = "/tmp/out"
os.makedirs(OUT_DIR, exist_ok=True)

class DownloadFilesService:
  async def download_files(
    self,
    downloadPage: str ,
    links_input: list[str],
    company_id: int,
    group_id: int
  ):
    logger.info("Iniciando download_files com company_id=%d, group_id=%d", company_id, group_id)
    headers = {"Api-Secret": settings.BACKEND_SECRET_KEY}
    download_headers = {"Api-Key": settings.SCRAPING_API_KEY}

    # Processamento de downloadPage
    if downloadPage:
      try:
        logger.info("Solicitando conteúdo de downloadPage para %s", downloadPage)
        resp = requests.post(
          settings.SCRAPING_API_URL + "/download",
          json={"url": downloadPage},
          headers=download_headers,
          timeout=30
        )
        resp.raise_for_status()
        result = resp.json()
        file_base64 = result.get("base64_encoded")
        if not file_base64:
          raise ValueError("Nenhum arquivo retornado pela API de download")
        logger.debug("Conteúdo recebido em base64, tamanho: %d", len(file_base64))

        # Decode HTML content and convert to text
        file_data = base64.b64decode(file_base64)
        html_content = file_data.decode("utf-8")
        txt_content = html2text.html2text(html_content)

        # Save txt to temporary file
        txt_name = f"{uuid.uuid4().hex}.txt"
        txt_path = os.path.join(OUT_DIR, txt_name)
        with open(txt_path, "w", encoding="utf-8") as f:
          f.write(txt_content)
        logger.info("TXT gerado: %s", txt_name)

        # Generate a "beautiful" filename for upload
        try:
          parsed = urlparse(downloadPage)
          txt_beautiful_name = (
            parsed.netloc.replace(".", "_") + "_" +
            "_".join(parsed.path.strip("/").split("/")) + "_" +
            "_".join(parsed.query.split("&")) + "_" +
            "_".join(parsed.fragment.split("#"))
          ) or uuid.uuid4().hex
          txt_beautiful_name += ".txt"
        except Exception:
          txt_beautiful_name = txt_name

        # Encode txt for upload
        with open(txt_path, "rb") as f:
          upload_base64 = base64.b64encode(f.read()).decode("utf-8")

        # Upload txt
        if settings.BACKEND_UPLOAD_URL:
          payload = {
            "fileName": txt_beautiful_name,
            "companyId": company_id,
            "groupId": group_id,
            "file": upload_base64,
          }
          try:
            upl_resp = requests.post(settings.BACKEND_UPLOAD_URL, json=payload, headers=headers, timeout=30)
            upl_resp.raise_for_status()
            logger.info("TXT enviado: %s", txt_beautiful_name)
          except Exception as e:
            logger.error("Falha ao enviar TXT: %s", e, exc_info=True)
        else:
          logger.warning("BACKEND_UPLOAD_URL não configurado. Pulando upload de TXT.")

        # Cleanup temporary txt
        os.remove(txt_path)
        logger.debug("TXT temporário removido: %s", txt_path)

      except Exception as e:
        logger.error("Erro no processamento de downloadPage %s: %s", downloadPage, e, exc_info=True)

    # Processamento de links_input
    used_names = set()
    for link in links_input:
      logger.info("Processando link: %s", link)
      try:
        parsed = urlparse(link)
        decoded_path = unquote(parsed.path)
        original_name = os.path.basename(decoded_path) or f"arquivo_{uuid.uuid4().hex}"
        original_name = original_name.replace(" ", "_")
        base, ext = os.path.splitext(original_name)
        unique_name = original_name
        counter = 1
        while unique_name in used_names:
          unique_name = f"{base}_{counter}{ext}"
          counter += 1
        used_names.add(unique_name)

        # Request file base64 from external service
        logger.info("Solicitando download de arquivo para %s", link)
        resp = requests.post(
          settings.SCRAPING_API_URL + "/download",
          json={"url": link},
          headers=download_headers,
          timeout=30
        )
        resp.raise_for_status()
        result = resp.json()
        file_base64 = result.get("base64_encoded")
        if not file_base64:
          raise ValueError("Nenhum arquivo retornado pela API de download")
        logger.debug("Conteúdo recebido em base64, tamanho: %d", len(file_base64))

        # Upload file
        if settings.BACKEND_UPLOAD_URL:
          payload = {
            "fileName": unique_name,
            "companyId": company_id,
            "groupId": group_id,
            "file": file_base64,
          }
          try:
            upl_resp = requests.post(settings.BACKEND_UPLOAD_URL, json=payload, headers=headers, timeout=30)
            upl_resp.raise_for_status()
            logger.info("Arquivo enviado: %s", unique_name)
          except Exception as e:
            logger.error("Falha ao enviar arquivo %s: %s", unique_name, e, exc_info=True)
        else:
          logger.warning("BACKEND_UPLOAD_URL não configurado. Pulando upload de arquivo: %s", unique_name)

      except Exception as e:
        logger.error("Erro ao processar link %s: %s", link, e, exc_info=True)

    # Notificação final
    if settings.BACKEND_NOTIFY_URL:
      try:
        notify_payload = {
          "companyId": company_id,
          "groupId": group_id,
          "fileName": "placeholder",
          "file": "placeholder"
        }
        notify_resp = requests.post(settings.BACKEND_NOTIFY_URL, json=notify_payload, headers=headers, timeout=10)
        notify_resp.raise_for_status()
        logger.info("Notificação final enviada.")
      except Exception as e:
        logger.error("Falha ao enviar notificação final: %s", e, exc_info=True)
    else:
      logger.warning("BACKEND_NOTIFY_URL não configurado. Pulando notificação final.")
