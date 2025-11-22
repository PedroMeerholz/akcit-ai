import os
from typing import Type
from pinecone import Pinecone
from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from sentence_transformers import SentenceTransformer


class SearchInput(BaseModel):
    """Schema de entrada para a ferramenta de busca."""
    search_cnpj: str = Field(..., description="O CNPJ exato da empresa para filtrar a busca no banco de dados.")
    

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