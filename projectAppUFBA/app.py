import streamlit as st
import html
import re
from modules.database import (
    obter_primeiro_acesso,
    obter_dados_perfil,
)
from modules.perfilWidget import (
    render_widget_perfil,
    cancelar_selecao,
)
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
    limpar_sessao_do_usuario,
)
from modules.home import render_home
from modules.anuncio_simulado import render_anuncio_simulado
from modules.estilo import aplicar_css, aplicar_responsividade

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
    st.rerun()
    
def _cancelar_saida():
    # Mesmo motivo: sem o rerun do app inteiro, o diálogo não fecha.
    st.rerun()

@st.dialog("Sair da conta?", width="small")
def _confirmar_saida():
    st.write("Você vai voltar para a tela de login.")
    # _sair_da_conta() apaga os dados da pessoa antes do rerun. Se o dialogo
    # ainda estiver aberto nesse rerun, as chaves podem nao existir mais.
    nome = st.session_state.get("nome_usuario") or ""
    tipo = st.session_state.get("tipo_usuario") or ""
    if nome:
        st.caption(f"**{nome}** ({tipo})")
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
        on_click=_cancelar_saida,
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
    # O CSS fica em static/css/app_logado.css.
    aplicar_css("app_logado.css")

    # Ajustes gerais de tela estreita. Ficam depois do CSS acima de proposito:
    # em empate de especificidade, a ultima regra vence.
    aplicar_responsividade()

    # Aviso deixado pelo dialogo do perfil (foto salva ou removida). Um
    # st.toast chamado direto no callback do dialogo nao aparece no navegador,
    # entao o callback guarda o texto e ele e mostrado aqui, no redesenho.
    msg = st.session_state.pop("toast_notificacao", None)
    if msg:
        st.toast(msg)
    
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

    # Barra lateral. Este bloco ja esta dentro do "else" de usuario logado,
    # entao a consulta e direta: antes ela ficava dentro de um segundo if, e
    # "dados" so existia se esse if fosse verdadeiro.
    # Retorna exatamente (nome, foto_bytes), do cache.
    dados = obter_dados_perfil(st.session_state.get("username"))

    if dados:
        nome_db, foto_bytes = dados
        
        with st.sidebar:
          with st.container(key="cabecalho_sidebar", horizontal_alignment="center", gap="small"):
            st.title("Criptoeduca")
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
                width="stretch",
            ):
                cancelar_selecao()   
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

    # A home tem botoes que levam a outra pagina. Como ela e desenhada depois
    # do radio, o clique nao pode gravar "menu" na hora: a chave do widget ja
    # foi consumida neste run. O pedido chega por "navegar_para" e e aplicado
    # aqui, antes do radio existir.
    pedido_de_pagina = st.session_state.pop("navegar_para", None)
    if (
        pedido_de_pagina in opcoes
        and not (tipo == "Aluno" and st.session_state.get("primeiro_acesso") == 1)
    ):
        st.session_state["menu"] = pedido_de_pagina

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

    # O botao de teste do pop-up e ferramenta da coordenacao: para o aluno
    # ele estragaria a simulacao, que depende de o aviso chegar de surpresa.
    forcar_anuncio = tipo == "Administrador" and st.sidebar.button(
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
        if pagina in ("Painel da Coordenação", "Painel Geral", "Painel Principal"):
            # A mesma home se adapta ao perfil: aluno, professor ou
            # coordenacao. A chave diaria de professor continua no painel da
            # coordenacao, dentro de modules/home.py.
            render_home()

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
