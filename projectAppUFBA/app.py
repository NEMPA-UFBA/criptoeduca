import streamlit as st
from modules.database import criar_tabelas, conectar
from modules.sessaoInterativa import render_sessao_interativa
from modules.introducaoCriptografia import render_introducao_criptografia
from modules.login import (
    render_login,
    obter_chave_professor_diaria,
    segredo_da_chave_configurado,
)

# Configuração global
st.set_page_config(page_title="Criptoeduca", page_icon="🎓", layout="wide")

# Inicializa as tabelas no SQLite
criar_tabelas()

# Confirmação de saída.
#
# Fica aqui, antes do if/else, porque o st.dialog precisa ser chamado no fluxo
# principal do script — dentro de um if do Streamlit ele não abre.
#
# Sem esta pergunta, um toque errado no "Sair" derrubava a sessão na hora e a
# pessoa perdia a página em que estava.
@st.dialog("Sair da conta?", width="small")
def _confirmar_saida():
    st.write("Você vai voltar para a tela de login.")
    st.caption(
        f"**{st.session_state['nome_usuario']}** "
        f"({st.session_state['tipo_usuario']})"
    )
    confirmar, cancelar = st.columns(2)
    if confirmar.button("Sair", type="primary", width="stretch"):
        st.session_state["usuario_logado"] = False
        st.rerun()
    if cancelar.button("Cancelar", width="stretch"):
        st.rerun()


if "usuario_logado" not in st.session_state:
    st.session_state["usuario_logado"] = False
if "nome_usuario" not in st.session_state:
    st.session_state["nome_usuario"] = ""
if "tipo_usuario" not in st.session_state:
    st.session_state["tipo_usuario"] = ""

if not st.session_state["usuario_logado"]:
    render_login()
else:
    # ---------- CSS da tela logada ----------
    # Este bloco mora aqui, e não em modules/login.py, porque o <style> de lá
    # está dentro de render_login() e o app só chama render_login() quando
    # ninguém está logado. Ou seja: até agora a tela logada não tinha uma
    # linha de CSS próprio, e a sidebar ficava com a cara do tema padrão.
    #
    # Os seletores usam .st-key-*, a classe que o app mesmo dá pelo key= do
    # widget. Ela é estável: o frontend monta "st-key-" + o nome do key,
    # trocando o que não for letra, número, hífen ou underscore. Já o
    # stBaseButton-secondary do botão não serviria — ele não aparece
    # literalmente em nenhum arquivo do bundle do frontend, é montado em
    # runtime, e pode mudar na próxima versão do Streamlit.
    #
    # Efeito colateral útil do key=: .st-key-botao_sair só envolve o botão do
    # logout, então o botão de recolher a barra fica de fora sem precisar de
    # nenhuma regra que o exclua.
    st.markdown(
        """
        <style>
        /* ---------- Menu da barra lateral ---------- */
        /* O item ativo precisa ficar claro. Sem isto o item escolhido e o não
           escolhido são idênticos — o mesmo defeito que o seletor de perfil
           teve na tela de login, por causa do mesmo [role="radio"] que o
           Streamlit 1.64 trocou por data-selected. */
        .st-key-menu [data-testid="stRadioOption"] {
            padding: 0.55rem 0.75rem;
            margin-bottom: 0.15rem;
            border-radius: 8px;
            /* A barra da esquerda é o indicador de "você está aqui". Ela é
               transparente no estado normal para não existir quando não há
               nada selecionado. */
            border-left: 3px solid transparent;
            color: #e2e8f0;
            transition: background-color 0.3s ease, color 0.3s ease,
                        border-color 0.3s ease;
        }
        .st-key-menu [data-testid="stRadioOption"]:hover {
            background-color: rgba(79, 70, 229, 0.16);
        }
        .st-key-menu [data-testid="stRadioOption"][data-selected="true"] {
            background-color: rgba(79, 70, 229, 0.28);
            border-left-color: #4F46E5;
            color: #ffffff;
            font-weight: 600;
        }
        .st-key-menu [data-testid="stRadioOption"][data-selected="true"]:hover {
            background-color: rgba(79, 70, 229, 0.36);
        }
        .st-key-menu [data-testid="stRadioOption"]:active {
            background-color: rgba(79, 70, 229, 0.42);
        }

        /* ---------- Botão de sair ---------- */
        /* Vermelho, que é o sinal convencional para sair. E o hover muda a cor
           do texto, não só o fundo: sem isso a pessoa precisa ler o rótulo
           para saber qual botão é. */
        .st-key-botao_sair button {
            border-radius: 8px;
            transition: background-color 0.3s ease, color 0.3s ease,
                        border-color 0.3s ease;
        }
        .st-key-botao_sair button:hover {
            background-color: rgba(239, 68, 68, 0.16);
            border-color: rgba(239, 68, 68, 0.45);
            color: #fca5a5;
        }
        .st-key-botao_sair button:active {
            background-color: rgba(239, 68, 68, 0.28);
        }

        /* ---------- Press Start 2P nos títulos ---------- */
        /* A fonte vem de [[theme.fontFaces]] na config.toml e é a mesma que o
           login já usa, com o mesmo apelido sem espaços. O tamanho é pequeno
           de propósito: o advance da Press Start 2P é 1em por caractere e a
           largura útil da sidebar é 260px, medidos no navegador. A 18px o
           título "Criptoeduca" ocupa 198px e sobra folga; a 24px, que é o
           padrão do Streamlit na sidebar, daria 264px e estouraria.
           Nos títulos de página a conta é a mesma, mas eles são longos: os
           maiores passam de 50 caracteres e quebram em duas linhas. Uma fonte
           pixelada aguenta a quebra com line-height 1.4. */
        [data-testid="stSidebar"] h1 {
            font-family: "PressStart2P", monospace;
            font-size: 18px !important;
            /* A Press Start 2P só tem o peso 400. Deixar 700 aqui faria o
               navegador inventar um negrito falso, que borra os pixels. */
            font-weight: 400;
            line-height: 1.4;
            /* Streamlit aplica tracking negativo em alguns textos; em fonte
               monoespaçada isso fecha os glyphs e quebra a grade. */
            letter-spacing: 0;
            /* Sem isto o Chrome suaviza a borda dos pixels e o resultado fica
               desfocado, que é o oposto do pretendido. */
            -webkit-font-smoothing: none;
            color: #f1f5f9;
        }
        [data-testid="stMain"] h1 {
            font-family: "PressStart2P", monospace;
            font-size: 18px !important;
            font-weight: 400;
            line-height: 1.4;
            letter-spacing: 0;
            -webkit-font-smoothing: none;
            color: #f1f5f9;
        }

        /* "Usuário:" e "Perfil:" são contexto de quem está logado, não conteúdo.
           O <strong> é o que os separa dos outros <p> da sidebar: é o único
           detalhe que eles carregam e que nenhum outro parágrafo da barra
           lateral tem. Os itens do menu, o rótulo "Navegação" e o texto do
           botão de sair não usam negrito, então este seletor casa com
           exatamente dois elementos. Fixar o tamanho aqui também evita que, ao
           trocar de perfil, as duas linhas mudem de largura e a barra "pule". */
        [data-testid="stSidebar"] p:has(strong) {
            opacity: 0.6;
            font-size: 0.85rem;
        }

        /* Quem pede menos animação não recebe transição */
        @media (prefers-reduced-motion: reduce) {
            .st-key-menu [data-testid="stRadioOption"],
            .st-key-botao_sair button {
                transition: none;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    
    tipo = st.session_state["tipo_usuario"]

    # Sincroniza o status de primeiro acesso do banco de dados para o session_state caso seja aluno
    if "username" in st.session_state and tipo == "Aluno":
        conn = conectar()
        c = conn.cursor()
        c.execute("SELECT primeiro_acesso FROM usuarios WHERE username = ?", (st.session_state["username"],))
        res = c.fetchone()
        conn.close()
        if res:
            st.session_state["primeiro_acesso"] = res[0]

    # --- FLUXO OBRIGATÓRIO DO PRIMEIRO LOGIN (APENAS PARA ALUNOS) ---
    if tipo == "Aluno" and st.session_state.get("primeiro_acesso") == 1:
            render_sessao_interativa(modo_voluntario=False)

    # Barra lateral
    st.sidebar.title("Criptoeduca")
    st.sidebar.write(f"Usuário: **{st.session_state['nome_usuario']}**")
    st.sidebar.write(f"Perfil: **{tipo}**")

    # Menus condicionais baseados no perfil do usuário.
    # O Administrador precisa da propria lista: antes ele caia no else e
    # recebia o menu do Aluno, porque so o Professor era distinguido.
    if tipo == "Administrador":
        opcoes = ["Painel da Coordenação", "Gerenciar Aulas", "Notas dos Alunos", "Sessões Interativas", "Módulos de Aprendizado"]
    elif tipo == "Professor":
        opcoes = ["Painel Geral", "Gerenciar Aulas", "Notas dos Alunos", "Sessões Interativas", "Módulos de Aprendizado"]
    else:
        opcoes = ["Painel Principal", "Sessões Interativas", "Meu Progresso", "Módulos de Aprendizado"]

    # O botão "Voltar para o Menu Principal" mora na página do mural, que é
    # desenhada depois do radio. Gravar st.session_state["menu"] de lá levanta
    # StreamlitAPIException: a chave já foi consumida pelo widget neste run. O
    # pedido chega por outra chave e é aplicado aqui, antes do radio existir.
    if st.session_state.get("voltar_para_menu", False):
        st.session_state["menu"] = opcoes[0]
        del st.session_state["voltar_para_menu"]

    pagina = st.sidebar.radio("Navegação", opcoes, key="menu")

    st.sidebar.divider()
    if st.sidebar.button("🚪 Sair / Logout", key="botao_sair"):
        _confirmar_saida()

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

    elif pagina == "Módulos de Aprendizado":
        render_introducao_criptografia()
        st.title("📚 Módulos de Aprendizado: Introdução à Criptografia")
        st.write("Explore as videoaulas teóricas e teste seus conhecimentos com os quizzes interativos.")

    elif pagina == "Sessões Interativas":
        st.title("🎯 Sessão do Mural")
        # Chama a função que renderiza o mural e o painel de moderação para gestores
        render_sessao_interativa(modo_voluntario=True)

    elif pagina == "Meu Progresso":
        st.title("📊 Desempenho")
        st.write("Notas e progresso do aluno.")