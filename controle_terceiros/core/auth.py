"""Login simples (usuário + senha) com perfis de acesso."""
from __future__ import annotations

import hashlib
import hmac
import secrets

import streamlit as st

from core import db


def hash_senha(senha: str, sal: str | None = None) -> str:
    sal = sal or secrets.token_hex(8)
    h = hashlib.pbkdf2_hmac("sha256", senha.encode(), sal.encode(), 120_000).hex()
    return f"{sal}${h}"


def conferir(senha: str, armazenado: str) -> bool:
    try:
        sal, _ = armazenado.split("$", 1)
    except ValueError:
        return False
    return hmac.compare_digest(hash_senha(senha, sal), armazenado)


def usuario_atual() -> dict | None:
    return st.session_state.get("usuario")


def pode(acao: str) -> bool:
    u = usuario_atual()
    if not u:
        return False
    perfil = u.get("perfil", "consulta")
    if acao == "admin":
        return perfil == "admin"
    if acao == "registrar":
        return perfil in ("admin", "operador")
    return True


def pode_editar_registro(criado_por: str) -> bool:
    u = usuario_atual()
    return bool(u) and (u["perfil"] == "admin" or (u["perfil"] == "operador" and criado_por == u["usuario"]))


def _caixa_central():
    _, meio, _ = st.columns([1, 1.3, 1])
    return meio


def tela_login():
    with _caixa_central():
        st.markdown("<div class='login-titulo'>Controle de Terceirização</div>"
                    "<div class='login-sub'>Envio e retorno de peças em fornecedores externos</div>",
                    unsafe_allow_html=True)
        with st.form("login"):
            usuario = st.text_input("Usuário").strip().lower()
            senha = st.text_input("Senha", type="password")
            if st.form_submit_button("Entrar", type="primary", use_container_width=True):
                df = db.ler("usuarios")
                reg = df[(df["usuario"].str.lower() == usuario) & (df["ativo"] != "Não")]
                if not reg.empty and conferir(senha, reg.iloc[0]["senha_hash"]):
                    r = reg.iloc[0]
                    st.session_state["usuario"] = {"usuario": r["usuario"], "nome": r["nome"] or r["usuario"],
                                                   "perfil": r["perfil"] or "consulta"}
                    st.rerun()
                else:
                    st.error("Usuário ou senha inválidos.")


def tela_primeiro_admin():
    with _caixa_central():
        st.markdown("<div class='login-titulo'>Primeiro acesso</div>"
                    "<div class='login-sub'>Crie o usuário administrador do sistema</div>",
                    unsafe_allow_html=True)
        with st.form("primeiro_admin"):
            nome = st.text_input("Seu nome")
            usuario = st.text_input("Usuário (login)").strip().lower()
            s1 = st.text_input("Senha", type="password")
            s2 = st.text_input("Repita a senha", type="password")
            if st.form_submit_button("Criar administrador", type="primary", use_container_width=True):
                if not (nome and usuario and s1):
                    st.error("Preencha todos os campos.")
                elif s1 != s2:
                    st.error("As senhas não conferem.")
                elif len(s1) < 6:
                    st.error("Use uma senha com pelo menos 6 caracteres.")
                else:
                    db.inserir("usuarios", {"usuario": usuario, "nome": nome, "senha_hash": hash_senha(s1),
                                            "perfil": "admin", "ativo": "Sim"})
                    st.session_state["usuario"] = {"usuario": usuario, "nome": nome, "perfil": "admin"}
                    st.rerun()


def sair():
    st.session_state.pop("usuario", None)
    st.rerun()
