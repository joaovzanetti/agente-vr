# 🤖 Desafio 4 – Agente VR Mensal (LangChain + Streamlit)

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)  
[![LangChain](https://img.shields.io/badge/LangChain-Framework-orange)](https://www.langchain.com/)  
[![Streamlit](https://img.shields.io/badge/Streamlit-UI-red)](https://streamlit.io/)  

Este repositório implementa um **Agente Autônomo em LangChain** para processar planilhas de **Vale Refeição (VR)**.  
O agente aplica as regras de negócio do desafio, gera a planilha final e realiza **validações automáticas**.

---

## 🎯 Objetivo do desafio
- Processar as planilhas de **entrada**: `ATIVOS`, `FERIAS`/`FÉRIAS` e `DESLIGADOS`.  
- Aplicar a regra de custeio **80/20**:
  - **80%** empresa  
  - **20%** colaborador  
- Gerar a planilha final no modelo:  
  ```
  VR_MENSAL_MM_YYYY.xlsx
  ```
- Incluir a aba **Validações**, verificando:
  - Estrutura de colunas (comparada com `entradas/VR Mensal 05.2025.xlsx`)  
  - Correção da regra 80/20 (linha a linha e somatório)  
  - Presença de valores negativos  

---

## 📂 Estrutura do projeto
```
desafio_vr_agente/
├── agent_vr.py              # Agente LangChain (ReAct + Ferramentas)
├── steps.py                 # Pipeline de processamento (ETL das planilhas)
├── utils.py                 # Funções auxiliares
├── ui_streamlit_agent.py    # Interface interativa em Streamlit
├── requirements_agent.txt   # Dependências
├── README.md                # Este arquivo
├── entradas/                # Planilhas de entrada + modelo
│   ├── ATIVOS.xlsx
│   ├── FERIAS.xlsx
│   ├── DESLIGADOS.xlsx
│   └── VR Mensal 05.2025.xlsx
└── VR_MENSAL_08_2025.xlsx   # Exemplo de saída gerada
```

---

## ⚙️ Instalação
### Pré-requisitos
- Python **3.10+**  
- **pip** e **venv** configurados  
- (Opcional) [Ollama](https://ollama.com/) para rodar LLMs locais  
- (Opcional) **OPENAI_API_KEY** para rodar com OpenAI  

### Setup
```bash
# criar ambiente virtual
python -m venv .venv
# ativar (Windows)
.\.venv\Scripts\activate
# ativar (Linux/Mac)
source .venv/bin/activate

# instalar dependências
pip install -r requirements_agent.txt
```

---

## 🚀 Modos de execução

### 🔹 1) Interface Web (Streamlit)
```bash
streamlit run ui_streamlit_agent.py
```
Abrirá em: [http://localhost:8501](http://localhost:8501)

- **Agente (LLM)** → roda via OpenAI ou Ollama  
- **Fallback (direto em Python)** → roda sem LLM, útil para ambientes sem chave/sem Ollama  

---

### 🔹 2) Linha de Comando com OpenAI
```powershell
setx OPENAI_API_KEY "sk-xxxx"
.\.venv\Scripts\activate
python agent_vr.py --llm openai --ask "Gere o VR de 08/2025 usando entradas/ e valide com o modelo entradas/VR Mensal 05.2025.xlsx"
```

---

### 🔹 3) Linha de Comando com Ollama
Baixe um modelo:
```bash
ollama pull qwen2:0.5b
```

Execute:
```powershell
$env:OLLAMA_MODEL = "qwen2:0.5b"
python agent_vr.py --llm ollama --ask "Liste as colunas obrigatórias da aba ATIVOS"
```

---

## 🔄 Modelos Ollama recomendados

| Modelo           | RAM mínima | Observações |
|------------------|------------|-------------|
| `qwen2:0.5b`     | 3–4 GiB    | Muito leve, roda em PCs modestos. Pode ser lento e alucinar. |
| `phi3:mini`      | 6 GiB+     | Melhor equilíbrio entre leveza e qualidade. |
| `tinyllama:1.1b` | 4–5 GiB    | Alternativa leve, desempenho similar ao qwen2. |
| `mistral:7b`     | 8 GiB+     | Robusto, boa qualidade. |
| `llama3:8b`      | 10–12 GiB+ | Alta qualidade, exige máquina forte. |

---

## 📄 Saída gerada

- `VR_MENSAL_MM_YYYY.xlsx`  
- Abas:
  - **VR Mensal** → valores finais (TOTAL, Custo empresa, Desconto profissional)  
  - **ATIVOS**, **FERIAS**, **DESLIGADOS**  
  - **Validações** → com:
    - colunas faltantes/extras  
    - regra 80/20  
    - negativos detectados  

---

## 🧯 Troubleshooting
- **`OPENAI_API_KEY` não definida** → definir variável e reabrir terminal  
- **Ollama “connection refused”** → iniciar `ollama serve`  
- **Streamlit finaliza sem agir** → limitação de modelo pequeno, use prompts curtos ou modelos mais potentes do Ollama.  
- **Erro de arquivo não encontrado** → confirme que o Excel está na **raiz do projeto**  

---

## 🔐 Privacidade
- Nenhum dado sensível é enviado externamente em **Fallback** ou **Ollama**.  
- Em **OpenAI**, apenas o prompt é enviado; as planilhas são processadas localmente.
