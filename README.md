# Desafio 4 — **Agente VR Mensal** (LangChain + UI)

Este repositório entrega um **agente em LangChain** (com UI em Streamlit) que:
- processa as planilhas de **entrada** (ATIVOS, FÉRIAS/FERIAS, DESLIGADOS),
- aplica as **regras de elegibilidade** e o rateio **80/20** (80% empresa / 20% profissional),
- gera a planilha final `VR_MENSAL_MM_YYYY.xlsx`,
- cria a aba **Validações** (estrutura, 80/20, negativos).

> ✅ O agente foi projetado para rodar em três modos:  
> 1) **Streamlit (UI)** — com **OpenAI**, **Ollama** (local) ou **Fallback** (sem LLM)  
> 2) **CLI com OpenAI** (sem UI)  
> 3) **CLI com Ollama** (sem UI)

---

## 📂 Estrutura esperada

```
desafio_vr_agente/
├── agent_vr.py                  # Agente LangChain (ferramentas + orquestração)
├── steps.py                     # Pipeline de processamento (carregar, montar, exportar)
├── utils.py                     # Funções auxiliares (normalização etc.)
├── ui_streamlit_agent.py        # Interface web (Streamlit)
├── requirements_agent.txt       # Dependências
├── README.md                    # ESTE arquivo
├── entradas/                    # Insumos e modelo
│   ├── ATIVOS.xlsx
│   ├── FERIAS.xlsx     (ou FÉRIAS.xlsx)
│   ├── DESLIGADOS.xlsx
│   └── VR Mensal 05.2025.xlsx  # Modelo (aba de referência)
└── (exemplo) VR_MENSAL_08_2025.xlsx
```

---

## 🧰 Requisitos

- Python 3.10+  
- Windows, macOS ou Linux  
- (Opcional) Conta e **OPENAI_API_KEY** válida **ou** **Ollama** instalado para rodar LLM local  
- `pip install -r requirements_agent.txt`

### Instalação rápida (Windows / PowerShell)
```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements_agent.txt
```

### Instalação rápida (macOS/Linux)
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements_agent.txt
```

---

## 🚀 Modos de execução

### 1) **Streamlit (UI)**

Inicie a interface:
```powershell
.\.venv\Scripts\activate
streamlit run ui_streamlit_agent.py
```
A UI abre em `http://localhost:8501/` com **duas abas**:

- **🤖 Agente (LLM)** — usa LangChain + LLM (OpenAI ou Ollama)  
  Sidebar → selecione o provedor: **openai**, **ollama** ou **auto**  
  - **OpenAI**: defina a chave antes:
    ```powershell
    setx OPENAI_API_KEY "sk-xxxxx"
    # feche e reabra o PowerShell
    ```
  - **Ollama**: tenha o serviço ativo e um modelo disponível  
    ```powershell
    ollama pull qwen2:0.5b     # modelo leve (recomendado para máquinas menos potentes)
    $env:OLLAMA_MODEL = "qwen2:0.5b"
    ```

## 🔄 Modelos Ollama recomendados

O agente suporta execução com **LLMs locais via Ollama**.  
Você pode escolher o modelo conforme o hardware disponível:

| Modelo           | Tamanho aprox. | RAM mínima recomendada | Observações |
|------------------|----------------|-------------------------|-------------|
| `qwen2:0.5b`     | ~0.5B params   | 3–4 GiB                | Muito leve, roda em PCs modestos. Pode ser lento e “alucinar” em prompts longos. |
| `phi3:mini`      | ~3.8B params   | 6 GiB+                 | Equilíbrio entre leveza e qualidade. Recomendado se não houver OpenAI. |
| `tinyllama:1.1b` | ~1.1B params   | 4–5 GiB                | Alternativa leve, desempenho similar ao qwen2. |
| `mistral:7b`     | ~7B params     | 8 GiB+                 | Mais robusto, resultados melhores. Requer máquina mais forte. |
| `llama3:8b`      | ~8B params     | 10–12 GiB+             | Alta qualidade, próximo do OpenAI em alguns casos. Necessita bastante memória. |

### Comandos de instalação
```bash
# Exemplo de pull para instalar modelos
ollama pull qwen2:0.5b
ollama pull phi3:mini
ollama pull tinyllama:1.1b
ollama pull mistral:7b
ollama pull llama3:8b

Após o download, selecione o modelo a ser usado definindo a variável de ambiente:

$env:OLLAMA_MODEL = "qwen2:0.5b"



  **Exemplo de prompt (curto, recomendado):**
  ```
  Gere o VR de 08/2025 usando a pasta entradas com regra integral e salve como VR_MENSAL_08_2025.xlsx. Depois valide a planilha gerada usando o modelo entradas/VR Mensal 05.2025.xlsx.
  ```

  > ⚠️ **Modelos muito pequenos (ex.: qwen2:0.5b)** podem ser **lentos** e às vezes **não seguir o ReAct** em tarefas longas.  
  > Se notar que “finaliza” sem executar ferramentas, rode em **duas etapas** (Gerar → Validar).

- **🧰 Geração direta (fallback)** — roda **sem LLM**, apenas Python  
  Preencha: pasta de entradas, mês/ano, nome do arquivo e **modelo** → **Gerar** → **Validar**.  
  Útil para ambientes sem chave ou sem Ollama.

---

### 2) **CLI com OpenAI** (sem UI)
```powershell
setx OPENAI_API_KEY "sk-xxxxx"
# feche e reabra o PowerShell
.\.venv\Scripts\activate
python .\agent_vr.py --llm openai --ask "Gere o VR de 08/2025 usando a pasta entradas com regra integral e valide com o modelo entradas/VR Mensal 05.2025.xlsx."
```

### 3) **CLI com Ollama** (sem UI)
```powershell
ollama pull qwen2:0.5b
$env:OLLAMA_MODEL = "qwen2:0.5b"
.\.venv\Scripts\activate
python .\agent_vr.py --llm ollama --ask "Gere o VR de 08/2025 usando a pasta entradas com regra integral e valide com o modelo entradas/VR Mensal 05.2025.xlsx."
```

> 💡 Dica de testes “rápidos” com modelos pequenos (seguem ferramentas com 1 passo):
```powershell
python .\agent_vr.py --llm ollama --ask "Liste as colunas obrigatórias da aba ATIVOS"
python .\agent_vr.py --llm ollama --ask "Mostre a aba Validações do arquivo VR_MENSAL_08_2025.xlsx"
```

---

## 📄 Saída gerada

- **Arquivo**: `VR_MENSAL_MM_YYYY.xlsx`  
- **Abas**:
  - **VR Mensal** — com `DIAS`, `VALOR_DIARIO_VR`, `TOTAL`, `Custo empresa` (= 0.8*TOTAL), `Desconto profissional` (= 0.2*TOTAL)  
  - **ATIVOS**, **FERIAS**, **DESLIGADOS** — bases auxiliares (quando disponíveis)  
  - **Validações** — checks automáticos:
    - **Colunas faltantes/extras** (comparação com o **modelo** `entradas/VR Mensal 05.2025.xlsx`)
    - **Regra 80/20** por linha e no somatório
    - **Valores negativos** (TOTAL, Custo empresa, Desconto profissional)
    - Detecção opcional de “validações de referência”

> **Regra 80/20**: é **aplicada e reforçada** automaticamente na aba “VR Mensal”.

---

## ✅ Como validar manualmente (dupla-checagem)

1) Abra `VR_MENSAL_MM_YYYY.xlsx` → **VR Mensal**  
   - confira se `Custo empresa ≈ TOTAL * 0,8`  
   - `Desconto profissional ≈ TOTAL * 0,2`  

2) Abra **Validações**  
   - “80/20: OK”  
   - Colunas faltantes/extras → se houver, são alertas informativos  
   - Valores negativos → se apontar, geralmente vêm dos insumos (ex.: férias acima do padrão)

---

## 🧪 Notas para o avaliador

- O agente foi implementado com **LangChain (ReAct)** e ferramentas:
  - `gerar_vr_mensal` — processa insumos, aplica regras, exporta Excel  
  - `validar_conformidade` — compara estrutura com o **modelo** (aba “VR Mensal”), verifica 80/20, negativos, e preenche a aba **Validações**  
  - `ler_validacoes` — retorna o conteúdo da aba **Validações** em JSON  
  - `listar_colunas_obrigatorias` — lista o schema esperado por aba  

- O modo **Fallback (UI)** cumpre integralmente o objetivo **sem LLM** (útil caso não haja chave ou hardware).

- **OpenAI** é o caminho **recomendado** para o agente (rápido e estável).  
  - Pré-checagem (opcional):
    ```bash
    python - << 'PY'
from langchain_openai import ChatOpenAI
print(ChatOpenAI(model="gpt-4o-mini", temperature=0).invoke("ping").content)
PY
    ```
- **Ollama** funciona, mas:
  - modelos grandes exigem RAM (ex.: `llama3:8b` ≈ 5–6 GiB livres),
  - modelos **muito pequenos** (ex.: `qwen2:0.5b`) podem **alucinar** em prompts longos; use prompts **curtos**.

---

## 🧯 Troubleshooting

- **`OPENAI_API_KEY` não definida**  
  → definir variável de ambiente e reabrir o terminal.

- **Ollama 404 / “model not found”**  
  → `ollama pull <modelo>` e `ollama list` para confirmar o nome.  
  → defina `OLLAMA_MODEL`, ex.: `qwen2:0.5b`.

- **Ollama “connection refused” (WinError 10061)**  
  → inicie o serviço: `ollama serve`  
  → se a porta 11434 estiver ocupada, mude:  
    ```powershell
    $env:OLLAMA_HOST = "127.0.0.1:11435"
    ollama serve -p 11435
    ```

- **Streamlit abre mas o agente “finaliza” sem agir**  
  → é limitação do modelo tiny. Reenvie com prompts curtos **ou** use a ferramenta `pipeline_gerar_e_validar`.

- **Erro de arquivo não encontrado**  
  → confirme que `VR_MENSAL_MM_YYYY.xlsx` está na **raiz do projeto** ou passe o caminho completo.  
  → nomes com espaços/parênteses precisam estar exatos (ex.: `"VR_MENSAL_08_2025 (1).xlsx"`).

---

## 🔐 Observações de privacidade

- O agente não solicita nem exibe PII (CPF, etc.).  
- Arquivos Excel não são enviados a serviços externos no **Fallback** ou com **Ollama**.  
- No modo **OpenAI**, apenas o **texto dos prompts** e mensagens do agente são enviados à API — as planilhas são processadas **localmente** pelo Python.

---

## 🧾 Licença & Créditos

Projeto desenvolvido para o **Desafio 4 – Agente VR Mensal**.  
Tecnologias: **Python, LangChain, Streamlit, Pandas, OpenPyXL**.  
LLM: **OpenAI** (opcional) ou **Ollama** (local).

---

Qualquer dúvida de execução, basta rodar o **Fallback** na UI para garantir a geração/validação local, e/ou usar **OpenAI** para testar o fluxo completo de agente com alto desempenho.
