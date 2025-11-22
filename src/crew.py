import os
from typing import Type
from pydantic import BaseModel, Field
from crewai import Agent, Crew, Process, Task, LLM
from crewai.project import CrewBase, agent, crew, task
from crewai.tools import BaseTool
from pinecone import Pinecone
from sentence_transformers import SentenceTransformer

# --- 1. Definindo os argumentos que a ferramenta espera (Input Schema) ---
class SearchInput(BaseModel):
    """Schema de entrada para a ferramenta de busca."""
    search_cnpj: str = Field(..., description="O CNPJ exato da empresa para filtrar a busca no banco de dados.")

# --- 2. Configuração da Ferramenta com Filtro ---
class PineconeBGESearchTool(BaseTool):
    name: str = "Busca Contratual com Filtro"
    description: str = (
        "Utilize esta ferramenta para buscar cláusulas contratuais filtrando por empresa. "
        "É OBRIGATÓRIO fornecer a pergunta e o CNPJ."
    )
    args_schema: Type[BaseModel] = SearchInput

    def _run(self, search_cnpj: str) -> str:
        # 1. Conexão Pinecone
        pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
        index = pc.Index(os.getenv("PINECONE_INDEX_NAME"))

        # 2. Carregar Modelo BGE
        model = SentenceTransformer('BAAI/bge-base-en-v1.5')

        # 3. Gerar Embedding com Instrução
        instruction = "Represent this sentence for searching relevant passages: "
        query_vector = model.encode(instruction + search_cnpj).tolist()

        # 4. Buscar no Pinecone
        try:
            results = index.query(
                vector=query_vector,
                top_k=5,
                include_metadata=True,
                filter={
                    "cnpj": {"$eq": search_cnpj} 
                }
            )
        except Exception as e:
            return f"Erro na busca do Pinecone: {str(e)}. Verifique se o metadado 'cnpj' existe no index."

        # 5. Formatar contexto
        context_text = ""
        if 'matches' in results and results['matches']:
            for match in results['matches']:
                text_chunk = match['metadata'].get('text', 'Conteúdo não disponível')
                # Opcional: verificar se o CNPJ retornado realmente bate (sanity check)
                meta_cnpj = match['metadata'].get('cnpj', 'N/A')
                
                context_text += f"---\n[CNPJ: {meta_cnpj}] Trecho: {text_chunk}\n"
        else:
            context_text = f"Nenhuma informação encontrada para o CNPJ {search_cnpj} com essa pergunta."
            
        print(context_text)
        return context_text

# Instancia a ferramenta
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
