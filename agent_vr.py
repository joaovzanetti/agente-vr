# agent_vr.py — Agente LangChain para VR Mensal (OpenAI OU Ollama)
# -----------------------------------------------------------------------------
# Exemplos:
#   # UI (se você tiver o Streamlit):
#   streamlit run ui_streamlit_agent.py
#
#   # CLI com OpenAI:
#   setx OPENAI_API_KEY "sk-xxxxx"  (feche e reabra o PowerShell)
#   python agent_vr.py --llm openai --ask "Gere o VR de 08/2025 usando a pasta entradas com regra integral e valide com o modelo entradas/VR Mensal 05.2025.xlsx."
#
#   # CLI com Ollama (modelo leve):
#   ollama pull qwen2:0.5b
#   $env:OLLAMA_MODEL = "qwen2:0.5b"
#   python agent_vr.py --llm ollama --ask "Liste as colunas obrigatórias da aba ATIVOS"
# -----------------------------------------------------------------------------

from __future__ import annotations

import os
import sys
import json
import glob
import argparse
from datetime import date
from typing import Optional, Dict, Any, List

import pandas as pd

# LangChain
from pydantic import BaseModel, Field
from langchain.tools import StructuredTool
from langchain.agents import AgentExecutor, create_react_agent
from langchain_core.prompts import PromptTemplate

# Garante que a raiz (onde está steps.py) está no path
sys.path.append(os.path.dirname(__file__))

# ========================= Integração com o pipeline (raiz) ====================
def _import_pipeline():
    """Carrega steps.py por caminho absoluto."""
    import importlib.util
    import pathlib

    here = pathlib.Path(__file__).parent
    steps_path = here / "steps.py"
    if not steps_path.exists():
        raise ImportError("Não encontrei 'steps.py' na raiz do projeto.")

    spec = importlib.util.spec_from_file_location("steps", steps_path)
    steps_mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(steps_mod)

    Contexto_cls = getattr(steps_mod, "Contexto", None)

    for fn in ("carregar_bases", "montar_base_elegiveis", "exportar_planilha"):
        if not hasattr(steps_mod, fn):
            raise ImportError(f"'steps.py' não possui a função obrigatória: {fn}()")

    return steps_mod, Contexto_cls


def _ctx_fallback_for(competencia: date, pos15_regra: str):
    """Cria um contexto fallback com .dict() garantido."""
    comp = pd.Timestamp(competencia.year, competencia.month, 1)
    if competencia.month == 12:
        fim = pd.Timestamp(competencia.year + 1, 1, 1) - pd.Timedelta(days=1)
    else:
        fim = pd.Timestamp(competencia.year, competencia.month + 1, 1) - pd.Timedelta(days=1)
    ini = pd.Timestamp(competencia.year, competencia.month, 1)

    class _CtxFallback:
        def __init__(self, i, f, c, regra):
            self.periodo_ini = i
            self.periodo_fim = f
            self.competencia = c
            self.pos15_regra = regra
        def dict(self):
            return {
                "periodo_ini": self.periodo_ini,
                "periodo_fim": self.periodo_fim,
                "competencia": self.competencia,
                "pos15_regra": self.pos15_regra,
            }
    return _CtxFallback(ini, fim, comp, pos15_regra)


def _make_contexto(Contexto_cls, competencia: date, pos15_regra: str):
    """Tenta usar Contexto do steps.py; se falhar, usa fallback .dict()."""
    if Contexto_cls is not None:
        try:
            comp = pd.Timestamp(competencia.year, competencia.month, 1)
            if competencia.month == 12:
                fim = pd.Timestamp(competencia.year + 1, 1, 1) - pd.Timedelta(days=1)
            else:
                fim = pd.Timestamp(competencia.year, competencia.month + 1, 1) - pd.Timedelta(days=1)
            ini = pd.Timestamp(competencia.year, competencia.month, 1)
            ctx = Contexto_cls(periodo_ini=ini, periodo_fim=fim, competencia=comp, pos15_regra=pos15_regra)
            if hasattr(ctx, "dict"):
                return ctx
        except Exception:
            pass
    return _ctx_fallback_for(competencia, pos15_regra)

# ================================= Utilitários =================================
REQUIRED_FILES_HINTS = {
    "ATIVOS": "ATIVOS",
    "DESLIGADOS": "DESLIGADOS",
    "FERIAS": "FÉRIAS",  # aceita 'FERIAS'
}

def _validate_input_dir(input_dir: str) -> None:
    if not os.path.isdir(input_dir):
        raise FileNotFoundError(f"Pasta não encontrada: {input_dir}")
    files = [f.lower() for f in os.listdir(input_dir) if f.lower().endswith(".xlsx")]
    for hint in REQUIRED_FILES_HINTS.values():
        if not any(hint.lower() in f for f in files):
            raise FileNotFoundError(
                f"Precisa existir um .xlsx que contenha '{hint}' dentro de {input_dir}"
            )

def _find_excel(path_like: str) -> str:
    """Resolve um caminho de Excel a partir de nome parcial, com heurística."""
    cand = path_like
    if not cand.lower().endswith(".xlsx"):
        cand += ".xlsx"
    if os.path.isfile(cand):
        return cand
    # tenta glob no diretório atual
    matches = glob.glob(f"*{os.path.basename(cand)}*")
    matches = [m for m in matches if m.lower().endswith(".xlsx")]
    if matches:
        # pega o mais recente por mtime
        matches.sort(key=lambda p: os.path.getmtime(p), reverse=True)
        return matches[0]
    raise FileNotFoundError(f"Arquivo Excel não encontrado: {path_like}")

def _aplicar_80_20_no_arquivo(xlsx_path: str) -> None:
    """Garante 80/20 (empresa/profissional) na planilha final (1ª aba)."""
    with pd.ExcelFile(xlsx_path) as xls:
        aba = xls.sheet_names[0]
        df = pd.read_excel(xls, sheet_name=aba)
    df.columns = [str(c) for c in df.columns]
    if "TOTAL" in df.columns:
        total = pd.to_numeric(df["TOTAL"], errors="coerce").fillna(0)
        df["Custo empresa"] = total * 0.80
        df["Desconto profissional"] = total * 0.20
    with pd.ExcelWriter(xlsx_path, engine="openpyxl", mode="a", if_sheet_exists="replace") as w:
        df.to_excel(w, sheet_name=aba, index=False)

def _safe_metrics_from_excel(xlsx_path: str) -> Dict[str, Any]:
    with pd.ExcelFile(xlsx_path) as xls:
        sheet = xls.sheet_names[0]
        df = pd.read_excel(xls, sheet_name=sheet)
    total = len(df)
    df.columns = [str(c) for c in df.columns]
    sind_col = next((c for c in df.columns if "SINDICATO" in c.upper()), None)
    sindicatos = int(df[sind_col].nunique()) if sind_col else None
    sums = {}
    for cand in ["TOTAL", "Custo empresa", "Desconto profissional", "DIAS", "VALOR_DIARIO_VR"]:
        if cand in df.columns:
            ser = pd.to_numeric(df[cand], errors="coerce")
            if ser.notna().any():
                sums[cand] = float(ser.fillna(0).sum())
    return {"linhas": total, "sindicatos_unicos": sindicatos, "somas": sums}

# ================================= Ferramentas =================================
class GerarVRInput(BaseModel):
    input_dir: str = Field(..., description="Pasta com .xlsx de entrada")
    mes: int = Field(..., ge=1, le=12)
    ano: int = Field(..., ge=2000, le=2100)
    pos15_regra: str = Field("integral", description="integral|proporcional")
    nome_saida: Optional[str] = Field(None, description="Nome/caminho do .xlsx a gerar")

def gerar_vr_mensal_tool(input_dir: str, mes: int, ano: int,
                         pos15_regra: str = "integral",
                         nome_saida: Optional[str] = None) -> str:
    steps_mod, Contexto_cls = _import_pipeline()
    _validate_input_dir(input_dir)
    competencia = date(ano, mes, 1)
    ctx = _make_contexto(Contexto_cls, competencia, pos15_regra)
    out = nome_saida or f"VR_MENSAL_{mes:02d}_{ano}.xlsx"

    bases = steps_mod.carregar_bases(input_dir)

    # montar_base com retry caso algum código interno exija .dict()
    try:
        base = steps_mod.montar_base_elegiveis(bases, ctx)
    except AttributeError as e:
        if "dict" in str(e).lower():
            ctx = _ctx_fallback_for(competencia, pos15_regra)
            base = steps_mod.montar_base_elegiveis(bases, ctx)
        else:
            raise

    # exportar com retry pelo mesmo motivo
    try:
        steps_mod.exportar_planilha(base, bases, ctx, out)
    except AttributeError as e:
        if "dict" in str(e).lower():
            ctx = _ctx_fallback_for(competencia, pos15_regra)
            steps_mod.exportar_planilha(base, bases, ctx, out)
        else:
            raise

    _aplicar_80_20_no_arquivo(out)  # reforço 80/20 para garantir
    metrics = _safe_metrics_from_excel(out)
    return json.dumps({
        "status": "ok",
        "saida": os.path.abspath(out),
        "competencia": {"mes": mes, "ano": ano},
        "pos15_regra": pos15_regra,
        "metricas": metrics
    }, ensure_ascii=False)

class ValidarInput(BaseModel):
    caminho_saida: str = Field(..., description="Excel gerado (pode ser nome parcial)")
    modelo_entradas: str = Field(..., description="Planilha-modelo em /entradas (aba contém 'VR Mensal')")
    validacoes_ref: Optional[str] = Field(None, description="Opcional: outra planilha de validações")
    tolerancia: float = Field(0.01, description="Tolerância p/ 80/20 (linha e agregado)")

def validar_conformidade_tool(caminho_saida: str, modelo_entradas: str,
                              validacoes_ref: Optional[str] = None, tolerancia: float = 0.01) -> str:
    gerado = _find_excel(caminho_saida)
    modelo = _find_excel(modelo_entradas)

    # 1) estrutura do modelo
    with pd.ExcelFile(modelo) as xls:
        aba_modelo = next((s for s in xls.sheet_names if "vr mensal" in s.lower()), xls.sheet_names[0])
        df_modelo = pd.read_excel(xls, sheet_name=aba_modelo)
    df_modelo.columns = [str(c) for c in df_modelo.columns]
    colunas_esperadas = list(df_modelo.columns)

    # 2) planilha gerada
    with pd.ExcelFile(gerado) as xls_out:
        aba_out = next((s for s in xls_out.sheet_names if "vr mensal" in s.lower()), xls_out.sheet_names[0])
        df_out = pd.read_excel(xls_out, sheet_name=aba_out)
    df_out.columns = [str(c) for c in df_out.columns]

    # 3) estrutura
    faltantes = [c for c in colunas_esperadas if c not in df_out.columns]
    extras = [c for c in df_out.columns if c not in colunas_esperadas]

    # 4) 80/20
    # se não existirem colunas, cria reforço
    if not all(c in df_out.columns for c in ["TOTAL", "Custo empresa", "Desconto profissional"]):
        _aplicar_80_20_no_arquivo(gerado)
        with pd.ExcelFile(gerado) as x:
            df_out = pd.read_excel(x, sheet_name=aba_out)
        df_out.columns = [str(c) for c in df_out.columns]

    issues_80_20: List[Dict[str, Any]] = []
    if all(c in df_out.columns for c in ["TOTAL", "Custo empresa", "Desconto profissional"]):
        total = pd.to_numeric(df_out["TOTAL"], errors="coerce").fillna(0)
        ce = pd.to_numeric(df_out["Custo empresa"], errors="coerce").fillna(0)
        dp = pd.to_numeric(df_out["Desconto profissional"], errors="coerce").fillna(0)

        ce_ok = (abs(ce - total*0.8) <= tolerancia).all()
        dp_ok = (abs(dp - total*0.2) <= tolerancia).all()
        if not ce_ok or not dp_ok:
            issues_80_20.append({"msg":"Falha 80/20 por linha","ce_ok":bool(ce_ok),"dp_ok":bool(dp_ok)})

        total_sum = max(1.0, float(total.sum()))
        ce_sum_ok = abs(float(ce.sum()) - total_sum*0.8) <= tolerancia*total_sum
        dp_sum_ok = abs(float(dp.sum()) - total_sum*0.2) <= tolerancia*total_sum
        if not ce_sum_ok or not dp_sum_ok:
            issues_80_20.append({"msg":"Falha 80/20 agregado","ce_sum_ok":bool(ce_sum_ok),"dp_sum_ok":bool(dp_sum_ok)})

    # 5) integridade
    negativos: List[str] = []
    for c in ["DIAS", "TOTAL", "Custo empresa", "Desconto profissional"]:
        if c in df_out.columns:
            serie = pd.to_numeric(df_out[c], errors="coerce").fillna(0)
            if (serie < 0).any():
                negativos.append(c)

    # 6) referência de validações (opcional)
    tem_val_ref = False
    if validacoes_ref:
        try:
            with pd.ExcelFile(_find_excel(validacoes_ref)) as xls_val:
                tem_val_ref = "Validações" in xls_val.sheet_names
        except Exception:
            tem_val_ref = False

    # 7) escreve/atualiza aba "Validações"
    resumo = pd.DataFrame([
        {"Check":"Colunas faltantes", "Detalhe": ", ".join(map(str, faltantes)) or "-"},
        {"Check":"Colunas extras", "Detalhe": ", ".join(map(str, extras)) or "-"},
        {"Check":"80/20", "Detalhe": "OK" if not issues_80_20 else str(issues_80_20)},
        {"Check":"Valores negativos", "Detalhe": ", ".join(map(str, negativos)) or "-"},
        {"Check":"Validações ref. detectada?", "Detalhe": "Sim" if tem_val_ref else "Não utilizado"},
    ])
    with pd.ExcelWriter(gerado, engine="openpyxl", mode="a", if_sheet_exists="replace") as writer:
        resumo.to_excel(writer, sheet_name="Validações", index=False)

    return json.dumps({
        "status": "ok",
        "arquivo": os.path.abspath(gerado),
        "aba_modelo": aba_modelo,
        "faltantes": faltantes,
        "extras": extras,
        "issues_80_20": issues_80_20,
        "negativos": negativos
    }, ensure_ascii=False)

class LerValidacoesInput(BaseModel):
    caminho_saida: str = Field(..., description="Caminho ou nome (parcial) do .xlsx gerado")
    max_linhas: int = Field(50, ge=1, le=500)

def ler_validacoes_tool(caminho_saida: str, max_linhas: int = 50) -> str:
    try:
        arq = _find_excel(caminho_saida)
    except Exception as e:
        return json.dumps({"status":"erro","mensagem":str(e)}, ensure_ascii=False)

    try:
        with pd.ExcelFile(arq) as xls:
            if "Validações" not in xls.sheet_names:
                return json.dumps({"status":"sem_validacoes","arquivo":arq}, ensure_ascii=False)
            df = pd.read_excel(xls, sheet_name="Validações")
    except Exception as e:
        return json.dumps({"status":"erro","mensagem":str(e)}, ensure_ascii=False)

    prev = df.head(max_linhas)
    return json.dumps({
        "status":"ok",
        "arquivo": os.path.abspath(arq),
        "linhas": int(len(df)),
        "preview": json.loads(prev.to_json(orient="records", force_ascii=False))
    }, ensure_ascii=False)

class ListarSchemaInput(BaseModel):
    aba: str = Field(..., description="ATIVOS, FERIAS, DESLIGADOS")

def listar_colunas_obrigatorias_tool(aba: str) -> str:
    obrigatorias = {
        "ATIVOS": ["MATRICULA", "EMPRESA", "TITULO_DO_CARGO", "SINDICATO", "ADMISSAO"],
        "FERIAS": ["MATRICULA", "DIAS_DE_FERIAS"],
        "DESLIGADOS": ["MATRICULA", "DATA_DEMISSÃO", "COMUNICADO_DE_DESLIGAMENTO"]
    }
    aba_key = aba.strip().upper()
    cols = obrigatorias.get(aba_key, [])
    if not cols:
        return json.dumps({"status":"erro","detalhe":f"Aba desconhecida: {aba}"}, ensure_ascii=False)
    return json.dumps({"status":"ok","aba":aba_key,"colunas":cols}, ensure_ascii=False)

# ============================== LLM factory ====================================
def _make_llm(choice: str = "auto"):
    """
    Retorna Chat LLM:
    - OpenAI (se OPENAI_API_KEY) quando choice=auto/openai
    - Ollama local quando choice=auto/ollama
    Default do Ollama: qwen2:0.5b (é leve e não estoura RAM).
    """
    choice = (choice or "auto").lower()

    if choice in ("auto", "openai"):
        try:
            from langchain_openai import ChatOpenAI
            if os.getenv("OPENAI_API_KEY"):
                return ChatOpenAI(model="gpt-4o-mini", temperature=0)
        except Exception:
            if choice == "openai":
                raise RuntimeError("OpenAI indisponível. Instale 'langchain-openai' e defina OPENAI_API_KEY.")

    if choice in ("auto", "ollama"):
        try:
            from langchain_community.chat_models import ChatOllama
            model_name = os.getenv("OLLAMA_MODEL", "qwen2:0.5b")
            return ChatOllama(model=model_name, temperature=0)
        except Exception as e:
            if choice == "ollama":
                raise RuntimeError(
                    "Ollama indisponível. Rode 'ollama pull <modelo>' (ex.: qwen2:0.5b) e garanta que o serviço está ativo."
                ) from e

    # Tentativa final: OpenAI se existir chave
    try:
        from langchain_openai import ChatOpenAI
        if os.getenv("OPENAI_API_KEY"):
            return ChatOpenAI(model="gpt-4o-mini", temperature=0)
    except Exception:
        pass

    raise RuntimeError(
        "Nenhum LLM disponível.\n"
        "- OpenAI: defina OPENAI_API_KEY e instale langchain-openai\n"
        "- Ollama: instale/rode Ollama e faça 'ollama pull qwen2:0.5b' (modelo leve)"
    )

# =============================== Agente (ReAct) ================================
SYSTEM_PROMPT = (
    "Você é um agente especialista em VR. Gere a planilha final seguindo o modelo em /entradas, "
    "aplique 80/20 (empresa/profissional) e atualize a aba 'Validações' com checagens. "
    "Nunca exponha PII (CPF, nomes). Responda com métricas e caminhos de arquivo."
)

REACT_TEMPLATE = """{system_prompt}

Ferramentas disponíveis:
{tools}

Formato:
Question: pergunta do usuário
Thought: seu raciocínio
Action: uma das ferramentas {tool_names}
Action Input: JSON
Observation: resultado da ferramenta
... (repita conforme necessário)
Thought: I now know the final answer
Final Answer: resposta final (sem PII), com caminho do arquivo e métricas

Comece!

Question: {input}
{agent_scratchpad}
"""
PROMPT = PromptTemplate.from_template(REACT_TEMPLATE)

def build_agent(llm_choice: str = "auto", verbose: bool = True) -> AgentExecutor:
    gerar_vr = StructuredTool.from_function(
        func=gerar_vr_mensal_tool, name="gerar_vr_mensal",
        description="Gera o Excel final a partir da pasta de entradas (aplica 80/20).",
        args_schema=GerarVRInput
    )
    validar_conf = StructuredTool.from_function(
        func=validar_conformidade_tool, name="validar_conformidade",
        description="Valida a planilha gerada contra o modelo de /entradas e checa 80/20 + integridade; atualiza 'Validações'.",
        args_schema=ValidarInput
    )
    ler_val = StructuredTool.from_function(
        func=ler_validacoes_tool, name="ler_validacoes",
        description="Preview seguro da aba 'Validações' (aceita nome parcial do arquivo).",
        args_schema=LerValidacoesInput
    )
    listar_schema = StructuredTool.from_function(
        func=listar_colunas_obrigatorias_tool, name="listar_colunas_obrigatorias",
        description="Lista colunas esperadas por aba (ATIVOS/FERIAS/DESLIGADOS).",
        args_schema=ListarSchemaInput
    )

    tools = [gerar_vr, validar_conf, ler_val, listar_schema]
    llm = _make_llm(llm_choice)
    agent = create_react_agent(llm=llm, tools=tools, prompt=PROMPT.partial(system_prompt=SYSTEM_PROMPT))
    return AgentExecutor(agent=agent, tools=tools, verbose=verbose, handle_parsing_errors=True)

# =================================== CLI ======================================
def _cli() -> int:
    ap = argparse.ArgumentParser(description="Agente VR (OpenAI ou Ollama)")
    ap.add_argument("--ask", type=str, help="Comando em linguagem natural (pt-br)")
    ap.add_argument("--llm", type=str, default="auto", choices=["auto","openai","ollama"],
                    help="Escolha do LLM: auto (default) | openai | ollama")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    if not args.ask:
        print('Ex.: python agent_vr.py --llm auto --ask "Gere o VR de 08/2025 usando a pasta entradas com regra integral e valide com o modelo entradas/VR Mensal 05.2025.xlsx."')
        return 0

    try:
        agent = build_agent(llm_choice=args.llm, verbose=args.verbose)
        out = agent.invoke({"input": args.ask})
        print(out["output"])
        return 0
    except Exception as e:
        msg = str(e)
        if ("Connection refused" in msg or "Failed to establish a new connection" in msg or "WinError 10061" in msg) and args.llm in ("auto","ollama"):
            print(
                "❌ LLM local (Ollama) indisponível.\n"
                "→ 'ollama pull qwen2:0.5b' e deixe o serviço ativo (ollama serve).\n"
                "Ou rode com OpenAI (defina OPENAI_API_KEY) ou use --llm openai."
            )
            return 1
        print(f"❌ Erro: {e}")
        return 1

if __name__ == "__main__":
    raise SystemExit(_cli())