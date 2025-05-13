import streamlit as st
import requests

# Configuração da página
st.set_page_config(page_title="TCC - Scraping & Chat", layout="wide")

API_BASE = "http://localhost:8080"
PAGES = ["Scraping", "Chat"]

# Inicialização do session_state
for key, default in {
    'active_page': 'Scraping',
    'scraped_links': [],
    'selected_links': [],
    'collection_name': '',
    'collections': [],
    'selected_collection': ''
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

# Dicionário que guarda um histórico para cada coleção
if 'chat_histories' not in st.session_state:
    st.session_state.chat_histories = {}

# Funções auxiliares
def ensure_history():
    """Garante que exista uma lista para a coleção selecionada."""
    col = st.session_state.selected_collection
    if col and col not in st.session_state.chat_histories:
        st.session_state.chat_histories[col] = []

def new_conversation():
    """Inicia nova conversa, limpando só o histórico da coleção atual."""
    col = st.session_state.selected_collection
    if col:
        st.session_state.chat_histories[col] = []

# Sidebar de navegação
st.sidebar.title("Navegação")
st.session_state.active_page = st.sidebar.radio(
    "Ir para:", PAGES, index=PAGES.index(st.session_state.active_page)
)

# === Página de Scraping ===
if st.session_state.active_page == 'Scraping':
    st.title("TCC – Scraping de Documentos")

    url = st.text_input("URL para Scraping:", key="url_input")
    folder_name = st.text_input("Nome da Coleção:", key="folder_input")

    if st.button("🚀 Scraping e listagem"):
        st.session_state.selected_links.clear()
        if not url:
            st.error("Insira uma URL válida.")
        elif not folder_name:
            st.error("Insira o nome da pasta.")
        else:
            with st.spinner("Raspando e listando links…"):
                try:
                    resp = requests.post(
                        f"{API_BASE}/scraping",
                        json={"url": url, "folderName": folder_name},
                        timeout=60
                    )
                    resp.raise_for_status()
                    st.session_state.scraped_links = resp.json()
                    st.success(f"Encontrados {len(st.session_state.scraped_links)} links.")
                except Exception as e:
                    st.error(f"Erro ao raspar: {e}")
                    st.session_state.scraped_links.clear()

    if st.session_state.scraped_links:
    # checkbox “Selecionar todos”
        select_all = st.checkbox("Selecionar todos", key="select_all")
        if select_all:
            # marca todos
            st.session_state.selected_links = st.session_state.scraped_links.copy()
        else:
            # limpa todos (se desmarcou o “select_all”)
            st.session_state.selected_links = []

        st.subheader("Selecione os links para inserir:")
    for i, link in enumerate(st.session_state.scraped_links):
        # checkbox individual já refletindo seleção
        checked = link in st.session_state.selected_links
        chk = st.checkbox(f"{i+1}. {link}", value=checked, key=f"chk_{i}")
        if chk and link not in st.session_state.selected_links:
            st.session_state.selected_links.append(link)
        if not chk and link in st.session_state.selected_links:
            st.session_state.selected_links.remove(link)

    if st.session_state.selected_links:
        if st.button("🚀 Inserir selecionados"):
            with st.spinner("Inserindo no Milvus…"):
                try:
                    insert_resp = requests.post(
                        f"{API_BASE}/milvus/insert",
                        json={
                            "links": st.session_state.selected_links,
                            "folder_name": folder_name
                        },
                        timeout=120
                    )
                    insert_resp.raise_for_status()
                    st.success("Inserção concluída com sucesso!")
                    # define coleção padrão para chat
                    st.session_state.collection_name = f"_{folder_name}_"
                    st.session_state.scraped_links.clear()
                    st.session_state.selected_links.clear()
                except Exception as e:
                    st.error(f"Erro ao inserir: {e}")

# === Página de Chat ===
else:
    st.title("TCC – Chat com Base Vetorizada e Contexto de Histórico")

    # 1) Carrega lista de coleções
    if not st.session_state.collections:
        try:
            resp = requests.get(f"{API_BASE}/milvus/collections", timeout=30)
            resp.raise_for_status()
            st.session_state.collections = resp.json()
            # seta default se vier do scraping
            if st.session_state.collection_name in st.session_state.collections:
                st.session_state.selected_collection = st.session_state.collection_name
        except Exception as e:
            st.error(f"Erro ao buscar coleções: {e}")

    # 2) Escolha de coleção
    if st.session_state.collections:
        # pegamos o retorno da selectbox para garantir atualização imediata
        col = st.selectbox(
            "Selecione a coleção:",
            options=st.session_state.collections,
            index=(
                st.session_state.collections.index(st.session_state.selected_collection)
                if st.session_state.selected_collection in st.session_state.collections else 0
            )
        )
        # atualiza o estado e garante o histórico
        if col != st.session_state.selected_collection:
            st.session_state.selected_collection = col
        ensure_history()

        # botão de nova conversa
        st.button("Limpar Contexto", on_click=new_conversation)

        # 3) Exibição do histórico
        history = st.session_state.chat_histories.get(col, [])
        for msg in history:
            st.chat_message(msg['role']).markdown(msg['content'])

        # 4) Input do usuário
        user_input = st.chat_input("Faça sua pergunta:")
        if user_input:
            history.append({'role': 'user', 'content': user_input})
            st.chat_message('user').markdown(user_input)

            assistant_msg = st.chat_message('assistant')
            full_answer = ""
            try:
                resp = requests.post(
                    f"{API_BASE}/chat/ask",
                    json={
                        "collection": col,
                        "question": user_input,
                        "messages": history
                    },
                    timeout=60,
                    stream=True
                )
                resp.raise_for_status()
                for line in resp.iter_lines(decode_unicode=True):
                    if line:
                        chunk = line.decode('utf-8') if isinstance(line, (bytes, bytearray)) else line
                        assistant_msg.markdown(chunk)
                        full_answer += chunk
                history.append({'role':'assistant','content': full_answer})
            except Exception as e:
                assistant_msg.markdown(f"**Erro no chat:** {e}")
                history.append({'role':'assistant','content': f"Erro: {e}"})
    else:
        st.info("Nenhuma coleção disponível para chat.")
