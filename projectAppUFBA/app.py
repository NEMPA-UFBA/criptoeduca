import streamlit as st
from modules.database import criar_tabelas
from modules.login import (
    render_login,
    obter_chave_professor_diaria,
    segredo_da_chave_configurado,
)

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

if not st.session_state["usuario_logado"]:
    render_login()
else:
    tipo = st.session_state["tipo_usuario"]

    # Barra lateral
    st.sidebar.title("🎓 EduStream")
    st.sidebar.write(f"Usuário: **{st.session_state['nome_usuario']}**")
    st.sidebar.write(f"Perfil: **{tipo}**")

    # Menus condicionais baseados no perfil do usuário.
    # O Administrador precisa da propria lista: antes ele caia no else e
    # recebia o menu do Aluno, porque so o Professor era distinguido.
    if tipo == "Administrador":
        opcoes = ["Painel da Coordenação", "Gerenciar Aulas", "Notas dos Alunos"]
    elif tipo == "Professor":
        opcoes = ["Painel Geral", "Gerenciar Aulas", "Notas dos Alunos"]
    else:
        opcoes = ["Painel Principal", "Sessões Interativas", "Meu Progresso"]

    pagina = st.sidebar.radio("Navegação", opcoes)

    st.sidebar.divider()
    if st.sidebar.button("🚪 Sair / Logout"):
        st.session_state["usuario_logado"] = False
        st.rerun()

    # Conteudo condicional.
    # Precisa cobrir os seis itens de menu: o bloco anterior so tratava os
    # tres do Aluno, entao Professor e Administrador escolhiam uma pagina e
    # nao recebiam nada, nem o titulo.
    if pagina == "Painel da Coordenação":
        st.title("🛡️ Painel da Coordenação")
        st.write("Visão geral da plataforma e credenciamento de professores.")

        # Gera a mesma chave do dia usando a função do login.py
        st.subheader("🔑 Chave de Acesso para Novos Professores")
        st.info("Passe este código para os professores que forem se cadastrar hoje:")
        # Exibe em um bloco clicável para fácil cópia
        st.code(obter_chave_professor_diaria(), language="text")
        st.caption("Esta chave expira automaticamente às 23:59:59 de hoje.")

        # Aviso de configuração. Fica aqui e não em st.secrets porque quem
        # precisa saber é a coordenação, e é a coordenação quem usa o painel —
        # não quem programa o sistema. Fora do alcance dessa pessoa, o aviso é
        # ruído.
        if not segredo_da_chave_configurado():
            st.warning(
                "⚠️ Esta chave está sendo derivada do segredo padrão que vem no "
                "código-fonte. Ela tem 12 caracteres e é muito difícil de adivinhar, "
                "mas qualquer pessoa com uma cópia do repositório consegue calcular "
                "a chave do dia. Para fechar isso, crie "
                "`.streamlit/secrets.toml` com `CHAVE_SEGREDO = \"...\"` "
                "(esse caminho já está no .gitignore) e reinicie o app. "
                "Esta mensagem some sozinha quando o segredo estiver configurado.",
                icon="⚠️",
            )

    elif pagina == "Painel Geral":
        st.title("📋 Painel Geral")
        st.write("Aulas, quizzes e materiais do professor.")

    elif pagina == "Gerenciar Aulas":
        st.title("📚 Gerenciar Aulas")
        st.write("Criar, editar e publicar aulas.")

    elif pagina == "Notas dos Alunos":
        st.title("🧮 Notas dos Alunos")
        st.write("Lançamento e consulta de notas.")

    elif pagina == "Painel Principal":
        st.title(f"Bem-vindo(a) de volta, {st.session_state['nome_usuario']}! 👋")
        st.write("Aqui fica o painel da plataforma de estudos.")

    elif pagina == "Sessões Interativas":
        st.title("🎯 Sessões Interativas")
        st.write("Aulas e quizzes gravados.")

    elif pagina == "Meu Progresso":
        st.title("📊 Desempenho")
        st.write("Notas e progresso do aluno.")