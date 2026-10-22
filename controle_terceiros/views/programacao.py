import datetime as dt

import pandas as pd
import streamlit as st

from core import auth, calc, db, ui
from core.schema import DIAS_CURTO, MESES

ui.cabecalho("Programação de envios", "Quantidade prevista por dia e acompanhamento previsto × realizado")

forn, serv, prod = db.ler("fornecedores"), db.ler("servicos"), db.ler("produtos")
env, rec, prog = db.ler("envios"), db.ler("recebimentos"), db.ler("programacao")
hoje = dt.date.today()

abas = ["📅 Cronograma do mês"] + (["➕ Gerar programação", "✏️ Ajustar dia a dia"] if auth.pode("registrar") else [])
tabs = st.tabs(abas)

# ------------------------------------------------------------------ cronograma (equivalente às abas por fornecedor)
with tabs[0]:
    c1, c2, c3, c4 = st.columns([1.5, 1.5, 0.8, 1])
    f = c1.selectbox("Fornecedor", ui.opcoes(forn), key="cr_forn")
    s = c2.selectbox("Serviço", ["Todos"] + ui.opcoes(serv), key="cr_serv")
    anos = sorted({hoje.year, hoje.year - 1, hoje.year + 1})
    ano = c3.selectbox("Ano", anos, index=anos.index(hoje.year), key="cr_ano")
    mes = c4.selectbox("Mês", range(1, 13), index=hoje.month - 1, format_func=lambda m: MESES[m - 1], key="cr_mes")

    E, R, P = (calc.filtrar(d, [f], s) for d in (env, rec, prog))
    dia = calc.serie_diaria(E, R, P, ano, mes)
    prog_dias = dia[dia["Previsto"] > 0]
    passados = prog_dias[prog_dias["data"] <= pd.Timestamp(hoje)]
    bateu = (passados["Enviado"] >= passados["Previsto"]).sum()

    m = st.columns(5)
    m[0].metric("Previsto no mês", ui.n(dia["Previsto"].sum()), border=True)
    m[1].metric("Enviado", ui.n(dia["Enviado"].sum()), border=True,
                delta=ui.pct(calc.div(dia["Enviado"].sum(), dia["Previsto"].sum()), 0) + " do previsto"
                if dia["Previsto"].sum() else None, delta_color="off")
    m[2].metric("Recebido", ui.n(dia["Recebido"].sum()), border=True)
    m[3].metric("Dias com meta atingida", f"{bateu} de {len(passados)}" if len(passados) else "–", border=True,
                help="Considera só os dias programados que já passaram.")
    m[4].metric("Não conformes", ui.n(dia["Não conforme"].sum()), border=True,
                delta=ui.pct(calc.div(dia["Não conforme"].sum(), dia["Recebido"].sum())) if dia["Recebido"].sum() else None,
                delta_color="off")

    st.dataframe(dia, hide_index=True, use_container_width=True, height=36 + 35 * len(dia),
                 column_config={"data": st.column_config.DateColumn("Data", format="DD/MM/YYYY"),
                                "Perf. dia (%)": st.column_config.NumberColumn(format="%.0f%%"),
                                "NC (%)": st.column_config.NumberColumn(format="%.1f%%")})
    ui.botao_excel({f"{f} {MESES[mes - 1]}": dia}, f"cronograma_{f}_{ano}_{mes:02d}.xlsx")

if not auth.pode("registrar"):
    st.stop()

# ------------------------------------------------------------------ gerar
with tabs[1]:
    st.caption("Gere de uma vez a programação de um período — por exemplo, 75 peças/dia de segunda a sexta.")
    c1, c2, c3 = st.columns(3)
    g_forn = c1.selectbox("Fornecedor", ui.opcoes(db.ativos("fornecedores")), key="g_forn")
    g_serv = c2.selectbox("Serviço", ui.servicos_do_fornecedor(forn, g_forn, ui.opcoes(db.ativos("servicos"))), key="g_serv")
    g_prod = c3.selectbox("Produto", ui.opcoes(db.ativos("produtos")), key="g_prod")
    c4, c5, c6 = st.columns([1.3, 0.8, 1.8])
    per = c4.date_input("Período", value=(hoje, hoje + dt.timedelta(days=30)), format="DD/MM/YYYY", key="g_per")
    qtd = c5.number_input("Peças por dia", min_value=1, step=1, value=75)
    dsem = c6.multiselect("Dias da semana", DIAS_CURTO, default=DIAS_CURTO[:5])
    substituir = st.checkbox("Substituir a programação já existente neste período (mesmo fornecedor/serviço/produto)",
                             value=True)

    if len(per) == 2:
        datas = [d for d in pd.date_range(per[0], per[1]) if DIAS_CURTO[d.weekday()] in dsem]
        st.info(f"Serão programados **{len(datas)} dias** × {qtd} = **{ui.n(len(datas) * qtd)} peças** "
                f"de {per[0]:%d/%m/%Y} a {per[1]:%d/%m/%Y}.")
        if st.button("Gerar programação", type="primary", disabled=not datas):
            mesma = ((prog["fornecedor"] == g_forn) & (prog["servico"] == g_serv) & (prog["produto"] == g_prod)
                     & (prog["data"] >= pd.Timestamp(per[0])) & (prog["data"] <= pd.Timestamp(per[1])))
            if substituir and mesma.any():
                db.substituir_tudo("programacao", prog[~mesma])
            db.inserir("programacao", [{"data": d.date(), "fornecedor": g_forn, "servico": g_serv,
                                        "produto": g_prod, "qtd_prevista": int(qtd)} for d in datas])
            st.toast(f"{len(datas)} dias programados.", icon="📅")
            st.rerun()

# ------------------------------------------------------------------ ajustar
with tabs[2]:
    st.caption("Edite as quantidades de cada dia. Zere a quantidade para remover o dia da programação.")
    c1, c2, c3, c4 = st.columns([1.5, 1.5, 0.8, 1])
    a_forn = c1.selectbox("Fornecedor", ui.opcoes(forn), key="a_forn")
    a_serv = c2.selectbox("Serviço", ui.opcoes(serv), key="a_serv")
    a_ano = c3.selectbox("Ano", anos, index=anos.index(hoje.year), key="a_ano")
    a_mes = c4.selectbox("Mês", range(1, 13), index=hoje.month - 1, format_func=lambda m: MESES[m - 1], key="a_mes")
    ini, fim = calc.periodo(a_ano, a_mes)
    filtro = ((prog["fornecedor"] == a_forn) & (prog["servico"] == a_serv)
              & (prog["data"] >= ini) & (prog["data"] <= fim))
    atual = prog[filtro].sort_values("data")
    if atual.empty:
        st.info("Não há programação neste mês para esta combinação. Use a aba **Gerar programação**.")
    else:
        editado = st.data_editor(atual[["id", "data", "produto", "qtd_prevista"]], hide_index=True,
                                 use_container_width=True, disabled=["id", "data", "produto"],
                                 key=f"ed_{a_forn}_{a_serv}_{a_ano}_{a_mes}",
                                 column_config={"data": st.column_config.DateColumn("Data", format="DD/MM/YYYY"),
                                                "qtd_prevista": st.column_config.NumberColumn("Previsto", min_value=0, step=1)})
        if st.button("💾 Salvar ajustes", type="primary"):
            novo = prog.set_index("id")
            novo.loc[editado["id"], "qtd_prevista"] = editado.set_index("id")["qtd_prevista"].fillna(0).astype(int)
            novo = novo[novo["qtd_prevista"] > 0].reset_index()
            db.substituir_tudo("programacao", novo)
            st.toast("Programação atualizada.", icon="✅")
            st.rerun()
