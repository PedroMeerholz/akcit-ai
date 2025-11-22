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
st.markdown("### Sistema de Consulta de Contratos por CNPJ")
st.markdown("---")

# --- Sidebar ---
with st.sidebar:
    st.header("ℹ️ Sobre")
    st.markdown("""
    Este sistema consulta informações contratuais 
    armazenadas na base de conhecimento utilizando 
    IA e RAG (Retrieval-Augmented Generation).
    
    **Informações disponíveis:**
    - Valor original do contrato
    - Data de pagamento
    - Multa por atraso
    - Juros por atraso
    """)
    st.markdown("---")
    st.caption("Desenvolvido com CrewAI + Groq")

# --- Formulário de Consulta ---
col1, col2 = st.columns([3, 1])

with col1:
    cnpj_input = st.text_input(
        "Digite o CNPJ da empresa:",
        placeholder="XX.XXX.XXX/XXXX-XX",
        help="Você pode inserir o CNPJ com ou sem formatação"
    )

with col2:
    st.markdown("<br>", unsafe_allow_html=True)  # Espaçamento
    btn_consultar = st.button("🔍 Consultar", use_container_width=True, type="primary")

# --- Processamento e Exibição ---
if btn_consultar:
    if not cnpj_input:
        st.error("⚠️ Por favor, insira um CNPJ válido.")
    else:
        # Limpa o CNPJ
        cnpj_limpo = ''.join(filter(str.isdigit, cnpj_input))
        
        if len(cnpj_limpo) != 14:
            st.error("⚠️ CNPJ inválido. Deve conter 14 dígitos.")
        else:
            # Formata CNPJ para exibição
            cnpj_formatado = f"{cnpj_limpo[:2]}.{cnpj_limpo[2:5]}.{cnpj_limpo[5:8]}/{cnpj_limpo[8:12]}-{cnpj_limpo[12:14]}"
            
            st.markdown("---")
            st.info(f"🔎 Consultando informações para o CNPJ: **{cnpj_formatado}**")
            
            with st.spinner("🤖 Analisando base de conhecimento..."):
                # Monta a query com o CNPJ
                query = f"Consulte as informações contratuais do CNPJ {cnpj_formatado}"
                resultado = run_contract_agent(query)
            
            # Exibe o resultado
            st.success("✅ Consulta realizada com sucesso!")
            
            st.markdown("### � Resultado da Consulta")
            
            # Container com borda para o resultado            
            st.markdown(resultado)
            
            st.markdown("</div>", unsafe_allow_html=True)
            
            # Botão de download do resultado
            st.markdown("---")
            col_download1, col_download2, col_download3 = st.columns([1, 2, 1])
            with col_download2:
                from datetime import datetime
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                
                st.download_button(
                    label="💾 Baixar Resultado",
                    data=f"# Consulta Contratual - {cnpj_formatado}\n\n{resultado}",
                    file_name=f"consulta_{cnpj_limpo}_{timestamp}.md",
                    mime="text/markdown",
                    use_container_width=True
                )

# --- Rodapé ---
st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: #666; font-size: 0.9em;'>"
    "Sistema de Consulta Contratual | Powered by AI"
    "</div>",
    unsafe_allow_html=True
)