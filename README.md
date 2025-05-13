# TCC – Scraping, Vetorização e Chat

Este projeto integra um **backend** em FastAPI para raspagem de links, extração de texto via OCR, geração de embeddings e armazenamento em Milvus, com um **frontend** em Streamlit para orquestrar scraping e conversação interativa.

---

## 🗂 Estrutura do Repositório

```
├── app/
│   ├── main.py                   # Entrada do FastAPI
│   ├── modules/
│   │   ├── milvus/               # Lógica de vetorização e Milvus
│   │   │   ├── router.py         # Endpoints /milvus/
│   │   │   ├── schemas/          # Pydantic DTOs
│   │   │   └── utils/
│   │   │       ├── downloader.py # download_links_to_temp_dir
│   │   │       ├── ocr.py         # OCRService
│   │   │       ├── embbeding.py   # geração de embeddings
│   │   │       └── milvus.py      # prepare_collection, insert_batch
│   │   ├── chat/                 # Rota de streaming de chat
│   │   └── scraping/             # Serviço de scraping local
│   └── core/
│       ├── dependencies.py       # get_milvus_client
│       └── logging.py            # configuração de logger
├── front/
│   └── app.py                    # Frontend Streamlit (Scraping + Chat)
├── requirements.txt              # Dependências Python
└── README.md                     # Este arquivo
```

---

## 🚀 Tecnologias Utilizadas

* **Python 3.9+**
* **FastAPI**: servidor web assíncrono e definição de rotas
* **Streamlit**: frontend interativo para scraping e chat
* **Pymilvus**: cliente Milvus para criação de coleção e inserção de vetores
* **OpenAI / Mistral**: geração de embeddings e OCR via AI
* **PyMuPDF**, **Tesseract**, **pdf2image**: extração de texto de PDFs
* **BeautifulSoup**: parsing de HTML para extrair links

---

## 💾 Instalação

1. Clone este repositório:

   ```bash
   git clone <seu-repo-url>
   cd seu-repo
   ```

2. Crie e ative um ambiente virtual:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate   # Linux/Mac
   .\.venv\Scripts\activate  # Windows
   ```

3. Instale as dependências:

   ```bash
   pip install -r requirements.txt
   ```

4. Configure variáveis de ambiente (no `.env` ou export):

   ```ini
   OPENAI_API_KEY=...
   MILVUS_URL=localhost:19530
   # (Opcional) MISTRAL_API_KEY, SCRAPING_API_URL, SCRAPING_API_KEY
   ```

---

## 🏃‍♂️ Como Executar

### Backend (FastAPI)

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8080
```

* **GET** `/milvus/collections` – lista collections disponíveis
* **POST** `/scraping` – recebe `{ url, folderName }`, retorna lista de links
* **POST** `/milvus/insert` – recebe `{ links, folder_name }`, faz download, OCR, embedding e insere em Milvus
* **POST** `/chat/ask` – recebe `{ collection, question, messages? }`, retorna resposta em streaming

### Frontend (Streamlit)

```bash
streamlit run front/app.py
```

* Aba **Scraping**: informe a URL, colete links, selecione e insira em Milvus
* Aba **Chat**: escolha a coleção vetorizada e faça perguntas via streaming

---

## 📖 Uso

1. Na aba **Scraping**, cole uma **URL** de onde extrair documentos.
2. Selecione os links desejados e insira no Milvus.
3. Na aba **Chat**, selecione a coleção vetorizada e faça perguntas; o histórico de conversas será exibido.

---

## 🤝 Contribuições

Contribuições são bem-vindas! Faça um *fork*, crie uma *branch*, implemente sua feature e abra um *pull request*.

---

## 📄 Licença

Este projeto está sob a licença MIT. Veja o arquivo `LICENSE` para mais detalhes.
