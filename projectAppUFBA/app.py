import uuid
from datetime import datetime, timezone

import extra_streamlit_components as stx
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
    restaurar_cookie_login,
    opcoes_cookie_login,
    enviar_cookie_login,
    ler_cookie_login,
    apagar_cookie_login,
)
from modules.home import render_home
from modules.anuncio_simulado import render_anuncio_simulado
from modules.estilo import aplicar_css, aplicar_responsividade
from modules.sobre_equipe import render_sobre_equipe
from modules.carregamento import (
    CHAVE_TRANSICAO,
    etapas_da_pagina,
    etapas_do_menu,
    marcar_transicao_do_login,
    pagina_inicial,
    preparar_pagina,
)

def _chave_da_pagina(nome):
    """Converte o rótulo do menu em uma key estável para o container.

    Prefixo "tela_", e não "pagina_": várias páginas já usam keys internas
    começando com "pagina_" (pagina_home, pagina_modulo_<slug>...). A regra
    CSS que esconde a página anterior (ver _css_esconde_tela_anterior) pega
    tudo com "tela_"; com o mesmo prefixo das keys internas, ela esconderia
    pedaços da própria página aberta.
    """
    chave = re.sub(r"[^a-zA-Z0-9]+", "_", nome or "").strip("_").lower()
    return "tela_%s" % (chave or "inicio")


def _css_esconde_tela_anterior(chave_atual):
    """CSS que esconde qualquer tela que não seja a aberta agora.

    Por que existe: a cada clique o Streamlit redesenha a página de cima para
    baixo e mantém o que é antigo na tela, esmaecido, até o script terminar.
    Numa troca de página, a página anterior ficava visível (às vezes por
    baixo da nova) durante todo o carregamento: a "sobreposição".

    Esta regra chega ao navegador logo depois do menu, no começo da
    execução, e some com a tela anterior na hora. Numa interação dentro da
    mesma página ela não esconde nada, porque só existe a tela atual.

    st.html só com <style> não ocupa posição na página (vai para o contêiner
    de eventos), então não desloca nenhum elemento.
    """
    return (
        "<style>"
        f'.stMain [class*="st-key-tela_"]:not(.st-key-{chave_atual}) {{ display: none !important; }}'
        "</style>"
    )


# Configuração global
st.set_page_config(page_title="Criptoeduca", page_icon="🎓", layout="wide")

# --- VAGAS FIXAS DO TOPO ---
#
# O Streamlit reaproveita os elementos da página pela POSIÇÃO em que aparecem.
# Se numa execução surge um elemento a mais lá em cima e na seguinte ele some,
# tudo o que vem depois muda de posição, e o navegador mostra a tela nova por
# cima da antiga (esmaecida) até o fim da execução: a sobreposição do login
# com o menu.
#
# Os elementos do cookie apareciam só em algumas execuções: o componente de
# gravar o cookie (logo depois do login e no logout), o de apagar (cookie
# inválido) e um st.markdown de estilo que a biblioteca emite a cada get/set.
# Os avisos ("Concluindo o início da sessão…", "Encerrando…", aviso de
# COOKIE_SECRET) também. Agora todos moram em dois contêineres que existem em
# TODA execução, sempre nas duas primeiras posições:
#   vaga_cookie: os iframes do componente de cookie (invisíveis);
#   vaga_topo:   os avisos de texto.
# O que muda dentro de um contêiner não mexe na posição do resto da página.
#   tela_login:  o formulário de login. Existe também com a pessoa logada,
#                vazio e escondido (ver o começo do "else" lá embaixo).
#
# Por que o login precisa de uma vaga fixa: na troca login -> menu, quem
# ocupava a posição do formulário passava a ser outro contêiner (o dos
# avisos), e o Streamlit deixava os campos antigos do formulário, esmaecidos,
# dentro dele até a execução acabar. Com a vaga fixa, os restos ficam
# dentro da própria tela_login, que o CSS esconde logo na primeira linha da
# execução logada.
vaga_cookie = st.container(key="vaga_cookie")
vaga_topo = st.container(key="vaga_topo")
vaga_login = st.container(key="tela_login")
# Os contêineres vazios têm altura 0, mas o Streamlit põe 1rem de espaço
# entre um bloco e outro, e cada vaga vazia empurrava a página 16 px para
# baixo. Por isso o CSS esconde a "embalagem" (stLayoutWrapper) de cada vaga:
#   vaga_cookie: sempre (os iframes têm altura 0 e não mostram nada).
#     Esconder não impede o componente de funcionar: a própria biblioteca já
#     escondia o iframe com display: none, e o teste no navegador confirmou
#     o cookie gravado e lido de volta.
#   vaga_topo: só quando não tem aviso nem barra de carregamento.
# st.html só com <style> não ocupa posição (ver modules/estilo.py).
st.html(
    "<style>"
    '.stMain [data-testid="stLayoutWrapper"]:has(> .st-key-vaga_cookie)'
    " { display: none !important; }"
    '.stMain [data-testid="stLayoutWrapper"]:has(> .st-key-vaga_topo)'
    ':not(:has([data-testid="stAlert"], .ce-carregando))'
    " { display: none !important; }"
    "</style>"
)

with vaga_cookie:
    cookie_manager = stx.CookieManager(key="cookie_manager")

aviso_cookie = st.session_state.pop("_cookie_login_aviso", None)
if aviso_cookie:
    with vaga_topo:
        st.warning(aviso_cookie)

# Gravação do cookie de "manter conectado", pedida pelo login.
#
# Antes, enquanto o navegador não confirmava a gravação, o app mostrava
# "Concluindo o início da sessão…" e parava (st.stop). A pessoa já estava
# autenticada, mas esperava uma ida e volta inteira do componente para ver o
# menu, e essa tela intermediária era mais uma troca de tela (e mais uma
# sobreposição).
#
# Agora o menu é desenhado na mesma execução. O componente de gravar fica na
# vaga_cookie até confirmar; quando confirma, o Streamlit roda o app de novo
# (é assim que componentes devolvem valor) e a pendência é apagada. Como as
# posições são fixas, essa execução extra não troca nada na tela.
#
# Segurança: nada muda. A sessão já foi autenticada pela senha; o cookie só
# serve para lembrar o login na próxima visita. Se a gravação falhar, a
# pendência continua e é tentada de novo na próxima execução, como antes.
cookie_login_pendente = st.session_state.get("_cookie_login_pendente")
if cookie_login_pendente:
    with vaga_cookie:
        cookie_gravado = enviar_cookie_login(
            cookie_manager,
            cookie_login_pendente["valor"],
            cookie_login_pendente["expira_em"],
            f"set_login_{cookie_login_pendente['key']}",
            cookie_login_pendente["opcoes"],
        )
    if cookie_gravado:
        st.session_state.pop("_cookie_login_pendente", None)

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
    st.session_state["_ignorar_cookie_login"] = True
    st.session_state["_logout_cookie_key"] = uuid.uuid4().hex
    st.session_state["pediu_logout"] = True
    st.rerun(scope="app")
    
def _cancelar_saida():
    # Mesmo motivo: sem o rerun do app inteiro, o diálogo não fecha.
    st.rerun()

@st.dialog("Sair da conta?", width="small")
def _confirmar_saida():
    st.write("Você vai voltar para a tela de login.")
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


if st.session_state.get("pediu_logout", False):
    opcoes_cookie = opcoes_cookie_login(st.context.url)
    if opcoes_cookie is None:
        vaga_topo.warning(
            "Não foi possível expirar o cookie de login por esta conexão. "
            "Acesse o app por HTTPS ou por http://localhost:8501."
        )
    else:
        # O logout continua esperando a confirmação (st.stop): aqui sim é
        # preciso, porque se a pessoa fechar a aba antes do cookie expirar,
        # a próxima visita entraria logada de novo. Componente e aviso ficam
        # nas vagas fixas do topo, para não deslocar a página.
        with vaga_cookie:
            cookie_expirado = enviar_cookie_login(
                cookie_manager,
                "",
                datetime(1970, 1, 1, tzinfo=timezone.utc),
                f"expire_logout_{st.session_state['_logout_cookie_key']}",
                opcoes_cookie,
            )
        if not cookie_expirado:
            with vaga_topo:
                st.info("Encerrando a sessão…")
            st.stop()
    st.session_state.pop("pediu_logout", None)
    st.session_state.pop("_logout_cookie_key", None)
    for chave in ("usuario_logado", "nome_usuario", "username", "tipo_usuario"):
        st.session_state.pop(chave, None)
elif not st.session_state.get(
    "_ignorar_cookie_login", False
) and not st.session_state.get("usuario_logado", False):
    # ler_cookie_login usa st.context.cookies: o cookie já está disponível
    # na primeira execução, e o menu abre direto, sem o login piscar antes
    # (ver modules/login.py).
    valor_cookie = ler_cookie_login(cookie_manager)
    dados_cookie = restaurar_cookie_login(valor_cookie)
    if dados_cookie:
        st.session_state["usuario_logado"] = True
        st.session_state["username"] = dados_cookie["username"]
        st.session_state["nome_usuario"] = dados_cookie["nome_usuario"]
        st.session_state["tipo_usuario"] = dados_cookie["tipo_usuario"]
        # Login lembrado também passa pela tela de transição: é a mesma
        # passagem do login para o menu, só que sem digitar a senha.
        st.session_state[CHAVE_TRANSICAO] = True
    elif valor_cookie:
        with vaga_cookie:
            apagar_cookie_login(cookie_manager, "delete_invalido")

if "usuario_logado" not in st.session_state:
    st.session_state["usuario_logado"] = False
if "nome_usuario" not in st.session_state:
    st.session_state["nome_usuario"] = ""
if "tipo_usuario" not in st.session_state:
    st.session_state["tipo_usuario"] = ""

if not st.session_state["usuario_logado"]:
    # Mesma regra das telas do menu: esconde qualquer "tela_" que não seja a
    # do login. Cobre a volta do logout, quando a página logada ainda estaria
    # esmaecida por baixo do formulário.
    st.html(_css_esconde_tela_anterior("tela_login"))
    with vaga_login:
        render_login()
else:
    # Primeira coisa da tela logada: some com o login. Vem antes de qualquer
    # consulta ao banco, então o formulário esmaecido não fica na tela
    # enquanto o menu é montado. (A regra geral, _css_esconde_tela_anterior,
    # só chega depois do menu lateral.)
    st.html("<style>.stMain .st-key-tela_login { display: none !important; }</style>")

    # Barra de carregamento já na espera do menu. Antes do menu lateral o app
    # consulta o perfil (nome e foto) e, para aluno, o primeiro acesso. Logo
    # depois do login, essa espera deixava a área principal vazia. Aqui as
    # consultas correm juntas e, se passarem de 0,15 s, a barra aparece na
    # vaga_topo (posição fixa). Com os dados no cache, nada é desenhado.
    #
    # TELA DE TRANSIÇÃO LOGIN -> MENU. Logo depois do login (senha ou cookie)
    # a barra aparece SEMPRE, por pelo menos TRANSICAO_MINIMA_SEGUNDOS, e
    # busca também os dados da página que vai abrir. Assim tudo chega numa
    # barra só, antes do menu lateral ser desenhado, e a barra da tela (mais
    # abaixo) não precisa aparecer de novo. Enquanto ela está na tela, o CSS
    # mantém a navegação lateral recolhida (ver carregamento.css).
    transicao = marcar_transicao_do_login()
    username_logado = st.session_state.get("username")
    tipo_logado = st.session_state["tipo_usuario"]
    etapas_do_topo = etapas_do_menu(
        username_logado,
        tipo_logado,
        precisa_primeiro_acesso="primeiro_acesso" not in st.session_state,
    )
    if transicao:
        etapas_do_topo += etapas_da_pagina(
            st.session_state.get("menu") or pagina_inicial(tipo_logado),
            tipo_logado,
            username_logado,
        )
    with vaga_topo:
        preparar_pagina(etapas_do_topo, transicao=transicao)
    # Só depois da barra terminar: se a execução for interrompida no meio
    # (a confirmação do cookie faz isso), a seguinte continua a mesma barra.
    st.session_state.pop(CHAVE_TRANSICAO, None)

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
        # Antes era um st.markdown com <style>, que OCUPA uma posição na
        # página. Quando o aluno terminava o mural, esse elemento sumia, tudo
        # subia uma posição e a página nova aparecia por cima da antiga. O
        # aplicar_css usa st.html, que não ocupa posição (ver modules/estilo.py).
        aplicar_css("menu_primeiro_acesso.css")

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
                # A key das abas persiste depois que o diálogo fecha. Sem isto,
                # quem veio do atalho do mural continuaria abrindo o perfil na
                # aba Seguir usuários para sempre.
                st.session_state["abas_widget_perfil"] = "👤 Meu perfil"
                render_widget_perfil()

        # Atalho "Seguir pessoas" do mural. O mural é desenhado depois da
        # barra lateral, por isso o botão de lá não abre o diálogo direto: o
        # callback dele só grava esta chave. Callbacks rodam ANTES do script,
        # então o pedido é lido aqui mesmo, na passada disparada pelo clique.
        if st.session_state.pop("abrir_seguir_usuarios", False):
            cancelar_selecao()
            st.session_state["abas_widget_perfil"] = "🤝 Seguir usuários"
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
    # Páginas comuns a todos os perfis entram uma vez só, aqui. Repetir o
    # rótulo nas três listas é como ele acaba escrito diferente em uma delas,
    # e o elif lá embaixo deixa de casar para aquele perfil.
    opcoes.append("Equipe e Diário de Bordo")

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
    chave_da_tela = _chave_da_pagina(pagina)
    st.html(_css_esconde_tela_anterior(chave_da_tela))

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
    # O pop-up roda um fragmento com timer, e um fragmento OCUPA uma posição
    # na página mesmo sem desenhar nada (testado no Streamlit 1.64). Depois que
    # o pop-up aparece, o fragmento deixa de ser chamado; sem este contêiner
    # fixo, a página inteira subia uma posição e era desenhada por cima da
    # anterior (a sobreposição que aparecia ~2 min depois do login).
    # O contêiner existe sempre, com ou sem pop-up: a posição nunca muda.
    with st.container(key="vaga_avisos"):
        render_anuncio_simulado(forcar=forcar_anuncio)

    # --- UMA VAGA FIXA PARA CADA TELA ---
    #
    # Medido no navegador: quando um contêiner novo chega na posição onde
    # estava outro, o Streamlit põe os elementos antigos (esmaecidos) DENTRO
    # do novo até a execução terminar. Com uma vaga só para todas as páginas,
    # a tela do Mural recebia a Home inteira esmaecida por dentro, e a regra
    # de CSS não tinha como esconder (o contêiner era o da tela atual). Era a
    # sobreposição que ainda aparecia junto com a barra de carregamento.
    #
    # Agora toda tela do menu tem a sua vaga, criada em TODA execução, sempre
    # na mesma ordem (a do menu). Só a vaga da página aberta recebe conteúdo;
    # as outras ficam vazias, e um contêiner vazio não aparece nem ocupa
    # espaço. Na troca de página, os restos da página anterior ficam na vaga
    # DELA, que a regra _css_esconde_tela_anterior esconde.
    vagas_das_telas = {
        opcao: st.container(key=_chave_da_pagina(opcao)) for opcao in opcoes
    }
    vaga_da_tela = vagas_das_telas[pagina]

    # --- FLUXO OBRIGATÓRIO DO PRIMEIRO LOGIN (APENAS PARA ALUNOS) ---
    # Fica depois da barra lateral de proposito: assim o botao de Sair continua
    # acessivel. O st.stop() e o que faltava -- sem ele o mural era desenhado e
    # a pagina normal aparecia logo abaixo, na mesma tela, e o aluno pulava a
    # etapa obrigatoria sem publicar nada.
    #
    # O mural obrigatório também fica dentro do contêiner da tela (aqui a
    # chave é a do mural, porque o menu está travado nele). Antes ele era
    # desenhado solto, fora de qualquer "tela_": quando o aluno publicava e
    # ia para a Home, a regra de CSS não tinha como esconder o mural antigo.
    if tipo == "Aluno" and st.session_state.get("primeiro_acesso") == 1:
        with vaga_da_tela:
            preparar_pagina(
                etapas_da_pagina(pagina, tipo, st.session_state.get("username"))
            )
            render_sessao_interativa(modo_voluntario=False)
        st.stop()

    # Cada pagina tem sua propria vaga (ver "UMA VAGA FIXA PARA CADA TELA"
    # acima). A key da vaga e o que permite ao CSS identificar o DOM daquela
    # tela na transicao e esconder o da pagina de origem.
    with vaga_da_tela:
        # Tela de carregamento (modules/carregamento.py): busca antes os dados
        # que a página vai usar e, se a espera passar de 0,15 s, mostra a
        # barra com as etapas. Sempre o primeiro elemento da tela, sempre
        # presente (mesmo quando a barra não aparece), para nada mudar de
        # posição entre uma execução e outra.
        preparar_pagina(
            etapas_da_pagina(
                pagina,
                tipo,
                st.session_state.get("username"),
            )
        )
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

        elif pagina == "Equipe e Diário de Bordo":
            render_sobre_equipe()
