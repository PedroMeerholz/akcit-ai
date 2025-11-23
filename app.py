import pandas as pd
import streamlit as st

from src.crew import AgentCrew


def run_contract_agent(payment_info: dict) -> str:
    crew_instance = AgentCrew()

    inputs = {
        "cnpj": payment_info['cnpj'],
        "payment_info": payment_info
    }
    result = crew_instance.contractCrew().kickoff(inputs=inputs)
    return {
        "status": "atrasado_valor_errado",
        "content": result
    }

# --- Configuração da Página ---
st.set_page_config(page_title="Contratos.IA", page_icon="⚖️", layout="wide")

# Inicializa histórico na sessão se não existir
if 'historico_pagamentos' not in st.session_state:
    st.session_state['historico_pagamentos'] = []

st.title("⚖️ Contratos.IA")
st.markdown("### Gestão Inteligente de Fiscalização Contratual")
st.markdown("---")

# --- Criação de Abas ---
tab_form, tab_dash = st.tabs(["📝 Nova Análise", "📊 Dashboard de Acompanhamento"])

# ==============================================================================
# ABA 1: FORMULÁRIO DE NOVA ANÁLISE
# ==============================================================================
with tab_form:
    with st.container():
        st.subheader("Dados do Pagamento")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            cnpj_input = st.text_input(
                "CNPJ da Empresa",
                placeholder="XX.XXX.XXX/XXXX-XX",
                help="Insira apenas números ou com formatação"
            )
        
        with col2:
            valor_input = st.number_input(
                "Valor do Pagamento (R$)",
                min_value=0.0,
                format="%.2f",
                step=100.00
            )
            
        with col3:
            data_input = st.date_input(
                "Data do Pagamento",
                value=None,
                help="Selecione a data em que o pagamento foi realizado"
            )

        btn_consultar = st.button("🔍 Analisar Contrato", type="primary", use_container_width=True)

    # --- Processamento ---
    if btn_consultar:
        if not cnpj_input:
            st.error("⚠️ Por favor, insira um CNPJ válido.")
        else:
            cnpj_limpo = ''.join(filter(str.isdigit, cnpj_input))
            
            if len(cnpj_limpo) != 14:
                st.error("⚠️ CNPJ inválido. Deve conter 14 dígitos.")
            else:
                # Formata CNPJ para exibição/envio
                cnpj_formatado = f"{cnpj_limpo[:2]}.{cnpj_limpo[2:5]}.{cnpj_limpo[5:8]}/{cnpj_limpo[8:12]}-{cnpj_limpo[12:14]}"
                
                st.markdown("---")
                st.info(f"🔎 Processando análise para: **{cnpj_formatado}** | Valor: **R$ {valor_input:,.2f}**")
                
                with st.spinner("🤖 Agente consultando contrato e validando regras..."):
                    
                    payment_data = {
                        "cnpj": cnpj_formatado,
                        "data_pagamento": data_input.strftime("%d/%m/%Y"),
                        "valor_pago": valor_input
                    }
                    
                    # Chamada da função original
                    resultado = run_contract_agent(payment_data)
                    
                    # Armazenar no histórico da sessão para o Dashboard
                    st.session_state['historico_pagamentos'].append({
                        "cnpj": cnpj_formatado,
                        "valor": valor_input,
                        "data": data_input,
                        "status": resultado.get("status", "desconhecido"), # Assumindo que retorna dict
                        "detalhes": resultado.get("content")
                    })
                
                st.success("✅ Análise concluída!")
                
                # Exibição do Resultado Imediato
                st.markdown("### 📋 Parecer do Agente")
                with st.container(border=True):
                    # Exibe o retorno completo ou apenas a análise textual
                    st.write(resultado.get("content")['summary'])

# ==============================================================================
# ABA 2: DASHBOARD
# ==============================================================================
with tab_dash:
    st.subheader("Visão Geral dos Pagamentos")
    
    if not st.session_state['historico_pagamentos']:
        st.warning("Nenhuma análise realizada ainda. Utilize a aba 'Nova Análise' para alimentar o dashboard.")
    else:
        df = pd.DataFrame(st.session_state['historico_pagamentos'])
        
        # --- Definição dos Segmentos ---
        # Segmento 1: Pagamentos atrasados com valor errado
        seg_atrasado_valor_errado = df[df['status'] == 'atrasado_valor_errado']
        
        # Segmento 2: Pagamentos em dia com valor errado
        seg_em_dia_valor_errado = df[df['status'] == 'em_dia_valor_errado']
        
        # Segmento 3: Pagamentos atrasados com valor correto
        seg_atrasado_valor_correto = df[df['status'] == 'atrasado_valor_correto']
        
        # Segmento 4: Pagamento em dia com valor correto
        seg_em_dia_valor_correto = df[df['status'] == 'em_dia_valor_correto']

        # --- Métricas (KPIs) ---
        kpi1, kpi2, kpi3, kpi4 = st.columns(4)
        
        kpi1.metric("Atrasado / Valor Errado 🚨", len(seg_atrasado_valor_errado))
        kpi2.metric("Em Dia / Valor Errado ⚠️", len(seg_em_dia_valor_errado))
        kpi3.metric("Atrasado / Valor Correto ⏱️", len(seg_atrasado_valor_correto))
        kpi4.metric("Em Dia / Valor Correto ✅", len(seg_em_dia_valor_correto))
        
        st.markdown("---")
        
        # --- Listas Detalhadas ---
        col_lists_1, col_lists_2 = st.columns(2)
        
        def show_table(title, dataframe, color_header):
            st.markdown(f"##### {title}")
            if not dataframe.empty:
                st.dataframe(
                    dataframe[['cnpj', 'data', 'valor']], 
                    use_container_width=True,
                    hide_index=True
                )
            else:
                st.caption("Nenhum registro encontrado.")

        with col_lists_1:
            st.error("🔴 **Atenção Crítica (Atrasado + Valor Errado)**")
            show_table("", seg_atrasado_valor_errado, "red")
            
            st.markdown("<br>", unsafe_allow_html=True)
            
            st.warning("🟠 **Atenção no Valor (Em Dia + Valor Errado)**")
            show_table("", seg_em_dia_valor_errado, "orange")

        with col_lists_2:
            st.info("🔵 **Atenção no Prazo (Atrasado + Valor Correto)**")
            show_table("", seg_atrasado_valor_correto, "blue")
            
            st.markdown("<br>", unsafe_allow_html=True)
            
            st.success("🟢 **Conformes (Em Dia + Valor Correto)**")
            show_table("", seg_em_dia_valor_correto, "green")

# --- Rodapé ---
st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: #666; font-size: 0.9em;'>"
    "Agente Fiscal de Contratos | Powered by CrewAI & Streamlit"
    "</div>",
    unsafe_allow_html=True
)