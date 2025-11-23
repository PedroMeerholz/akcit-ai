from typing import Type
from datetime import datetime
from pydantic import BaseModel
from crewai.tools import BaseTool


class PaymentValidationInput(BaseModel):
    contract_info: dict
    payment_info: dict


class PaymentValidatorTool(BaseTool):
    name: str = "Payment Validator Tool"
    description: str = (
        "Use esta ferramenta para validar pagamentos com base nas informações contratuais. "
        "Forneça os detalhes do contrato e do pagamento para validação."
    )
    args_schema: Type[BaseModel] = PaymentValidationInput


    def _run(self, contract_info: dict, payment_info: dict) -> str:
        correct_payment_day = int(contract_info.get("dia_pagamento"))
        payment_day = payment_info.get("data_pagamento")
        payment_day = datetime.strptime(payment_day, "%d/%m/%Y").date()
        payment_day = int(payment_day.day)

        paid_value = payment_info.get("valor_pago")
        contract_value = contract_info.get("valor_mensal")
        contract_value = contract_value.replace("R$ ", "").replace(".", "").replace(",", ".")
        contract_value = float(contract_value)

        # Validar data de pagamento com dia de pagamento contratual
        if correct_payment_day < payment_day:
            late_days = payment_day - correct_payment_day
            fine = contract_info.get("multa_moratoria")
            interest = contract_info.get("juros_diarios")
            interest = interest / 100

            total_fine = contract_value * (1 + interest) ** late_days - contract_value
            total_amount_due = contract_value + total_fine + (fine * late_days)
            total_amount_due = round(total_amount_due, 2)

            amount_diff = total_amount_due - paid_value
            amount_diff = round(amount_diff, 2)

            # Se atrasado, validar valor
            if amount_diff > 0:
                # Se valor incorreto, retornar "Pagamento atrasado e valor incorreto. Valor correto: X."
                return {
                    "payment_status": "atrasado_valor_incorreto",
                    "paid_value": f"{paid_value}",
                    "expected_value": f"{total_amount_due}",
                    "amount_diff": f"{amount_diff}"
                }
            else:
                # Se valor correto, retornar "Pagamento atrasado, mas valor correto."
                return {
                    "payment_status": "atrasado_valor_correto",
                    "paid_value": f"{paid_value}",
                    "expected_value": f"{total_amount_due}",
                    "amount_diff": f"{amount_diff}"
                }

        else:
            # Se no prazo, validar valor
            if paid_value != contract_value:
                # Se valor incorreto, retornar "Pagamento no prazo, mas valor incorreto. Valor correto: X."
                return {
                    "payment_status": "no_prazo_valor_incorreto",
                    "paid_value": f"{paid_value}",
                    "expected_value": f"{total_amount_due}",
                    "amount_diff": f"{amount_diff}"
                }
            else:
                # Se valor correto, retornar "Pagamento realizado corretamente."
                return {
                    "payment_status": "no_prazo_valor_correto",
                    "paid_value": f"{paid_value}",
                    "expected_value": f"{total_amount_due}",
                    "amount_diff": f"{amount_diff}"
                }
