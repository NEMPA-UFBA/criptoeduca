"""Folha de estilo da identidade visual do CriptoEduca.

O CSS do app estava espalhado: app.py, modules/login.py e
modules/sessaoInterativa.py escreviam as mesmas cores em lugares diferentes.
Isso não é só bagunça -- é o que produz a inconsistência de hover e de
override que cada um dos arquivos tentava consertar por conta própria. Por
isso a paleta fica aqui, num lugar só, e as páginas pedem o que precisam.

A paleta é a que o login e o mural já usavam, então o app não muda de cor
nenhuma: fundo #0f172a, painel #1e293b, roxo #4F46E5, ciano #38bdf8.

A fonte Press Start 2P é usada só em títulos. Ela é pixelada e tem avanço
de 1em por caractere: em texto corrido ela fica ilegível, e o próprio app.py
já restringe o uso dela aos h1. Aqui a regra é a mesma.

Sobre o HTML: o Streamlit passa o texto do st.markdown pelo interpretador de
Markdown antes de entregar ao navegador. Duas coisas quebram com HTML
cru, e as duas apareceram na verificação no navegador:

  1. Linha começando com 4 espaços vira bloco de código. A indentação do
     próprio arquivo Python contam.
  2. Linha em branco no meio do HTML encerra o bloco HTML e o resto volta
     a ser Markdown -- aí sobra um "</div>" escrito na tela.

Por isso os trechos de HTML do app são montados sem indentação e sem linha
em branco. Ver _html() em modules/mainmenu.py.
"""

from pathlib import Path

import streamlit as st

# As folhas de estilo ficam em static/css/, uma por tela. Antes cada uma era
# uma string enorme dentro do .py. Em arquivo .css o editor colore e confere a
# sintaxe, e os .py ficam so com a logica.
PASTA_CSS = Path(__file__).resolve().parent.parent / "static" / "css"


def aplicar_css(nome):
    """Injeta static/css/<nome> na pagina.

    st.html com um Path de .css: o Streamlit poe o conteudo dentro de
    <style> e, como so ha estilo, manda para o container de eventos -- nao
    cria um elemento vazio no meio da pagina, como o st.markdown criava.
    Quando a tela deixa de chamar esta funcao, o <style> sai da pagina
    (verificado no navegador), entao o CSS de uma tela nao vaza para outra.

    CUIDADO: o st.html passa o conteudo pelo sanitizador DOMPurify, que
    DESCARTA o <style> inteiro se o texto tiver "<" seguido de letra ou "/",
    mesmo dentro de um comentario CSS (ex.: escrever <strong> num comentario).
    Nos .css, cite elementos HTML sem os sinais de menor e maior.
    """
    st.html(PASTA_CSS / nome)

# Cores da identidade. Nomeadas para não repetir o literal hex em dois
# lugares e acabar divergindo.
FUNDO = "#0f172a"
PAINEL = "#1e293b"
PAINEL_ALTO = "#24334a"
ROXO = "#4F46E5"
CIANO = "#38bdf8"
AMBAR = "#f59e0b"
VERDE = "#22c55e"
TEXTO = "#e2e8f0"
TEXTO_FRACO = "#94a3b8"



# Regras que valem para TODAS as telas logadas, inclusive as que nao chamam
# aplicar_estilo() (mural, paineis, perfil). Por isso ficam numa folha a
# parte: o app.py injeta esta uma vez, logo depois do CSS da barra lateral.


def aplicar_estilo():
    """Injeta a folha de estilo da identidade (static/css/identidade.css)."""
    aplicar_css("identidade.css")


def aplicar_responsividade():
    """Injeta os ajustes de tela estreita (static/css/responsivo.css)."""
    aplicar_css("responsivo.css")


def html_bruto(trecho):
    """Deixa um trecho de HTML pronto para o interpretador de Markdown.

    O Streamlit passa o texto do st.markdown pelo Markdown antes de mandar
    ao navegador, e HTML cru tem duas armadilhas:

      - linha começando com 4 espaços vira bloco de código (a indentação do
        próprio arquivo Python conta);
      - linha em branco no meio do HTML encerra o bloco HTML, e o resto
        volta a ser Markdown -- sobrando um "</div>" escrito na tela.

    As duas apareceram na verificação no navegador. Por isso este função
    tira a indentação e remove as linhas em branco.
    """
    linhas = [linha.strip() for linha in trecho.strip().splitlines()]
    return "\n".join(linha for linha in linhas if linha)
