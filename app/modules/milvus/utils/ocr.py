from typing import Union, List, Dict
import pandas as pd
import docx
from docx.table import Table
import fitz  # PyMuPDF
from pathlib import Path
import re
from datetime import datetime
import logging
import json
from fastapi.exceptions import HTTPException
from openai import OpenAI
import pytesseract
from pdf2image import convert_from_path
import tempfile
from mistralai import Mistral
from app.config.settings import settings
import base64
import os

from mistralai import Mistral
import uuid
from typing import Optional, Tuple
mistral_client = Mistral(api_key=settings.MISTRAL_API_KEY)
client = OpenAI(api_key=settings.OPENAI_API_KEY)
logger = logging.getLogger(__name__)
class OCRService:
    TEXT_EXTENSIONS = {'.txt', '.md'}
    DOCUMENT_EXTENSIONS = {'.pdf', '.docx', '.doc', '.xlsx', '.csv', '.xls'}
    def __init__(self):
        self.mistral_client = mistral_client
    def _clean_text(self, text: str) -> str:
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'[^\w\s.,!?;:()\[\]{}@#$%&*\-+=/\\]', '', text)
        text = text.replace('\r\n', '\n').replace('\r', '\n')
        return text.strip()
    def _get_file_extension(self, file_path: Union[str, Path]) -> str:
        """Obtém a extensão do arquivo em minúsculas."""
        return Path(file_path).suffix.lower()
    def _clean_sheet_text(self, text: str) -> str:
        text = text.replace('\r\n', '\n').replace('\r', '\n')
        text = re.sub(r'([^\n])\n## Aba:', r'\1\n\n## Aba:', text)
        text = re.sub(r'([^\n])\n### Linha:', r'\1\n\n### Linha:', text)
        text = re.sub(r'\n{4,}', '\n\n\n', text)
        text = re.sub(r'(#+)([^ #])', r'\1 \2', text)
        text = re.sub(r'[ \t]+', ' ', text)
        text = re.sub(r'[^\w\s.,!?;:()\[\]{}@#$%&*\-+=/\\]', '', text)
        return text.strip()
    def _format_as_markdown(self, text: str) -> str:
        title_candidate = text.split('\n')[0].strip()
        md_content = [
            text
        ]
        return "\n".join(md_content)
    

    def _extract_text_from_pdf(self, file_path: Union[str, Path]) -> List[Dict]:
        """
        Extrai texto corrido de um PDF, página por página.
        """
        doc = fitz.open(file_path)
        pages_content: List[Dict] = []

        try:
            for page_idx, page in enumerate(doc):
                page_num = page_idx + 1

                # 1. Extração de texto com fitz
                text = page.get_text("text")
                clean = self._clean_text(text)

                # 2. Armazena conteúdo
                pages_content.append({
                    "page_number": page_num,
                    "content": clean.strip()
                })

            return pages_content

        finally:
            doc.close()

    def _ocr_with_openai(self, item):
        # Convert image byte data into a base64-encoded string
        item = base64.b64encode(item).decode("utf-8")
        response = client.chat.completions.create(
            model="gpt-4o-mini-2024-07-18",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Você é um conversor de PDF para markdown. Converta esta imagem de um documento PDF para um documento markdown válido. Não inclua nenhum comentário adicional. Retorne somente o conteúdo do documento markdown sem adição dos marcadores ``` para delimitar o markdown.",
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{item}",
                                "detail": "high",
                            },
                        },
                    ],
                }
            ],
            max_tokens=4095,
            temperature=0.0,
        )
        return response.choices[0].message.content
    def _extract_text_from_pdf_openai(self, file_path: Union[str, Path]) -> List[Dict]:
        
        
        # Convert PDF pages to images
        pdf_images = convert_from_path(file_path, dpi=300)
        results = []

        for idx, image in enumerate(pdf_images):
            # Create temporary file in tmp directory
            tmp_dir = Path("/tmp")
            if not tmp_dir.exists():
                tmp_dir.mkdir(parents=True, exist_ok=True)

            tmp_file_path = tmp_dir / f"page_{idx}_{Path(file_path).stem}.jpg"
            
            try:
                # Save image to temporary file
                image.save(tmp_file_path, format='JPEG')
                
                # Read the image file
                with open(tmp_file_path, "rb") as img_file:
                    img_bytes = img_file.read()
                
                # Call the OpenAI OCR function
                text = self._ocr_with_openai(img_bytes)
                results.append({"page_number": idx + 1, "content": text})
                
            except Exception as e:
                logger.error(f"Error processing page {idx+1} with OpenAI: {str(e)}")
                results.append({"page_number": idx + 1, "content": f"Error extracting text with OpenAI: {str(e)}"})
            
            finally:
                # Clean up temporary file
                if tmp_file_path.exists():
                    try:
                        os.remove(tmp_file_path)
                        logger.info(f"Temporary file {tmp_file_path} removed successfully")
                    except Exception as e:
                        logger.warning(f"Failed to remove temporary file {tmp_file_path}: {str(e)}")
        
        return results
    def _extract_text_from_pdf_ocr(self, file_path: Union[str, Path]) -> List[Dict]:
        pages = convert_from_path(file_path, dpi=300)
        results = []
        for idx, page in enumerate(pages):
            text = self._clean_text(pytesseract.image_to_string(page, lang='por+eng'))
            results.append({"page_number": idx + 1, "content": text})
        return results
    def _extract_table(self, table) -> str:
        """Convert a docx table to markdown format"""
        rows = []
        
        # Extract header row
        header_row = []
        for cell in table.rows[0].cells:
            header_row.append(cell.text.strip() or " ")
        
        rows.append("| " + " | ".join(header_row) + " |")
        
        # Add markdown separator row
        rows.append("| " + " | ".join(["---"] * len(header_row)) + " |")
        
        # Extract data rows
        for row in table.rows[1:]:
            cells = []
            for cell in row.cells:
                cells.append(cell.text.strip() or " ")
            rows.append("| " + " | ".join(cells) + " |")
        
        return "\n".join(rows)
    
    def _extract_text_from_docx(self, file_path: Union[str, Path]) -> List[Dict]:
        """
        Extract text and tables from a Word document.
        Returns a list of dictionaries with page number and content.
        """
        doc = docx.Document(file_path)
        content_parts = []
        
        # Process all elements (paragraphs and tables) in order
        for element in doc.element.body:
            # Process paragraphs
            if element.tag.endswith('p'):
                paragraph = docx.text.paragraph.Paragraph(element, doc)
                if paragraph.text.strip():
                    if paragraph.style.name.startswith('Heading'):
                        try:
                            level = int(paragraph.style.name[-1])
                        except ValueError:
                            level = 1
                        content_parts.append(f"{'#' * level} {paragraph.text}")
                    else:
                        content_parts.append(paragraph.text)
            
            # Process tables
            elif element.tag.endswith('tbl'):
                table = Table(element, doc)
                content_parts.append(self._extract_table(table))
        
        text = self._clean_text("\n\n".join(content_parts))
        return [{"page_number": 1, "content": text}]
    def _extract_text_from_excel(self, file_path: Union[str, Path]) -> List[Dict]:
        xls = pd.ExcelFile(file_path)
        pages = []
        for i, sheet_name in enumerate(xls.sheet_names):
            df = xls.parse(sheet_name).fillna('')
            sections = [f"## Aba: {sheet_name}"]
            if df.empty:
                sections.append("*Esta planilha está vazia*")
            else:
                for col in df.columns:
                    if pd.api.types.is_datetime64_any_dtype(df[col]):
                        df[col] = df[col].apply(lambda x: x.strftime('%Y-%m-%d %H:%M:%S') if pd.notna(x) else '')
                    elif pd.api.types.is_numeric_dtype(df[col]):
                        df[col] = df[col].apply(lambda x: str(x).replace('.', ',') if pd.notna(x) else '')
                    else:
                        df[col] = df[col].astype(str)
                for idx, row in df.iterrows():
                    row_content = [f"### Linha: {idx}"]
                    for col in df.columns:
                        val = row[col].strip()
                        if val:
                            row_content.append(f"- {col}: {val}")
                    if len(row_content) > 1:
                        sections.append("\n".join(row_content))
            text = self._clean_sheet_text("\n\n".join(sections))
            pages.append({"page_number": i + 1, "content": text})
        return pages
    def _extract_text_from_csv(self, file_path: Union[str, Path]) -> List[Dict]:
        df = pd.read_csv(file_path).fillna('')
        lines = ["# CSV Extraído"]
        if df.empty:
            lines.append("*CSV vazio*")
        else:
            for col in df.columns:
                if pd.api.types.is_datetime64_any_dtype(df[col]):
                    df[col] = df[col].apply(lambda x: x.strftime('%Y-%m-%d %H:%M:%S') if pd.notna(x) else '')
                elif pd.api.types.is_numeric_dtype(df[col]):
                    df[col] = df[col].apply(lambda x: str(x).replace('.', ',') if pd.notna(x) else '')
                else:
                    df[col] = df[col].astype(str)
            for i, row in df.iterrows():
                row_str = [f"### Linha: {i}"]
                for col in df.columns:
                    val = row[col].strip()
                    if val:
                        row_str.append(f"- {col}: {val}")
                lines.append("\n".join(row_str))
        text = self._clean_sheet_text("\n\n".join(lines))
        return [{"page_number": 1, "content": text}]
    def _extract_text_from_pdf_mistral(
        self,
        file_path: Union[str, Path]
    ) -> List[Dict]:
        """
        Extract text from PDF using Mistral AI's OCR service,
        writing each chunk to a temporary file that is auto-deleted.
        """
        # Abre o PDF original
        try:
            doc = fitz.open(file_path)
            total_pages = doc.page_count

            # Inicializa o cliente Mistral
            mistral_client = self.mistral_client

            all_pages: List[Dict] = []
            chunk_size = 500

            for start in range(0, total_pages, chunk_size):
                end = min(start + chunk_size, total_pages)

                # Cria um novo documento contendo apenas as páginas [start, end)
                chunk = fitz.open()
                chunk.insert_pdf(doc, from_page=start, to_page=end - 1)

                # Usa NamedTemporaryFile para auto-remover o arquivo
                with tempfile.NamedTemporaryFile(suffix=".pdf", delete=True) as tmp:
                    # Salva a fatia no arquivo temporário
                    chunk.save(tmp.name)
                    chunk.close()
                    tmp.flush()

                    # Faz upload e processa OCR
                    with open(tmp.name, "rb") as f:
                        uploaded = mistral_client.files.upload(
                            file={"file_name": Path(tmp.name).name, "content": f},
                            purpose="ocr"
                        )
                    signed = mistral_client.files.get_signed_url(
                        file_id=uploaded.id,
                        expiry=1
                    )
                    resp = mistral_client.ocr.process(
                        model="mistral-ocr-latest",
                        document={"type": "document_url", "document_url": signed.url}
                    )

                    # Extrai páginas e marca números
                    pages = json.loads(resp.json())["pages"]
                    for i, p in enumerate(pages, start=start + 1):
                        all_pages.append({
                            "page_number": i,
                            "content": p["markdown"]
                        })

            doc.close()
            logger.info(
                "Successfully processed %s with Mistral OCR in %d pages",
                Path(file_path).name,
                len(all_pages)
            )
            return all_pages
        except Exception as e:
            logger.error(f"Error processing {Path(file_path).name} with Mistral OCR: {e}")
            raise
    def process_file(self, file_path: Union[str, Path]) -> Dict:
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"Arquivo não encontrado: {file_path}")
        def format_pages(pages: List[Dict]) -> List[Dict]:
            return [
                {
                    "page_number": p["page_number"],
                    "content": self._format_as_markdown(p["content"])
                }
                for p in pages if p["content"].strip()
            ]
        logger.info("Iniciando processamento do arquivo: %s", file_path)
        if self._get_file_extension(file_path) in self.TEXT_EXTENSIONS:
            if file_path.suffix == '.txt':
                text = self._clean_text(open(file_path, 'r', encoding='utf-8').read())
            elif file_path.suffix == '.md':
                text = self._clean_text(open(file_path, 'r', encoding='utf-8').read())
            return {
                "status": "success",
                "file_name": file_path.name,
                "pages": [{"page_number": 1, "content": self._format_as_markdown(text)}]
            }
        if file_path.suffix == '.pdf':
            try:
                # Tenta primeiro a extração direta de texto
                pages = self._extract_text_from_pdf(file_path)
                
                empty_pages = sum(1 for p in pages if not p["content"].strip())
                # Se não houver conteúdo ou as páginas estiverem vazias, tenta o Mistral OCR primeiro
                if  empty_pages >=2:
                    logger.info(f"Conteúdo insuficiente com extração direta para {file_path.name}, tentando Mistral OCR")
                    try:
                        # Try Mistral OCR first as fallback
                        pages = self._extract_text_from_pdf_mistral(file_path)
                
                        
                        # Verifica se o Mistral OCR obteve conteúdo suficiente
                        mistral_has_content = any(p['content'].strip() for p in pages)
                        if not mistral_has_content or not pages:
                            logger.info(f"Conteúdo insuficiente com Mistral OCR para {file_path.name}, tentando OCR local")
                            try:
                                pages = self._extract_text_from_pdf_ocr(file_path)
                            
                            except Exception as ocr_error:
                                logger.warning(f"Erro na extração com OCR local de {file_path.name}: {str(ocr_error)}. Tentando com OpenAI OCR")
                                pages = self._extract_text_from_pdf_openai(file_path)
                    except Exception as mistral_error:
                        # Se Mistral falhar, tenta OCR local e depois OpenAI
                        logger.warning(f"Erro na extração com Mistral OCR de {file_path.name}: {str(mistral_error)}. Tentando com OCR local")
                        try:
                            pages = self._extract_text_from_pdf_ocr(file_path)
                            
                            # Verifica se o OCR local obteve conteúdo suficiente
                            local_has_content = any(p['content'].strip() for p in pages)
                            if not local_has_content or not pages:
                                logger.info(f"Conteúdo insuficiente com OCR local para {file_path.name}, tentando OpenAI OCR")
                                pages = self._extract_text_from_pdf_openai(file_path)
                    
                        except Exception as ocr_error:
                            logger.warning(f"Erro na extração com OCR local de {file_path.name}: {str(ocr_error)}. Tentando com OpenAI OCR")
                            pages = self._extract_text_from_pdf_openai(file_path)
            
            except Exception as e:
                # Em caso de erro na extração direta, tenta com Mistral primeiro, depois OCR local, e por fim OpenAI
                logger.warning(f"Erro na extração direta de {file_path.name}: {str(e)}. Tentando com Mistral OCR")
                try:
                    # Try Mistral first
                    pages = self._extract_text_from_pdf_mistral(file_path)
                    
                    # Verifica se o Mistral obteve conteúdo suficiente
                    mistral_has_content = any(p['content'].strip() for p in pages)
                    if not mistral_has_content or not pages:
                        logger.info(f"Conteúdo insuficiente com Mistral OCR para {file_path.name}, tentando OCR local")
                        try:
                            pages = self._extract_text_from_pdf_ocr(file_path)
                            
                        except Exception as ocr_error:
                            logger.warning(f"Erro na extração com OCR local de {file_path.name}: {str(ocr_error)}. Tentando com OpenAI OCR")
                            pages = self._extract_text_from_pdf_openai(file_path)
                        
                except Exception as mistral_error:
                    # Se Mistral falhar, tenta OCR local e depois OpenAI
                    logger.warning(f"Erro na extração com Mistral OCR de {file_path.name}: {str(mistral_error)}. Tentando com OCR local")
                    try:
                        pages = self._extract_text_from_pdf_ocr(file_path)
                        
                        
                        # Verifica se o OCR local obteve conteúdo suficiente
                        local_has_content = any(p['content'].strip() for p in pages)
                        if not local_has_content or not pages:
                            logger.info(f"Conteúdo insuficiente com OCR local para {file_path.name}, tentando OpenAI OCR")
                            pages = self._extract_text_from_pdf_openai(file_path)
                            
                    except Exception as ocr_error:
                        logger.warning(f"Erro na extração com OCR local de {file_path.name}: {str(ocr_error)}. Tentando com OpenAI OCR")
                        pages = self._extract_text_from_pdf_openai(file_path)
                        
            
            # Registra o método final usado
            logger.info(f"Arquivo {file_path.name} processado com sucesso")
            return {"status": "success", "file_name": file_path.name, "pages": format_pages(pages)}
        elif file_path.suffix == '.docx':
            pages = self._extract_text_from_docx(file_path)
            return {"status": "success", "file_name": file_path.name, "pages": format_pages(pages)}
        elif file_path.suffix in ['.xlsx', '.xls']:
            pages = self._extract_text_from_excel(file_path)
            return {"status": "success", "file_name": file_path.name, "pages": format_pages(pages)}
        elif file_path.suffix == '.csv':
            pages = self._extract_text_from_csv(file_path)
            return {"status": "success", "file_name": file_path.name, "pages": format_pages(pages)}
        raise ValueError(f"Tipo de arquivo não suportado: {file_path.suffix}")