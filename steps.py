# steps.py — pipeline VR Mensal com Validações automáticas

import os
import pandas as pd
from dataclasses import dataclass
from utils import normalize_cols, strip_accents_upper, infer_estado_from_sindicato


# ---------------------- Contexto ----------------------
@dataclass
class Contexto:
    periodo_ini: pd.Timestamp
    periodo_fim: pd.Timestamp
    competencia: pd.Timestamp
    pos15_regra: str = "integral"  # 'integral' | 'proporcional'

    def dict(self):
        return {
            "periodo_ini": self.periodo_ini,
            "periodo_fim": self.periodo_fim,
            "competencia": self.competencia,
            "pos15_regra": self.pos15_regra,
        }


# ---------------------- Funções principais ----------------------
def carregar_bases(input_dir: str) -> dict:
    """
    Lê planilhas ATIVOS, FÉRIAS, DESLIGADOS da pasta.
    Retorna dict de DataFrames com colunas normalizadas.
    """
    import glob

    bases = {}
    for path in glob.glob(os.path.join(input_dir, "*.xlsx")):
        nome = os.path.basename(path).upper()
        df = pd.read_excel(path)
        df.columns = normalize_cols(df.columns)
        if "ATIVOS" in nome:
            bases["ATIVOS"] = df
        elif "FERIAS" in nome or "FÉRIAS" in nome:
            bases["FERIAS"] = df
        elif "DESLIGADOS" in nome:
            bases["DESLIGADOS"] = df
    return bases


def montar_base_elegiveis(bases: dict, ctx: Contexto) -> pd.DataFrame:
    """
    Constrói base final de elegíveis a VR:
    - exclui desligados
    - ajusta dias considerando férias
    - calcula TOTAL e adiciona colunas auxiliares
    """
    ativos = bases.get("ATIVOS", pd.DataFrame()).copy()
    ferias = bases.get("FERIAS", pd.DataFrame())
    desligados = bases.get("DESLIGADOS", pd.DataFrame())

    # remove desligados
    if not desligados.empty and "MATRICULA" in ativos.columns:
        ativos = ativos[~ativos["MATRICULA"].isin(desligados["MATRICULA"])]

    # ajusta dias de VR
    if not ferias.empty and "MATRICULA" in ativos.columns and "DIAS_DE_FERIAS" in ferias.columns:
        ativos = ativos.merge(
            ferias[["MATRICULA", "DIAS_DE_FERIAS"]],
            on="MATRICULA",
            how="left"
        )
        ativos["DIAS"] = 22 - ativos["DIAS_DE_FERIAS"].fillna(0)
    else:
        ativos["DIAS"] = 22

    # valor diário e total
    ativos["VALOR_DIARIO_VR"] = 30.0  # fixo
    ativos["TOTAL"] = ativos["DIAS"] * ativos["VALOR_DIARIO_VR"]

    # sindicato e estado
    if "SINDICATO" in ativos.columns:
        ativos["SINDICATO"] = ativos["SINDICATO"].map(strip_accents_upper)
        ativos["ESTADO"] = ativos["SINDICATO"].map(infer_estado_from_sindicato)

    return ativos


def _gerar_validacoes(df: pd.DataFrame) -> pd.DataFrame:
    """Gera dataframe de validações automáticas."""
    checks = []

    # 80/20
    if all(c in df.columns for c in ["TOTAL", "Custo empresa", "Desconto profissional"]):
        total = pd.to_numeric(df["TOTAL"], errors="coerce").fillna(0)
        ce = pd.to_numeric(df["Custo empresa"], errors="coerce").fillna(0)
        dp = pd.to_numeric(df["Desconto profissional"], errors="coerce").fillna(0)

        ce_ok = (abs(ce - total * 0.8) < 0.01).all()
        dp_ok = (abs(dp - total * 0.2) < 0.01).all()

        checks.append({"Check": "Regra 80/20", "Detalhe": "OK" if ce_ok and dp_ok else "Falha"})

    # Negativos
    negativos = []
    for col in ["DIAS", "TOTAL", "Custo empresa", "Desconto profissional"]:
        if col in df.columns:
            if (df[col] < 0).any():
                negativos.append(col)
    checks.append({"Check": "Valores negativos", "Detalhe": ", ".join(negativos) if negativos else "Nenhum"})

    return pd.DataFrame(checks)


def exportar_planilha(base: pd.DataFrame, bases: dict, ctx: Contexto, out_path: str) -> None:
    """
    Exporta a planilha final no formato esperado.
    Inclui abas auxiliares e Validações automáticas.
    """
    validacoes = _gerar_validacoes(base)

    with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
        base.to_excel(writer, sheet_name="VR Mensal", index=False)
        for k, df in bases.items():
            df.to_excel(writer, sheet_name=k, index=False)
        validacoes.to_excel(writer, sheet_name="Validações", index=False)