import datetime as dt

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from core import calc, db, ui

ui.cabecalho("Consulta e rastreio", "Encontre qualquer NF, OP ou corrida e veja onde estão as peças")

env, rec = db.ler("envios"), calc.com_total(db.ler("recebimentos"))
forn = db.ler("fornecedores")
hoje = dt.date.today()

aba1, aba2, aba3 = st.tabs(["🔎 Busca geral", "📦 Peças no fornecedor", "📒 Extrato por fornecedor"])

# ------------------------------------------------------------------ busca
with aba1:
    c1, c2, c3 = st.columns([2.2, 1.2, 1])
    termo = c1.text_input("Buscar", placeholder="Ex.: 163384   ·   op956429   ·   lotus trinca", key="busca_geral")
    datas = c2.date_input("Período", value=(dt.date(hoje.year, 1, 1), hoje), format="DD/MM/YYYY")
    tipo = c3.radio("Mostrar", ["Tudo", "Envios", "Recebimentos"], horizontal=True)
    ini, fim = (pd.Timestamp(datas[0]), pd.Timestamp(datas[-1])) if datas else (pd.Timestamp.min, pd.Timestamp.max)

    e = pd.DataFrame({"Tipo": "📤 Envio", "ID": env["id"], "data": env["data"], "Fornecedor": env["fornecedor"],
                      "Serviço": env["servico"], "Produto": env["produto"], "Quantidade": env["quantidade"],
                      "Reprovado": 0, "NF": env["nf"], "OP / NF ref.": env["op"], "Corrida": env["corrida"],
                      "Detalhe": env["observacao"], "Responsável": env["responsavel"]})
    r = pd.DataFrame({"Tipo": "📥 Recebimento", "ID": rec["id"], "data": rec["data"], "Fornecedor": rec["fornecedor"],
                      "Serviço": rec["servico"], "Produto": rec["produto"], "Quantidade": rec["total"],
                      "Reprovado": rec["reprovado"], "NF": rec["nf_retorno"], "OP / NF ref.": rec["nf_referencia"],
                      "Corrida": "", "Detalhe": (rec["motivo_nc"] + " " + rec["observacao"]).str.strip(),
                      "Responsável": rec["responsavel"]})
    base = {"Tudo": [e, r], "Envios": [e], "Recebimentos": [r]}[tipo]
    tudo = pd.concat(base, ignore_index=True)
    tudo = calc.no_periodo(tudo, ini, fim)
    tudo = ui.busca_texto(tudo, termo, ["ID", "Fornecedor", "Serviço", "Produto", "NF", "OP / NF ref.",
                                        "Corrida", "Detalhe", "Responsável"])
    tudo = tudo.sort_values(["data", "ID"], ascending=False)
    m1, m2, m3 = st.columns(3)
    m1.metric("Registros", ui.n(len(tudo)), border=True)
    m2.metric("Peças enviadas", ui.n(tudo.loc[tudo["Tipo"].str.contains("Envio"), "Quantidade"].sum()), border=True)
    m3.metric("Peças recebidas", ui.n(tudo.loc[tudo["Tipo"].str.contains("Receb"), "Quantidade"].sum()), border=True)
    st.dataframe(tudo, hide_index=True, use_container_width=True,
                 column_config={"data": st.column_config.DateColumn("Data", format="DD/MM/YYYY"),
                                "Quantidade": st.column_config.NumberColumn(format="%d"),
                                "Reprovado": st.column_config.NumberColumn(format="%d")})
    ui.botao_excel({"Busca": tudo}, "busca_terceirizacao.xlsx")

# ------------------------------------------------------------------ lotes
with aba2:
    lotes = calc.lotes_fifo(env, rec, ui.lead_padrao(forn))
    c1, c2 = st.columns([2, 1])
    f_sel = c1.multiselect("Fornecedor", ui.opcoes(forn), placeholder="Todos", key="lotes_forn")
    concl = c2.toggle("Mostrar também lotes concluídos", value=False)
    L = calc.filtrar(lotes, f_sel)
    if not concl:
        L = L[L["pendente"] > 0]
    pend = L[L["pendente"] > 0]
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Peças fora de casa", ui.n(pend["pendente"].sum()), border=True)
    m2.metric("Lotes em aberto", ui.n(len(pend)), border=True)
    m3.metric("Lote mais antigo", f"{pend['dias'].max()} dias" if len(pend) else "–", border=True)
    m4.metric("Lotes atrasados", ui.n((pend["status"] == "🔴 Atrasado").sum()), border=True)
    st.dataframe(L.sort_values(["pendente", "dias"], ascending=[False, False]).drop(columns=["no_prazo"]),
                 hide_index=True, use_container_width=True,
                 column_config={**ui.config_colunas_mov(),
                                "data": st.column_config.DateColumn("Enviado em", format="DD/MM/YYYY"),
                                "recebido": st.column_config.NumberColumn("Voltou", format="%d"),
                                "pendente": st.column_config.NumberColumn("Falta voltar", format="%d"),
                                "status": "Situação",
                                "dias": st.column_config.NumberColumn("Dias fora", format="%d"),
                                "lead_padrao": st.column_config.NumberColumn("Prazo (d)", format="%d"),
                                "lead_time": st.column_config.NumberColumn("Lead time (d)", format="%.1f"),
                                "ultimo_retorno": st.column_config.DateColumn("Último retorno", format="DD/MM/YYYY")})
    st.caption("Os recebimentos são casados com os envios por ordem de chegada (o primeiro lote enviado é o "
               "primeiro a voltar), separadamente por fornecedor, serviço e produto.")
    ui.botao_excel({"Lotes": L}, "lotes_fornecedor.xlsx")

# ------------------------------------------------------------------ extrato
with aba3:
    c1, c2 = st.columns([1, 1])
    f_ext = c1.selectbox("Fornecedor", ui.opcoes(forn), key="ext_forn")
    servs = ["Todos"] + sorted(env.loc[env["fornecedor"] == f_ext, "servico"].unique().tolist())
    s_ext = c2.selectbox("Serviço", servs, key="ext_serv")
    ex = calc.extrato(calc.filtrar(env, [f_ext], s_ext), calc.filtrar(rec, [f_ext], s_ext))
    if ex.empty:
        st.info("Sem movimentações para este fornecedor.")
    else:
        neg = ex[ex["Saldo no fornecedor"] < 0]
        if not neg.empty:
            st.warning(f"⚠️ O saldo ficou negativo em {neg.iloc[0]['data']:%d/%m/%Y}: há recebimento lançado antes do "
                       "envio correspondente (data ou NF provavelmente incorreta). Vale conferir.")
        fig = go.Figure(go.Scatter(x=ex["data"], y=ex["Saldo no fornecedor"], mode="lines+markers", line_shape="hv",
                                   line=dict(color=ui.COR["enviado"], width=2), fill="tozeroy",
                                   fillcolor="rgba(194,65,12,0.10)"))
        fig.update_layout(title="Saldo de peças no fornecedor ao longo do tempo", height=300,
                          margin=dict(l=10, r=10, t=50, b=10))
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(ex.iloc[::-1], hide_index=True, use_container_width=True,
                     column_config={"data": st.column_config.DateColumn("Data", format="DD/MM/YYYY")})
        ui.botao_excel({"Extrato": ex}, f"extrato_{f_ext}.xlsx")
