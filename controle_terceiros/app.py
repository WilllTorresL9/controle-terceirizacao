"""Controle de Terceirização — envio e retorno de peças em fornecedores externos.

Executar:  streamlit run app.py
"""
import streamlit as st

st.set_page_config(page_title="Controle de Terceirização", page_icon="🏭", layout="wide")

from core import auth, db, ui  # noqa: E402

ui.estilo()

try:
    db.backend()
except Exception as e:  # erro de credencial, planilha não compartilhada etc.
    st.error("Não foi possível conectar ao banco de dados (Google Sheets).")
    st.exception(e)
    st.info("Confira o arquivo `.streamlit/secrets.toml` e se a planilha foi compartilhada "
            "com o e-mail da conta de serviço (como Editor). Veja o README.")
    st.stop()

if not auth.usuario_atual():
    if db.ler("usuarios").empty:
        auth.tela_primeiro_admin()
    else:
        auth.tela_login()
    st.stop()

u = auth.usuario_atual()

paginas = {
    "Operação": [
        st.Page("views/painel.py", title="Painel", icon="📊", default=True),
        st.Page("views/envio.py", title="Registrar envio", icon="📤"),
        st.Page("views/recebimento.py", title="Registrar recebimento", icon="📥"),
        st.Page("views/consulta.py", title="Consulta e rastreio", icon="🔎"),
        st.Page("views/programacao.py", title="Programação (previsto)", icon="📅"),
    ],
    "Cadastros": [
        st.Page("views/cadastros.py", title="Fornecedores, serviços e produtos", icon="🏭"),
        st.Page("views/conta.py", title="Minha conta", icon="👤"),
    ],
}
if auth.pode("admin"):
    paginas["Cadastros"].append(st.Page("views/usuarios.py", title="Usuários", icon="🔐"))

nav = st.navigation(paginas)

with st.sidebar:
    st.markdown(f"**{u['nome']}**  \n<small>{u['perfil'].capitalize()}</small>", unsafe_allow_html=True)
    if db.modo() != "Google Sheets":
        st.warning("Modo local de teste: dados gravados em `dados_local/` (CSV).", icon="🧪")
    c1, c2 = st.columns(2)
    if c1.button("🔄 Atualizar", use_container_width=True, help="Recarrega os dados da planilha"):
        db.limpar_cache()
        st.rerun()
    if c2.button("Sair", use_container_width=True):
        auth.sair()

nav.run()
