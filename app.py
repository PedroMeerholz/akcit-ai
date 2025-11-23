import json
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from src.crew import AgentCrew


# --- Persistência de histórico ---
HISTORY_PATH = Path("historico_pagamentos.json")


def _ensure_history_path() -> None:
    """Garante que o diretório destino do arquivo de histórico exista."""
    parent_dir = HISTORY_PATH.parent
    if parent_dir != Path('.'):
        parent_dir.mkdir(parents=True, exist_ok=True)


def load_history() -> list[dict]:
    """Carrega o histórico de análises do arquivo JSON, se existir."""
    if HISTORY_PATH.exists():
        try:
            with HISTORY_PATH.open("r", encoding="utf-8") as file:
                history = json.load(file)
            # Normaliza datas salvas como string ISO para objetos date
            for item in history:
                data_value = item.get("data")
                if isinstance(data_value, str):
                    item["data"] = date.fromisoformat(data_value)
            return history
        except (json.JSONDecodeError, ValueError):
            return []
    return []


def save_history(history: list[dict]) -> None:
    """Persiste o histórico de análises em arquivo JSON."""
    _ensure_history_path()

    def _serialize(value):
        if isinstance(value, date):
            return value.isoformat()
        return value

    serializable_history = [
        {key: _serialize(val) for key, val in entry.items()}
        for entry in history
    ]

    with HISTORY_PATH.open("w", encoding="utf-8") as file:
        json.dump(serializable_history, file, ensure_ascii=False, indent=2)


def format_date_display(value) -> str:
    """Formata qualquer representação de data para DD/MM/YYYY."""
    if isinstance(value, datetime):
        return value.strftime("%d/%m/%Y")
    if isinstance(value, date):
        return value.strftime("%d/%m/%Y")
    if isinstance(value, str):
        try:
            return pd.to_datetime(value).strftime("%d/%m/%Y")
        except Exception:
            return value
    return str(value)


def format_model_response(response) -> str:
    """Prepara o conteúdo retornado pelo modelo para exibição."""
    if response is None:
        return "Nenhuma resposta disponível."
    if isinstance(response, dict):
        summary = response.get("summary")
        if isinstance(summary, str) and summary.strip():
            return summary
        try:
            return json.dumps(response, ensure_ascii=False, indent=2)
        except TypeError:
            return str(response)
    if isinstance(response, list):
        try:
            return json.dumps(response, ensure_ascii=False, indent=2)
        except TypeError:
            return str(response)
    return str(response)


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

# Inicializa histórico na sessão (carregando do arquivo, se existir)
if 'historico_pagamentos' not in st.session_state:
    st.session_state['historico_pagamentos'] = load_history()

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
        elif data_input is None:
            st.error("⚠️ Por favor, selecione a data do pagamento.")
        else:
            cnpj_limpo = ''.join(filter(str.isdigit, cnpj_input))
            
            if len(cnpj_limpo) != 14:
                st.error("⚠️ CNPJ inválido. Deve conter 14 dígitos.")
            else:
                # Formata CNPJ para exibição/envio
                cnpj_formatado = f"{cnpj_limpo[:2]}.{cnpj_limpo[2:5]}.{cnpj_limpo[5:8]}/{cnpj_limpo[8:12]}-{cnpj_limpo[12:14]}"
                
                st.markdown("---")
                st.info(f"🔎 Processando análise para: **{cnpj_formatado}** | Valor: **R$ {valor_input:,.2f}**")
                
                conteudo_modelo = None

                with st.spinner("🤖 Agente consultando contrato e validando regras..."):
                    payment_data = {
                        "cnpj": cnpj_formatado,
                        "data_pagamento": data_input.strftime("%d/%m/%Y"),
                        "valor_pago": valor_input
                    }
                    
                    # Chamada da função original
                    resultado = run_contract_agent(payment_data)
                    conteudo_modelo = resultado.get("content")

                    # Normaliza o conteúdo para formatos serializáveis
                    if not isinstance(conteudo_modelo, (str, int, float, bool, list, dict)) and conteudo_modelo is not None:
                        conteudo_modelo = str(conteudo_modelo)

                    novo_registro = {
                        "cnpj": cnpj_formatado,
                        "valor": valor_input,
                        "data": data_input,
                        "status": resultado.get("status", "desconhecido"),
                        "detalhes": conteudo_modelo
                    }

                    st.session_state['historico_pagamentos'].append(novo_registro)
                    save_history(st.session_state['historico_pagamentos'])
                
                st.success("✅ Análise concluída!")
                
                # Exibição do Resultado Imediato
                st.markdown("### 📋 Parecer do Agente")
                with st.container(border=True):
                    # Exibe o retorno completo ou apenas a análise textual
                    if conteudo_modelo is None:
                        st.write("Não foi possível obter a resposta do agente.")
                    elif isinstance(conteudo_modelo, dict) and 'summary' in conteudo_modelo:
                        st.write(conteudo_modelo['summary'])
                    else:
                        st.write(conteudo_modelo)

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
        
        # --- Listas Detalhadas em Dropdowns ---
        col_lists_1, col_lists_2 = st.columns(2)

        def render_segment(header_text: str, dataframe: pd.DataFrame, alert_type: str) -> None:
            callout_map = {
                "error": st.error,
                "warning": st.warning,
                "info": st.info,
                "success": st.success,
            }
            callout = callout_map.get(alert_type, st.write)
            callout(header_text)

            if dataframe.empty:
                st.caption("Nenhum registro encontrado.")
                return

            records = dataframe[['cnpj', 'data', 'detalhes']].to_dict('records')
            for record in records:
                titulo = f"{record.get('cnpj', 'CNPJ desconhecido')} • {format_date_display(record.get('data'))}"
                resposta_modelo = format_model_response(record.get('detalhes'))

                with st.expander(titulo):
                    if resposta_modelo.strip().startswith('{') or resposta_modelo.strip().startswith('['):
                        st.code(resposta_modelo, language="json")
                    else:
                        st.markdown(resposta_modelo)

        with col_lists_1:
            render_segment("🔴 **Atenção Crítica (Atrasado + Valor Errado)**", seg_atrasado_valor_errado, "error")
            st.markdown("<br>", unsafe_allow_html=True)
            render_segment("🟠 **Atenção no Valor (Em Dia + Valor Errado)**", seg_em_dia_valor_errado, "warning")

        with col_lists_2:
            render_segment("🔵 **Atenção no Prazo (Atrasado + Valor Correto)**", seg_atrasado_valor_correto, "info")
            st.markdown("<br>", unsafe_allow_html=True)
            render_segment("🟢 **Conformes (Em Dia + Valor Correto)**", seg_em_dia_valor_correto, "success")

# --- Rodapé ---
st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: #666; font-size: 0.9em;'>"
    "Agente Fiscal de Contratos | Powered by CrewAI & Streamlit"
    "</div>",
    unsafe_allow_html=True
)