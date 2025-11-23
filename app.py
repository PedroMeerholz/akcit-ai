import streamlit as st

from src.crew import AgentCrew


def run_contract_agent(payment_info: dict) -> str:
    crew_instance = AgentCrew()

    inputs = {
        "cnpj": payment_info['cnpj'],
        "payment_info": payment_info
    }
    result = crew_instance.contractCrew().kickoff(inputs=inputs)
    print(result)
    return result

# --- Configuração da Página ---
st.set_page_config(page_title="Contratos.IA", page_icon="⚖️", layout="wide")

st.title("⚖️ Contratos.IA")
st.markdown("### Sistema de Consulta de Contratos por CNPJ")
st.markdown("---")

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
                # query = f"Consulte as informações contratuais do CNPJ {cnpj_formatado}"
                
                payment_data = {
                    "cnpj": cnpj_formatado,
                    "data_pagamento": "22/11/2025",
                    "valor_pago": 1050.00
                }
                
                resultado = run_contract_agent(payment_data)
            
            # Exibe o resultado
            st.success("✅ Consulta realizada com sucesso!")
            
            st.markdown("### � Resultado da Consulta")
            
            # Container com borda para o resultado            
            st.write(resultado)
            
            

# --- Rodapé ---
st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: #666; font-size: 0.9em;'>"
    "Sistema de Consulta Contratual | Powered by AI"
    "</div>",
    unsafe_allow_html=True
)