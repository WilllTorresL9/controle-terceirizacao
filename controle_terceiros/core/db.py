"""Camada de dados usada pelas páginas: leitura com cache, gravação e IDs."""
from __future__ import annotations

import datetime as dt

import pandas as pd
import streamlit as st

from core.backends import GSheetsBackend, LocalBackend
from core.schema import CHAVE, DATAS, NUMERICOS, PREFIXO_ID, SEED, TABELAS


def _segredos():
    try:
        cred = st.secrets.get("gcp_service_account")
        planilha = st.secrets.get("planilha", {}).get("url")
        return (dict(cred), planilha) if cred and planilha else (None, None)
    except Exception:
        return None, None


@st.cache_resource(show_spinner="Conectando ao banco de dados…")
def backend():
    cred, planilha = _segredos()
    b = GSheetsBackend(cred, planilha) if cred else LocalBackend("dados_local")
    for tabela, colunas in TABELAS.items():
        b.garantir(tabela, colunas)
    agora = agora_txt()
    for tabela, linhas in SEED.items():
        if b.ler(tabela, TABELAS[tabela]).empty:
            pref = PREFIXO_ID[tabela]
            b.anexar(tabela, TABELAS[tabela], [
                {**l, "id": f"{pref}-{i:06d}", "criado_em": agora, "criado_por": "sistema"}
                for i, l in enumerate(linhas, start=1)
            ])
    return b


def modo() -> str:
    return backend().nome


def agora_txt() -> str:
    return dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


@st.cache_data(ttl=120, show_spinner=False)
def _ler_cache(tabela: str) -> pd.DataFrame:
    return backend().ler(tabela, TABELAS[tabela])


def limpar_cache():
    _ler_cache.clear()


def _datas(serie: pd.Series) -> pd.Series:
    """Aceita AAAA-MM-DD (padrão do sistema) e DD/MM/AAAA (digitado à mão na planilha)."""
    txt = serie.astype(str).str.strip().str[:10]
    iso = pd.to_datetime(txt, errors="coerce", format="%Y-%m-%d")
    br = pd.to_datetime(txt, errors="coerce", format="%d/%m/%Y")
    return iso.fillna(br).dt.normalize()


def tipar(df: pd.DataFrame, tabela: str) -> pd.DataFrame:
    for c in NUMERICOS.get(tabela, []):
        df[c] = pd.to_numeric(df[c].astype(str).str.replace(",", "."), errors="coerce").fillna(0)
        if tabela != "fornecedores":
            df[c] = df[c].round().astype(int)
    for c in DATAS.get(tabela, []):
        df[c] = _datas(df[c])
    return df


def ler(tabela: str, tipado: bool = True) -> pd.DataFrame:
    df = _ler_cache(tabela).copy()
    return tipar(df, tabela) if tipado else df


def ativos(tabela: str) -> pd.DataFrame:
    df = ler(tabela)
    return df[df["ativo"].str.strip().str.lower().isin(["sim", "s", "true", "1", ""])]


def _usuario() -> str:
    u = st.session_state.get("usuario") or {}
    return u.get("usuario", "")


def _proximos_ids(tabela: str, n: int) -> list[str]:
    df = backend().ler(tabela, TABELAS[tabela])  # leitura sem cache para não repetir ID
    nums = df["id"].astype(str).str.extract(r"(\d+)$")[0].dropna()
    inicio = int(nums.astype(int).max()) + 1 if len(nums) else 1
    pref = PREFIXO_ID[tabela]
    return [f"{pref}-{i:06d}" for i in range(inicio, inicio + n)]


def inserir(tabela: str, linhas: dict | list[dict]) -> list[str]:
    linhas = [linhas] if isinstance(linhas, dict) else list(linhas)
    if not linhas:
        return []
    agora, user = agora_txt(), _usuario()
    if CHAVE[tabela] == "id":
        ids = _proximos_ids(tabela, len(linhas))
        for l, i in zip(linhas, ids):
            l["id"] = i
    for l in linhas:
        l.setdefault("criado_em", agora)
        if "criado_por" in TABELAS[tabela]:
            l.setdefault("criado_por", user)
    backend().anexar(tabela, TABELAS[tabela], linhas)
    limpar_cache()
    return [l[CHAVE[tabela]] for l in linhas]


def atualizar(tabela: str, chave_valor: str, mudancas: dict):
    if "atualizado_em" in TABELAS[tabela]:
        mudancas = {**mudancas, "atualizado_em": f"{agora_txt()} ({_usuario()})"}
    backend().atualizar(tabela, TABELAS[tabela], CHAVE[tabela], chave_valor, mudancas)
    limpar_cache()


def excluir(tabela: str, chave_valor: str):
    backend().excluir(tabela, TABELAS[tabela], CHAVE[tabela], chave_valor)
    limpar_cache()


def substituir_tudo(tabela: str, df: pd.DataFrame):
    """Regrava a aba inteira (usado em operações em lote, ex.: programação)."""
    backend().substituir_tudo(tabela, TABELAS[tabela], df)
    limpar_cache()
