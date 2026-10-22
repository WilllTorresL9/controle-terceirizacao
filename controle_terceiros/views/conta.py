import streamlit as st

from core import auth, db, ui

ui.cabecalho("Minha conta", "Alterar a sua senha de acesso")
u = auth.usuario_atual()
st.write(f"Usuário: **{u['usuario']}** · Perfil: **{u['perfil']}**")

with st.form("troca_senha", clear_on_submit=True):
    atual = st.text_input("Senha atual", type="password")
    s1 = st.text_input("Nova senha", type="password")
    s2 = st.text_input("Repita a nova senha", type="password")
    ok = st.form_submit_button("Alterar senha", type="primary")
if ok:
    reg = db.ler("usuarios").set_index("usuario").loc[u["usuario"]]
    if not auth.conferir(atual, reg["senha_hash"]):
        st.error("Senha atual incorreta.")
    elif len(s1) < 6 or s1 != s2:
        st.error("A nova senha precisa ter 6+ caracteres e ser repetida igual.")
    else:
        db.atualizar("usuarios", u["usuario"], {"senha_hash": auth.hash_senha(s1)})
        st.success("Senha alterada.")
