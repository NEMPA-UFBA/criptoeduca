"""Tela de carregamento das páginas que consultam o banco.

Como funciona, em uma frase: antes de desenhar a página, os dados que ela vai
usar são buscados em linhas de execução paralelas (threads), todas ao mesmo
tempo. Se isso terminar
rápido, nada aparece; se demorar, uma barra de progresso moldurada mostra as
etapas até os dados chegarem. Depois a página é desenhada normalmente, e as
funções de leitura dela encontram tudo pronto no cache.

Por que buscar os dados antes, e não colocar a barra dentro de cada página:
as funções de leitura (carregar_modulos, carregar_estado_modulos,
carregar_mural...) já têm @st.cache_data / @st.cache_resource. Chamá-las aqui,
com os MESMOS argumentos que a página usa, enche o cache; quando a página as
chama de novo, a resposta vem da memória, sem ir ao banco. Assim a barra mostra
progresso real sem reescrever nenhuma página.

Por que uma thread: o Streamlit só manda um elemento para o navegador quando
o código chega até ele. Enquanto uma consulta lenta roda, nada é redesenhado.
Com a consulta numa thread, o código principal fica livre para atualizar a
barra a cada 0,1 s e decidir, depois de 0,15 s, se a barra precisa aparecer.
É o padrão de multithreading descrito na documentação do Streamlit
(add_script_run_ctx), que dá à thread o contexto da sessão.

Por que a barra só aparece quando há espera: com os dados no cache, a página
carrega em milissegundos. Uma barra desenhada e apagada nesse tempo seria só
um piscar a cada clique.
"""
import html
import logging
import threading
import time

import streamlit as st
from streamlit.runtime.scriptrunner import add_script_run_ctx, get_script_run_ctx

from modules.estilo import aplicar_css

logger = logging.getLogger(__name__)

# Abaixo disto, a espera não é percebida e a barra nem é desenhada.
LIMIAR_SEGUNDOS = 0.15
# De quanto em quanto tempo a barra é redesenhada enquanto espera.
INTERVALO_SEGUNDOS = 0.1
# Quantidade de barrinhas verticais. São só ilustrativas: não correspondem às
# etapas, apenas dividem a barra em partes iguais.
SEGMENTOS = 20
# Duração mínima da tela de transição entre o login e o menu. Curta o
# bastante para não atrasar quem tem banco rápido, longa o bastante para a
# barra ser vista enchendo, em vez de piscar. Se o banco demorar mais que
# isso, a barra fica até os dados chegarem.
TRANSICAO_MINIMA_SEGUNDOS = 0.6
# Chave da sessão que pede a tela de transição (ver marcar_transicao_do_login).
CHAVE_TRANSICAO = "_transicao_login"
# Quantas consultas antecipadas (as desta tela) podem estar no banco ao mesmo
# tempo, somando todas as sessões. O pool tem 10 conexões
# (DB_POOL_MAX_CONNECTIONS em modules/database.py); 4 deixa 6 livres para as
# consultas normais das páginas. Ver _disparar_etapas.
_VAGAS_NO_BANCO = threading.BoundedSemaphore(4)


def _html_da_barra(porcento, etapa, transicao=False):
    """Monta o HTML da barra moldurada.

    O preenchimento é arredondado para cima até o próximo segmento inteiro,
    para nunca aparecer meia barrinha acesa.
    """
    passo = 100 / SEGMENTOS
    acesos = min(SEGMENTOS, int(-(-porcento // passo)))  # divisão arredondando para cima
    largura = acesos * passo
    # A classe ce-transicao só existe na tela login -> menu: é ela que
    # recolhe a navegação lateral (regra no fim de carregamento.css).
    classes = "ce-carregando ce-transicao" if transicao else "ce-carregando"
    return (
        f'<div class="{classes}" role="progressbar" aria-valuemin="0" '
        f'aria-valuemax="100" aria-valuenow="{int(porcento)}" '
        f'aria-label="Carregando: {html.escape(etapa)}">'
        '<p class="ce-carregando-marca">CriptoEduca</p>'
        '<div class="ce-carregando-trilho">'
        f'<div class="ce-carregando-barra" style="width:{largura:.2f}%"></div>'
        "</div>"
        f'<p class="ce-carregando-etapa"><span>{html.escape(etapa)}</span>'
        f"<span>{int(porcento)}%</span></p>"
        "</div>"
    )


def preparar_pagina(etapas, transicao=None):
    """Busca os dados da página e mostra a barra se a espera for perceptível.

    etapas: lista de (rótulo, função, argumentos), na ordem em que devem rodar.
    Os argumentos têm que ser IGUAIS aos que a página usa, inclusive na forma
    (posicional ou nomeado), senão o cache não reaproveita o resultado.

    transicao: None (uso normal) ou o dicionário devolvido por
    marcar_transicao_do_login (inicio, fim e quanto já foi mostrado). Com ele, a barra aparece SEMPRE, sem o limiar
    de 0,15 s, e fica na tela até o fim do prazo mesmo que os dados cheguem
    antes. O preenchimento acompanha o MENOR entre o progresso real e o tempo
    passado, então a barra avança de forma contínua em vez de saltar de 5%
    para 100%. É a tela de transição entre o login e o menu.

    Sempre cria a vaga da barra (st.empty), mesmo quando ela não aparece: a
    posição dos elementos da página fica igual em toda execução. Se a vaga
    existisse só às vezes, o conteúdo mudaria de posição e o Streamlit
    mostraria o conteúdo antigo por baixo do novo (a "sobreposição").

    Erros nas etapas são só registrados no log: a página chama as mesmas
    funções logo depois e mostra a mensagem de erro dela, como sempre fez.
    """
    total = len(etapas)
    if transicao is not None and etapas:
        # Na transição a barra já nasce desenhada, no ponto em que estava.
        # Com st.empty() aqui, uma execução interrompida no meio (o
        # componente de cookie faz isso no F5 e logo depois do login) apagava
        # a barra e desenhava de novo: um piscar no meio da transição.
        aplicar_css("carregamento.css")
        porcento = transicao["porcento"]
        vaga = st.markdown(
            _html_da_barra(porcento, _etapa_em(etapas, porcento), True),
            unsafe_allow_html=True,
        )
    else:
        vaga = st.empty()
    if not etapas:
        return

    concluidas = set()
    threads = _disparar_etapas(etapas, concluidas)

    def ainda_trabalhando():
        return any(t.is_alive() for t in threads)

    if transicao is None:
        # Espera até o limiar. As etapas correm juntas, então o tempo de
        # espera é o da consulta mais lenta, não a soma de todas.
        prazo = time.monotonic() + LIMIAR_SEGUNDOS
        for t in threads:
            t.join(max(0.0, prazo - time.monotonic()))
        if not ainda_trabalhando():
            return  # rápido: dados já estavam no cache, nada a mostrar
        inicio = fim = None
    else:
        inicio, fim = transicao["inicio"], transicao["fim"]

    def falta_tempo():
        return fim is not None and time.monotonic() < fim

    # Na transição, o CSS também recolhe a navegação lateral enquanto a
    # barra estiver na tela (regra com :has em carregamento.css). Quando a
    # barra sai, a lateral volta sozinha: não há estado para desfazer.
    if transicao is None:
        aplicar_css("carregamento.css")
        desenhado = None
    else:
        desenhado = transicao["porcento"]
    while ainda_trabalhando() or falta_tempo():
        real = 100 * len(concluidas) / total
        if fim is not None:
            # Na transição, a barra não passa do tempo decorrido: com os
            # dados no cache ela ainda leva o prazo inteiro para encher.
            decorrido = 100 * (time.monotonic() - inicio) / (fim - inicio)
            real = min(real, decorrido)
        # Começa em 5% para a moldura não aparecer vazia.
        porcento = max(5, min(100, round(real)))
        if transicao is not None:
            # A barra da transição nunca volta para trás, nem quando a
            # execução é interrompida e as etapas recomeçam a contagem.
            porcento = max(porcento, transicao["porcento"])
            transicao["porcento"] = porcento
        if porcento != desenhado:  # só redesenha quando algo mudou
            vaga.markdown(
                _html_da_barra(
                    porcento, _etapa_em(etapas, porcento), transicao is not None
                ),
                unsafe_allow_html=True,
            )
            desenhado = porcento
        time.sleep(INTERVALO_SEGUNDOS)
    vaga.empty()


def _etapa_em(etapas, porcento):
    """Legenda da barra: a etapa que corresponde à fração acesa.

    No uso normal a fração vem das etapas concluídas, então a legenda é a
    primeira que ainda não terminou. Na transição a fração acompanha o tempo,
    e a legenda avança junto com as barrinhas.
    """
    total = len(etapas)
    return etapas[min(total - 1, int(porcento * total / 100))][0]


def marcar_transicao_do_login():
    """Prazo da tela de transição login -> menu, guardado na sessão.

    login.py (senha certa) e app.py (login lembrado pelo cookie) gravam
    _transicao_login = True. Na primeira execução logada, este True vira o
    dicionário {inicio, fim, porcento}, com fim = inicio +
    TRANSICAO_MINIMA_SEGUNDOS.

    Por que guardar o prazo, e não só um aviso de "mostre a barra": logo
    depois do login, o navegador confirma o cookie e o Streamlit interrompe a
    execução para rodar o app de novo. Com o prazo na sessão, a execução
    seguinte continua a mesma barra, do mesmo ponto, em vez de começar outra.
    app.py apaga a chave quando a transição termina.

    Devolve None quando não há transição pendente.
    """
    valor = st.session_state.get(CHAVE_TRANSICAO)
    if not valor:
        return None
    if valor is True:
        agora = time.monotonic()
        valor = {
            "inicio": agora,
            "fim": agora + TRANSICAO_MINIMA_SEGUNDOS,
            # Quanto da barra já foi mostrado. preparar_pagina atualiza este
            # valor a cada quadro, para a barra não voltar atrás.
            "porcento": 5,
        }
        st.session_state[CHAVE_TRANSICAO] = valor
    return valor


def pagina_inicial(tipo):
    """Primeira página do menu para o perfil (ver _PAGINA_INICIAL)."""
    return _PAGINA_INICIAL.get(tipo, "Painel Principal")


def _disparar_etapas(etapas, concluidas=None):
    """Começa todas as etapas AO MESMO TEMPO, uma thread para cada uma.

    Antes as etapas rodavam uma depois da outra numa thread só: a Home do
    aluno esperava modulos + mural + progresso, somados. Juntas, a espera vira
    a da consulta mais lenta. O banco aguenta: o pool é ThreadedConnectionPool,
    feito para ser usado por várias threads.

    O semáforo _VAGAS_NO_BANCO limita quantas destas consultas antecipadas
    podem estar no banco ao mesmo tempo, somando TODAS as sessões. O pool tem
    10 conexões e, quando acabam, o psycopg2 não espera: levanta PoolError.
    Sem o limite, alguns logins simultâneos de professores (5 etapas cada)
    esgotariam o pool e a página de outra pessoa quebraria. Com ele, sobram
    sempre conexões para as consultas normais das páginas.

    concluidas: conjunto onde cada thread põe o índice da sua etapa ao
    terminar (com ou sem erro). Pode ser None quando ninguém acompanha.
    Devolve a lista de threads, já iniciadas.
    """
    contexto = get_script_run_ctx()
    trava = threading.Lock()

    def trabalhar(indice, funcao, argumentos):
        try:
            with _VAGAS_NO_BANCO:
                funcao(*argumentos)
        except Exception:  # a página trata o erro quando chamar de novo
            logger.warning(
                "Etapa de carregamento falhou: %s",
                getattr(funcao, "__name__", repr(funcao)),
                exc_info=True,
            )
        finally:
            if concluidas is not None:
                with trava:
                    concluidas.add(indice)

    threads = []
    for indice, (_rotulo, funcao, argumentos) in enumerate(etapas):
        t = threading.Thread(
            target=trabalhar,
            args=(indice, funcao, argumentos),
            name="carregamento-%d" % indice,
            daemon=True,
        )
        # Dá à thread o contexto da sessão atual, para o cache funcionar nela.
        add_script_run_ctx(t, contexto)
        t.start()
        threads.append(t)
    return threads


# Primeira página de cada perfil: o primeiro item de "opcoes" em app.py.
# Se um dia mudar lá, mude aqui também. Se ficar diferente, nada quebra: o
# aquecimento só deixa de adiantar os dados daquela página.
_PAGINA_INICIAL = {
    "Administrador": "Painel da Coordenação",
    "Professor": "Painel Geral",
    "Aluno": "Painel Principal",
}


def aquecer_cache_do_login(username, tipo):
    """Logo depois do login certo, começa a buscar o que a 1ª tela vai pedir.

    Por que: na execução seguinte ao login, o app pede, uma de cada vez,
    obter_primeiro_acesso (só aluno), obter_dados_perfil e os dados da
    página inicial. Cada um é uma ida ao banco, e elas se somavam. Aqui todas
    começam juntas, em paralelo, enquanto o Streamlit ainda está trocando a
    tela de login pelo menu. Quando o app chega em cada chamada, ou o
    resultado já está no cache, ou a chamada espera a busca que já está em
    andamento (o st.cache_data tem uma trava por chave e não consulta o banco
    duas vezes para a mesma coisa).

    Não espera nada e não desenha nada: só dispara as threads e volta.
    Os argumentos são os mesmos, e na mesma forma, que app.py usa.
    """
    etapas = etapas_do_menu(username, tipo, precisa_primeiro_acesso=True)
    etapas += etapas_da_pagina(_PAGINA_INICIAL.get(tipo), tipo, username)
    _disparar_etapas(etapas)


def etapas_do_menu(username, tipo, precisa_primeiro_acesso):
    """O que app.py consulta ANTES de desenhar o menu lateral.

    obter_dados_perfil (nome e foto do cabeçalho) e, só para aluno que ainda
    não tem o valor na sessão, obter_primeiro_acesso. Usado em dois lugares:
    no aquecimento do login (acima) e no topo da tela logada, para a barra de
    carregamento aparecer já nessa espera (ver app.py).
    """
    from modules.database import obter_dados_perfil, obter_primeiro_acesso

    etapas = [("Abrindo seu perfil", obter_dados_perfil, (username,))]
    if tipo == "Aluno" and precisa_primeiro_acesso:
        etapas.append(
            ("Conferindo o primeiro acesso", obter_primeiro_acesso, (username,))
        )
    return etapas


def etapas_da_pagina(pagina, tipo, username):
    """Quais dados cada página lenta usa, na forma exata em que ela os pede.

    Fica num lugar só para ser fácil manter: se uma página passar a usar outra
    função de leitura, é aqui que ela entra. Páginas que não consultam o banco
    (Equipe, Turma, Notas) devolvem lista vazia.
    """
    # Importados aqui dentro para não criar dependência circular na carga
    # dos módulos (modules.modulos e modules.database importam o Streamlit).
    from modules.database import (
        carregar_cifras_compartilhadas,
        carregar_estado_modulos,
        carregar_mural,
        carregar_pergaminhos,
        contar_usuarios_por_tipo,
        listar_progresso_recente,
        listar_seguidos,
    )
    from modules.modulos import carregar_modulos

    modulos = ("Abrindo os módulos", carregar_modulos, ())
    estado = ("Buscando seu progresso", carregar_estado_modulos, (username,))

    if pagina in ("Painel da Coordenação", "Painel Geral", "Painel Principal"):
        etapas = [modulos, ("Lendo o mural", carregar_mural, ())]
        if tipo == "Aluno":
            return etapas + [estado]
        return etapas + [
            ("Reunindo os exemplos de golpe", carregar_pergaminhos, ()),
            ("Contando os usuários", contar_usuarios_por_tipo, ()),
            ("Buscando a atividade recente", listar_progresso_recente, (5,)),
        ]
    if pagina == "Módulos de Aprendizado":
        # Mapa, página do módulo e leitura usam os mesmos dois conjuntos.
        return [modulos, estado]
    if pagina == "Meu Progresso":
        return [modulos, estado]
    if pagina == "Mural de Criptografia":
        return [
            ("Lendo o mural", carregar_mural, ()),
            ("Buscando quem você segue", listar_seguidos, (username,)),
            ("Abrindo suas cifras", carregar_cifras_compartilhadas, (username,)),
        ]
    if pagina == "Exemplos de Crimes Digitais":
        return [("Reunindo os exemplos de golpe", carregar_pergaminhos, ())]
    return []
