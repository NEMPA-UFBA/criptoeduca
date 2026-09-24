import streamlit as st
from modules.database import criar_tabelas
from modules.login import render_login, obter_chave_professor_diaria

# Configuração global
st.set_page_config(page_title="Plataforma EduStream", page_icon="🎓", layout="wide")

# Inicializa as tabelas no SQLite
criar_tabelas()

if "usuario_logado" not in st.session_state:
    st.session_state["usuario_logado"] = False
if "nome_usuario" not in st.session_state:
    st.session_state["nome_usuario"] = ""
if "tipo_usuario" not in st.session_state:
    st.session_state["tipo_usuario"] = ""

# Inicializa a variável de controle da sessão
if "usuario_logado" not in st.session_state:
    st.session_state["usuario_logado"] = False

# Controle de acesso
if "usuario_logado" not in st.session_state:
    st.session_state["usuario_logado"] = False

if not st.session_state["usuario_logado"]:
    render_login()
else:
    # Barra lateral
    st.sidebar.title("🎓 EduStream")
    st.sidebar.write(f"Usuário: **{st.session_state['nome_usuario']}**")
    st.sidebar.write(f"Perfil: **{st.session_state['tipo_usuario']}**")
    
    # Menus condicionais baseados no perfil do usuário
    if st.session_state["tipo_usuario"] == "Professor":
        opcoes = ["Painel Geral", "Gerenciar Aulas", "Notas dos Alunos"]
    else:
        opcoes = ["Painel Principal", "Sessões Interativas", "Meu Progresso"]
        
    pagina = st.sidebar.radio("Navegação", opcoes)
    # Se o usuário for Administrador ou Coordenador
    if st.session_state["tipo_usuario"] == "Administrador":
       st.title("🛡️ Painel da Coordenação")
    
    # Gera a mesma chave do dia usando a função do login.py
       chave_hoje = obter_chave_professor_diaria()
    
       st.subheader("🔑 Chave de Acesso para Novos Professores")
       st.info("Passe este código para os professores que forem se cadastrar hoje:")
    
    # Exibe em um bloco clicável para fácil cópia
       st.code(chave_hoje, language="text")
       st.caption("Esta chave expira automaticamente às 23:59:59 de hoje.")
    
    st.sidebar.divider()
    if st.sidebar.button("🚪 Sair / Logout"):
        st.session_state["usuario_logado"] = False
        st.rerun()
    # Conteúdo condicional
    st.title(f"Área do {st.session_state['tipo_usuario']}")
    st.write(f"Você está navegando na página: **{pagina}**")

    # Renderização do conteúdo selecionado
    if pagina == "Painel Principal":
        st.title(f"Bem-vindo(a) de volta, {st.session_state['nome_usuario']}! 👋")
        st.write("Aqui fica o painel da plataforma de estudos.")
    elif pagina == "Sessões Interativas":
        st.title("🎯 Sessões Interativas")
        st.write("Aulas e quizzes gravados.")
    elif pagina == "Meu Progresso":
        st.title("📊 Desempenho")
        st.write("Notas e progresso do aluno.")