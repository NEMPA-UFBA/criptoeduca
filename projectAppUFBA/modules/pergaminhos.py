"""A pagina dos pergaminhos: os exemplos de crimes digitais.

Cada exemplo de golpe e um PERGAMINHO: uma roleta de papel que a pessoa
clica para abrir, e que mostra o conteudo do golpe na ordem em que ele
foi escrito. Clicar em outro pergaminho fecha o anterior -- e por isso
que o estado do pergaminho aberto mora em st.session_state, e nao em um
st.expander: o expander do Streamlit deixa dois abertos ao mesmo tempo,
e o que se quer aqui e um so.

O miolo do pergaminho e uma lista de BLOCOS, e nao um monte de campos
com nome fixo. A pessoa escolhe o tipo de cada bloco e monta a ordem:

    titulo    -> secao maior, em negrito escuro
    subtitulo -> rubrica pequena, em caixa alta, com filete embaixo
    paragrafo -> texto corrido do documento
    fonte     -> credito no rodape, pequeno e esmaecido

Quatro tipos so. Um documento de aula e feito disto: secoes, subsecoes,
paragrafos e a fonte citada no fim. Aceitar mais tipos seria aceitar
uma tabela, um formulario e um video dentro de um papel de 1400.

De onde vem o conteudo:

  - dos exemplos pre-colocados em dados/exemplos_crime.json, que sao
    inseridos no banco quando a pagina e carregada, se ainda nao
    existirem (exemplos ja existentes nao sao sobrescritos);
  - do que o Professor e a Coordenacao publicam em "Gerenciar Conteudos
    -> Exemplos de Golpe", pelo construtor de blocos que este arquivo
    desenha.

Os dois sao a mesma coisa na tela: um pergaminho. Por isso o que a
coordenacao publica vira parte dos pergaminhos, e nao uma pagina
separada.
"""

import html
from datetime import date, datetime

import streamlit as st

from modules.database import (
    carregar_pergaminhos,
    salvar_conteudo,
    atualizar_conteudo,
    inativar_conteudo,
    reativar_conteudo,
)
from modules.estilo import aplicar_css, aplicar_estilo, html_bruto
from modules.exemplos_crime import (
    ROTULO_TIPO,
    TIPOS_BLOCO,
    resumo_do_bloco,
)

# Chave da sessao que guarda o id do pergaminho aberto. Um so pergaminho
# aberto por vez: e a sessao que garante isso, nao o CSS.
CHAVE_ABERTO = "pergaminho_aberto"

# Categorias oferecidas no formulario de publicacao. A primeira e a que
# aparece no comeco; "Outro" deixa o professor digitar a dele.
CATEGORIAS = [
    "Financeiro",
    "Engenharia Social",
    "Roubo de Identidade",
    "Outro",
]

# Os mesmos tons do resto do app, mas do lado de dentro do papel: o
# pergaminho e claro, e o texto sobre ele e escuro. Sem isso o texto
# claro do app sumiria em cima do papel.
# O CSS desta tela fica em static/css/pergaminhos.css (ver aplicar_css em modules/estilo.py).


def _html(trecho):
    """Atalho para html_bruto (ver a explicação lá)."""
    return html_bruto(trecho)


def _blocos_do(pergaminho):
    """A lista de blocos do pergaminho, sempre no formato pronto.

    Ha dois caminhos, e o segundo existe para ninguem ficar no escuro:

      1. o pergaminho ja tem "blocos" (formato novo) -> e o que ele mostra;
      2. nao tem (linha publicada antes desta mudanca) -> os blocos sao
         montados com o que esta nas colunas antigas do banco.

    Sem o caminho 2, todo conteudo publicado antes de hoje apareceria
    como um pergaminho em branco: a coluna nova ate existe, so que vazia.
    """
    brutos = pergaminho.get("blocos")
    if isinstance(brutos, list) and brutos:
        prontos = []
        for bruto in brutos:
            if not isinstance(bruto, dict):
                continue
            tipo = str(bruto.get("tipo") or "").strip().lower()
            texto = str(bruto.get("texto") or "").strip()
            if tipo not in ROTULO_TIPO or not texto:
                continue
            prontos.append({"tipo": tipo, "texto": texto})
        if prontos:
            return prontos

    # ---------- Formato antigo ----------
    blocos = []

    corpo = str(pergaminho.get("corpo") or "").strip()
    if corpo:
        blocos.append({"tipo": "paragrafo", "texto": corpo})

    exemplo = str(pergaminho.get("exemplo") or "").strip()
    if exemplo:
        blocos.append({"tipo": "subtitulo", "texto": "Exemplo de mensagem"})
        blocos.append({"tipo": "paragrafo", "texto": exemplo})

    for rotulo, campo in (("Sinais de alerta", "sinais"),
                          ("Como se proteger", "protecao")):
        linhas = [linha.strip()
                  for linha in str(pergaminho.get(campo) or "").splitlines()]
        linhas = [linha for linha in linhas if linha]
        if linhas:
            blocos.append({"tipo": "subtitulo", "texto": rotulo})
            for linha in linhas:
                blocos.append({"tipo": "paragrafo", "texto": linha})

    return blocos


def _blocos_html(blocos):
    """HTML dos blocos, um de cada vez, na ordem da lista.

    O texto passa por html.escape antes de qualquer coisa: ele vem de
    arquivo editavel e de formulario, e vai parar dentro de
    unsafe_allow_html=True. Sem o escape, um <script> escrito no texto
    do golpe executaria na tela do aluno -- que e exatamente a falha
    que o mural ja teve uma vez.

    Paragrafo vira um <p> por linha digitada: quem aperta Enter no
    campo esta quebrando o texto de proposito, e o Markdown do
    Streamlit nao faria essa quebra dentro de HTML.
    """
    pecas = []
    for bloco in blocos:
        tipo = bloco["tipo"]
        bruto = bloco["texto"]

        if tipo == "paragrafo":
            for linha in bruto.splitlines():
                linha = linha.strip()
                if linha:
                    pecas.append("<p>%s</p>" % html.escape(linha))
            continue

        # Os outros tres tipos sao uma unica linha: espaços repetidos e
        # quebras dentro do campo virariam espaço na tela de qualquer
        # forma, e um h4 com \\n no meio sai desalinhado.
        texto = html.escape(" ".join(bruto.split()))

        if tipo == "titulo":
            pecas.append(
                '<h4 class="ce-pergaminho-titulo-bloco">%s</h4>' % texto
            )
        elif tipo == "subtitulo":
            pecas.append(
                '<p class="ce-pergaminho-titulo-secao">%s</p>' % texto
            )
        elif tipo == "fonte":
            pecas.append('<p class="ce-pergaminho-fonte">%s</p>' % texto)

    return "\n".join(pecas)


def _miolo_html(pergaminho):
    """HTML do miolo aberto: os blocos, na ordem em que foram montados."""
    categoria = html.escape(pergaminho.get("categoria") or "")
    titulo_categoria = ""
    if categoria:
        titulo_categoria = (
            '<span class="ce-pergaminho-categoria">%s</span>' % categoria
        )

    credito = ""
    autor = pergaminho.get("autor") or ""
    data = pergaminho.get("data") or ""
    if autor or data:
        pedacos = []
        if autor:
            pedacos.append("Publicado por %s" % html.escape(str(autor)))
        if data:
            pedacos.append(str(data))
        credito = '<p class="ce-pergaminho-credito">%s</p>' % " &middot; ".join(
            pedacos
        )

    titulo = html.escape(pergaminho.get("titulo") or "")
    conteudo = _blocos_html(_blocos_do(pergaminho))

    return _html(
        f"""
        <div class="ce-pergaminho-sombra">
          <div class="ce-pergaminho">
            <div class="ce-pergaminho-rodape">{titulo_categoria}</div>
            <h3>{titulo}</h3>
            {conteudo}
            {credito}
          </div>
        </div>
        """
    )


def _categoria_do_pergaminho(pergaminho):
    """Categoria para o selo e para o filtro, sem string vazia."""
    return (pergaminho.get("categoria") or "Outros").strip() or "Outros"


def _resumo_do_pergaminho(pergaminho, limite=170):
    """Primeiro paragrafo do pergaminho, cortado para caber no cartao.

    O cartao e uma vitrine: ele nao carrega o texto inteiro. O corte
    acontece numa fronteira de palavra para nao terminar no meio de uma.
    """
    for bloco in _blocos_do(pergaminho):
        if bloco["tipo"] != "paragrafo":
            continue
        texto = " ".join(bloco["texto"].split())
        if not texto:
            continue
        if len(texto) > limite:
            texto = texto[:limite].rstrip()
            texto = texto.rsplit(" ", 1)[0] + "…"
        return texto

    corpo = " ".join(str(pergaminho.get("corpo") or "").split())
    if corpo:
        if len(corpo) > limite:
            corpo = corpo[:limite].rstrip().rsplit(" ", 1)[0] + "…"
        return corpo
    return "Abra o exemplo para ler o conteúdo completo."


def _alternar_pergaminho(pid):
    """Abre o pergaminho escolhido ou fecha o que ja estava aberto."""
    atual = st.session_state.get(CHAVE_ABERTO)
    st.session_state[CHAVE_ABERTO] = None if atual == pid else pid


def render_pergaminhos():
    """Desenha a pagina de exemplos de crimes digitais."""
    with st.container(key="pagina_crimes_digitais"):
        _render_pagina_pergaminhos()


def _render_pagina_pergaminhos():
    """Desenha o conteudo da pagina do aluno dentro do contêiner identificado."""
    aplicar_estilo()
    aplicar_css("pergaminhos.css")

    st.markdown(
        _html(
            """
            <p class="ce-pixel">EXEMPLOS DE CRIMES DIGITAIS</p>
            <p class="ce-subtitulo">Clique em um pergaminho para abrir o exemplo do golpe. Ao clicar em outro, o anterior fecha.</p>
            """
        ),
        unsafe_allow_html=True,
    )

    with st.spinner("Carregando exemplos..."):
        pergaminhos = carregar_pergaminhos()

    if not pergaminhos:
        st.info(
            "Nenhum exemplo de crime cadastrado ainda. Os exemplos "
            "pré-colocados vêm do arquivo `dados/exemplos_crime.json`, e o "
            "Professor e a Coordenação publicam os novos em "
            "\"Gerenciar Conteúdos → Exemplos de Golpe\"."
        )
        return

    # O pergaminho aberto. Um so: clicar no mesmo fecha, clicar em outro
    # troca. A chave fica na sessao porque o Streamlit redesenha a tela
    # inteira a cada clique.
    aberto = st.session_state.get(CHAVE_ABERTO)

    for pergaminho in pergaminhos:
        pid = pergaminho["id"]
        icone = pergaminho.get("icone") or "📜"
        titulo = pergaminho.get("titulo") or ""
        esta_aberto = aberto == pid

        # O key muda conforme o estado: assim o CSS consegue distinguir o
        # pergaminho aberto do fechado, porque a classe st-key-* do
        # Streamlit vem do key do widget.
        if esta_aberto:
            chave_widget = f"pergaminho_aberto_{pid}"
        else:
            chave_widget = f"pergaminho_{pid}"

        st.button(
            f"{icone}  {titulo}",
            key=chave_widget,
            width="stretch",
            on_click=_alternar_pergaminho,
            args=(pid,),
        )

        if esta_aberto:
            st.markdown(_miolo_html(pergaminho), unsafe_allow_html=True)


# --------------------------------------------------------------------------
# O CONSTRUTOR DE BLOCOS
# --------------------------------------------------------------------------
# A pessoa escolhe o tipo de cada bloco, aperta "Adicionar bloco" e
# reorganiza com as setas. O estado mora em chaves de session_state por
# POSICAO ("<prefixo>_tipo_0", "<prefixo>_texto_0"), e nao numa lista.
# Isto nao e preferencia: o Streamlit identifica cada widget pela chave,
# entao trocar a ordem dos blocos significa trocar o valor de duas
# chaves. Mudar so uma lista faria os widgets continuarem mostrando o
# que estavam mostrando antes.
#
# A operacao e ADIADA para a execucao seguinte porque o Streamlit nao
# deixa alterar o valor de um widget depois que ele foi criado na mesma
# execucao. Clicar na seta grava a intencao em CHAVE_OPERACAO_BLOCO; no
# comeco da execucao seguinte, quando ainda nao ha nenhum widget na
# tela, a intencao e aplicada. E por isso que nao ha st.rerun() aqui:
# o clique ja provoca a execucao seguinte sozinho.
CHAVE_OPERACAO_BLOCO = "_bloco_operacao"

# A limpeza apos publicar ou salvar tambem e adiada, pelo mesmo motivo:
# apagar a chave de um widget acabado de ser criado daria erro.
CHAVE_LIMPAR_PUBLICACAO = "_limpar_publicacao"
CHAVE_LIMPAR_EDICAO = "_limpar_edicao"


def _chave_n(prefixo):
    return "%s_n_blocos" % prefixo


def _chave_tipo(prefixo, posicao):
    return "%s_tipo_%d" % (prefixo, posicao)


def _chave_texto(prefixo, posicao):
    return "%s_texto_%d" % (prefixo, posicao)


def _quantidade(prefixo):
    """Quantidade de blocos naquele formulario. Nunca devolve None."""
    return int(st.session_state.get(_chave_n(prefixo), 0) or 0)


def _ler_bloco(prefixo, posicao):
    return (
        st.session_state.get(_chave_tipo(prefixo, posicao), "paragrafo"),
        st.session_state.get(_chave_texto(prefixo, posicao), ""),
    )


def _gravar_bloco(prefixo, posicao, tipo, texto):
    st.session_state[_chave_tipo(prefixo, posicao)] = tipo
    st.session_state[_chave_texto(prefixo, posicao)] = texto


def _apagar_chaves(prefixo, posicao):
    st.session_state.pop(_chave_tipo(prefixo, posicao), None)
    st.session_state.pop(_chave_texto(prefixo, posicao), None)


def _iniciar_blocos(prefixo, blocos):
    """Cria as chaves dos blocos uma unica vez, quando elas nao existem."""
    if _chave_n(prefixo) in st.session_state:
        return
    st.session_state[_chave_n(prefixo)] = len(blocos)
    for posicao, bloco in enumerate(blocos):
        _gravar_bloco(prefixo, posicao,
                      bloco.get("tipo", "paragrafo"),
                      bloco.get("texto", ""))


def _limpar_blocos(prefixo):
    for posicao in range(_quantidade(prefixo)):
        _apagar_chaves(prefixo, posicao)
    st.session_state[_chave_n(prefixo)] = 0


def _pedir_operacao(prefixo, operacao, a, b=None):
    """Guarda o que a pessoa pediu, para ser aplicado na execucao seguinte."""
    st.session_state[CHAVE_OPERACAO_BLOCO] = [prefixo, operacao, a, b]


def _aplicar_operacao():
    """Aplica o pedido de bloco pendente. Chamar ANTES de criar widgets."""
    pendente = st.session_state.pop(CHAVE_OPERACAO_BLOCO, None)
    if not pendente:
        return

    prefixo, operacao, a, b = pendente
    n = _quantidade(prefixo)

    if operacao == "mover":
        # "a" e a posicao, "b" e o delta (-1 sobe, 1 desce).
        origem = a
        destino = a + (b or 0)
        if 0 <= origem < n and 0 <= destino < n and origem != destino:
            meu = _ler_bloco(prefixo, origem)
            do_outro = _ler_bloco(prefixo, destino)
            _gravar_bloco(prefixo, destino, *meu)
            _gravar_bloco(prefixo, origem, *do_outro)

    elif operacao == "apagar" and 0 <= a < n:
        # Tudo abaixo sobe uma posicao; a ultima posicao some.
        for posicao in range(a, n - 1):
            _gravar_bloco(prefixo, posicao,
                          *_ler_bloco(prefixo, posicao + 1))
        _apagar_chaves(prefixo, n - 1)
        st.session_state[_chave_n(prefixo)] = n - 1

    elif operacao == "inserir" and 0 <= a <= n:
        # Tudo de "a" para baixo desce uma posicao; o novo ocupa a "a".
        for posicao in range(n - 1, a - 1, -1):
            _gravar_bloco(prefixo, posicao + 1,
                          *_ler_bloco(prefixo, posicao))
        _gravar_bloco(prefixo, a, b or "paragrafo", "")
        st.session_state[_chave_n(prefixo)] = n + 1


def _aplicar_limpezas():
    """Apaga os campos de quem ja foi salvo. Chamar antes de criar widgets."""
    if st.session_state.pop(CHAVE_LIMPAR_PUBLICACAO, False):
        _limpar_blocos("pub_")
        for chave in ("pub_titulo", "pub_icone", "pub_categoria",
                      "pub_categoria_livre", "pub_tipo_novo"):
            st.session_state.pop(chave, None)

    if st.session_state.pop(CHAVE_LIMPAR_EDICAO, False):
        _limpar_blocos("ed_")
        for chave in ("ed_titulo", "ed_icone", "ed_categoria"):
            st.session_state.pop(chave, None)


def _adicionar_bloco(prefixo, chave_tipo):
    # O tipo e lido no callback, e nao capturado no args: dentro do form o
    # selectbox pode ter mudado sem rerun, e o args ainda teria o valor
    # antigo.
    tipo = st.session_state.get(chave_tipo, "paragrafo")
    _pedir_operacao(prefixo, "inserir", _quantidade(prefixo), tipo)


def _mover_bloco(prefixo, posicao, delta):
    _pedir_operacao(prefixo, "mover", posicao, delta)


def _apagar_bloco(prefixo, posicao):
    _pedir_operacao(prefixo, "apagar", posicao)


def _controle_adicionar(prefixo, chave_tipo):
    """O seletor de tipo + o botao que poe um bloco novo no fim da lista."""
    colunas = st.columns([3.4, 2.2, 4.4])
    colunas[0].selectbox(
        "Tipo do novo bloco",
        options=list(ROTULO_TIPO),
        format_func=lambda t: ROTULO_TIPO[t],
        key=chave_tipo,
    )
    colunas[1].form_submit_button(
        "Adicionar",
        icon=":material/add:",
        key="%sadicionar" % prefixo,
        help="Acrescenta um bloco desse tipo no fim do pergaminho.",
        on_click=_adicionar_bloco,
        args=(prefixo, chave_tipo),
    )


def _desenhar_blocos(prefixo):
    """Um bloco por secao: a linha de tipo e botoes, e o texto embaixo.

    O texto le a largura inteira de proposito. Antes ele competia com o
    seletor e com tres botoes na mesma linha, e um paragrafo de aula
    ficava espremido numa coluna estreita.

    Os botoes usam o "icon=" do Streamlit (Material Symbols): ele
    desenha o glifo sozinho, entao nao depende de a fonte do sistema
    ter o emoji. Setas como "⬆" sao caracteres de apresentacao emoji e
    somem em branco em maquina sem o pacote de emoji.
    """
    quantidade = _quantidade(prefixo)

    if not quantidade:
        st.caption(
            "Nenhum bloco ainda. Escolha o tipo acima e aperte "
            "\"Adicionar\"."
        )
        return

    for posicao in range(quantidade):
        # Cada bloco vive dentro de um contende com borda. Sem isto a
        # pessoa olha uma fileira de botoes e uma caixa de texto solta
        # e nao sabe onde um bloco termina e o outro comeca -- era o
        # que ficava "baguncado".
        with st.container(border=True):
            linha = st.columns([3.6, 1.45, 1.45, 1.45])
            linha[0].selectbox(
                "Bloco %d" % (posicao + 1),
                options=list(ROTULO_TIPO),
                format_func=lambda t: ROTULO_TIPO[t],
                key=_chave_tipo(prefixo, posicao),
            )
            # As setas podem sair de qualquer posicao: pedir para subir o
            # primeiro ou descer o ultimo nao faz mal, _aplicar_operacao
            # checa os limites. Evitar o clique com "disabled" custaria um
            # widget a mais por linha em troca de nada.
            #
            # O "key" e obrigatorio aqui. Sem ele o Streamlit monta a
            # chave a partir do rotulo -- "FormSubmitter:<form>-Subir" --
            # e como todas as linhas tem o mesmo rotulo, a segunda linha
            # ja derrubava a pagina inteira com
            # StreamlitDuplicateElementKey.
            linha[1].form_submit_button(
                "Subir", icon=":material/arrow_upward:",
                key="%ssobe_%d" % (prefixo, posicao),
                help="Move este bloco para cima.",
                on_click=_mover_bloco,
                args=(prefixo, posicao, -1),
            )
            linha[2].form_submit_button(
                "Descer", icon=":material/arrow_downward:",
                key="%sdesce_%d" % (prefixo, posicao),
                help="Move este bloco para baixo.",
                on_click=_mover_bloco,
                args=(prefixo, posicao, 1),
            )
            linha[3].form_submit_button(
                "Tirar", icon=":material/close:",
                key="%stira_%d" % (prefixo, posicao),
                help="Apaga este bloco.",
                on_click=_apagar_bloco,
                args=(prefixo, posicao),
            )

            st.text_area(
                "Texto do bloco %d" % (posicao + 1),
                key=_chave_texto(prefixo, posicao),
                height=96,
                label_visibility="collapsed",
            )


def _ler_blocos(prefixo):
    """Le os blocos do formulario como lista pronta para o banco."""
    return [
        {"tipo": tipo, "texto": texto.strip()}
        for tipo, texto in (
            _ler_bloco(prefixo, posicao)
            for posicao in range(_quantidade(prefixo))
        )
        if texto.strip()
    ]


def _publicar_exemplo():
    """Grava um exemplo novo como callback do envio do formulario."""
    titulo = str(st.session_state.get("pub_titulo", "")).strip()
    blocos = _ler_blocos("pub_")
    if not titulo or not blocos:
        st.session_state["_crime_erro"] = (
            "Preencha o título do golpe e monte pelo menos um bloco de "
            "conteúdo."
        )
        return

    st.session_state.pop("_crime_erro", None)
    categoria = st.session_state.get("pub_categoria", "")
    categoria_livre = st.session_state.get("pub_categoria_livre", "")
    salvar_conteudo(
        titulo,
        resumo_do_bloco(blocos),
        st.session_state.get("username", ""),
        str(st.session_state.get("pub_icone", "")).strip() or "📜",
        (str(categoria_livre).strip() if categoria == "Outro" else categoria),
        "",
        "",
        "",
        blocos,
    )
    st.session_state[CHAVE_LIMPAR_PUBLICACAO] = True
    st.session_state["_crime_aviso"] = (
        "Exemplo publicado! Ele já aparece como pergaminho."
    )


def _salvar_exemplo_edicao(pergaminho):
    """Grava a edicao como callback do envio do formulario."""
    titulo = str(st.session_state.get("ed_titulo", "")).strip()
    blocos = _ler_blocos("ed_")
    if not titulo or not blocos:
        st.session_state["_crime_erro"] = (
            "O título e pelo menos um bloco de conteúdo não podem ficar "
            "vazios."
        )
        return

    st.session_state.pop("_crime_erro", None)
    atualizar_conteudo(
        pergaminho["id"],
        titulo,
        resumo_do_bloco(blocos),
        str(st.session_state.get("ed_icone", "")).strip() or "📜",
        str(st.session_state.get("ed_categoria", "")).strip(),
        "",
        "",
        "",
        blocos,
    )
    # crime_em_edicao e _crime_prefill_id nao sao chave de widget, entao
    # podem ser apagados agora. Os campos nao podem: estao na tela.
    st.session_state.pop("crime_em_edicao", None)
    st.session_state.pop("_crime_prefill_id", None)
    st.session_state[CHAVE_LIMPAR_EDICAO] = True
    st.session_state["_crime_aviso"] = "Exemplo atualizado."


def _formulario_publicar():
    """Formulario de publicacao de um exemplo de crime.

    Tudo dentro de um st.form, inclusive o construtor de blocos, para que
    o texto nao se mexa a cada tecla. Os botoes de bloco sao
    st.form_submit_button justamente porque st.button nao e permitido
    dentro de form.
    """
    _iniciar_blocos("pub_", [])

    with st.form("form_publicar_crime"):
        st.text_input("Título do golpe", key="pub_titulo")
        st.text_input("Ícone (um emoji)", value="📜", key="pub_icone")
        categoria = st.selectbox("Categoria", CATEGORIAS, key="pub_categoria")
        if categoria == "Outro":
            st.text_input(
                "Escreva a categoria", key="pub_categoria_livre"
            )

        st.caption(
            "Conteúdo do pergaminho, de cima para baixo. Tipos: %s."
            % ", ".join(ROTULO_TIPO[t] for t in TIPOS_BLOCO)
        )
        _controle_adicionar("pub_", "pub_tipo_novo")
        _desenhar_blocos("pub_")

        st.form_submit_button(
            "Publicar exemplo",
            type="primary",
            on_click=_publicar_exemplo,
        )


def _preencher_campos_edicao(pergaminho):
    """Escreve o exemplo nos campos de edicao, uma vez so.

    Os campos do Streamlit nao aceitam mudar de valor depois de criados
    nesta execucao, entao o preenchimento acontece por session_state,
    antes do widget existir.

    O preenchimento acontece UMA VEZ por exemplo. Se fosse a cada
    execucao, qualquer outro clique na tela -- o de inativar outro
    exemplo, por exemplo -- reescreveria os campos e apagaria o que a
    pessoa estava escrevendo. O guarda _crime_prefill_id diz qual
    exemplo foi o ultimo a ser preenchido.
    """
    if st.session_state.get("_crime_prefill_id") == pergaminho["id"]:
        return

    # Zera os blocos do exemplo anterior antes de carregar os novos: a
    # lista que sobrou de um exemplo com mais blocos continuaria na tela
    # do que tem menos.
    _limpar_blocos("ed_")

    st.session_state["ed_titulo"] = pergaminho.get("titulo") or ""
    st.session_state["ed_icone"] = pergaminho.get("icone") or "📜"
    st.session_state["ed_categoria"] = pergaminho.get("categoria") or ""

    blocos = _blocos_do(pergaminho)
    st.session_state[_chave_n("ed_")] = len(blocos)
    for posicao, bloco in enumerate(blocos):
        _gravar_bloco("ed_", posicao, bloco["tipo"], bloco["texto"])

    st.session_state["_crime_prefill_id"] = pergaminho["id"]


def _formulario_editar(pergaminho):
    """Formulario de edicao de um exemplo, ja preenchido."""
    _preencher_campos_edicao(pergaminho)

    with st.form(f"form_editar_crime_{pergaminho['id']}"):
        st.text_input("Título do golpe", key="ed_titulo")
        st.text_input("Ícone (um emoji)", key="ed_icone")
        st.text_input("Categoria", key="ed_categoria")

        st.caption(
            "Conteúdo do pergaminho, de cima para baixo. Tipos: %s."
            % ", ".join(ROTULO_TIPO[t] for t in TIPOS_BLOCO)
        )
        _controle_adicionar("ed_", "ed_tipo_novo")
        _desenhar_blocos("ed_")

        st.form_submit_button(
            "Salvar alterações",
            type="primary",
            on_click=_salvar_exemplo_edicao,
            args=(pergaminho,),
        )


def _data_curta(valor):
    """Data do cartao, sem o horario e sem microssegundos."""
    if isinstance(valor, (date, datetime)):
        return valor.strftime("%d/%m/%Y")
    texto = str(valor or "").strip()
    if not texto:
        return ""
    try:
        return datetime.fromisoformat(texto).strftime("%d/%m/%Y")
    except ValueError:
        return texto.split(" ")[0]


def _card_admin_html(pergaminho):
    """Cartao compacto da lista de gerenciamento."""
    ativo = bool(pergaminho.get("ativo"))
    icone = html.escape(pergaminho.get("icone") or "📜")
    titulo = html.escape(pergaminho.get("titulo") or "")
    categoria = html.escape(_categoria_do_pergaminho(pergaminho))
    resumo = html.escape(_resumo_do_pergaminho(pergaminho, limite=150))

    origem = pergaminho.get("origem") or "publicado"
    rotulo_origem = "Pré-colocado" if origem == "pre_colocado" else "Publicado"
    autor = str(pergaminho.get("autor") or "").strip().lstrip("@")
    data = _data_curta(pergaminho.get("data"))
    partes_rodape = [rotulo_origem]
    if autor and origem != "pre_colocado":
        partes_rodape.append("por @%s" % autor)
    if data:
        partes_rodape.append(data)
    rodape = html.escape(" · ".join(partes_rodape))

    status = "Ativo" if ativo else "Inativo"
    classe_status = (
        "ce-admin-status-ativo" if ativo else "ce-admin-status-inativo"
    )
    classe_card = (
        "ce-admin-card" if ativo else "ce-admin-card ce-admin-card-inativo"
    )

    return _html(
        f"""
        <div class="{classe_card}">
          <div class="ce-admin-topo">
            <span class="ce-admin-icone">{icone}</span>
            <span class="ce-admin-status {classe_status}">{status}</span>
          </div>
          <p class="ce-admin-titulo">{titulo}</p>
          <div class="ce-admin-meta">
            <span class="ce-admin-chip">{categoria}</span>
          </div>
          <p class="ce-admin-resumo">{resumo}</p>
          <div class="ce-admin-rodape">{rodape}</div>
        </div>
        """
    )


def _abrir_edicao_crime(pid):
    st.session_state["crime_em_edicao"] = pid


def _cancelar_edicao_crime():
    st.session_state.pop("crime_em_edicao", None)
    st.session_state.pop("_crime_prefill_id", None)
    st.session_state[CHAVE_LIMPAR_EDICAO] = True


def _inativar_crime(pid):
    inativar_conteudo(pid)
    st.session_state["_crime_aviso"] = (
        "Exemplo inativado. Ele não aparece mais para o aluno, mas "
        "continua aqui na aba Inativos para ser reativado."
    )


def _reativar_crime(pid):
    reativar_conteudo(pid)
    st.session_state["_crime_aviso"] = (
        "Exemplo reativado. Ele já aparece de novo para o aluno."
    )


def _painel_edicao_crime(pergaminho):
    """Mostra o formulario de edicao ao lado da previa do pergaminho."""
    icone = html.escape(pergaminho.get("icone") or "📜")
    titulo = html.escape(pergaminho.get("titulo") or "")
    categoria = _categoria_do_pergaminho(pergaminho)
    origem = pergaminho.get("origem") or "publicado"
    rotulo_origem = "Pré-colocado" if origem == "pre_colocado" else "Publicado"
    status = "Ativo" if pergaminho.get("ativo") else "Inativo"

    st.markdown(
        _html(
            """
            <p class="ce-admin-edicao-rotulo">EDITAR EXEMPLO</p>
            <p class="ce-subtitulo">As alterações só aparecem para o aluno depois de salvar.</p>
            """
        ),
        unsafe_allow_html=True,
    )

    col_titulo, col_voltar = st.columns(
        [4, 1], vertical_alignment="center"
    )
    with col_titulo:
        st.markdown(
            _html(
                f'<p class="ce-admin-edicao-titulo">{icone} {titulo}</p>'
            ),
            unsafe_allow_html=True,
        )
        st.caption(
            "Categoria: %s · Origem: %s · Status: %s"
            % (categoria, rotulo_origem, status)
        )
    with col_voltar:
        st.button(
            "← Voltar",
            key="cancelar_edicao_crime",
            width="stretch",
            on_click=_cancelar_edicao_crime,
        )

    st.divider()

    col_form, col_previa = st.columns([1.15, 0.85], gap="large")
    with col_form:
        _formulario_editar(pergaminho)
    with col_previa:
        st.markdown(
            '<p class="ce-admin-previa-rotulo">PRÉVIA DO EXEMPLO SALVO</p>',
            unsafe_allow_html=True,
        )
        previa = dict(pergaminho)
        previa["data"] = _data_curta(pergaminho.get("data"))
        st.markdown(_miolo_html(previa), unsafe_allow_html=True)


def render_gerenciar_crime():
    """Pagina de publicacao e edicao dos exemplos de crime.

    E o que a coordenacao usa: publica um golpe novo, edita um exemplo
    pre-colocado, inativa o que nao serve mais e reativa o que voltou a
    servir. Tudo o que aparece aqui vira pergaminho na pagina dos alunos.

    As duas chamadas de baixo sao obrigatorias e vem ANTES de qualquer
    widget: e onde os pedidos de reordenar/apagar blocos e as limpezas
    de formulario sao aplicados, sempre num momento em que nenhum campo
    da tela existe ainda. Depois do primeiro widget elas dariam erro.
    """
    with st.container(key="pagina_gerenciar_exemplos_golpe"):
        _render_gerenciar_crime()


def _render_gerenciar_crime():
    aplicar_estilo()
    aplicar_css("pergaminhos.css")
    _aplicar_operacao()
    _aplicar_limpezas()

    aviso = st.session_state.pop("_crime_aviso", None)
    if aviso:
        st.success(aviso)
    erro = st.session_state.pop("_crime_erro", None)
    if erro:
        st.error(erro)

    st.markdown(
        _html(
            """
            <p class="ce-pixel">EXEMPLOS DE CRIMES DIGITAIS</p>
            <p class="ce-subtitulo">Publique, edite, inative ou reative exemplos de golpe. Só os exemplos ativos aparecem como pergaminho para o aluno.</p>
            """
        ),
        unsafe_allow_html=True,
    )

    pergaminhos = carregar_pergaminhos(incluir_inativos=True)

    edicao = st.session_state.get("crime_em_edicao")
    if edicao is not None:
        alvo = next(
            (p for p in pergaminhos if p["id"] == edicao),
            None,
        )
        if alvo is None:
            st.session_state.pop("crime_em_edicao", None)
        else:
            _painel_edicao_crime(alvo)
            return

    with st.expander("➕ Publicar um exemplo novo", expanded=False):
        _formulario_publicar()

    st.divider()
    st.subheader("Exemplos já publicados")

    if not pergaminhos:
        st.info("Nenhum exemplo publicado ainda.")
        return

    ativos = sum(1 for p in pergaminhos if p.get("ativo"))
    inativos = len(pergaminhos) - ativos
    st.caption(
        "%d ativo(s) · %d inativo(s) · %d no total"
        % (ativos, inativos, len(pergaminhos))
    )
    st.caption(
        "Os exemplos pré-colocados voltam ao texto de "
        "`dados/exemplos_crime.json` na próxima carga do app."
    )

    col_busca, col_filtro = st.columns([2, 1])
    busca = col_busca.text_input(
        "Buscar exemplo",
        key="admin_busca_exemplos",
        placeholder="Título, categoria ou autor",
    )
    filtro = col_filtro.pills(
        "Mostrar",
        ["Ativos", "Inativos", "Todos"],
        default="Ativos",
        required=True,
        key="admin_filtro_status",
    )
    if not filtro:
        filtro = "Ativos"

    lista = pergaminhos
    if filtro == "Ativos":
        lista = [p for p in lista if p.get("ativo")]
    elif filtro == "Inativos":
        lista = [p for p in lista if not p.get("ativo")]

    termo = busca.strip().casefold()
    if termo:
        def _combina(pergaminho):
            campos = [
                pergaminho.get("titulo") or "",
                _categoria_do_pergaminho(pergaminho),
                pergaminho.get("autor") or "",
                _resumo_do_pergaminho(pergaminho, limite=400),
            ]
            return termo in " ".join(campos).casefold()

        lista = [p for p in lista if _combina(p)]

    # Ativos primeiro, e dentro de cada grupo a ordem original dos ids.
    lista = sorted(
        lista,
        key=lambda p: (0 if p.get("ativo") else 1, p["id"]),
    )

    if not lista:
        st.info("Nenhum exemplo encontrado com esses filtros.")
        return

    # Os botoes de bloco gravam o pedido no callback e o clique ja provoca
    # o rerun que aplica a operacao no inicio desta pagina. Nao ha rerun
    # manual aqui.
    COLUNAS = 2
    for inicio in range(0, len(lista), COLUNAS):
        trecho = lista[inicio : inicio + COLUNAS]
        # Sempre duas colunas, mesmo quando sobra um cartao na ultima
        # fileira: assim o ultimo cartao nao estica para a largura toda e
        # a grade fica alinhada com a dos modulos.
        colunas = st.columns(COLUNAS)
        for coluna, pergaminho in zip(colunas, trecho):
            pid = pergaminho["id"]
            with coluna:
                with st.container(key=f"admin_exemplo_{pid}"):
                    st.markdown(
                        _card_admin_html(pergaminho),
                        unsafe_allow_html=True,
                    )
                    col_editar, col_acao = st.columns(2)
                    col_editar.button(
                        "✏️ Editar",
                        key=f"editar_crime_{pid}",
                        width="stretch",
                        on_click=_abrir_edicao_crime,
                        args=(pid,),
                    )
                    if pergaminho.get("ativo"):
                        with col_acao.popover(
                            "🗑️ Inativar", width="stretch"
                        ):
                            st.warning(
                                "Este exemplo deixa de aparecer para o "
                                "aluno. Você pode reativá-lo depois."
                            )
                            st.button(
                                "Confirmar inativação",
                                key=f"confirmar_inativar_crime_{pid}",
                                type="primary",
                                width="stretch",
                                on_click=_inativar_crime,
                                args=(pid,),
                            )
                    else:
                        col_acao.button(
                            "♻️ Reativar",
                            key=f"reativar_crime_{pid}",
                            width="stretch",
                            on_click=_reativar_crime,
                            args=(pid,),
                        )
