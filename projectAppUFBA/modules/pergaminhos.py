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
    regravados no banco a cada carga do app (o arquivo e a fonte da
    verdade deles);
  - do que o Professor e a Coordenacao publicam em "Gerenciar Aulas",
    pelo construtor de blocos que este arquivo desenha.

Os dois sao a mesma coisa na tela: um pergaminho. Por isso o que a
coordenacao publica vira parte dos pergaminhos, e nao uma pagina
separada.
"""

import html

import streamlit as st

from modules.database import (
    carregar_pergaminhos,
    salvar_conteudo,
    atualizar_conteudo,
    inativar_conteudo,
)
from modules.estilo import html_bruto
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
CSS_PERGAMINHOS = """
<style>
/* ==========================================================================
   O PERGAMINHO
   ==========================================================================
   A ideia e fazer o papel parecer papel: um rolo de madeira com o pergaminho
   enrolado em cima, e a folha aberta embaixo, amarelada, com manchas, com a
   borda rasgada e com a tinta escura por cima.

   As tres peças sao:

     1. A ROLTA (o botao do Streamlit) -- a ponta enrolada do pergaminho,
        apoiada nas duas varas de madeira. E o que a pessoa clica.
     2. A FOLHA (o miolo) -- o papel aberto, com as manchas e a borda rasgada.
     3. O TEXTO -- a tinta, em cor de tinta ferrogálica sobre papel.

   Os seletores sao por ATRIBUTO e nao por classe. A classe que o Streamlit
   monta e "st-key-" + o key inteiro, ou seja "st-key-pergaminho_3" e
   "st-key-pergaminho_aberto_3". Um seletor de classe exato nao casaria com
   nenhuma das duas. O seletor por atributo casa com as duas -- "st-key-
   pergaminho_" esta dentro de "st-key-pergaminho_aberto_3" -- e por isso a
   regra do aberto vem depois, para sobrescrever.
   ========================================================================== */

/* ---------- 1. A ROLTA: o botao que abre ---------- */
[class*="st-key-pergaminho_"] button {
    position: relative;
    width: 100%;
    text-align: left;
    padding: 0.55rem 3.2rem 0.55rem 1.1rem;
    color: #f3e6c8;
    font-weight: 700;
    font-size: 0.98rem;
    letter-spacing: 0.01em;
    /* O gradiente de cima para baixo e o que faz o papel enrolado parecer
       um cilindro: a parte de cima recebe a luz, a de baixo fica na
       sombra. Uma cor só nao daria a.volume nenhum. */
    background:
        linear-gradient(180deg,
            #d9c18c 0%,
            #c9ad74 12%,
            #b8995f 30%,
            #ab8a52 50%,
            #b8995f 70%,
            #c9ad74 88%,
            #8e7141 100%);
    border: 1px solid #6b5228;
    /* O canto de cima e de baixo arredondados e o que faz parecer que o
       papel esta enrolado; as pontas de madeira entram por cima, com os
       pseudo-elementos abaixo. */
    border-radius: 14px 14px 5px 5px;
    box-shadow:
        inset 0 1px 0 rgba(255, 240, 200, 0.45),
        inset 0 -3px 6px rgba(60, 40, 10, 0.5),
        0 4px 12px rgba(0, 0, 0, 0.45);
    transition: transform 0.18s ease, filter 0.18s ease,
                box-shadow 0.18s ease;
}
/* As duas varas de madeira atravessando o rolo. Sao os pseudo-elementos:
   ::before fica na ponta esquerda e ::after na direita, e cada um e uma
   vara com o gradiente transversal que imita o veio da madeira. */
[class*="st-key-pergaminho_"] button::before,
[class*="st-key-pergaminho_"] button::after {
    content: "";
    position: absolute;
    top: -3px;
    bottom: -3px;
    width: 16px;
    background:
        linear-gradient(90deg,
            #4a3316 0%,
            #8a6428 22%,
            #b8893f 42%,
            #7d5a22 68%,
            #513916 100%);
    border: 1px solid #33240d;
    border-radius: 4px;
    box-shadow:
        inset 0 1px 0 rgba(255, 225, 170, 0.35),
        0 2px 4px rgba(0, 0, 0, 0.5);
}
[class*="st-key-pergaminho_"] button::before {
    left: -2px;
}
[class*="st-key-pergaminho_"] button::after {
    right: -2px;
}
[class*="st-key-pergaminho_"] button:hover {
    filter: brightness(1.09) saturate(1.05);
    transform: translateY(-1px);
    box-shadow:
        inset 0 1px 0 rgba(255, 240, 200, 0.55),
        inset 0 -3px 6px rgba(60, 40, 10, 0.5),
        0 7px 18px rgba(0, 0, 0, 0.5);
}
[class*="st-key-pergaminho_"] button:active {
    transform: translateY(1px);
}
/* O texto do botao e o titulo do golpe. A sombra em cima e a mesma ilusao
   de relevo que o Streamlit aplica nos botoes claros, so que invertida
   para o texto claro sobre o rolo escuro. */
[class*="st-key-pergaminho_"] button p {
    color: #f3e6c8;
    font-weight: 700;
    text-shadow: 0 1px 1px rgba(40, 25, 5, 0.75);
}
/* O pergaminho aberto: a ponta foi puxada, e o rolo fica com a madeira a
   mostra, mais claro e mais alto. */
[class*="st-key-pergaminho_aberto_"] button {
    background:
        linear-gradient(180deg,
            #ecd9a8 0%,
            #dcc18a 14%,
            #cbae72 34%,
            #bf9f60 52%,
            #cbae72 70%,
            #ddc18c 88%,
            #a3854c 100%);
    color: #3d2c11;
    border-color: #5d461f;
    border-radius: 16px 16px 4px 4px;
    box-shadow:
        inset 0 1px 0 rgba(255, 245, 215, 0.6),
        inset 0 -4px 8px rgba(60, 40, 10, 0.45),
        0 9px 22px rgba(0, 0, 0, 0.5);
}
[class*="st-key-pergaminho_aberto_"] button p {
    color: #3d2c11;
    text-shadow: 0 1px 0 rgba(255, 240, 205, 0.5);
}
/* O rotulo do botao leva um emoji, que o Streamlit bota junto do texto. O
   espacamento a direita foi aumentado para o texto nao passar por baixo da
   vara de madeira da ponta. */

/* ---------- 2. A FOLHA: o papel aberto ---------- */
/* A sombra do papel fica no ENVOLTORIO, e nao na folha.
   A folha usa clip-path para serrar a borda em dentes -- e o clip-path
   recorta a sombra junto. A sombra entao vai no wrapper, com
   filter: drop-shadow, que enxerga a silhueta ja recortada e projeta a
   sombra no contorno dos dentes, e nao num retangulo. */
.ce-pergaminho-sombra {
    margin: -1rem 0 1.4rem 0;
    filter: drop-shadow(0 10px 20px rgba(0, 0, 0, 0.45))
            drop-shadow(0 2px 4px rgba(0, 0, 0, 0.3));
}
.ce-pergaminho {
    position: relative;
    color: #3d2c14;
    /* A serifada vem no container, e nao so nos filhos: e o que garante
       que qualquer texto que caia aqui dentro (inclusive o que o
       Streamlit escrever) saia com cara de documento antigo. */
    font-family: Georgia, "Times New Roman", serif;
    padding: 1.35rem 1.6rem 1.6rem 1.6rem;
    /* A borda rasgada e feita com tres coisas ao mesmo tempo:
         - o gradiente que mancha o papel em varios pontos;
         - o recorte (clip-path) que serra a borda em dentes irregulares;
         - a sombra interna, que escurece as beiradas.
       Uma folha de papel velho nao tem borda reta: e por isso que o
       clip-path tem aquelas medidas assim tresnadas. */
    background:
        radial-gradient(ellipse at 12% 8%, rgba(120, 85, 30, 0.16) 0%, rgba(120, 85, 30, 0) 42%),
        radial-gradient(ellipse at 88% 22%, rgba(140, 95, 35, 0.13) 0%, rgba(140, 95, 35, 0) 38%),
        radial-gradient(ellipse at 72% 88%, rgba(110, 75, 25, 0.15) 0%, rgba(110, 75, 25, 0) 40%),
        radial-gradient(ellipse at 26% 78%, rgba(150, 105, 40, 0.11) 0%, rgba(150, 105, 40, 0) 34%),
        radial-gradient(circle at 50% 50%, rgba(255, 250, 230, 0.5) 0%, rgba(255, 250, 230, 0) 70%),
        linear-gradient(168deg, #e9d6a6 0%, #e2cb95 45%, #d8bd82 100%);
    clip-path: polygon(
        0.4% 0%, 8% 0.7%, 17% 0%, 27% 0.9%, 38% 0.2%, 49% 1%, 61% 0.1%, 72% 0.8%,
        84% 0%, 93% 0.6%, 99.5% 0.1%, 100% 6%, 99.7% 18%, 100% 32%, 99.6% 48%,
        100% 63%, 99.8% 78%, 100% 92%, 99.4% 100%, 88% 99.3%, 76% 100%, 64% 99.2%,
        51% 100%, 39% 99.1%, 27% 100%, 16% 99.4%, 6% 100%, 0.3% 99.6%, 0% 90%,
        0.4% 76%, 0% 61%, 0.5% 46%, 0% 32%, 0.4% 18%, 0.1% 7%
    );
    box-shadow:
        inset 0 0 30px rgba(110, 75, 25, 0.22),
        inset 0 0 6px rgba(90, 60, 20, 0.18);
}
/* A costura do papel: a dobra onde o pergaminho foi dobrado para caber
   na roleta. E a sombra suave que desce do rolo de madeira. */
.ce-pergaminho::before {
    content: "";
    position: absolute;
    left: 0;
    right: 0;
    top: 0;
    height: 26px;
    background: linear-gradient(180deg, rgba(70, 45, 12, 0.42), rgba(70, 45, 12, 0));
    pointer-events: none;
}
/* A mancha de cera que fecha o pergaminho. Fica no canto, como o lacre de
   um documento antigo. */
.ce-pergaminho::after {
    content: "";
    position: absolute;
    right: 22px;
    top: 18px;
    width: 34px;
    height: 34px;
    border-radius: 50%;
    background:
        radial-gradient(circle at 34% 30%, #b8382c 0%, #8e2a20 45%, #6b1d15 100%);
    box-shadow:
        inset 0 -2px 4px rgba(0, 0, 0, 0.45),
        inset 0 2px 3px rgba(255, 180, 160, 0.35),
        0 2px 4px rgba(0, 0, 0, 0.4);
    opacity: 0.9;
    pointer-events: none;
}
/* A tinta. O titulo e mais escuro e mais fechado do que o corpo, como no
   documento antigo. O espaco a direita existe para o titulo nao passar por
   baixo do lacre de cera, que fica no canto. */
.ce-pergaminho h3 {
    margin: 0 0 0.15rem 0;
    padding-right: 3.2rem;
    font-size: 1.18rem;
    font-weight: 700;
    color: #33240e;
    letter-spacing: 0.01em;
    font-family: Georgia, "Times New Roman", serif;
}
/* O subtitulo da categoria, em caixa alta e espacado: e a "rubrica" do
   documento. */
.ce-pergaminho-categoria {
    display: inline-block;
    color: #7a5c28;
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.16em;
    text-transform: uppercase;
    margin-bottom: 0.5rem;
    font-family: Georgia, "Times New Roman", serif;
}
.ce-pergaminho p {
    margin: 0 0 0.95rem 0;
    line-height: 1.65;
    color: #4a3618;
    font-family: Georgia, "Times New Roman", serif;
    font-size: 0.97rem;
}
/* A mensagem falsa do golpe, como se tivesse sido escrita numa tira de
   papel e colada no documento. O papel e mais claro e a borda e serrada
   de outro jeito. */
.ce-pergaminho-exemplo {
    background:
        linear-gradient(175deg, #f6ecc9 0%, #eddfb4 100%);
    border: 1px dashed #9a7a3e;
    border-radius: 3px;
    padding: 0.85rem 1rem;
    margin: 0 0 1.1rem 0;
    box-shadow: inset 0 1px 4px rgba(120, 85, 30, 0.18);
    transform: rotate(-0.35deg);
}
.ce-pergaminho-exemplo p {
    margin: 0;
    font-family: "Courier New", monospace;
    font-size: 0.9rem;
    color: #3f2c11;
    line-height: 1.6;
}
/* O rotulo das secoes, em caixa alta, como o titulo de um capitulo.
   O seletor traz a classe "p" de proposito: sem ela, ".ce-pergaminho p"
   (-- que tira 0.97rem de fonte e margem de baixo) tem especificidade
   maior e engolia esta regra inteira, deixando a rubrica do mesmo tamaho
   do texto corrido e na mesma cor dele. */
.ce-pergaminho p.ce-pergaminho-titulo-secao {
    font-weight: 700;
    color: #6b4f21;
    font-size: 0.76rem;
    line-height: 1.5;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    margin: 1.15rem 0 0.5rem 0;
    font-family: Georgia, "Times New Roman", serif;
    /* A linha fina embaixo do rotulo e a mesma coisa nas secoes do
       documento antigo: um filete separando o titulo do texto. */
    border-bottom: 1px solid rgba(107, 79, 33, 0.35);
    padding-bottom: 0.25rem;
}
/* O titulo de uma secao do conteudo. Nao e o h3 do cabecalho (que e o
   nome do golpe): e o que a pessoa escolheu dentro do pergaminho, e por
   isso o tamanho fica abaixo do do cabecalho para nao disputar com ele. */
.ce-pergaminho h4.ce-pergaminho-titulo-bloco {
    margin: 1.2rem 0 0.45rem 0;
    font-size: 1.04rem;
    font-weight: 700;
    color: #33240e;
    letter-spacing: 0.01em;
    font-family: Georgia, "Times New Roman", serif;
}
/* A FONTE: o credito do texto citado, no rodape do bloco.

   Pequena e esmaecida de proposito -- ela assina o que foi escrito sem
   competir com o texto. Duas coisas aqui sao cuidado, e nao capricho:

     - o seletor traz "p" porque ".ce-pergaminho p" (especificidade
       maior) sobrescreveria o tamanho e a margem;
     - a cor e escura ANTES da opacidade. O papel e claro: aplicando
       opacidade em cima de um texto ja claro, o credito sumiria no
       fundo. Assim sobra contraste para os 0.6.

   0.68rem da ~11px, que e o chao para texto de apoio -- abaixo disso
   nao se le no celular. O hover devolve a opacidade inteira, para quem
   quiser ler com calma. */
.ce-pergaminho p.ce-pergaminho-fonte {
    margin: 1.15rem 0 0 0;
    font-size: 0.68rem;
    line-height: 1.5;
    color: #5a431f;
    opacity: 0.6;
    font-style: italic;
    text-align: right;
    letter-spacing: 0.02em;
    font-family: Georgia, "Times New Roman", serif;
}
.ce-pergaminho p.ce-pergaminho-fonte:hover {
    opacity: 1;
}
.ce-pergaminho ul {
    margin: 0 0 1.1rem 0;
    padding-left: 1.35rem;
}
.ce-pergaminho li {
    color: #4a3618;
    line-height: 1.6;
    margin-bottom: 0.3rem;
    font-family: Georgia, "Times New Roman", serif;
    font-size: 0.95rem;
}
/* O marcador da lista e um pontinho, do mesmo jeito que no documento
   antigo -- o Streamlit botaria um triangulo, que grita com o papel. */
.ce-pergaminho li::marker {
    color: #8a6a30;
}
/* O credito, no rodape do documento: quem publicou e quando. E de outro
   dono que a "fonte" -- a fonte e do texto, e esta e do app. Mesmo
   cuidado com a especificidade pelo mesmo motivo. */
.ce-pergaminho p.ce-pergaminho-credito {
    font-size: 0.76rem;
    line-height: 1.5;
    color: #8a6b38;
    margin: 0.8rem 0 0 0;
    font-style: italic;
    font-family: Georgia, "Times New Roman", serif;
}
.ce-pergaminho-rodape {
    display: flex;
    flex-wrap: wrap;
    gap: 0.45rem;
    align-items: center;
    margin-bottom: 0.8rem;
}
/* Em tela estreita (celular de aluno) o papel aperta: a borda rasgada
   continua, mas o texto ganha folga. */
@media (max-width: 640px) {
    .ce-pergaminho {
        padding: 1.1rem 1.15rem 1.3rem 1.15rem;
    }
    .ce-pergaminho-sombra {
        margin: -1rem 0 1.2rem 0;
    }
    [class*="st-key-pergaminho_"] button {
        padding: 0.55rem 2.9rem 0.55rem 0.9rem;
        font-size: 0.9rem;
    }
    /* No celular a fonte de 0.68rem com 0.6 de opacidade e o primeiro
       item a sumir, por ser o menor e o mais esmaecido da tela. Subir
       uma etapa nos dois mantem o contraste sem mudar a hierarquia:
       ela continua sendo a menor coisa do pergaminho. */
    .ce-pergaminho p.ce-pergaminho-fonte {
        font-size: 0.75rem;
        opacity: 0.72;
    }
}
/* Quem pede menos animacao nao recebe transform nem transicao */
@media (prefers-reduced-motion: reduce) {
    [class*="st-key-pergaminho_"] button {
        transition: none;
    }
    [class*="st-key-pergaminho_"] button:hover {
        transform: none;
    }
    .ce-pergaminho-exemplo {
        transform: none;
    }
}
</style>
"""


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


def render_pergaminhos():
    """Desenha a pagina de exemplos de crimes digitais (o pergaminhos)."""
    st.markdown(CSS_PERGAMINHOS, unsafe_allow_html=True)

    st.markdown(
        _html(
            """
            <p class="ce-pixel">EXEMPLOS DE CRIMES DIGITAIS</p>
            <p class="ce-subtitulo">Clique em um pergaminho para abrir o exemplo do golpe. Ao clicar em outro, o anterior fecha.</p>
            """
        ),
        unsafe_allow_html=True,
    )

    pergaminhos = carregar_pergaminhos()

    if not pergaminhos:
        st.info(
            "Nenhum exemplo de crime cadastrado ainda. Os exemplos "
            "pré-colocados vêm do arquivo `dados/exemplos_crime.json`, e o "
            "Professor e a Coordenação publicam os novos em "
            "\"Gerenciar Aulas\"."
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

        if st.button(
            f"{icone}  {titulo}",
            key=chave_widget,
            width="stretch",
        ):
            if esta_aberto:
                # Clicar no que ja estava aberto fecha.
                st.session_state[CHAVE_ABERTO] = None
            else:
                st.session_state[CHAVE_ABERTO] = pid
            st.rerun()

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


def _controle_adicionar(prefixo, chave_tipo):
    """O seletor de tipo + o botao que poe um bloco novo no fim da lista."""
    colunas = st.columns([3.4, 2.2, 4.4])
    tipo = colunas[0].selectbox(
        "Tipo do novo bloco",
        options=list(ROTULO_TIPO),
        format_func=lambda t: ROTULO_TIPO[t],
        key=chave_tipo,
    )
    if colunas[1].form_submit_button(
        "Adicionar",
        icon=":material/add:",
        key="%sadicionar" % prefixo,
        help="Acrescenta um bloco desse tipo no fim do pergaminho.",
    ):
        _pedir_operacao(prefixo, "inserir", _quantidade(prefixo), tipo)


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
            if linha[1].form_submit_button(
                "Subir", icon=":material/arrow_upward:",
                key="%ssobe_%d" % (prefixo, posicao),
                help="Move este bloco para cima.",
            ):
                _pedir_operacao(prefixo, "mover", posicao, -1)
            if linha[2].form_submit_button(
                "Descer", icon=":material/arrow_downward:",
                key="%sdesce_%d" % (prefixo, posicao),
                help="Move este bloco para baixo.",
            ):
                _pedir_operacao(prefixo, "mover", posicao, 1)
            if linha[3].form_submit_button(
                "Tirar", icon=":material/close:",
                key="%stira_%d" % (prefixo, posicao),
                help="Apaga este bloco.",
            ):
                _pedir_operacao(prefixo, "apagar", posicao)

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


def _formulario_publicar():
    """Formulario de publicacao de um exemplo de crime.

    Tudo dentro de um st.form, inclusive o construtor de blocos, para que
    o texto nao se mexa a cada tecla. Os botoes de bloco sao
    st.form_submit_button justamente porque st.button nao e permitido
    dentro de form.
    """
    _iniciar_blocos("pub_", [])

    with st.form("form_publicar_crime"):
        titulo = st.text_input("Título do golpe", key="pub_titulo")
        icone = st.text_input("Ícone (um emoji)", value="📜", key="pub_icone")
        categoria = st.selectbox("Categoria", CATEGORIAS, key="pub_categoria")
        categoria_livre = ""
        if categoria == "Outro":
            categoria_livre = st.text_input(
                "Escreva a categoria", key="pub_categoria_livre"
            )

        st.caption(
            "Conteúdo do pergaminho, de cima para baixo. Tipos: %s."
            % ", ".join(ROTULO_TIPO[t] for t in TIPOS_BLOCO)
        )
        _controle_adicionar("pub_", "pub_tipo_novo")
        _desenhar_blocos("pub_")

        publicar = st.form_submit_button("Publicar exemplo", type="primary")

    if not publicar:
        return

    blocos = _ler_blocos("pub_")
    if not titulo.strip() or not blocos:
        st.error(
            "Preencha o título do golpe e monte pelo menos um bloco de "
            "conteúdo."
        )
        return

    salvar_conteudo(
        titulo.strip(),
        resumo_do_bloco(blocos),
        st.session_state.get("username", ""),
        icone.strip() or "📜",
        (categoria_livre.strip() if categoria == "Outro" else categoria),
        "",
        "",
        "",
        blocos,
    )
    st.session_state[CHAVE_LIMPAR_PUBLICACAO] = True
    st.success("Exemplo publicado! Ele já aparece como pergaminho.")
    st.rerun()


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
        titulo = st.text_input("Título do golpe", key="ed_titulo")
        icone = st.text_input("Ícone (um emoji)", key="ed_icone")
        categoria = st.text_input("Categoria", key="ed_categoria")

        st.caption(
            "Conteúdo do pergaminho, de cima para baixo. Tipos: %s."
            % ", ".join(ROTULO_TIPO[t] for t in TIPOS_BLOCO)
        )
        _controle_adicionar("ed_", "ed_tipo_novo")
        _desenhar_blocos("ed_")

        salvar = st.form_submit_button("Salvar alterações", type="primary")

    if not salvar:
        return

    blocos = _ler_blocos("ed_")
    if not titulo.strip() or not blocos:
        st.error(
            "O título e pelo menos um bloco de conteúdo não podem ficar "
            "vazios."
        )
        return

    atualizar_conteudo(
        pergaminho["id"],
        titulo.strip(),
        resumo_do_bloco(blocos),
        icone.strip() or "📜",
        categoria.strip(),
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
    st.success("Exemplo atualizado.")
    st.rerun()


def render_gerenciar_crime():
    """Pagina de publicacao e edicao dos exemplos de crime.

    E o que a coordenacao usa: publica um golpe novo, edita um exemplo
    pre-colocado, ou inativa um que nao serve mais. Tudo o que aparece
    aqui vira pergaminho na pagina dos alunos.

    As duas chamadas de baixo sao obrigatorias e vem ANTES de qualquer
    widget: e onde os pedidos de reordenar/apagar blocos e as limpezas
    de formulario sao aplicados, sempre num momento em que nenhum campo
    da tela existe ainda. Depois do primeiro widget elas dariam erro.
    """
    _aplicar_operacao()
    _aplicar_limpezas()

    st.markdown(
        _html(
            """
            <p class="ce-pixel">EXEMPLOS DE CRIMES DIGITAIS</p>
            <p class="ce-subtitulo">Publique um exemplo de golpe novo, edite um dos pré-colocados, ou tire da lista o que não serve mais. Tudo o que for publicado aqui aparece como pergaminho para o aluno.</p>
            """
        ),
        unsafe_allow_html=True,
    )

    st.subheader("Publicar um exemplo novo")
    _formulario_publicar()

    st.divider()
    st.subheader("Exemplos já publicados")

    pergaminhos = carregar_pergaminhos()
    if not pergaminhos:
        st.info("Nenhum exemplo publicado ainda.")
        return

    edicao = st.session_state.get("crime_em_edicao")
    if edicao is not None:
        alvo = next(
            (p for p in pergaminhos if p["id"] == edicao),
            None,
        )
        if alvo is not None:
            st.markdown("#### Editando: %s" % alvo.get("titulo", ""))
            _formulario_editar(alvo)
            st.divider()

    # Se um pedido de bloco foi gravado AGORA, ele so existe na tela na
    # execucao seguinte -- e nada dispara essa execucao sozinho: o clique
    # ja gastou a unica delas. Sem este rerun o botao de adicionar,
    # subir e tirar pareceria nao fazer nada.
    if st.session_state.get(CHAVE_OPERACAO_BLOCO):
        st.rerun()

    for pergaminho in pergaminhos:
        pid = pergaminho["id"]
        titulo = pergaminho.get("titulo") or ""
        icone = pergaminho.get("icone") or "📜"
        origem = pergaminho.get("origem") or "publicado"
        rotulo_origem = (
            "pré-colocado" if origem == "pre_colocado" else "publicado"
        )

        with st.expander(f"{icone}  {titulo}", expanded=False):
            rotulo_aviso = ""
            if origem == "pre_colocado":
                rotulo_aviso = (
                    " — os itens pré-colocados voltam ao texto de "
                    "`dados/exemplos_crime.json` na próxima carga do app."
                )
            st.caption("Origem: %s%s" % (rotulo_origem, rotulo_aviso))

            for bloco in _blocos_do(pergaminho):
                if bloco["tipo"] == "titulo":
                    st.markdown("#### %s" % bloco["texto"])
                elif bloco["tipo"] == "subtitulo":
                    st.markdown("**%s**" % bloco["texto"])
                elif bloco["tipo"] == "fonte":
                    st.caption("Fonte: %s" % bloco["texto"])
                else:
                    st.write(bloco["texto"])

            col1, col2 = st.columns(2)
            if col1.button("Editar", key=f"editar_crime_{pid}"):
                st.session_state["crime_em_edicao"] = pid
                st.rerun()
            if col2.button("Inativar", key=f"inativar_crime_{pid}"):
                inativar_conteudo(pid)
                st.warning("Exemplo inativado. Ele não aparece mais para o aluno.")
                st.rerun()
