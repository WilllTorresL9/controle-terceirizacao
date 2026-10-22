"""Componentes visuais reutilizados pelas páginas."""
from __future__ import annotations

import io
import math

import pandas as pd
import streamlit as st

from core import auth, db

COR = {"enviado": "#C2410C", "recebido": "#1D4E89", "previsto": "#8A8F98", "nc": "#B91C1C", "ok": "#15803D"}

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@500&display=swap');
html, body, [class*="css"], .stMarkdown, .stTextInput, .stSelectbox { font-family: 'IBM Plex Sans', sans-serif; }
.block-container { padding-top: 1.6rem; padding-bottom: 3rem; }
.cab { border-left: 6px solid #C2410C; padding: .15rem 0 .15rem .9rem; margin-bottom: 1.1rem; }
.cab h1 { font-size: 1.65rem; font-weight: 700; margin: 0; letter-spacing: -.01em; }
.cab p { margin: .15rem 0 0; color: #5B6170; font-size: .95rem; }
[data-testid="stMetricValue"] { font-family: 'IBM Plex Mono', monospace; font-size: 1.55rem; }
[data-testid="stMetricLabel"] p { font-size: .8rem; text-transform: uppercase; letter-spacing: .04em; }
.login-titulo { font-size: 1.9rem; font-weight: 700; margin-top: 3rem; border-left: 6px solid #C2410C; padding-left: .8rem; }
.login-sub { color: #5B6170; margin: .2rem 0 1.4rem .95rem; }
.saldo-box { background: #FFF4EC; border: 1px solid #F3C9A8; border-radius: 8px; padding: .7rem 1rem; }
.saldo-box b { font-family: 'IBM Plex Mono', monospace; font-size: 1.25rem; color: #9A3412; }
</style>
"""


def estilo():
    st.markdown(CSS, unsafe_allow_html=True)


def cabecalho(titulo: str, subtitulo: str = ""):
    st.markdown(f"<div class='cab'><h1>{titulo}</h1><p>{subtitulo}</p></div>", unsafe_allow_html=True)


def n(v) -> str:
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "–"
    return f"{v:,.0f}".replace(",", ".")


def pct(v, casas=1) -> str:
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "–"
    return f"{v * 100:.{casas}f}%".replace(".", ",")


def dias(v) -> str:
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "–"
    return f"{v:.1f} d".replace(".", ",")


def opcoes(df: pd.DataFrame, col: str = "nome") -> list[str]:
    return sorted(df[col].dropna().astype(str).unique().tolist())


def servicos_do_fornecedor(fornecedores: pd.DataFrame, nome: str, todos: list[str]) -> list[str]:
    reg = fornecedores[fornecedores["nome"] == nome]
    if reg.empty or not str(reg.iloc[0]["servicos"]).strip():
        return todos
    lista = [s.strip() for s in str(reg.iloc[0]["servicos"]).split(";") if s.strip()]
    return [s for s in lista if s in todos] or todos


def lead_padrao(fornecedores: pd.DataFrame) -> dict:
    return {r["nome"]: float(r["lead_time_dias"]) for _, r in fornecedores.iterrows()
            if r["lead_time_dias"] and float(r["lead_time_dias"]) > 0}


def excel(abas: dict[str, pd.DataFrame]) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        for nome, df in abas.items():
            d = df.copy()
            for c in d.columns:
                if pd.api.types.is_datetime64_any_dtype(d[c]):
                    d[c] = d[c].dt.date
            d.to_excel(w, sheet_name=nome[:31], index=False)
    return buf.getvalue()


def botao_excel(abas: dict[str, pd.DataFrame], nome_arquivo: str, rotulo="⬇️ Exportar Excel"):
    st.download_button(rotulo, excel(abas), file_name=nome_arquivo,
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


def busca_texto(df: pd.DataFrame, termo: str, colunas: list[str]) -> pd.DataFrame:
    """Busca rápida: todas as palavras digitadas precisam aparecer em alguma coluna."""
    if not termo.strip() or df.empty:
        return df
    alvo = df[colunas].astype(str).agg(" ".join, axis=1).str.lower()
    mask = pd.Series(True, index=df.index)
    for palavra in termo.lower().split():
        mask &= alvo.str.contains(palavra, regex=False)
    return df[mask]


# --------------------------------------------------------------------------- edição genérica
def secao_edicao(tabela: str, df: pd.DataFrame, campos: list[tuple], rotulo: str, descrever):
    """Expander para corrigir/excluir um registro.

    campos: lista de (coluna, tipo, rótulo[, opções]); tipo ∈ data | int | texto | select
    descrever: função(linha) -> texto mostrado na lista de seleção
    """
    if df.empty:
        return
    editaveis = df[df["criado_por"].map(auth.pode_editar_registro)]
    with st.expander(f"✏️ Corrigir ou excluir {rotulo}"):
        if editaveis.empty:
            st.caption("Você só pode corrigir registros lançados por você (administradores corrigem qualquer um).")
            return
        editaveis = editaveis.sort_values(["data", "id"], ascending=False).head(300)
        escolha = st.selectbox("Selecione o registro", editaveis["id"].tolist(),
                               format_func=lambda i: descrever(editaveis[editaveis["id"] == i].iloc[0]),
                               key=f"sel_{tabela}")
        reg = editaveis[editaveis["id"] == escolha].iloc[0]
        with st.form(f"edit_{tabela}_{escolha}"):
            novos, cols = {}, st.columns(3)
            for i, campo in enumerate(campos):
                col, tipo, rot = campo[:3]
                with cols[i % 3]:
                    if tipo == "data":
                        novos[col] = st.date_input(rot, value=reg[col].date(), format="DD/MM/YYYY")
                    elif tipo == "int":
                        novos[col] = st.number_input(rot, min_value=0, step=1, value=int(reg[col]))
                    elif tipo == "select":
                        ops = list(campo[3])
                        if reg[col] not in ops:
                            ops = [reg[col]] + ops
                        novos[col] = st.selectbox(rot, ops, index=ops.index(reg[col]))
                    else:
                        novos[col] = st.text_input(rot, value=str(reg[col]))
            confirma = st.checkbox("Confirmo a exclusão deste registro")
            c1, c2 = st.columns(2)
            salvar = c1.form_submit_button("💾 Salvar alterações", type="primary", use_container_width=True)
            apagar = c2.form_submit_button("🗑️ Excluir", use_container_width=True)
        if salvar:
            db.atualizar(tabela, escolha, novos)
            st.toast(f"{escolha} atualizado.", icon="✅")
            st.rerun()
        if apagar:
            if not confirma:
                st.warning("Marque a caixa de confirmação para excluir.")
            else:
                db.excluir(tabela, escolha)
                st.toast(f"{escolha} excluído.", icon="🗑️")
                st.rerun()


def config_colunas_mov():
    return {
        "data": st.column_config.DateColumn("Data", format="DD/MM/YYYY"),
        "id": st.column_config.TextColumn("ID", width="small"),
        "fornecedor": "Fornecedor", "servico": "Serviço", "produto": "Produto",
        "quantidade": st.column_config.NumberColumn("Qtd", format="%d"),
        "nf": "NF", "op": "OP", "corrida": "Corrida", "responsavel": "Responsável",
        "observacao": "Observação", "qtd_aprovada": st.column_config.NumberColumn("Aprovadas", format="%d"),
        "qtd_nao_conforme": st.column_config.NumberColumn("Não conf.", format="%d"),
        "qtd_sucata": st.column_config.NumberColumn("Sucata", format="%d"),
        "total": st.column_config.NumberColumn("Total", format="%d"),
        "motivo_nc": "Motivo NC", "nf_retorno": "NF retorno", "nf_referencia": "NF(s) de envio",
        "criado_por": "Lançado por",
    }
