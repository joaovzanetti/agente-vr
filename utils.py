# utils.py — funções auxiliares para o agente VR

import re
import unicodedata

def normalize_cols(cols):
    """
    Normaliza nomes de colunas:
    - remove acentos
    - deixa em maiúsculas
    - troca espaços por underscore
    """
    norm = []
    for c in cols:
        if not isinstance(c, str):
            c = str(c)
        c = unicodedata.normalize("NFKD", c)
        c = "".join(ch for ch in c if not unicodedata.combining(ch))
        c = c.upper().strip()
        c = re.sub(r"\s+", "_", c)
        norm.append(c)
    return norm

def strip_accents_upper(s: str) -> str:
    """Remove acentos e coloca em maiúsculas."""
    if not isinstance(s, str):
        return str(s)
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return s.upper().strip()

def infer_estado_from_sindicato(sindicato: str) -> str:
    """
    Infere estado a partir do texto do sindicato.
    Heurística simples: procura sigla de estado no nome.
    """
    if not isinstance(sindicato, str):
        return "?"
    s = strip_accents_upper(sindicato)
    for uf in ["SP","RJ","MG","RS","PR","SC","BA","PE","GO","DF","ES","MT","MS","PA","AM","CE"]:
        if uf in s:
            return uf
    return "?"
