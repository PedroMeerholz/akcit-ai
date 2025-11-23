import os
from crewai import Agent, Crew, Process, Task, LLM
from crewai.project import CrewBase, agent, crew, task
from pydantic import BaseModel, Field

from .tools.PaymentValidatorTool import PaymentValidatorTool
from .tools.PineconeBGESearchTool import PineconeBGESearchTool


pinecone_tool = PineconeBGESearchTool()
payment_validator_tool = PaymentValidatorTool()

llm = LLM(
    model=os.getenv("GROQ_MODEL"),
    temperature=0.1,
    base_url="https://api.groq.com/openai/v1",
    api_key=os.getenv("GROQ_API_KEY")
)


class ContractResultSchema(BaseModel):
    nome_cliente: str = Field(..., description="Nome do cliente associado ao contrato")
    cnpj: str = Field(..., description="CNPJ do cliente")
    valor_mensal: str = Field(..., description="Valor mensal do contrato")
    dia_pagamento: str = Field(..., description="Dia do mês em que o pagamento deve ser realizado")
    multa_moratoria: float = Field(..., description="Percentual de multa moratória em caso de atraso")
    juros_diarios: float = Field(..., description="Percentual de juros diários em caso de atraso")


class PaymentValidationResultSchema(BaseModel):
    customer: str = Field(..., description="Nome do cliente associado ao pagamento")
    payment_status: str = Field(..., description="Status do pagamento (ex: atrasado_valor_incorreto, ok, etc)")
    paid_value: str = Field(..., description="Valor efetivamente pago")
    expected_value: str = Field(..., description="Valor que deveria ter sido pago")
    amount_diff: str = Field(..., description="Diferença entre o pago e o esperado")


class PaymentStatusSchema(BaseModel):
    summary: str = Field(..., description="Resumo do status do pagamento")
    payment_validation: PaymentValidationResultSchema = Field(..., description="Detalhes da validação do pagamento")


@CrewBase
class AgentCrew:
    
    @agent
    def contractAgent(self) -> Agent:
        return Agent(
            role="Especialista Jurídico",
            goal="Analisar contratos específicos filtrando pelo CNPJ correto.",
            backstory="Você é um analista meticuloso. Para responder perguntas sobre um contrato, "
                      "você SEMPRE usa a ferramenta de busca passando a pergunta E o CNPJ do cliente "
                      "para garantir que não está lendo o contrato da empresa errada.",
            verbose=True,
            tools=[pinecone_tool],
            llm=llm
        )
    

    @agent
    def paymentAgent(self) -> Agent:
        return Agent(
            role="Especialista Financeiro",
            goal="Analisar se os pagamentos dos contratos foram realizados corretamente",
            backstory="Você é um analista meticuloso. Para analisar pagamentos, "
                      "você SEMPRE usa a ferramenta de validação passando as informações do contrato "
                      "e as informações do pagamento.",
            verbose=True,
            tools=[payment_validator_tool],
            llm=llm
        )
    

    @agent
    def paymentStatusAgent(self) -> Agent:
        return Agent(
            role="Especialista Financeiro",
            goal="Analisar se os pagamentos dos contratos foram realizados corretamente",
            backstory="Você é um analista meticuloso. "
                      "Analise o resultado da validação do pagamento e retorne um resumo claro e direto do status do pagamento. "
                      "Neste resumo infome o cliente responsável pelo pagamento, o status do pagamento, o valor pago, o valor esperado e a diferença entre os valores.",
            verbose=True,
            llm=llm
        )
    

    @task
    def contractTask(self) -> Task:
        return Task(
            description="Para o cliente com CNPJ: {cnpj}, descubra os dados do contrato.\n"
                        "IMPORTANTE SOBRE O USO DA FERRAMENTA:\n"
                        "1. Ao chamar a ferramenta de busca, o argumento 'search_cnpj' DEVE SER UMA STRING.\n"
                        "2. MANTENHA ESTRITAMENTE A PONTUAÇÃO do CNPJ (pontos, barra e traço).\n"
                        "3. Exemplo correto: '12.345.678/0001-90'.\n"
                        "4. Exemplo ERRADO: '12345678000190'.\n"
                        "5. Se a busca retornar vazio, NÃO TENTE REMOVER A PONTUAÇÃO. Pare e reporte o erro.",
            expected_output="JSON válido com: {nome_cliente, cnpj, valor_mensal, dia_pagamento, multa_moratoria, juros_diarios}",
            output_pydantic=ContractResultSchema,
            agent=self.contractAgent()
        )
    

    @task
    def paymentTask(self) -> Task:
        return Task(
            description="Siga os passos estritos:\n"
                        "1. Recupere as informações do contrato (contexto).\n"
                        "2. Analise os dados do pagamento: {payment_info}.\n"
                        "3. Use a ferramenta 'PaymentValidatorTool'.\n"
                        "4. Preencha o schema de saída com os dados retornados.\n\n"
                        "REGRAS CRÍTICAS DE FORMATAÇÃO:\n"
                        "- NÃO gere um dicionário Python (não use aspas simples ').\n"
                        "- GERE APENAS JSON VÁLIDO (use aspas duplas \").\n"
                        "- Se a ferramenta retornar aspas simples, VOCÊ DEVE converter para aspas duplas.",
            expected_output="Um JSON válido conforme o schema PaymentValidationResultSchema",
            output_pydantic=PaymentValidationResultSchema,
            agent=self.paymentAgent(),
            context=[self.contractTask()]
        )
    

    @task
    def paymentStatusTask(self) -> Task:
        return Task(
            description="Siga os passos estritos:\n"
                        "1. Recupere as informações da validação do pagamento (contexto).\n"
                        "2. Forneça um resumo claro e direto do status do pagamento"
                        "REGRAS CRÍTICAS DE FORMATAÇÃO:\n"
                        "- NÃO gere um dicionário Python (não use aspas simples ').\n"
                        "- GERE APENAS JSON VÁLIDO (use aspas duplas \").\n"
                        "- Se a ferramenta retornar aspas simples, VOCÊ DEVE converter para aspas duplas.",
            expected_output="Um JSON válido conforme o schema PaymentStatusSchema",
            output_pydantic=PaymentStatusSchema,
            agent=self.paymentStatusAgent(),
            context=[self.paymentTask()]
        )
    

    @crew
    def contractCrew(self) -> Crew:
        return Crew(
            agents=[self.contractAgent(), self.paymentAgent()],
            tasks=[self.contractTask(), self.paymentTask(), self.paymentStatusTask()],
            process=Process.sequential,
            verbose=True
        )
