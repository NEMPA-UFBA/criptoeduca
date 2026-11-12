import html
import re

import streamlit as st
from modules.database import obter_primeiro_acesso, obter_dados_perfil
from modules.perfilWidget import render_widget_perfil
from modules.sessaoInterativa import render_sessao_interativa
from modules.mainmenu import (
    render_modulos,
    render_navegacao_modulos,
    render_progresso_aluno,
)
from modules.paginaModulo import render_pagina_modulo
from modules.pergaminhos import render_pergaminhos
from modules.gerenciar_conteudos import render_gerenciar_conteudos
from modules.leitura import CHAVE_LEITURA, render_pagina_leitura
from modules.modulos import carregar_modulos
from modules.login import (
    render_login,
    obter_chave_professor_diaria,
    segredo_da_chave_configurado,
    limpar_sessao_do_usuario,
)
from modules.anuncio_simulado import render_anuncio_simulado

def _chave_da_pagina(nome):
    """Converte o rótulo do menu em uma key estável para o container."""
    chave = re.sub(r"[^a-zA-Z0-9]+", "_", nome or "").strip("_").lower()
    return "pagina_%s" % (chave or "inicio")


# Configuração global
st.set_page_config(page_title="Criptoeduca", page_icon="🎓", layout="wide")

# Confirmação de saída.
#
# Fica aqui, antes do if/else, porque o st.dialog precisa ser chamado no fluxo
# principal do script — dentro de um if do Streamlit ele não abre.
#
# Sem esta pergunta, um toque errado no "Sair" derrubava a sessão na hora e a
# pessoa perdia a página em que estava.
def _sair_da_conta():
    # Os dados da pessoa saem junto com ela. Sem isto o próximo a usar
    # esta aba encontrava o username, o módulo aberto e a leitura em
    # curso do usuário anterior (ver limpar_sessao_do_usuario em
    # modules/login.py). Só as chaves simples são apagadas aqui: o menu
    # lateral está desenhado nesta tela, e as chaves de widget são
    # varridas no login seguinte.
    limpar_sessao_do_usuario()
    st.session_state["usuario_logado"] = False


@st.dialog("Sair da conta?", width="small")
def _confirmar_saida():
    st.write("Você vai voltar para a tela de login.")
    st.caption(
        f"**{st.session_state['nome_usuario']}** "
        f"({st.session_state['tipo_usuario']})"
    )
    confirmar, cancelar = st.columns(2)
    confirmar.button(
        "Sair",
        type="primary",
        width="stretch",
        on_click=_sair_da_conta,
    )
    cancelar.button(
        "Cancelar",
        width="stretch",
        on_click=lambda: None,
    )


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
        /* ---------- Moldura do avatar ---------- */
        /* [class*=...] pega a moldura da barra lateral e também a do diálogo de perfil. */
        [class*="st-key-moldura_avatar"] {
            position: relative;
            margin: 0.4rem auto 0.2rem;      /* centraliza o bloco na barra */
            padding: 8px;
        }
        [class*="st-key-moldura_avatar"] img {
            display: block;
            border-radius: 12px;
            padding: 3px;                    /* anel escuro entre foto e borda */
            border: 3px solid transparent;
            background:
                linear-gradient(#0f172a, #0f172a) padding-box,
                linear-gradient(135deg, #4F46E5, #38bdf8) border-box;
            box-shadow: 0 0 16px rgba(79, 70, 229, 0.45),
                        0 0 4px rgba(56, 189, 248, 0.35);
        }
        /* Cantos de mira (superior esquerdo e inferior direito) */
        [class*="st-key-moldura_avatar"]::before,
        [class*="st-key-moldura_avatar"]::after {
            content: "";
            position: absolute;
            width: 14px;
            height: 14px;
            border: 2px solid #38bdf8;
            pointer-events: none;
        }
        [class*="st-key-moldura_avatar"]::before {
            top: 0; left: 0;
            border-right: none; border-bottom: none;
        }
        [class*="st-key-moldura_avatar"]::after {
            bottom: 0; right: 0;
            border-left: none; border-top: none;
        }
        /* Some com o botão de "tela cheia" que aparece em cima da foto no hover */
        [class*="st-key-moldura_avatar"] [data-testid="stElementToolbar"] {
            display: none;
        }

        /* Etiqueta em pixel abaixo da foto */
        .ce-avatar-tag {
            font-family: "PressStart2P", monospace;
            font-size: 8px;
            letter-spacing: 0;
            -webkit-font-smoothing: none;
            color: #7dd3fc;
            text-align: center;
            margin: 0 0 0.6rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    
    tipo = st.session_state["tipo_usuario"]

    # Sincroniza o status de primeiro acesso do banco de dados para o session_state caso seja aluno
    if (
        "username" in st.session_state
        and tipo == "Aluno"
        and "primeiro_acesso" not in st.session_state
    ):
        # A leitura fica em cache: enquanto o aluno ainda nao publicou no
        # mural, o app roda varias vezes (cada tecla do formulario) e nao
        # pode consultar o banco em todas elas.
        st.session_state["primeiro_acesso"] = obter_primeiro_acesso(
            st.session_state["username"]
        )

    # --- PRIMEIRO ACESSO: COERÊNCIA DO MENU ---
    #
    # Enquanto primeiro_acesso for 1, todo o roteamento é interrompido
    # lá embaixo (mural forçado + st.stop) e o único lugar onde o aluno
    # está é o mural. Mas o radio lateral começava em "Painel Principal"
    # e continuava aceitando cliques que não levavam a lugar nenhum --
    # a tela do mural com o menu apontando para outra página, que era a
    # sensação de "página travada no menu errado".
    #
    # Duas correções, as duas AQUI, antes do st.sidebar.radio: a chave
    # de um widget só pode ser gravada antes do widget existir na tela.
    #
    # 1. O item selecionado passa a ser o mural, que é onde a pessoa
    #    realmente está. Se ela clicar em outro item, o valor volta para
    #    o mural no tique seguinte -- o menu deixa de mentir.
    # 2. Os outros itens ficam apagados e inertes (opacity/pointer-events):
    #    clicar neles não "não faz nada" de forma misteriosa, eles estão
    #    visivelmente fora de alcance, como um mapa com só um caminho
    #    aberto. Some quando o primeiro acesso é concluído, porque a
    #    regra só é emitida enquanto a condição vale.
    if tipo == "Aluno" and st.session_state.get("primeiro_acesso") == 1:
        if st.session_state.get("menu") != "Mural de Criptografia":
            st.session_state["menu"] = "Mural de Criptografia"
        st.markdown(
            """
            <style>
            .st-key-menu [data-testid="stRadioOption"]:not([data-selected="true"]) {
                opacity: 0.4;
                pointer-events: none;
            }
            </style>
            """,
            unsafe_allow_html=True,
        )

    # logo após o bloco de CSS da tela logada
    msg = st.session_state.pop("toast_notificacao", None)
    if msg:
        st.toast(msg)

    # Barra lateral
    username_atual = st.session_state.get("username")
    dados = obter_dados_perfil(username_atual)

    with st.sidebar:
        st.title("Criptoeduca")
        if dados:
            nome_db, foto_bytes = dados
            if foto_bytes:
                with st.container(
                    key="moldura_avatar",
                    width=118,
                    horizontal_alignment="center",
                ):
                    st.image(foto_bytes, width=96)
                st.markdown(
                    f'<p class="ce-avatar-tag">{html.escape(tipo.upper())}</p>',
                    unsafe_allow_html=True,
                )
            # Botão que abre a janela modal de edição
            if st.button(
                f"👤 {st.session_state.get('nome_usuario', nome_db)} ({st.session_state.get('tipo_usuario', '')})",
                key="btn_abrir_perfil",
                use_container_width=True,
            ):
                render_widget_perfil()
    # Menus condicionais baseados no perfil do usuário.
    # O Administrador precisa da propria lista: antes ele caia no else e
    # recebia o menu do Aluno, porque so o Professor era distinguido.
    # Os nomes dos itens do menu.
    #
    # "Sessões Interativas" virou "Mural de Criptografia": o que a página
    # faz é o mural, e o nome antigo prometia uma coisa que não existe
    # (sessões plural, de conteúdo, que nunca foram feitas).
    #
    # "Conteúdos" do Aluno virou "Exemplos de Crimes Digitais": os
    # pergaminhos. O material que a coordenação publica em "Gerenciar
    # Conteúdos > Exemplos de Golpe" não desapareceu -- ele virou o miolo
    # dos pergaminhos. Por isso o Aluno não tem mais uma página de avisos:
    # tem a página dos golpes, e o que a coordenação escreveu aparece lá
    # dentro.
    if tipo == "Administrador":
        opcoes = ["Painel da Coordenação", "Gerenciar Conteúdos", "Notas dos Alunos", "Mural de Criptografia", "Módulos de Aprendizado"]
    elif tipo == "Professor":
        opcoes = ["Painel Geral", "Turma", "Gerenciar Conteúdos", "Notas dos Alunos", "Mural de Criptografia", "Módulos de Aprendizado"]
    else:
        opcoes = ["Painel Principal", "Exemplos de Crimes Digitais", "Mural de Criptografia", "Meu Progresso", "Módulos de Aprendizado"]

    # O botão "Voltar para o Menu Principal" mora na página do mural, que é
    # desenhada depois do radio. Gravar st.session_state["menu"] de lá levanta
    # StreamlitAPIException: a chave já foi consumida pelo widget neste run. O
    # pedido chega por outra chave e é aplicado aqui, antes do radio existir.
    if st.session_state.get("voltar_para_menu", False):
        st.session_state["menu"] = opcoes[0]
        del st.session_state["voltar_para_menu"]

    # Sessoes antigas podem ter "Gerenciar Aulas" ou "Gerenciar Modulos"
    # gravado no menu. Os dois itens viraram um so; sem esta migracao o
    # radio receberia um valor que nao esta mais na lista de opcoes.
    menu_antigo = st.session_state.get("menu")
    if menu_antigo == "Gerenciar Aulas":
        st.session_state["menu"] = "Gerenciar Conteúdos"
        st.session_state["gerenciar_conteudos_aba"] = "Exemplos de Golpe"
    elif menu_antigo == "Gerenciar Módulos":
        st.session_state["menu"] = "Gerenciar Conteúdos"
        st.session_state["gerenciar_conteudos_aba"] = "Módulos"

    pagina = st.sidebar.radio("Navegação", opcoes, key="menu")

    # A hierarquia dos modulos aparece na propria lateralidade: recolhida,
    # logo abaixo do menu, com as categorias e os modulos de cada uma. So
    # existe quando a pagina aberta e a dos modulos, para nao poluir as
    # outras telas.
    if pagina == "Módulos de Aprendizado":
        render_navegacao_modulos()

    st.sidebar.divider()
    if st.sidebar.button("🚪 Sair / Logout", key="botao_sair"):
        _confirmar_saida()

    forcar_anuncio = st.sidebar.button(
        "🔔 Testar pop-up",
        key="botao_testar_anuncio",
        help="Abre imediatamente a notificação da simulação educativa.",
    )
    render_anuncio_simulado(forcar=forcar_anuncio)

    # --- FLUXO OBRIGATÓRIO DO PRIMEIRO LOGIN (APENAS PARA ALUNOS) ---
    # Fica depois da barra lateral de proposito: assim o botao de Sair continua
    # acessivel. O st.stop() e o que faltava -- sem ele o mural era desenhado e
    # a pagina normal aparecia logo abaixo, na mesma tela, e o aluno pulava a
    # etapa obrigatoria sem publicar nada.
    if tipo == "Aluno" and st.session_state.get("primeiro_acesso") == 1:
        render_sessao_interativa(modo_voluntario=False)
        st.stop()

    # Cada pagina tem seu proprio container com key. A key e o que permite
    # ao Streamlit identificar o DOM daquela tela na transicao e descartar
    # o anterior, em vez de deixar restos esmaecidos da pagina de origem.
    with st.container(key=_chave_da_pagina(pagina)):
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
                    "Esta chave está sendo derivada do segredo padrão que vem no "
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

        elif pagina == "Turma":
            # Pagina reservada para o professor. Por enquanto e so o lugar:
            # a lista de alunos e o acompanhamento da turma entram depois.
            if tipo != "Professor":
                st.error("Página exclusiva do professor.")
            else:
                st.title("👥 Turma")
                st.caption("Página da turma do professor.")

        elif pagina == "Gerenciar Conteúdos":
            # A pagina reune os dois editores que antes eram itens
            # separados: "Exemplos de Golpe" (pergaminhos) e "Modulos"
            # (modulos de aprendizado). Modulos criados no editor vao para
            # o banco; os originais continuam em dados/modulos.json.
            render_gerenciar_conteudos()

        elif pagina == "Notas dos Alunos":
            st.title("🧮 Notas dos Alunos")
            st.write("Lançamento e consulta de notas.")

        elif pagina == "Painel Principal":
            st.title(f"Bem-vindo(a) de volta, {st.session_state['nome_usuario']}! 👋")
            st.write("Aqui fica o painel da plataforma de estudos.")

        elif pagina == "Módulos de Aprendizado":
            # A home dos módulos é o mapa de missões (modules/mainmenu.py).
            # A página do módulo individual é a mesma rota, só que com um módulo
            # escolhido: o slug fica na sessão e a página volta para o mapa
            # quando o slug some.
            slug_modulo = st.session_state.get("modulo_selecionado")

            # A PAGINA DE LEITURA tem prioridade sobre a pagina do modulo.
            # E a mesma rota com outro estado: enquanto o aluno esta lendo,
            # o app desenha a leitura; quando ele conclui, a leitura some
            # da sessao e a pagina do modulo volta, com o quiz liberado.
            #
            # Fica dentro do app, e nao em uma pagina solta na pasta static,
            # porque a sessao do Streamlit morre quando o navegador sai do
            # app e volta: o aluno voltaria deslogado. Medido no navegador.
            slug_leitura = st.session_state.get(CHAVE_LEITURA)
            if slug_leitura:
                render_pagina_leitura(slug_leitura)
            elif slug_modulo:
                render_pagina_modulo(slug_modulo)
            else:
                render_modulos()

        elif pagina == "Mural de Criptografia":
            # O título desta página fica no próprio módulo do mural. Antes o app
            # desenhava um "Sessão do Mural" aqui e o módulo desenhava o dele logo
            # em seguida, então apareciam dois títulos seguidos.
            render_sessao_interativa(modo_voluntario=True)

        elif pagina == "Exemplos de Crimes Digitais":
            # A pagina dos pergaminhos. Substitui a antiga "Conteúdos": o que a
            # coordenação publica em "Gerenciar Conteúdos → Exemplos de Golpe"
            # aparece aqui, dentro de um pergaminho, em vez de uma lista de
            # avisos.
            render_pergaminhos()

        elif pagina == "Meu Progresso":
            render_progresso_aluno()
