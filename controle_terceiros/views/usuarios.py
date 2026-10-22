import streamlit as st

from core import auth, db, ui
from core.schema import PERFIS

if not auth.pode("admin"):
    st.error("Acesso restrito ao administrador.")
    st.stop()

ui.cabecalho("Usuários", "Quem pode acessar o sistema e o que cada um pode fazer")
df = db.ler("usuarios")
st.dataframe(df[["usuario", "nome", "perfil", "ativo", "criado_em"]], hide_index=True, use_container_width=True,
             column_config={"usuario": "Usuário", "nome": "Nome", "perfil": "Perfil", "ativo": "Ativo",
                            "criado_em": "Criado em"})
with st.expander("ℹ️ Perfis de acesso"):
    for p, d in PERFIS.items():
        st.markdown(f"- **{p}** — {d}")

c1, c2 = st.columns(2)
with c1:
    st.subheader("Novo usuário")
    with st.form("novo_user", clear_on_submit=True):
        nome = st.text_input("Nome")
        login = st.text_input("Usuário (login)").strip().lower()
        perfil = st.selectbox("Perfil", list(PERFIS), index=1)
        senha = st.text_input("Senha inicial", type="password")
        ok = st.form_submit_button("Criar usuário", type="primary")
    if ok:
        if not (nome and login and senha):
            st.error("Preencha todos os campos.")
        elif login in df["usuario"].tolist():
            st.error("Esse login já existe.")
        elif len(senha) < 6:
            st.error("Senha com pelo menos 6 caracteres.")
        else:
            db.inserir("usuarios", {"usuario": login, "nome": nome, "perfil": perfil,
                                    "senha_hash": auth.hash_senha(senha), "ativo": "Sim"})
            st.rerun()

with c2:
    st.subheader("Alterar usuário")
    outros = df[df["usuario"] != auth.usuario_atual()["usuario"]]
    if outros.empty:
        st.caption("Nenhum outro usuário cadastrado.")
    else:
        alvo = st.selectbox("Usuário", outros["usuario"].tolist())
        reg = outros[outros["usuario"] == alvo].iloc[0]
        with st.form(f"edit_user_{alvo}"):
            perfil = st.selectbox("Perfil", list(PERFIS), index=list(PERFIS).index(reg["perfil"]) if reg["perfil"] in PERFIS else 2)
            ativo = st.selectbox("Ativo", ["Sim", "Não"], index=0 if reg["ativo"] != "Não" else 1)
            nova = st.text_input("Redefinir senha (deixe vazio para manter)", type="password")
            ok2 = st.form_submit_button("Salvar", type="primary")
        if ok2:
            mud = {"perfil": perfil, "ativo": ativo}
            if nova:
                mud["senha_hash"] = auth.hash_senha(nova)
            db.atualizar("usuarios", alvo, mud)
            st.toast("Usuário atualizado.", icon="✅")
            st.rerun()
