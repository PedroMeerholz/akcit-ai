import streamlit as st
import src.utils.rag_backend as backend # Importamos nosso arquivo de lógica

# --- Configuração da Página ---
st.set_page_config(page_title="Contratos.IA", page_icon="⚖️", layout="wide")

st.title("⚖️ Contratos.IA")

# --- Sidebar (Gerenciado pelo Backend) ---
with st.sidebar:
    st.header("Base de Conhecimento")
    uploaded_file = st.file_uploader("Adicionar Contrato (PDF/TXT)", type=["pdf", "txt"])
    
    if uploaded_file and st.button("Processar e Indexar"):
        with st.spinner("Lendo, gerando embeddings e enviando ao Pinecone..."):
            # Chama a função do outro arquivo
            sucesso, mensagem = backend.process_and_index_file(uploaded_file)
            
            if sucesso:
                st.success(mensagem)
            else:
                st.error(mensagem)
    
    st.divider()
    if st.button("🗑️ Limpar Chat"):
        st.session_state["messages"] = []
        st.rerun()

# --- Loop do Chat ---

if "messages" not in st.session_state:
    st.session_state["messages"] = []

# Exibe histórico
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        
        # Exibe contexto se houver (Recuperado do histórico)
        if "context_html" in msg and msg["context_html"]:
            with st.expander("📚 Fontes utilizadas"):
                 st.markdown(
                    f"<div style='text-align: justify; font-size: 0.9em; color: #444;'>{msg['context_html']}</div>", 
                    unsafe_allow_html=True
                )

# Input do usuário
if prompt := st.chat_input("Pergunte sobre cláusulas, prazos ou multas..."):
    
    # 1. Mostra msg usuário
    with st.chat_message("user"):
        st.markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})

    # 2. Gera resposta (Chama o Backend)
    with st.chat_message("assistant"):
        with st.spinner("Analisando base jurídica..."):
            
            resposta, contexto_formatado = backend.get_chatbot_response(
                chat_history=st.session_state.messages, 
                user_prompt=prompt
            )
            
            st.markdown(resposta)
            
            if contexto_formatado:
                with st.expander("📚 Fontes utilizadas nesta resposta"):
                    st.markdown(
                        f"<div style='text-align: justify; font-size: 0.9em; color: #444;'>{contexto_formatado}</div>", 
                        unsafe_allow_html=True
                    )
    
    # 3. Salva no histórico
    st.session_state.messages.append({
        "role": "assistant", 
        "content": resposta, 
        "context_html": contexto_formatado
    })