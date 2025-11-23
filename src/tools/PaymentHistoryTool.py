import json
from pathlib import Path
from pydantic import BaseModel
from crewai.tools import BaseTool
from typing import Any, List, Type


class PaymentHistoryInput(BaseModel):
    cnpj: str


class PaymentHistoryOutput(BaseModel):
    cnpj: str
    payment_history: List[dict[str, Any]]


class PaymentHistoryTool(BaseTool):
    name: str = "Payment History Tool"
    description: str = (
        "Use esta ferramenta para consultar o histórico de pagamentos de um cliente específico. "
        "Forneça o CNPJ do cliente para obter o histórico detalhado de pagamentos."
    )
    args_schema: Type[BaseModel] = PaymentHistoryInput

    def _run(self, cnpj: str) -> PaymentHistoryOutput:
        normalized_cnpj = ''.join(filter(str.isdigit, cnpj))

        try:
            crm_path = Path("crm.json")
            data = json.loads(crm_path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            return PaymentHistoryOutput(
                cnpj=cnpj,
                payment_history=[],
            )
        except json.JSONDecodeError as exc:
            return PaymentHistoryOutput(
                cnpj=cnpj,
                payment_history=[],
            )

        if not isinstance(data, list):
            raise ValueError("Estrutura de dados inválida em crm.json.")

        for cliente in data:
            cliente_cnpj = ''.join(filter(str.isdigit, cliente.get("cnpj_cliente", "")))
            if cliente_cnpj == normalized_cnpj:
                historico = cliente.get("historico_pagamento", [])
                ultimos_pagamentos = historico[-6:]

                return PaymentHistoryOutput(
                    cnpj=cliente.get("cnpj_cliente", cnpj),
                    payment_history=list(ultimos_pagamentos),
                )

        return PaymentHistoryOutput(
            cnpj=cnpj,
            payment_history=[],
        )
