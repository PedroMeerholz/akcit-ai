import os
import PyPDF2
import re
from crewai import LLM
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_pinecone import PineconeVectorStore
from langchain_huggingface import HuggingFaceEmbeddings
from dotenv import load_dotenv

# Carrega variáveis de ambiente (.env)
load_dotenv()
os.environ["PINECONE_API_KEY"] = os.getenv("PINECONE_API_KEY")
# --- Configurações Globais ---
INDEX_NAME = "rag-index" # Nome do seu index no Pinecone

# Inicializa o modelo de Embeddings uma única vez (Performance)
# Usando BGE-Base conforme sua configuração
embeddings = HuggingFaceEmbeddings(
    model_name="BAAI/bge-base-en-v1.5",
    model_kwargs={'device': 'cpu'},  
    encode_kwargs={'normalize_embeddings': True}  
)

# --- Funções Auxiliares ---

def clean_text(text):
    """Limpa quebras de linha e espaços excessivos para melhor leitura."""
    text = text.replace("\n", " ")
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def get_vectorstore():
    """Retorna a conexão com o Pinecone."""
    return PineconeVectorStore(index_name=INDEX_NAME, embedding=embeddings)

def process_and_index_file(uploaded_file):
    """Processa o arquivo PDF/TXT e envia para o Pinecone."""
    text = ""
    try:
        # 1. Leitura do Arquivo
        if uploaded_file.type == "application/pdf":
            pdf_reader = PyPDF2.PdfReader(uploaded_file)
            for page in pdf_reader.pages:
                text += page.extract_text() or ""
        elif uploaded_file.type == "text/plain":
            text = uploaded_file.getvalue().decode("utf-8")
        
        if not text:
            return False, "O arquivo está vazio ou não pôde ser lido."

        # 2. Chunking (Divisão)
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200
        )
        chunks = text_splitter.split_text(text)
        
        # 3. Indexação (Upsert no Pinecone)
        vectorstore = get_vectorstore()
        vectorstore.add_texts(chunks)
        
        return True, f"Sucesso! {len(chunks)} trechos foram indexados no Pinecone."

    except Exception as e:
        return False, f"Erro ao processar arquivo: {str(e)}"

def get_chatbot_response(chat_history: list, user_prompt: str):
    """
    Lógica principal: RAG + LLM (Groq) via CrewAI.
    """
    try:
        # 1. Busca no Pinecone (Retrieval)
        vectorstore = get_vectorstore()
        docs = vectorstore.similarity_search(user_prompt, k=3) 
        
        # Limpa e formata o contexto
        cleaned_chunks = [clean_text(doc.page_content) for doc in docs]
        context_text_llm = "\n\n".join(cleaned_chunks)
        
        # Cria HTML para exibição bonita no Streamlit (Justificado)
        context_html = ""
        for i, chunk in enumerate(cleaned_chunks):
            context_html += f"<p><strong>Trecho {i+1}:</strong><br>{chunk}</p><hr>"

        # 2. Configura o LLM (Groq)
        # Nota: Mantive sua configuração que funcionou com base_url
        llm = LLM(
            model="meta-llama/llama-4-maverick-17b-128e-instruct", # Ou o modelo groq/llama3...
            temperature=0.1,
            base_url="https://api.groq.com/openai/v1",
            api_key=os.getenv("GROQ_API_KEY")
        )
        
        # 3. Monta o Prompt
        system_prompt = f"""
        Você é um assistente jurídico inteligente e preciso.
        Use ESTRITAMENTE o contexto abaixo recuperado do contrato para responder.
        Se a resposta não estiver no contexto, diga que não encontrou a informação.
        
        --- CONTEXTO DO CONTRATO ---
        {context_text_llm}
        ----------------------------
        """
        
        full_prompt = system_prompt + "\n\n--- Histórico Recente ---\n"
        
        # Adiciona histórico (últimas 5 mensagens)
        for msg in chat_history[-5:]: 
            if "content" in msg:
                 if msg["role"] == "user" and msg["content"] == user_prompt:
                    continue
                 full_prompt += f"{msg['role']}: {msg['content']}\n"
        
        full_prompt += f"user: {user_prompt}\n"
        full_prompt += "assistant: " 

        # 4. Gera Resposta
        response = llm.call(full_prompt)
        
        return response, context_html

    except Exception as e:
        return f"Erro no processamento: {str(e)}", ""