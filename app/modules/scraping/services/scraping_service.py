import requests
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from app.core.logging import logging
from app.config.settings import settings

logger = logging.getLogger(__name__)

class ScrapingService:
    # tipos de Content-Type que consideramos "arquivo"
    file_types = [
        "application/download",
        "application/pdf",
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "text/csv",
        "text/plain",
    ]
    # extensões comuns
    file_extensions = [".pdf", ".xls", ".xlsx", ".csv", ".docx", ".txt"]

    def is_content_type_file(self, content_type: str) -> bool:
        """Verifica se o Content-Type corresponde a um arquivo."""
        if not content_type:
            return False
        ct = content_type.split(";")[0].strip().lower()
        return any(ct.startswith(ft) for ft in self.file_types)

    @staticmethod
    def extract_links(html: str, base_url: str) -> set[str]:
        """Extrai todos os hrefs (absolutos) de <a> e <button>."""
        soup = BeautifulSoup(html, "html.parser")
        els = soup.select("a[href], button[href]")
        hrefs = {el["href"] for el in els if el.get("href")}
        return {urljoin(base_url, h) for h in hrefs if h}

    def is_possible_download_link(self, link: str) -> bool:
        """Filtro rápido por extensão ou padrões de 'download' na URL."""
        ll = link.lower()
        if any(ll.endswith(ext) for ext in self.file_extensions):
            return True
        parsed = urlparse(link)
        return "download" in parsed.path or "download-attachments" in parsed.path

    def _has_file_content_type(self, link: str) -> bool:
        """Faz HEAD e checa Content-Type antes de aceitar o link."""
        try:
            head = requests.head(link, allow_redirects=True, timeout=10)
            return self.is_content_type_file(head.headers.get("Content-Type", ""))
        except Exception:
            return False

    def start_scraping(self, url: str, verify_head: bool = True) -> list[str]:
        """
        1) GET na página
        2) extrai todos os links
        3) filtra por possíveis downloads
        4) opcionalmente faz HEAD para confirmar Content-Type
        Retorna: lista de URLs de arquivos
        """
        logger.info("Iniciando scraping: %s", url)
        resp = requests.get(url, headers={"User-Agent": "ScrapingService/1.0"}, timeout=60)
        resp.raise_for_status()

        raw_links = self.extract_links(resp.text, url)
        files = []
        for link in raw_links:
            if not self.is_possible_download_link(link):
                continue
            if verify_head:
                if self._has_file_content_type(link):
                    files.append(link)
            else:
                files.append(link)

        # remove duplicatas e retorna
        return sorted(set(files))
