"""Regras de cálculo dos indicadores (pandas puro, sem Streamlit).

Definições usadas:
- Recebido total      = aprovadas + não conformes + sucata
- Saldo no fornecedor = enviado acumulado − recebido acumulado
- Aderência ao programa = enviado no período ÷ previsto no período
- Índice de NC        = (não conformes + sucata) ÷ recebido total
- Lead time           = dias entre o envio e o retorno de cada peça, casando
                        recebimentos com envios por ordem de chegada (FIFO)
- Entrega no prazo    = lote retornou em até o lead time padrão do fornecedor
"""
from __future__ import annotations

import calendar
import datetime as dt

import numpy as np
import pandas as pd

from core.schema import DIAS_SEMANA

CHAVES = ["fornecedor", "servico", "produto"]


# --------------------------------------------------------------------------- utilidades
def periodo(ano: int, mes: int | None):
    if mes:
        ini = dt.date(ano, mes, 1)
        fim = dt.date(ano, mes, calendar.monthrange(ano, mes)[1])
    else:
        ini, fim = dt.date(ano, 1, 1), dt.date(ano, 12, 31)
    return pd.Timestamp(ini), pd.Timestamp(fim)


def no_periodo(df, ini, fim, col="data"):
    return df[(df[col] >= ini) & (df[col] <= fim)]


def filtrar(df, fornecedores=None, servico=None, produto=None):
    if fornecedores:
        df = df[df["fornecedor"].isin(fornecedores)]
    if servico and servico != "Todos":
        df = df[df["servico"] == servico]
    if produto and produto != "Todos":
        df = df[df["produto"] == produto]
    return df


def com_total(rec: pd.DataFrame) -> pd.DataFrame:
    rec = rec.copy()
    rec["total"] = rec["qtd_aprovada"] + rec["qtd_nao_conforme"] + rec["qtd_sucata"]
    rec["reprovado"] = rec["qtd_nao_conforme"] + rec["qtd_sucata"]
    return rec


def div(a, b):
    return (a / b) if b else np.nan


def dia_semana(d) -> str:
    return DIAS_SEMANA[pd.Timestamp(d).weekday()]


# --------------------------------------------------------------------------- saldo / FIFO
def saldo(env, rec, ate=None, chaves=("fornecedor",)):
    chaves = list(chaves)
    if ate is not None:
        env, rec = env[env["data"] <= ate], rec[rec["data"] <= ate]
    rec = com_total(rec)
    e = env.groupby(chaves)["quantidade"].sum().rename("enviado")
    r = rec.groupby(chaves)["total"].sum().rename("recebido")
    out = pd.concat([e, r], axis=1).fillna(0).astype(int)
    out["saldo"] = out["enviado"] - out["recebido"]
    return out.reset_index()


def lotes_fifo(env, rec, lead_padrao: dict | None = None, hoje=None) -> pd.DataFrame:
    """Uma linha por envio, mostrando quanto já voltou, quanto falta e o lead time."""
    hoje = pd.Timestamp(hoje or dt.date.today())
    lead_padrao = lead_padrao or {}
    rec = com_total(rec)
    linhas = []
    env = env.dropna(subset=["data"]).sort_values(["data", "id"])
    rec = rec.dropna(subset=["data"]).sort_values(["data", "id"])
    for chave, ge in env.groupby(CHAVES, sort=False):
        gr = rec[(rec["fornecedor"] == chave[0]) & (rec["servico"] == chave[1]) & (rec["produto"] == chave[2])]
        fila = [[r.data, int(r.total)] for r in gr.itertuples()]
        i = 0
        for e in ge.itertuples():
            falta, recebido, soma_dias, ultima = int(e.quantidade), 0, 0, pd.NaT
            while falta > 0 and i < len(fila):
                d, disp = fila[i]
                usar = min(falta, disp)
                if usar > 0:
                    recebido += usar
                    falta -= usar
                    soma_dias += usar * max((d - e.data).days, 0)
                    ultima = d
                    fila[i][1] -= usar
                if fila[i][1] <= 0:
                    i += 1
            lead = lead_padrao.get(chave[0]) or np.nan
            concluido = falta == 0
            dias = max(0, (ultima - e.data).days if concluido and pd.notna(ultima) else (hoje - e.data).days)
            if concluido:
                status = "✅ Concluído"
                prazo = (np.nan if np.isnan(lead) else dias <= lead)
            else:
                atrasado = (not np.isnan(lead)) and dias > lead
                status = ("🔴 Atrasado" if atrasado else ("🟡 Parcial" if recebido else "🔵 No fornecedor"))
                prazo = (False if atrasado else np.nan)
            linhas.append({
                "id": e.id, "data": e.data, "fornecedor": chave[0], "servico": chave[1], "produto": chave[2],
                "nf": e.nf, "op": e.op, "corrida": e.corrida, "quantidade": int(e.quantidade),
                "recebido": recebido, "pendente": falta, "status": status, "dias": dias,
                "lead_padrao": lead, "lead_time": div(soma_dias, recebido),
                "ultimo_retorno": ultima, "no_prazo": prazo,
            })
    cols = ["id", "data", "fornecedor", "servico", "produto", "nf", "op", "corrida", "quantidade",
            "recebido", "pendente", "status", "dias", "lead_padrao", "lead_time", "ultimo_retorno", "no_prazo"]
    return pd.DataFrame(linhas, columns=cols)


# --------------------------------------------------------------------------- indicadores
def indicadores(env, rec, prog, ini, fim, lotes: pd.DataFrame | None = None) -> dict:
    e, r, p = no_periodo(env, ini, fim), com_total(no_periodo(rec, ini, fim)), no_periodo(prog, ini, fim)
    previsto, enviado = int(p["qtd_prevista"].sum()), int(e["quantidade"].sum())
    recebido, reprov = int(r["total"].sum()), int(r["reprovado"].sum())
    hoje = pd.Timestamp(dt.date.today())
    s = saldo(env, rec, ate=min(fim, hoje))
    k = {
        "previsto": previsto, "enviado": enviado, "recebido": recebido,
        "aprovado": int(r["qtd_aprovada"].sum()), "nao_conforme": int(r["qtd_nao_conforme"].sum()),
        "sucata": int(r["qtd_sucata"].sum()), "reprovado": reprov,
        "saldo": int(s["saldo"].sum()) if not s.empty else 0,
        "aderencia": div(enviado, previsto), "indice_nc": div(reprov, recebido),
        "lead_time": np.nan, "no_prazo": np.nan, "atrasados": 0, "pecas_atrasadas": 0,
    }
    # aderência só até hoje (evita "penalizar" dias futuros já programados)
    p_ate_hoje = p[p["data"] <= hoje]["qtd_prevista"].sum()
    e_ate_hoje = e[e["data"] <= hoje]["quantidade"].sum()
    k["aderencia_ate_hoje"] = div(e_ate_hoje, p_ate_hoje)
    k["previsto_ate_hoje"] = int(p_ate_hoje)
    if lotes is not None and not lotes.empty:
        l = no_periodo(lotes, ini, fim)
        conc = l[l["pendente"] == 0]
        if conc["recebido"].sum():
            k["lead_time"] = (conc["lead_time"] * conc["recebido"]).sum() / conc["recebido"].sum()
        avaliados = l["no_prazo"].dropna()
        if len(avaliados):
            k["no_prazo"] = avaliados.astype(bool).mean()
        atr = lotes[lotes["status"] == "🔴 Atrasado"]
        k["atrasados"], k["pecas_atrasadas"] = len(atr), int(atr["pendente"].sum())
    return k


def resumo_fornecedores(env, rec, prog, ini, fim, lotes=None) -> pd.DataFrame:
    nomes = sorted(set(env["fornecedor"]) | set(rec["fornecedor"]) | set(prog["fornecedor"]))
    linhas = []
    for n in nomes:
        f = lambda d: d[d["fornecedor"] == n]
        k = indicadores(f(env), f(rec), f(prog), ini, fim, None if lotes is None else f(lotes))
        linhas.append({"Fornecedor": n, "Previsto": k["previsto"], "Enviado": k["enviado"],
                       "Recebido": k["recebido"], "Saldo no fornecedor": k["saldo"],
                       "Aderência (%)": k["aderencia"] * 100, "Não conforme + sucata": k["reprovado"],
                       "Índice NC (%)": k["indice_nc"] * 100, "Lead time (dias)": k["lead_time"],
                       "No prazo (%)": k["no_prazo"] * 100, "Lotes atrasados": k["atrasados"]})
    return pd.DataFrame(linhas)


def mensal(env, rec, prog, ano: int) -> pd.DataFrame:
    rec = com_total(rec)
    meses = pd.DataFrame({"mes": range(1, 13)})

    def soma(df, col, nome):
        d = df[df["data"].dt.year == ano]
        return d.groupby(d["data"].dt.month)[col].sum().rename(nome)

    out = meses.set_index("mes").join([soma(prog, "qtd_prevista", "Previsto"), soma(env, "quantidade", "Enviado"),
                                        soma(rec, "total", "Recebido"), soma(rec, "reprovado", "Reprovado")])
    return out.fillna(0).astype(int).reset_index()


def serie_diaria(env, rec, prog, ano: int, mes: int) -> pd.DataFrame:
    """Reproduz a visão diária das abas de fornecedor da planilha original."""
    ini, fim = periodo(ano, mes)
    rec = com_total(rec)
    dias = pd.DataFrame({"data": pd.date_range(ini, fim, freq="D")})

    def soma(df, col):
        d = no_periodo(df, ini, fim)
        return d.groupby("data")[col].sum()

    dias["Dia"] = dias["data"].map(dia_semana)
    dias["Previsto"] = dias["data"].map(soma(prog, "qtd_prevista")).fillna(0).astype(int)
    dias["Enviado"] = dias["data"].map(soma(env, "quantidade")).fillna(0).astype(int)
    dias["Perf. dia (%)"] = np.where(dias["Previsto"] > 0, dias["Enviado"] / dias["Previsto"].replace(0, np.nan) * 100, np.nan)
    dias["Recebido"] = dias["data"].map(soma(rec, "total")).fillna(0).astype(int)
    dias["Não conforme"] = dias["data"].map(soma(rec, "reprovado")).fillna(0).astype(int)
    dias["NC (%)"] = np.where(dias["Recebido"] > 0, dias["Não conforme"] / dias["Recebido"].replace(0, np.nan) * 100, np.nan)
    hoje = pd.Timestamp(dt.date.today())

    def situacao(r):
        if r["Previsto"] == 0:
            return "Extra" if r["Enviado"] else ""
        if r["Enviado"] >= r["Previsto"]:
            return "✅ Meta"
        return "⏳ Futuro" if r["data"] > hoje else "⚠️ Abaixo"
    dias["Situação"] = dias.apply(situacao, axis=1)
    return dias


def extrato(env, rec) -> pd.DataFrame:
    """Movimentação cronológica com saldo acumulado no fornecedor (tipo kardex)."""
    rec = com_total(rec)
    e = pd.DataFrame({"data": env["data"], "ordem": 0, "Tipo": "📤 Envio", "ID": env["id"],
                      "Fornecedor": env["fornecedor"], "Serviço": env["servico"],
                      "Documento": "NF " + env["nf"].astype(str) + np.where(env["op"] != "", " · OP " + env["op"].astype(str), ""),
                      "Saiu": env["quantidade"], "Voltou": 0, "Reprovado": 0})
    r = pd.DataFrame({"data": rec["data"], "ordem": 1, "Tipo": "📥 Recebimento", "ID": rec["id"],
                      "Fornecedor": rec["fornecedor"], "Serviço": rec["servico"],
                      "Documento": "NF " + rec["nf_retorno"].astype(str),
                      "Saiu": 0, "Voltou": rec["total"], "Reprovado": rec["reprovado"]})
    m = pd.concat([e, r], ignore_index=True).sort_values(["data", "ordem", "ID"])
    m["Saldo no fornecedor"] = (m["Saiu"] - m["Voltou"]).cumsum()
    return m.drop(columns="ordem").reset_index(drop=True)
