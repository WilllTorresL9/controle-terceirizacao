import datetime as dt

import pandas as pd
import streamlit as st

from core import auth, calc, db, ui
from core.schema import MOTIVOS_NC

ui.cabecalho("Registrar recebimento", "Retorno de peças do fornecedor, com aprovação, não conformidade e sucata")

forn_all = db.ler("fornecedores")
forn, serv, prod = db.ativos("fornecedores"), db.ativos("servicos"), db.ativos("produtos")
env, rec = db.ler("envios"), db.ler("recebimentos")
u = auth.usuario_atual()
hoje = pd.Timestamp(dt.date.today())

if msg := st.session_state.pop("msg_rec", None):
    st.success(msg, icon="✅")

if auth.pode("registrar"):
    # Mostra primeiro quem tem peças paradas — é de quem se espera retorno
    s = calc.saldo(env, rec)
    com_saldo = s[s["saldo"] > 0].sort_values("saldo", ascending=False)["fornecedor"].tolist()
    lista_forn = com_saldo + [f for f in ui.opcoes(forn) if f not in com_saldo]
    if not lista_forn:
        st.warning("Nenhum fornecedor cadastrado.")
        st.stop()

    c1, c2, c3 = st.columns(3)
    fornecedor = c1.selectbox("Fornecedor", lista_forn,
                              format_func=lambda f: f"{f}  ·  {int(s.loc[s['fornecedor'] == f, 'saldo'].sum())} pç no fornecedor"
                              if f in com_saldo else f)
    servico = c2.selectbox("Serviço realizado", ui.servicos_do_fornecedor(forn, fornecedor, ui.opcoes(serv)))
    produto = c3.selectbox("Produto", ui.opcoes(prod))

    chave = lambda d: d[(d["fornecedor"] == fornecedor) & (d["servico"] == servico) & (d["produto"] == produto)]
    lotes = calc.lotes_fifo(chave(env), chave(rec), ui.lead_padrao(forn_all))
    pend = lotes[lotes["pendente"] > 0]
    saldo_atual = int(pend["pendente"].sum())

    i1, i2 = st.columns([1, 3])
    i1.markdown(f"<div class='saldo-box'>Saldo no fornecedor<br><b>{ui.n(saldo_atual)} peças</b></div>", unsafe_allow_html=True)
    with i2:
        if pend.empty:
            st.caption("Não há lotes pendentes para esta combinação de fornecedor/serviço/produto.")
        else:
            st.dataframe(pend[["data", "nf", "op", "quantidade", "pendente", "dias", "status"]],
                         hide_index=True, use_container_width=True, height=min(38 + 35 * len(pend), 180),
                         column_config={**ui.config_colunas_mov(),
                                        "data": st.column_config.DateColumn("Enviado em", format="DD/MM/YYYY"),
                                        "pendente": st.column_config.NumberColumn("Falta voltar", format="%d"),
                                        "dias": st.column_config.NumberColumn("Dias fora", format="%d"),
                                        "status": "Situação"})

    with st.form("form_rec", clear_on_submit=True):
        a, b, c, d = st.columns(4)
        data = a.date_input("Data do recebimento", value=dt.date.today(), format="DD/MM/YYYY")
        aprov = b.number_input("✅ Aprovadas", min_value=0, step=1, value=None, placeholder="0")
        nconf = c.number_input("⚠️ Não conformes", min_value=0, step=1, value=None, placeholder="0",
                               help="Peças reprovadas que podem ser retrabalhadas/devolvidas.")
        sucata = d.number_input("❌ Sucata", min_value=0, step=1, value=None, placeholder="0")
        e, f, g = st.columns([1.3, 1, 1])
        motivo = e.selectbox("Motivo da não conformidade", [""] + MOTIVOS_NC,
                             help="Obrigatório quando houver não conformes ou sucata.")
        nf_ret = f.text_input("NF de retorno *")
        responsavel = g.text_input("Responsável", value=u["nome"])
        h, i = st.columns([1.3, 2])
        nfs_ref = h.multiselect("NF(s) de envio correspondentes", pend["nf"].astype(str).unique().tolist(),
                                help="Opcional: ajuda na rastreabilidade.")
        obs = i.text_input("Observação / detalhe da NC")
        acima = st.checkbox("Confirmo recebimento acima do saldo registrado no fornecedor")
        salvar = st.form_submit_button("📥 Registrar recebimento", type="primary", use_container_width=True)

    if salvar:
        aprov, nconf, sucata = int(aprov or 0), int(nconf or 0), int(sucata or 0)
        total, erros = aprov + nconf + sucata, []
        if total == 0:
            erros.append("Informe ao menos uma quantidade.")
        if not nf_ret.strip():
            erros.append("Informe a NF de retorno.")
        if (nconf + sucata) and not motivo:
            erros.append("Informe o motivo da não conformidade.")
        if data > dt.date.today():
            erros.append("A data não pode ser futura.")
        if total > saldo_atual and not acima:
            erros.append(f"Quantidade ({total}) maior que o saldo no fornecedor ({saldo_atual}). "
                         "Confira se o envio foi lançado ou marque a confirmação.")
        if erros:
            for x in erros:
                st.error(x)
        else:
            novo = db.inserir("recebimentos", {
                "data": data, "fornecedor": fornecedor, "servico": servico, "produto": produto,
                "qtd_aprovada": aprov, "qtd_nao_conforme": nconf, "qtd_sucata": sucata,
                "motivo_nc": motivo if (nconf + sucata) else "", "nf_retorno": nf_ret.strip(),
                "nf_referencia": "; ".join(nfs_ref), "responsavel": responsavel.strip(), "observacao": obs.strip()})[0]
            st.session_state["msg_rec"] = (f"Recebimento **{novo}** registrado: {total} peças de {fornecedor} "
                                           f"({aprov} aprovadas, {nconf} NC, {sucata} sucata).")
            st.rerun()
else:
    st.info("Seu perfil é de consulta: você pode visualizar, mas não registrar recebimentos.")

# ------------------------------------------------------------------ histórico
rec = calc.com_total(db.ler("recebimentos"))
st.subheader("Recebimentos lançados")
b1, b2 = st.columns([2, 1])
termo = b1.text_input("🔎 Buscar", placeholder="NF, fornecedor, motivo, responsável…", key="busca_rec")
dias = b2.selectbox("Período", [7, 30, 90, 365, 0], index=1,
                    format_func=lambda x: "Tudo" if x == 0 else f"Últimos {x} dias", key="per_rec")
lista = rec if dias == 0 else rec[rec["data"] >= hoje - pd.Timedelta(days=dias)]
lista = ui.busca_texto(lista, termo, ["id", "fornecedor", "servico", "produto", "nf_retorno", "nf_referencia",
                                      "motivo_nc", "responsavel", "observacao"])
lista = lista.sort_values(["data", "id"], ascending=False)
st.dataframe(lista[["id", "data", "fornecedor", "servico", "qtd_aprovada", "qtd_nao_conforme", "qtd_sucata", "total",
                    "motivo_nc", "nf_retorno", "nf_referencia", "responsavel", "observacao", "criado_por"]],
             hide_index=True, use_container_width=True, column_config=ui.config_colunas_mov())
st.caption(f"{len(lista)} recebimento(s) · {ui.n(lista['total'].sum())} peças · "
           f"{ui.n(lista['reprovado'].sum())} reprovadas")

if auth.pode("registrar"):
    ui.secao_edicao("recebimentos", rec, [
        ("data", "data", "Data"), ("fornecedor", "select", "Fornecedor", ui.opcoes(forn_all)),
        ("servico", "select", "Serviço", ui.opcoes(db.ler("servicos"))),
        ("produto", "select", "Produto", ui.opcoes(db.ler("produtos"))),
        ("qtd_aprovada", "int", "Aprovadas"), ("qtd_nao_conforme", "int", "Não conformes"),
        ("qtd_sucata", "int", "Sucata"), ("motivo_nc", "select", "Motivo NC", [""] + MOTIVOS_NC),
        ("nf_retorno", "texto", "NF retorno"), ("nf_referencia", "texto", "NF(s) de envio"),
        ("responsavel", "texto", "Responsável"), ("observacao", "texto", "Observação"),
    ], "um recebimento",
        lambda r: f"{r['id']} · {r['data']:%d/%m/%Y} · {r['fornecedor']} · {r['total']} pç · NF {r['nf_retorno']}")
