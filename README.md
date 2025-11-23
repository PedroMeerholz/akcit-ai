# Verif.ai – Fiscalização Inteligente de Pagamentos

## Visão Geral
- Plataforma de monitoramento que cruza contratos, pagamentos recebidos e comportamento histórico para destacar riscos de inadimplência ou divergência de valores.
- A interface principal é um dashboard Streamlit (`app.py`) que oferece um formulário de coleta de pagamentos e uma visão analítica alimentada em tempo real.
- A orquestração analítica roda com CrewAI (`src/crew.py`), acionando ferramentas próprias para buscar cláusulas no Pinecone, validar valores pagos e resgatar histórico recente do cliente.
- Cada parecer gerado é normalizado e persistido em `historico_pagamentos.json`, arquivo que abastece os componentes do dashboard.
- Dados contratuais e histórico fictício de clientes residem em `crm.json`, servindo como base para testes locais.

## Componentes Principais
- `app.py`: Streamlit app que coleta o pagamento, dispara a Crew, normaliza o resultado e exibe KPIs, listas de tickets e controles de recuperação.
- `src/crew.py`: definição dos agentes e tarefas da CrewAI (jurídico, financeiro e comportamento), com schemas Pydantic para padronizar as saídas.
- `src/tools/PineconeBGESearchTool.py`: ferramenta que busca cláusulas contratuais filtrando por CNPJ em um índice Pinecone BGE.
- `src/tools/PaymentValidatorTool.py`: rotina de validação financeira que compara pagamento informado com regras de atraso, multa e juros configuradas no contrato.
- `src/tools/PaymentHistoryTool.py`: acesso ao histórico local de pagamentos (`crm.json`) usado para enriquecer a análise comportamental.
- `knowledge/document_generator.py`: script opcional para gerar PDFs de contratos fictícios a partir de um template e preencher o conhecimento base.

## Requisitos
- Python 3.12+ (recomendado)
- pip 23+
- Streamlit, CrewAI, Sentence Transformers e Pinecone (instalados via `requirements-linux.txt`)
- Chaves das APIs Groq (`GROQ_API_KEY`, `GROQ_MODEL`) e Pinecone (`PINECONE_API_KEY`, `PINECONE_INDEX_NAME`)

## Configuração Inicial
1. **Clonar o repositório**
	```bash
	git clone https://github.com/PedroMeerholz/akcit-ai.git
	cd akcit-ai
	```
2. **Criar e ativar o ambiente virtual**
	```bash
	python3 -m venv .venv
	source .venv/bin/activate  # Windows: .venv\Scripts\activate
	```
3. **Instalar dependências**
	- **Linux**
		```bash
		pip install --upgrade pip
		pip install -r requirements-linux.txt
		```
	- **Windows ou macOS**
		```bash
		pip install --upgrade pip
		pip install -r requirements.txt
		```
4. **Configurar variáveis de ambiente**
	```bash
	cp .env.example .env
	# Preencha GROQ_API_KEY, GROQ_MODEL, PINECONE_API_KEY e PINECONE_INDEX_NAME
	```
5. **Popular dados de teste (opcional)**
	- Ajuste `crm.json` com seus clientes ou mantenha o seed fornecido para explorar o fluxo completo.
	- Gere contratos PDF fictícios com `python knowledge/document_generator.py` caso queira ampliar a base documental.

## Executando o Projeto
- Suba o dashboard com:
	```bash
	streamlit run app.py
	```
- O Streamlit carrega `historico_pagamentos.json` na inicialização e escreve novas análises no mesmo arquivo. Alterações feitas na interface (ex.: fechar ticket) persistem imediatamente.

## Fluxo de Execução End-to-End
1. **Coleta do pagamento (aba "Nova Análise")**
	- O operador informa CNPJ, valor pago e data de pagamento.
	- O app normaliza as entradas e chama `run_contract_agent` para iniciar a Crew.
2. **Orquestração da Crew**
	- `contractTask` obtém cláusulas relevantes no Pinecone usando o CNPJ como filtro rígido.
	- `paymentTask` valida valor e atraso com `PaymentValidatorTool`, retornando o schema `PaymentValidationResultSchema`.
	- `paymentStatusTask` gera um resumo financeiro estruturado.
	- `customerBehaviorTask` consulta o histórico em `crm.json` via `PaymentHistoryTool` e emite recomendações.
3. **Normalização e persistência**
	- `app.py` alinha campos textuais, converte validações em dicionários serializáveis e adiciona o resultado a `historico_pagamentos.json`.
	- Cada item recebe metadados (status do ticket, resumo, recomendações) para alimentar métricas e listas detalhadas.
4. **Visualização (aba "Dashboard de Acompanhamento")**
	- KPIs destacam quantidades por status e valores estimados de perda/recuperação.
	- Expansores apresentam o parecer completo e permitem marcar tickets como recuperados, atualizando o arquivo imediatamente.

## Dados e Integrações
- **`crm.json`**: matriz local simulando CRM + histórico de pagamentos; adapte para refletir seus clientes reais.
- **`historico_pagamentos.json`**: histórico consolidado das análises realizadas via interface; removê-lo zera o dashboard.
- **Pinecone**: exige índice previamente criado com embeddings BGE e metadado `cnpj`; configure o nome do índice em `.env`.
- **Groq**: o modelo selecionado em `GROQ_MODEL` deve ser compatível com a API OpenAI-like exposta pela Groq.

## Boas Práticas & Próximos Passos
- Versionar ou mover `historico_pagamentos.json` para um armazenamento transacional quando o volume crescer.
- Instrumentar logs do fluxo CrewAI diretamente no Streamlit para auditar decisões e monitorar custo de tokens.
- Automatizar o provisionamento das chaves de ambiente e do índice Pinecone (Terraform, scripts de bootstrap) para facilitar novas implantações.

## Passos Futuros
- **Integração com o gateway de pagamentos real**: mapear eventos do provedor utilizado pelo cliente (ex.: webhook de confirmação de pagamento, conciliação diária), criar um adaptador que converta esses payloads para o formato consumido por `run_contract_agent` e definir políticas de autenticação/retentativas. A partir daí, cada evento dispara automaticamente a Crew, eliminando a etapa manual do formulário.
- **Adoção do histórico corporativo**: substituir `crm.json` por um conector oficial (API, base relacional ou data lake) que recupere o histórico do cliente em tempo real. Isso inclui normalizar chaves (cnpj, ids internos), implementar cache ou paginação quando necessário e adicionar camadas de fallback para manter o dashboard operante em caso de indisponibilidade do sistema corporativo.

---

Com essa estrutura, basta alimentar o formulário para gerar pareceres automatizados e acompanhar as anomalias contratuais em tempo real.