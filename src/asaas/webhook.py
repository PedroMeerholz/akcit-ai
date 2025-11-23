import os
from pydantic import BaseModel
from fastapi import FastAPI, Header, HTTPException, Request, status

from model import AsaasPayment, AsaasWebhookPayload

app = FastAPI(title="Webhook Asaas Integration")

# Defina o token que você configurou no painel do Asaas
WEBHOOK_SECRET_TOKEN = os.getenv("ASAAS_API_KEY")


@app.post("/webhook/asaas", status_code=status.HTTP_200_OK)
async def asaas_webhook(
    payload: AsaasWebhookPayload, 
):
    """
    Recebe atualizações de pagamento do Asaas.
    """
    
    # 1. Validação de Segurança
    # O Asaas envia o token no header 'asaas-access-token'
    # if asaas_access_token != WEBHOOK_SECRET_TOKEN:
    #     print(f"Tentativa de acesso não autorizado. Token recebido: {asaas_access_token}")
    #     raise HTTPException(
    #         status_code=status.HTTP_401_UNAUTHORIZED, 
    #         detail="Token de acesso inválido"
    #     )

    # 2. Processamento do Evento
    print(f"Evento Recebido: {payload.event} | ID Pagamento: {payload.payment.id}")

    if payload.event == "PAYMENT_RECEIVED":
        # Lógica para aprovar o pedido no seu banco de dados
        print(f"Pagamento de R$ {payload.payment.value} confirmado!")
        # await atualizar_status_pedido(payload.payment.id, "pago")

    # 3. Resposta
    # O Asaas espera um status 200 OK para saber que você recebeu
    return {"status": "received"}
