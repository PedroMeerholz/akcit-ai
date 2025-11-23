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


def _extract_field_from_text(text: str, keys: tuple[str, ...]) -> str:
    for key in keys:
        pattern = rf"{key}=['\"]([^'\"]*)['\"]"
        match = re.search(pattern, text)
        if match:
            return match.group(1).strip()
    return ""


def _normalize_text_spacing(value) -> str:
    """Colapsa espaços e quebras de linha consecutivas em um único espaço."""
    if value in (None, ""):
        return ""

    text = str(value)
    normalized = re.sub(r"\s+", " ", text)
    return normalized.strip()


def parse_model_output_content(content, existing_validation=None):
    """Extrai resumo, análise, recomendações e validação do conteúdo do modelo."""
    summary_text = ""
    analysis_text = ""
    recommendations_text = ""
    validation_dict = normalize_validation(existing_validation)

    if isinstance(content, dict):
        summary_text = str(content.get("payment_summary") or "").strip()
        analysis_text = str(content.get("analysis") or "").strip()
        recommendations_text = str(content.get("recommendations") or "").strip()
        if validation_dict is None:
            validation_dict = normalize_validation(content.get("payment_validation"))

    elif isinstance(content, str):
        text = content.strip()
        if text:
            summary_text = _extract_field_from_text(text, ("payment_summary", "summary"))
            analysis_text = _extract_field_from_text(text, ("analysis", "behavior_analysis"))
            recommendations_text = _extract_field_from_text(text, ("recommendations", "recommendation", "suggestions"))

            if validation_dict is None:
                validation_dict = normalize_validation(parse_validation_string(text))

            if not summary_text and "=" not in text:
                summary_text = text
            elif not summary_text:
                summary_text = _extract_field_from_text(text, ("payment_summary", "summary", "analysis"))

    elif content is not None:
        summary_text = str(content).strip()

    if not summary_text and analysis_text:
        summary_text = analysis_text
    if not analysis_text and summary_text:
        analysis_text = summary_text

    summary_text = _normalize_text_spacing(summary_text)
    analysis_text = _normalize_text_spacing(analysis_text)
    recommendations_text = _normalize_text_spacing(recommendations_text)

    validation_dict = validation_dict or {}

    return summary_text, analysis_text, recommendations_text, validation_dict


def normalize_entry_outputs(entry: dict) -> None:
    """Garante que os campos de análise estejam presentes e normalizados."""
    payment_summary = _normalize_text_spacing(entry.get("payment_summary") or "")
    analysis_text = _normalize_text_spacing(entry.get("analysis") or "")
    recommendations_text = _normalize_text_spacing(entry.get("recommendations") or "")
    validation_dict = normalize_validation(entry.get("validacao_pagamento") or entry.get("payment_validation"))

    candidates: list = []
    if payment_summary or analysis_text or recommendations_text:
        candidates.append({
            "payment_summary": payment_summary,
            "analysis": analysis_text,
            "recommendations": recommendations_text,
            "payment_validation": validation_dict,
        })
    if entry.get("detalhes"):
        candidates.append(entry["detalhes"])

    if not candidates:
        candidates.append("")

    for candidate in candidates:
        parsed_summary, parsed_analysis, parsed_recommendations, parsed_validation = parse_model_output_content(
            candidate,
            existing_validation=validation_dict,
        )
        payment_summary = payment_summary or parsed_summary
        analysis_text = analysis_text or parsed_analysis
        recommendations_text = recommendations_text or parsed_recommendations
        if not validation_dict:
            validation_dict = parsed_validation

    payment_summary = _normalize_text_spacing(payment_summary) or "Informação não disponível."
    analysis_text = _normalize_text_spacing(analysis_text) or payment_summary
    recommendations_text = _normalize_text_spacing(recommendations_text) or "Recomendação não disponível."

    entry["payment_summary"] = payment_summary
    entry["analysis"] = analysis_text
    entry["recommendations"] = recommendations_text
    entry["validacao_pagamento"] = validation_dict or {}
    entry["detalhes"] = entry["payment_summary"]


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

                normalize_entry_outputs(item)
                item["status_ticket"] = item.get("status_ticket", "Em Aberto")

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
        normalize_entry_outputs(prepared_entry)
        prepared_entry["validacao_pagamento"] = normalize_validation(
            prepared_entry.get("validacao_pagamento")
        ) or {}
        prepared_entry["status_ticket"] = prepared_entry.get("status_ticket", "Em Aberto")
        prepared_entry["detalhes"] = prepared_entry.get("payment_summary", "")
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


def trigger_rerun() -> None:
    """Dispara a recarga da aplicação de forma compatível entre versões."""
    rerun_fn = getattr(st, "rerun", None)
    if callable(rerun_fn):
        rerun_fn()
        return

    experimental_fn = getattr(st, "experimental_rerun", None)
    if callable(experimental_fn):
        experimental_fn()


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


def get_payment_status_from_validation(validation_value) -> str:
    """Obtém o status do pagamento a partir da validação."""
    normalized = normalize_validation(validation_value)
    if not normalized:
        return "Desconhecido"

    candidate_keys = (
        "payment_status",
        "status_pagamento",
        "status",
        "payment_status_label",
    )

    for key in candidate_keys:
        value = normalized.get(key) if isinstance(normalized, dict) else None
        if value:
            return str(value)

    raw_value = normalized.get("raw") if isinstance(normalized, dict) else None
    if raw_value:
        match = re.search(r"payment_status=['\"]?([\w_ .-]+)['\"]?", str(raw_value))
        if match:
            return match.group(1)

    return "Desconhecido"


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
st.set_page_config(page_title="Verif.ai", layout="wide")

# Inicializa histórico na sessão (carregando do arquivo, se existir)
if 'historico_pagamentos' not in st.session_state:
    st.session_state['historico_pagamentos'] = load_history()

st.title("Verif.ai")
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

                    (
                        payment_summary_text,
                        analysis_text,
                        recommendations_text,
                        validacao_pagamento,
                    ) = parse_model_output_content(conteudo_modelo)

                    payment_summary_text = _normalize_text_spacing(payment_summary_text) or "Informação não disponível."
                    analysis_text = _normalize_text_spacing(analysis_text) or payment_summary_text
                    recommendations_text = _normalize_text_spacing(recommendations_text) or "Recomendação não disponível."
                    validacao_pagamento = validacao_pagamento or {}

                    novo_registro = {
                        "cnpj": cnpj_formatado,
                        "valor": valor_input,
                        "data": data_input,
                        "status": resultado.get("status", "desconhecido"),
                        "payment_summary": payment_summary_text,
                        "analysis": analysis_text,
                        "recommendations": recommendations_text,
                        "validacao_pagamento": validacao_pagamento,
                        "detalhes": payment_summary_text,
                        "status_ticket": "Em Aberto"
                    }

                    normalize_entry_outputs(novo_registro)
                    st.session_state['historico_pagamentos'].append(novo_registro)
                    save_history(st.session_state['historico_pagamentos'])
                
                st.success("✅ Análise concluída!")
                
                # Exibição do Resultado Imediato
                st.markdown("### 📋 Parecer do Agente")
                with st.container(border=True):
                    st.text(f"Análise do pagamento: {payment_summary_text}")
                    st.text(f"Análise comportamental: {analysis_text}")
                    st.text(f"Recomendação de abordagem: {recommendations_text}")

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

        if 'status_ticket' not in df.columns:
            df['status_ticket'] = 'Em Aberto'
        
        # --- Definição dos Segmentos ---
        df_aberto = df[df['status_ticket'] == 'Em Aberto']

        # Segmento 1: Pagamentos atrasados com valor errado
        seg_atrasado_valor_errado = df_aberto[df_aberto['status'] == 'atrasado_valor_errado']

        # Segmento 2: Pagamentos em dia com valor errado
        seg_em_dia_valor_errado = df_aberto[df_aberto['status'] == 'em_dia_valor_errado']

        # Segmento 3: Pagamentos atrasados com valor correto
        seg_atrasado_valor_correto = df_aberto[df_aberto['status'] == 'atrasado_valor_correto']

        # Segmento 4: Pagamento em dia com valor correto
        seg_em_dia_valor_correto = df_aberto[df_aberto['status'] == 'em_dia_valor_correto']

        pagamentos_valor_errado = df_aberto[df_aberto['status'].isin(['atrasado_valor_errado', 'em_dia_valor_errado'])]
        total_perda_valor_errado = 0.0
        if 'validacao_pagamento' in pagamentos_valor_errado.columns:
            perdas_series = pagamentos_valor_errado['validacao_pagamento'].apply(get_amount_diff_from_validation)
            total_perda_valor_errado = float(perdas_series.sum())

        pagamentos_recuperados = df[df['status_ticket'] == 'Recuperado']
        total_recuperado = 0.0
        if not pagamentos_recuperados.empty and 'validacao_pagamento' in pagamentos_recuperados.columns:
            recuperados_series = pagamentos_recuperados['validacao_pagamento'].apply(get_amount_diff_from_validation)
            total_recuperado = float(recuperados_series.sum())

        # --- Métricas (KPIs) ---
        kpi1, kpi2, kpi3, kpi4, kpi5, kpi6 = st.columns(6)
        
        kpi1.metric("Atrasado / Valor Errado 🚨", len(seg_atrasado_valor_errado))
        kpi2.metric("Em Dia / Valor Errado ⚠️", len(seg_em_dia_valor_errado))
        kpi3.metric("Atrasado / Valor Correto ⏱️", len(seg_atrasado_valor_correto))
        kpi4.metric("Em Dia / Valor Correto ✅", len(seg_em_dia_valor_correto))
        kpi5.metric("Perdas com Valores Errados 💸", format_currency_br(total_perda_valor_errado))
        kpi6.metric("Valores Recuperados ♻️", format_currency_br(total_recuperado))
        
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

            for idx, record in dataframe.iterrows():
                titulo = f"{record.get('cnpj', 'CNPJ desconhecido')} • {format_date_display(record.get('data'))}"
                payment_summary_display = _normalize_text_spacing(
                    record.get('payment_summary') or record.get('detalhes') or ""
                ) or "Informação não disponível."
                analysis_display = _normalize_text_spacing(
                    record.get('analysis') or payment_summary_display
                ) or payment_summary_display
                recommendations_display = _normalize_text_spacing(
                    record.get('recommendations') or ""
                ) or "Recomendação não disponível."

                validacao_display = normalize_validation(record.get('validacao_pagamento'))

                with st.expander(titulo):
                    st.text(f"Análise do pagamento: {payment_summary_display}")
                    st.text(f"Análise comportamental: {analysis_display}")
                    st.text(f"Recomendação de abordagem: {recommendations_display}")

                    if validacao_display:
                        tabela_validacao = pd.DataFrame([validacao_display])
                        st.table(tabela_validacao)
                    else:
                        st.caption("Nenhuma informação de validação disponível.")

                    close_key = f"close_ticket_{idx}"
                    if st.checkbox("Fechar Ticket", key=close_key):
                        st.session_state['historico_pagamentos'][idx]['status_ticket'] = "Recuperado"
                        save_history(st.session_state['historico_pagamentos'])
                        trigger_rerun()

        with col_lists_1:
            render_segment("🔴 **Atenção Crítica (Atrasado + Valor Errado)**", seg_atrasado_valor_errado, "error")
            st.markdown("<br>", unsafe_allow_html=True)
            render_segment("🟠 **Atenção no Valor (Em Dia + Valor Errado)**", seg_em_dia_valor_errado, "warning")

        with col_lists_2:
            render_segment("🔵 **Atenção no Prazo (Atrasado + Valor Correto)**", seg_atrasado_valor_correto, "info")
            st.markdown("<br>", unsafe_allow_html=True)
            render_segment("🟢 **Conformes (Em Dia + Valor Correto)**", seg_em_dia_valor_correto, "success")

        st.markdown("---")
        st.subheader("Tickets Recuperados")

        if pagamentos_recuperados.empty:
            st.caption("Nenhum ticket foi recuperado até o momento.")
        else:
            recuperados_exibicao = pagamentos_recuperados.copy()
            recuperados_exibicao['payment_status_extraido'] = recuperados_exibicao['validacao_pagamento'].apply(
                get_payment_status_from_validation
            )

            status_disponiveis = (
                recuperados_exibicao['payment_status_extraido']
                .fillna("Desconhecido")
                .unique()
                .tolist()
            )
            status_disponiveis.sort()
            opcoes_filtro = ["Todos"] + status_disponiveis

            status_selecionado = st.selectbox(
                "Filtrar por status do pagamento",
                options=opcoes_filtro,
                key="filtro_tickets_recuperados"
            )

            if status_selecionado != "Todos":
                recuperados_exibicao = recuperados_exibicao[
                    recuperados_exibicao['payment_status_extraido'] == status_selecionado
                ]

            if recuperados_exibicao.empty:
                st.caption("Nenhum ticket recuperado corresponde ao filtro selecionado.")
            else:
                for idx, record in recuperados_exibicao.iterrows():
                    titulo = f"{record.get('cnpj', 'CNPJ desconhecido')} • {format_date_display(record.get('data'))}"
                    payment_summary_display = _normalize_text_spacing(
                        record.get('payment_summary') or record.get('detalhes') or ""
                    ) or "Informação não disponível."
                    analysis_display = _normalize_text_spacing(
                        record.get('analysis') or payment_summary_display
                    ) or payment_summary_display
                    recommendations_display = _normalize_text_spacing(
                        record.get('recommendations') or ""
                    ) or "Recomendação não disponível."

                    validacao_display = normalize_validation(record.get('validacao_pagamento'))

                    with st.expander(titulo):
                        st.text(f"Análise do pagamento: {payment_summary_display}")
                        st.text(f"Análise comportamental: {analysis_display}")
                        st.text(f"Recomendação de abordagem: {recommendations_display}")

                        if validacao_display:
                            tabela_validacao = pd.DataFrame([validacao_display])
                            st.table(tabela_validacao)
                        else:
                            st.caption("Nenhuma informação de validação disponível.")

                        reopen_key = f"reopen_ticket_{idx}"
                        if st.checkbox("Reabrir Ticket", key=reopen_key):
                            st.session_state['historico_pagamentos'][idx]['status_ticket'] = "Em Aberto"
                            save_history(st.session_state['historico_pagamentos'])
                            trigger_rerun()

# --- Rodapé ---
st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: #666; font-size: 0.9em;'>"
    "Agente Fiscal de Contratos | Powered by CrewAI & Streamlit"
    "</div>",
    unsafe_allow_html=True
)