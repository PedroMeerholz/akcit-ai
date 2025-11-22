import re
import streamlit as st

from src.crew import ContractAgentCrew


def run_contract_agent(question: str):
    crew_instance = ContractAgentCrew()

    cnpj_pattern = r'\b\d{2}\.?\d{3}\.?\d{3}\/?\d{4}\-?\d{2}\b'
    cnpj_match = re.search(cnpj_pattern, question)
    cnpj = None
    if cnpj_match:
        cnpj = cnpj_match.group(0)

    result = crew_instance.contractCrew().kickoff(inputs={"cnpj": cnpj})
    return result

# --- Configuração da Página ---
st.set_page_config(page_title="Contratos.IA", page_icon="⚖️", layout="wide")

st.title("⚖️ Contratos.IA")

# --- Sidebar (Gerenciado pelo Backend) ---
with st.sidebar:
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
            resposta = run_contract_agent(prompt)
            
            st.markdown(resposta)
    
    # 3. Salva no histórico
    st.session_state.messages.append({
        "role": "assistant", 
        "content": resposta, 
    })