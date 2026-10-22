import datetime as dt

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from core import calc, db, ui
from core.schema import MESES

ui.cabecalho("Painel de indicadores", "Envios, retornos, saldo nos fornecedores e qualidade")

env, rec, prog = db.ler("envios"), db.ler("recebimentos"), db.ler("programacao")
forn, serv = db.ler("fornecedores"), db.ler("servicos")
hoje = dt.date.today()

# ------------------------------------------------------------------ filtros
anos = sorted({hoje.year} | set(env["data"].dt.year.dropna().astype(int)) | set(prog["data"].dt.year.dropna().astype(int)))
f1, f2, f3, f4 = st.columns([0.8, 1, 2, 1.6])
ano = f1.selectbox("Ano", anos, index=anos.index(hoje.year))
mes_txt = f2.selectbox("Mês", ["Ano inteiro"] + MESES, index=0)
mes = None if mes_txt == "Ano inteiro" else MESES.index(mes_txt) + 1
sel_forn = f3.multiselect("Fornecedores", ui.opcoes(forn), placeholder="Todos")
sel_serv = f4.selectbox("Serviço", ["Todos"] + ui.opcoes(serv))

ini, fim = calc.periodo(ano, mes)
E, R, P = (calc.filtrar(d, sel_forn, sel_serv) for d in (env, rec, prog))
lotes = calc.lotes_fifo(E, R, ui.lead_padrao(forn))
k = calc.indicadores(E, R, P, ini, fim, lotes)

# ------------------------------------------------------------------ KPIs
c = st.columns(7)
c[0].metric("Previsto", ui.n(k["previsto"]), border=True,
            help="Soma da programação no período (página Programação).")
c[1].metric("Enviado", ui.n(k["enviado"]), border=True,
            delta=f"{ui.pct(k['aderencia_ate_hoje'], 0)} do previsto até hoje" if k["previsto_ate_hoje"] else None,
            delta_color="off")
c[2].metric("Recebido", ui.n(k["recebido"]), border=True,
            help="Aprovadas + não conformes + sucata.")
c[3].metric("Saldo no fornecedor", ui.n(k["saldo"]), border=True,
            help="Peças que saíram e ainda não voltaram (posição atual).")
c[4].metric("Índice NC", ui.pct(k["indice_nc"]), border=True,
            delta=f"{ui.n(k['reprovado'])} peças", delta_color="off",
            help="(Não conformes + sucata) ÷ recebido.")
c[5].metric("Lead time médio", ui.dias(k["lead_time"]), border=True,
            help="Dias entre envio e retorno, ponderado pela quantidade (lotes concluídos).")
c[6].metric("Entregas no prazo", ui.pct(k["no_prazo"], 0), border=True,
            help="Lotes que voltaram dentro do lead time padrão do fornecedor (definido no cadastro).")

if k["atrasados"]:
    atr = lotes[lotes["status"] == "🔴 Atrasado"].sort_values("dias", ascending=False)
    with st.expander(f"🔴 {k['atrasados']} lote(s) acima do prazo — {ui.n(k['pecas_atrasadas'])} peças aguardando retorno",
                     expanded=True):
        st.dataframe(atr[["data", "fornecedor", "servico", "nf", "op", "quantidade", "pendente", "dias", "lead_padrao"]],
                     hide_index=True, use_container_width=True,
                     column_config={**ui.config_colunas_mov(),
                                    "pendente": st.column_config.NumberColumn("Pendente", format="%d"),
                                    "dias": st.column_config.NumberColumn("Dias fora", format="%d"),
                                    "lead_padrao": st.column_config.NumberColumn("Prazo (d)", format="%d")})
elif not ui.lead_padrao(forn):
    st.caption("💡 Cadastre o *lead time padrão* de cada fornecedor para ativar os alertas de atraso e o indicador de prazo.")

# ------------------------------------------------------------------ gráficos
g1, g2 = st.columns([1.7, 1])
with g1:
    m = calc.mensal(E, R, P, ano)
    m["Mês"] = [x[:3] for x in MESES]
    fig = go.Figure()
    fig.add_bar(x=m["Mês"], y=m["Enviado"], name="Enviado", marker_color=ui.COR["enviado"])
    fig.add_bar(x=m["Mês"], y=m["Recebido"], name="Recebido", marker_color=ui.COR["recebido"])
    fig.add_scatter(x=m["Mês"], y=m["Previsto"], name="Previsto", mode="lines+markers",
                    line=dict(color=ui.COR["previsto"], dash="dot", width=2))
    fig.update_layout(title=f"Movimentação mensal — {ano}", barmode="group", height=360,
                      margin=dict(l=10, r=10, t=50, b=10), legend=dict(orientation="h", y=1.12, x=1, xanchor="right"))
    st.plotly_chart(fig, use_container_width=True)
with g2:
    s = calc.saldo(E, R)
    s = s[s["saldo"] != 0].sort_values("saldo")
    fig = go.Figure(go.Bar(x=s["saldo"], y=s["fornecedor"], orientation="h", marker_color=ui.COR["enviado"],
                           text=s["saldo"], textposition="outside"))
    fig.update_layout(title="Peças no fornecedor agora", height=360, margin=dict(l=10, r=30, t=50, b=10))
    if s.empty:
        fig.add_annotation(text="Nenhuma peça em terceiros", showarrow=False, x=0.5, y=0.5, xref="paper", yref="paper")
    st.plotly_chart(fig, use_container_width=True)

# ------------------------------------------------------------------ tabela por fornecedor
st.subheader("Indicadores por fornecedor")
st.caption(f"Período: {ini:%d/%m/%Y} a {fim:%d/%m/%Y} · saldo = posição atual")
res = calc.resumo_fornecedores(E, R, P, ini, fim, lotes)
if res.empty:
    st.info("Ainda não há movimentações. Comece em **Registrar envio**.")
else:
    tot = {"Fornecedor": "TOTAL", **{c: res[c].sum() for c in ["Previsto", "Enviado", "Recebido",
                                                                  "Saldo no fornecedor", "Não conforme + sucata",
                                                                  "Lotes atrasados"]},
           "Aderência (%)": k["aderencia"] * 100, "Índice NC (%)": k["indice_nc"] * 100,
           "Lead time (dias)": k["lead_time"], "No prazo (%)": k["no_prazo"] * 100}
    res = pd.concat([res, pd.DataFrame([tot])], ignore_index=True)
    st.dataframe(res, hide_index=True, use_container_width=True, column_config={
        "Aderência (%)": st.column_config.ProgressColumn("Aderência ao previsto", format="%.0f%%", min_value=0, max_value=100),
        "Índice NC (%)": st.column_config.NumberColumn(format="%.2f%%"),
        "Lead time (dias)": st.column_config.NumberColumn(format="%.1f"),
        "No prazo (%)": st.column_config.NumberColumn(format="%.0f%%"),
    })
    ui.botao_excel({"Indicadores": res, "Mensal": m.drop(columns="mes")}, f"indicadores_{ano}.xlsx")

# ------------------------------------------------------------------ qualidade
Rp = calc.com_total(calc.no_periodo(R, ini, fim))
if Rp["reprovado"].sum():
    st.subheader("Não conformidades no período")
    q1, q2 = st.columns(2)
    por_forn = Rp.groupby("fornecedor")[["qtd_nao_conforme", "qtd_sucata"]].sum().reset_index()
    fig = go.Figure()
    fig.add_bar(x=por_forn["fornecedor"], y=por_forn["qtd_nao_conforme"], name="Não conforme", marker_color="#F59E0B")
    fig.add_bar(x=por_forn["fornecedor"], y=por_forn["qtd_sucata"], name="Sucata", marker_color=ui.COR["nc"])
    fig.update_layout(barmode="stack", height=320, margin=dict(l=10, r=10, t=30, b=10))
    q1.plotly_chart(fig, use_container_width=True)
    motivos = Rp[Rp["reprovado"] > 0].assign(motivo=lambda d: d["motivo_nc"].replace("", "Não informado"))
    motivos = motivos.groupby("motivo")["reprovado"].sum().sort_values(ascending=False).reset_index()
    q2.dataframe(motivos, hide_index=True, use_container_width=True,
                 column_config={"motivo": "Motivo", "reprovado": st.column_config.NumberColumn("Peças", format="%d")})
