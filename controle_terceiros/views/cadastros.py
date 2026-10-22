import pandas as pd
import streamlit as st

from core import auth, db, importador, ui

ui.cabecalho("Cadastros", "Fornecedores externos, tipos de serviço e produtos")

admin = auth.pode("admin")
abas = ["🏭 Fornecedores", "🛠️ Serviços", "📦 Produtos"] + (["📥 Importar planilha antiga"] if admin else [])
tabs = st.tabs(abas)
if not admin:
    st.caption("Somente administradores alteram cadastros.")

# ------------------------------------------------------------------ fornecedores
with tabs[0]:
    forn, serv = db.ler("fornecedores"), db.ler("servicos")
    termo = st.text_input("🔎 Buscar fornecedor", placeholder="Nome, cidade, serviço, contato…")
    lista = ui.busca_texto(forn, termo, ["nome", "razao_social", "cnpj", "contato", "cidade", "servicos", "email"])
    st.dataframe(lista[["id", "nome", "razao_social", "cnpj", "servicos", "lead_time_dias", "contato", "telefone",
                        "email", "cidade", "ativo", "observacoes"]],
                 hide_index=True, use_container_width=True,
                 column_config={"nome": "Fornecedor", "razao_social": "Razão social", "cnpj": "CNPJ",
                                "servicos": "Serviços que realiza",
                                "lead_time_dias": st.column_config.NumberColumn("Lead time padrão (d)", format="%.0f"),
                                "contato": "Contato", "telefone": "Telefone", "email": "E-mail",
                                "cidade": "Cidade", "ativo": "Ativo", "observacoes": "Observações"})

    if admin:
        modo = st.radio("Ação", ["Novo fornecedor", "Editar fornecedor"], horizontal=True, key="modo_forn")
        reg = {}
        if modo == "Editar fornecedor" and not forn.empty:
            fid = st.selectbox("Fornecedor", forn["id"], format_func=lambda i: forn.loc[forn["id"] == i, "nome"].iloc[0])
            reg = forn[forn["id"] == fid].iloc[0].to_dict()
        servs_atuais = [s.strip() for s in str(reg.get("servicos", "")).split(";") if s.strip()]
        with st.form(f"form_forn_{reg.get('id', 'novo')}", clear_on_submit=not reg):
            a, b, c = st.columns(3)
            nome = a.text_input("Nome fantasia *", value=reg.get("nome", ""), disabled=bool(reg),
                                help="O nome identifica o fornecedor nos lançamentos e não pode ser alterado depois.")
            razao = b.text_input("Razão social", value=reg.get("razao_social", ""))
            cnpj = c.text_input("CNPJ", value=reg.get("cnpj", ""))
            d, e, f = st.columns(3)
            contato = d.text_input("Contato", value=reg.get("contato", ""))
            tel = e.text_input("Telefone", value=reg.get("telefone", ""))
            email = f.text_input("E-mail", value=reg.get("email", ""))
            g, h, i, j = st.columns([1, 2, 1, 0.7])
            cidade = g.text_input("Cidade", value=reg.get("cidade", ""))
            servicos = h.multiselect("Serviços que realiza", ui.opcoes(serv),
                                     default=[s for s in servs_atuais if s in ui.opcoes(serv)])
            lead = i.number_input("Lead time padrão (dias)", min_value=0, step=1,
                                  value=int(reg.get("lead_time_dias") or 0),
                                  help="Prazo esperado entre envio e retorno. Usado nos alertas de atraso.")
            ativo = j.selectbox("Ativo", ["Sim", "Não"], index=0 if reg.get("ativo", "Sim") != "Não" else 1)
            obs = st.text_input("Observações", value=reg.get("observacoes", ""))
            ok = st.form_submit_button("💾 Salvar", type="primary")
        if ok:
            dados = {"razao_social": razao, "cnpj": cnpj, "contato": contato, "telefone": tel, "email": email,
                     "cidade": cidade, "servicos": "; ".join(servicos), "lead_time_dias": lead or "",
                     "ativo": ativo, "observacoes": obs}
            if reg:
                db.atualizar("fornecedores", reg["id"], dados)
                st.toast("Fornecedor atualizado.", icon="✅")
                st.rerun()
            elif not nome.strip():
                st.error("Informe o nome.")
            elif nome.strip().upper() in forn["nome"].str.upper().tolist():
                st.error("Já existe um fornecedor com esse nome.")
            else:
                db.inserir("fornecedores", {"nome": nome.strip().upper(), **dados})
                st.toast("Fornecedor cadastrado.", icon="✅")
                st.rerun()


# ------------------------------------------------------------------ serviços / produtos (mesma lógica)
def cadastro_simples(tabela: str, rotulo: str, extras: list[tuple[str, str]]):
    df = db.ler(tabela)
    st.dataframe(df[["id", "nome"] + [c for c, _ in extras] + ["ativo"]], hide_index=True, use_container_width=True,
                 column_config={"nome": rotulo, **{c: r for c, r in extras}, "ativo": "Ativo"})
    if not admin:
        return
    modo = st.radio("Ação", [f"Novo", f"Editar"], horizontal=True, key=f"modo_{tabela}")
    reg = {}
    if modo == "Editar" and not df.empty:
        rid = st.selectbox(rotulo, df["id"], format_func=lambda i: df.loc[df["id"] == i, "nome"].iloc[0], key=f"sel_{tabela}")
        reg = df[df["id"] == rid].iloc[0].to_dict()
    with st.form(f"form_{tabela}_{reg.get('id', 'novo')}", clear_on_submit=not reg):
        cols = st.columns(len(extras) + 2)
        nome = cols[0].text_input(f"{rotulo} *", value=reg.get("nome", ""), disabled=bool(reg))
        vals = {c: cols[k + 1].text_input(r, value=reg.get(c, "")) for k, (c, r) in enumerate(extras)}
        ativo = cols[-1].selectbox("Ativo", ["Sim", "Não"], index=0 if reg.get("ativo", "Sim") != "Não" else 1)
        ok = st.form_submit_button("💾 Salvar", type="primary")
    if ok:
        if reg:
            db.atualizar(tabela, reg["id"], {**vals, "ativo": ativo})
            st.rerun()
        elif not nome.strip():
            st.error("Informe o nome.")
        elif nome.strip().lower() in df["nome"].str.lower().tolist():
            st.error("Já existe um cadastro com esse nome.")
        else:
            db.inserir(tabela, {"nome": nome.strip(), **vals, "ativo": ativo})
            st.rerun()


with tabs[1]:
    cadastro_simples("servicos", "Serviço", [("descricao", "Descrição")])
with tabs[2]:
    cadastro_simples("produtos", "Produto", [("codigo", "Código"), ("descricao", "Descrição")])

# ------------------------------------------------------------------ importação
if admin:
    with tabs[3]:
        st.markdown("Envie a planilha Excel usada até hoje (abas **ENVIO**, **RECEBIMENTO** e uma aba por fornecedor). "
                    "O sistema importa envios, recebimentos e a programação prevista, ignorando o que já foi importado.")
        arq = st.file_uploader("Planilha (.xlsx)", type=["xlsx", "xlsm"])
        if arq:
            dados = importador.ler_planilha_antiga(arq)
            existentes = {"envios": db.ler("envios"), "recebimentos": db.ler("recebimentos"),
                          "programacao": db.ler("programacao")}
            campos = {"envios": ["data", "fornecedor", "quantidade", "nf"],
                      "recebimentos": ["data", "fornecedor", "qtd_aprovada", "nf_retorno"],
                      "programacao": ["data", "fornecedor", "servico", "qtd_prevista"]}
            novos = {t: importador.remover_duplicados(d, existentes[t], campos[t]) for t, d in dados.items()}
            c = st.columns(3)
            for col, (t, d) in zip(c, novos.items()):
                col.metric(t.capitalize(), f"{len(d)} novos", f"{len(dados[t]) - len(d)} já existentes", delta_color="off",
                           border=True)
            for t, d in novos.items():
                if not d.empty:
                    with st.expander(f"Prévia — {t}"):
                        st.dataframe(d, hide_index=True, use_container_width=True)
            faltam = sorted(set(pd.concat([d["fornecedor"] for d in novos.values() if not d.empty] or [pd.Series(dtype=str)]))
                            - set(db.ler("fornecedores")["nome"]))
            if faltam:
                st.info(f"Fornecedores que serão cadastrados automaticamente: {', '.join(faltam)}")
            if any(len(d) for d in novos.values()) and st.button("Importar agora", type="primary"):
                for nome in faltam:
                    db.inserir("fornecedores", {"nome": nome, "ativo": "Sim"})
                for t, d in novos.items():
                    if not d.empty:
                        db.inserir(t, d.to_dict("records"))
                st.success("Importação concluída.")
                st.balloons()
