import os
from crewai import Agent, Crew, Process, Task, LLM
from crewai.project import CrewBase, agent, crew, task

from tools.PineconeBGESearchTool import PineconeBGESearchTool


pinecone_tool = PineconeBGESearchTool()

llm = LLM(
    model="meta-llama/llama-4-maverick-17b-128e-instruct",
    temperature=0.1,
    base_url="https://api.groq.com/openai/v1",
    api_key=os.getenv("GROQ_API_KEY")
)

@CrewBase
class ContractAgentCrew:
    
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
    

    @task
    def contractTask(self) -> Task:
        return Task(
            description="Para o cliente com CNPJ: {cnpj}, descubra:\n"
                        "1. Nome do Cliente\n"
                        "2. Valor Mensal\n"
                        "3. Dia do Pagamento\n"
                        "4. Multa moratória (%)\n"
                        "5. Juros diários (%)\n"
                        "IMPORTANTE: Ao usar a ferramenta de busca, passe o CNPJ '{cnpj}' no argumento 'search_cnpj'.",
            expected_output="JSON válido com: {nome_cliente, cnpj, valor_mensal, dia_pagamento, multa_moratoria, juros_diarios}",
            agent=self.contractAgent()
        )
    

    @crew
    def contractCrew(self) -> Crew:
        return Crew(
            agents=[self.contractAgent()],
            tasks=[self.contractTask()],
            process=Process.sequential,
            verbose=True
        )
