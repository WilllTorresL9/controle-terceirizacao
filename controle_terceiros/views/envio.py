import datetime as dt

import pandas as pd
import streamlit as st

from core import auth, calc, db, ui

ui.cabecalho("Registrar envio", "Saída de peças para o fornecedor externo")

forn, serv, prod = db.ativos("fornecedores"), db.ativos("servicos"), db.ativos("produtos")
env, rec, prog = db.ler("envios"), db.ler("recebimentos"), db.ler("programacao")
u = auth.usuario_atual()
hoje = pd.Timestamp(dt.date.today())

if msg := st.session_state.pop("msg_envio", None):
    st.success(msg, icon="✅")

if auth.pode("registrar"):
    if forn.empty or serv.empty or prod.empty:
        st.warning("Cadastre ao menos um fornecedor, um serviço e um produto antes de registrar envios.")
        st.stop()

    c1, c2, c3 = st.columns(3)
    fornecedor = c1.selectbox("Fornecedor", ui.opcoes(forn))
    servico = c2.selectbox("Serviço a realizar", ui.servicos_do_fornecedor(forn, fornecedor, ui.opcoes(serv)))
    produto = c3.selectbox("Produto", ui.opcoes(prod))

    # contexto antes de lançar
    chave = lambda d: d[(d["fornecedor"] == fornecedor) & (d["servico"] == servico) & (d["produto"] == produto)]
    s = calc.saldo(chave(env), chave(rec))
    saldo_atual = int(s["saldo"].sum()) if not s.empty else 0
    prev_hoje = int(chave(prog)[chave(prog)["data"] == hoje]["qtd_prevista"].sum())
    env_hoje = int(chave(env)[chave(env)["data"] == hoje]["quantidade"].sum())
    i1, i2, i3 = st.columns(3)
    i1.markdown(f"<div class='saldo-box'>Já está no fornecedor<br><b>{ui.n(saldo_atual)} peças</b></div>", unsafe_allow_html=True)
    i2.markdown(f"<div class='saldo-box'>Previsto para hoje<br><b>{ui.n(prev_hoje)} peças</b></div>", unsafe_allow_html=True)
    i3.markdown(f"<div class='saldo-box'>Enviado hoje até agora<br><b>{ui.n(env_hoje)} peças</b></div>", unsafe_allow_html=True)
    st.write("")

    with st.form("form_envio", clear_on_submit=True):
        a, b, c, d = st.columns([1, 1, 1, 1])
        data = a.date_input("Data de saída", value=dt.date.today(), format="DD/MM/YYYY")
        quantidade = b.number_input("Quantidade de peças", min_value=0, step=1, value=None, placeholder="0")
        nf = c.text_input("NF de remessa *")
        op = d.text_input("OP")
        e, f, g = st.columns([1, 1, 2])
        corrida = e.text_input("Nº corrida")
        responsavel = f.text_input("Responsável", value=u["nome"])
        obs = g.text_input("Observação")
        enviar = st.form_submit_button("📤 Registrar envio", type="primary", use_container_width=True)

    if enviar:
        erros = []
        if not quantidade:
            erros.append("Informe a quantidade.")
        if not nf.strip():
            erros.append("Informe a NF de remessa.")
        if data > dt.date.today():
            erros.append("A data de saída não pode ser futura.")
        dup = env[(env["data"] == pd.Timestamp(data)) & (env["fornecedor"] == fornecedor)
                  & (env["nf"].astype(str) == nf.strip()) & (env["quantidade"] == (quantidade or 0))]
        if not dup.empty:
            erros.append(f"Este envio parece já ter sido lançado ({dup.iloc[0]['id']}).")
        if erros:
            for x in erros:
                st.error(x)
        else:
            novo = db.inserir("envios", {"data": data, "fornecedor": fornecedor, "servico": servico,
                                         "produto": produto, "quantidade": int(quantidade), "nf": nf.strip(),
                                         "op": op.strip(), "corrida": corrida.strip(),
                                         "responsavel": responsavel.strip(), "observacao": obs.strip()})[0]
            st.session_state["msg_envio"] = f"Envio **{novo}** registrado: {quantidade} peças para {fornecedor} (NF {nf})."
            st.rerun()
else:
    st.info("Seu perfil é de consulta: você pode visualizar, mas não registrar envios.")

# ------------------------------------------------------------------ histórico
env = db.ler("envios")
st.subheader("Envios lançados")
b1, b2 = st.columns([2, 1])
termo = b1.text_input("🔎 Buscar", placeholder="NF, OP, corrida, fornecedor, responsável…", key="busca_env")
dias = b2.selectbox("Período", [7, 30, 90, 365, 0], index=1,
                    format_func=lambda x: "Tudo" if x == 0 else f"Últimos {x} dias")
lista = env if dias == 0 else env[env["data"] >= hoje - pd.Timedelta(days=dias)]
lista = ui.busca_texto(lista, termo, ["id", "fornecedor", "servico", "produto", "nf", "op", "corrida", "responsavel", "observacao"])
lista = lista.sort_values(["data", "id"], ascending=False)
st.dataframe(lista[["id", "data", "fornecedor", "servico", "produto", "quantidade", "nf", "op", "corrida",
                    "responsavel", "observacao", "criado_por"]],
             hide_index=True, use_container_width=True, column_config=ui.config_colunas_mov())
st.caption(f"{len(lista)} envio(s) · {ui.n(lista['quantidade'].sum())} peças")

if auth.pode("registrar"):
    ops_forn, ops_serv, ops_prod = ui.opcoes(db.ler("fornecedores")), ui.opcoes(db.ler("servicos")), ui.opcoes(db.ler("produtos"))
    ui.secao_edicao("envios", env, [
        ("data", "data", "Data de saída"), ("fornecedor", "select", "Fornecedor", ops_forn),
        ("servico", "select", "Serviço", ops_serv), ("produto", "select", "Produto", ops_prod),
        ("quantidade", "int", "Quantidade"), ("nf", "texto", "NF"), ("op", "texto", "OP"),
        ("corrida", "texto", "Corrida"), ("responsavel", "texto", "Responsável"),
        ("observacao", "texto", "Observação"),
    ], "um envio",
        lambda r: f"{r['id']} · {r['data']:%d/%m/%Y} · {r['fornecedor']} · {r['quantidade']} pç · NF {r['nf']}")
