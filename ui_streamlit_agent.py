# ui_streamlit_agent.py — UI para o Agente VR (sem golden)
# - Abas:
#   1) Agente (LLM via OpenAI ou Ollama) — usa agent_vr.build_agent
#   2) Geração direta (fallback, sem LLM) — chama ferramentas do agent_vr
#
# Requisitos: requirements_agent.txt (inclui streamlit)
# Execução:  streamlit run ui_streamlit_agent.py

import json
import os
import streamlit as st

# Importa funções do agente/camada de ferramentas
try:
    from agent_vr import (
        build_agent,
        gerar_vr_mensal_tool,
        validar_conformidade_tool,
    )
except Exception as e:
    st.error(f"Falha ao importar agent_vr: {e}")
    st.stop()

st.set_page_config(page_title="Agente VR Mensal", page_icon="📊", layout="wide")
st.title("📊 Agente VR Mensal")

with st.sidebar:
    st.header("Configuração")
    llm_choice = st.selectbox(
        "LLM a usar no modo Agente",
        options=["auto", "openai", "ollama"],
        index=0,
        help="auto: usa OpenAI se houver OPENAI_API_KEY; senão tenta Ollama local."
    )
    st.caption("Dica: para OpenAI, defina a variável OPENAI_API_KEY. Para Ollama, deixe o serviço rodando e tenha o modelo baixado (`ollama pull llama3:instruct`).")

tab_agente, tab_fallback = st.tabs(["🤖 Agente (LLM)", "🧰 Geração direta (fallback)"])

# --------------------------------------------------------------------------------------
# Aba 1: Agente (LLM)
# --------------------------------------------------------------------------------------
with tab_agente:
    st.subheader("🤖 Conversa única com o agente (ReAct)")

    default_prompt = (
        "Gere o VR de 08/2025 usando a pasta entradas com regra integral "
        "e salve como VR_MENSAL_08_2025.xlsx. "
        "Depois valide a planilha gerada usando o modelo entradas/VR Mensal 05.2025.xlsx."
    )
    prompt = st.text_area(
        "Instrução ao agente",
        value=default_prompt,
        height=120,
        help="Você pode trocar a competência (mês/ano), a pasta de entrada, a regra pós-dia 15 e o nome do arquivo de saída."
    )

    run_agent = st.button("Executar agente", type="primary")
    if run_agent:
        with st.spinner("Executando agente..."):
            try:
                agent = build_agent(llm_choice=llm_choice, verbose=False)
                result = agent.invoke({"input": prompt})
                st.success("Agente finalizou.")
                st.code(result.get("output", ""), language="markdown")
            except Exception as e:
                st.error(f"Erro ao executar o agente: {e}")

# --------------------------------------------------------------------------------------
# Aba 2: Geração direta (sem LLM)
# --------------------------------------------------------------------------------------
with tab_fallback:
    st.subheader("🧰 Geração direta (sem LLM)")

    col1, col2, col3 = st.columns([1,1,1])
    with col1:
        input_dir = st.text_input("Pasta de entrada", value="entradas")
        regra = st.selectbox("Regra pós-dia 15", options=["integral", "proporcional"], index=0)
    with col2:
        mes = st.number_input("Mês", min_value=1, max_value=12, value=8, step=1)
        ano = st.number_input("Ano", min_value=2000, max_value=2100, value=2025, step=1)
    with col3:
        nome_saida = st.text_input("Nome do arquivo de saída", value=f"VR_MENSAL_{mes:02d}_{ano}.xlsx")
        modelo_path = st.text_input("Modelo em /entradas (aba 'VR Mensal')", value="entradas/VR Mensal 05.2025.xlsx")
        tol = st.number_input("Tolerância 80/20", min_value=0.0, max_value=1.0, value=0.01, step=0.01)

    c1, c2 = st.columns([1,1])
    with c1:
        btn_gerar = st.button("Gerar planilha", type="primary")
    with c2:
        btn_validar = st.button("Validar planilha")

    # Execução direta — Geração
    if btn_gerar:
        with st.spinner("Gerando planilha..."):
            try:
                resp = gerar_vr_mensal_tool(
                    input_dir=input_dir,
                    mes=int(mes),
                    ano=int(ano),
                    pos15_regra=regra,
                    nome_saida=nome_saida.strip() or None
                )
                data = json.loads(resp)
                st.success("Planilha gerada com sucesso.")
                st.json(data)
                saida = data.get("saida")
                if saida and os.path.exists(saida):
                    st.download_button(
                        label="⬇️ Baixar planilha gerada",
                        data=open(saida, "rb").read(),
                        file_name=os.path.basename(saida),
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
            except Exception as e:
                st.error(f"Erro ao gerar planilha: {e}")

    # Execução direta — Validação
    if btn_validar:
        with st.spinner("Validando planilha..."):
            try:
                saida = nome_saida.strip() or f"VR_MENSAL_{mes:02d}_{ano}.xlsx"
                if not os.path.exists(saida):
                    st.warning(f"Arquivo '{saida}' não existe ainda. Gere primeiro ou aponte o caminho correto.")
                else:
                    resp = validar_conformidade_tool(
                        caminho_saida=saida,
                        modelo_entradas=modelo_path,
                        validacoes_ref=None,
                        tolerancia=float(tol)
                    )
                    data = json.loads(resp)
                    st.success("Validação concluída.")
                    st.json(data)
                    # oferecer download do arquivo validado (aba 'Validações' atualizada)
                    if os.path.exists(saida):
                        st.download_button(
                            label="⬇️ Baixar planilha (com aba 'Validações' atualizada)",
                            data=open(saida, "rb").read(),
                            file_name=os.path.basename(saida),
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                        )
            except Exception as e:
                st.error(f"Erro na validação: {e}")