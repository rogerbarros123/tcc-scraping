import os
import uuid
import tempfile
import requests
import logging


def download_links_to_temp_dir(links: list[str], folder_name: str = None) -> str:
    """
    Faz o download de cada URL em `links` para um diretório temporário.
    O diretório é criado em uma pasta de temp do sistema com um nome UUID,
    opcionalmente prefixado por `folder_prefix`.

    Retorna:
        str: Caminho completo para o diretório onde os arquivos foram salvos.
    """
    # Gera um identificador único
    unique_id = uuid.uuid4().hex
    # Define nome da pasta temporária
    dir_name = f"{folder_name}_{unique_id}" if folder_name else unique_id
    temp_dir = os.path.join(tempfile.gettempdir(), dir_name)
    os.makedirs(temp_dir, exist_ok=True)
    file_paths  = []

    for link in links:
        try:
            response = requests.get(link, timeout=60)
            response.raise_for_status()
            # Extrai nome de arquivo da URL
            parsed = requests.utils.urlparse(link)
            filename = os.path.basename(parsed.path) or f"file_{uuid.uuid4().hex}"
            file_path = os.path.join(temp_dir, filename)
            file_paths.append(file_path)
            # Salva o conteúdo
            with open(file_path, "wb") as f:
                f.write(response.content)
            logging.info(f"Downloaded {link} -> {file_path}")
        except Exception as e:
            logging.error(f"Falha ao baixar {link}: {e}")

    return file_paths, temp_dir