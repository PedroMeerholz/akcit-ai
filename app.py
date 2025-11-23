import json
import re
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


def parse_validation_string(text: str) -> dict | None:
    """Extrai campos do PaymentValidationResultSchema representado como string."""
    if not isinstance(text, str):
        return None

    pattern = r"payment_validation=PaymentValidationResultSchema\((.*?)\)"
    match = re.search(pattern, text)
    inner = None

    if match:
        inner = match.group(1)
    elif text.strip().startswith("PaymentValidationResultSchema"):
        start = text.find('(')
        end = text.rfind(')')
        if start != -1 and end != -1:
            inner = text[start + 1:end]

    if not inner:
        return None

    pairs = re.findall(r"(\w+)=['\"]([^'\"]+)['\"]", inner)
    if not pairs:
        return None

    return {key: value for key, value in pairs}


def normalize_validation(validation_data):
    """Converte o resultado de validação para um dicionário serializável."""
    if validation_data in (None, ""):
        return None

    if isinstance(validation_data, dict):
        return {
            key: (str(value) if not isinstance(value, (int, float, bool, type(None))) else value)
            for key, value in validation_data.items()
        }

    if hasattr(validation_data, "model_dump"):
        return normalize_validation(validation_data.model_dump())

    if hasattr(validation_data, "dict"):
        return normalize_validation(validation_data.dict())

    if isinstance(validation_data, str):
        try:
            parsed = json.loads(validation_data)
            return normalize_validation(parsed)
        except json.JSONDecodeError:
            parsed = parse_validation_string(validation_data)
            if parsed:
                return normalize_validation(parsed)
            return {"raw": validation_data}

    return {"raw": str(validation_data)}


def extract_summary_and_validation(details_value, existing_validation=None):
    """Retorna o resumo textual e os detalhes de validação estruturados."""
    summary_text = ""
    validation_dict = normalize_validation(existing_validation)

    if isinstance(details_value, dict):
        summary_text = (details_value.get("summary") or "").strip()
        if validation_dict is None:
            validation_dict = normalize_validation(details_value.get("payment_validation"))

    elif isinstance(details_value, str):
        summary_match = re.search(r"summary=['\"]([^'\"]*)['\"]", details_value)
        summary_text = summary_match.group(1) if summary_match else details_value.strip()
        if validation_dict is None:
            validation_dict = normalize_validation(parse_validation_string(details_value))

    elif details_value is not None:
        summary_text = str(details_value)

    if not summary_text:
        summary_text = "Resumo não disponível."

    return summary_text, validation_dict


def load_history() -> list[dict]:
    """Carrega o histórico de análises do arquivo JSON, se existir."""
    if HISTORY_PATH.exists():
        try:
            with HISTORY_PATH.open("r", encoding="utf-8") as file:
                history = json.load(file)

            for item in history:
                data_value = item.get("data")
                if isinstance(data_value, str):
                    item["data"] = date.fromisoformat(data_value)

                summary_text, validation_dict = extract_summary_and_validation(
                    item.get("detalhes"),
                    item.get("validacao_pagamento")
                )
                item["detalhes"] = summary_text
                item["validacao_pagamento"] = normalize_validation(validation_dict)

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

    serializable_history = []
    for entry in history:
        prepared_entry = dict(entry)
        prepared_entry["validacao_pagamento"] = normalize_validation(
            prepared_entry.get("validacao_pagamento")
        ) or {}
        serializable_history.append({
            key: _serialize(val) for key, val in prepared_entry.items()
        })

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


def format_currency_br(value: float) -> str:
    """Formata valores monetários em BRL."""
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def parse_amount_value(value) -> float:
    """Normaliza diferentes representações de valores monetários."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)

    cleaned = str(value).strip()
    if not cleaned:
        return 0.0

    cleaned = cleaned.replace("R$", "").replace("\u00a0", "").replace(" ", "")

    numbers = re.findall(r"-?\d+(?:[.,]\d+)?", cleaned)
    if not numbers:
        return 0.0

    number = numbers[-1]
    if "," in number and "." in number:
        if number.rfind(",") > number.rfind("."):
            number = number.replace(".", "").replace(",", ".")
        else:
            number = number.replace(",", "")
    else:
        number = number.replace(",", ".")

    try:
        return float(number)
    except ValueError:
        return 0.0


def get_amount_diff_from_validation(validation_value) -> float:
    """Obtém o amount_diff já convertido para float a partir da validação."""
    normalized = normalize_validation(validation_value)
    if not normalized:
        return 0.0

    candidate_keys = (
        "amount_diff",
        "amount_difference",
        "difference",
        "valor_diferenca",
        "valor_diferenca_absoluto",
    )

    for key in candidate_keys:
        if key in normalized and normalized[key] not in (None, ""):
            return parse_amount_value(normalized[key])

    if "raw" in normalized and normalized["raw"]:
        return parse_amount_value(normalized["raw"])

    return 0.0


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
                resumo_textual = "Resumo não disponível."
                validacao_pagamento = {}

                with st.spinner("🤖 Agente consultando contrato e validando regras..."):
                    payment_data = {
                        "cnpj": cnpj_formatado,
                        "data_pagamento": data_input.strftime("%d/%m/%Y"),
                        "valor_pago": valor_input
                    }
                    
                    # Chamada da função original
                    resultado = run_contract_agent(payment_data)
                    conteudo_modelo = resultado.get("content")

                    resumo_textual, validacao_pagamento = extract_summary_and_validation(
                        conteudo_modelo
                    )
                    if validacao_pagamento is None:
                        validacao_pagamento = {}

                    novo_registro = {
                        "cnpj": cnpj_formatado,
                        "valor": valor_input,
                        "data": data_input,
                        "status": resultado.get("status", "desconhecido"),
                        "detalhes": resumo_textual,
                        "validacao_pagamento": validacao_pagamento
                    }

                    st.session_state['historico_pagamentos'].append(novo_registro)
                    save_history(st.session_state['historico_pagamentos'])
                
                st.success("✅ Análise concluída!")
                
                # Exibição do Resultado Imediato
                st.markdown("### 📋 Parecer do Agente")
                with st.container(border=True):
                    st.markdown(f"**Resumo:** {resumo_textual}")

                    if validacao_pagamento:
                        tabela_validacao = pd.DataFrame([validacao_pagamento])
                        st.table(tabela_validacao)
                    else:
                        st.caption("Nenhuma informação adicional de validação disponível.")

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

        pagamentos_valor_errado = df[df['status'].isin(['atrasado_valor_errado', 'em_dia_valor_errado'])]
        total_perda_valor_errado = 0.0
        if 'validacao_pagamento' in pagamentos_valor_errado:
            perdas_series = pagamentos_valor_errado['validacao_pagamento'].apply(get_amount_diff_from_validation)
            total_perda_valor_errado = float(perdas_series.sum())

        # --- Métricas (KPIs) ---
        kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)
        
        kpi1.metric("Atrasado / Valor Errado 🚨", len(seg_atrasado_valor_errado))
        kpi2.metric("Em Dia / Valor Errado ⚠️", len(seg_em_dia_valor_errado))
        kpi3.metric("Atrasado / Valor Correto ⏱️", len(seg_atrasado_valor_correto))
        kpi4.metric("Em Dia / Valor Correto ✅", len(seg_em_dia_valor_correto))
        kpi5.metric("Perdas com Valores Errados 💸", format_currency_br(total_perda_valor_errado))
        
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

            records = dataframe[['cnpj', 'data', 'detalhes', 'validacao_pagamento']].to_dict('records')
            for record in records:
                titulo = f"{record.get('cnpj', 'CNPJ desconhecido')} • {format_date_display(record.get('data'))}"
                resumo = record.get('detalhes')
                if resumo is None:
                    resumo = "Resumo não disponível."
                else:
                    resumo = str(resumo).strip() or "Resumo não disponível."

                validacao_display = normalize_validation(record.get('validacao_pagamento'))

                with st.expander(titulo):
                    st.markdown(f"**Resumo:** {resumo}")

                    if validacao_display:
                        tabela_validacao = pd.DataFrame([validacao_display])
                        st.table(tabela_validacao)
                    else:
                        st.caption("Nenhuma informação de validação disponível.")

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