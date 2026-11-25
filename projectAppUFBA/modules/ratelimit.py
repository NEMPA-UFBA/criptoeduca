"""
Limite de tentativas por cliente, com estado compartilhado entre sessoes.

Por que nao em st.session_state: o contador vive na sessao do navegador, e
abrir outra aba comeca do zero. Quem esta tentando adivinhar a chave do
Professor abre outra aba. O estado precisa ser do processo, nao da sessao.

Por que nao no SQLite: o estado e descartavel por definicao -- so importa
para dizer "errou 5 vezes, espera 30 s". Gravar no banco transformaria
tentativa de acesso em registro permanente, e o arquivo esta versionado no
Git.

O estado vive na memoria do processo, entao some quando o servidor reinicia
nao e compartilhado entre replicas. Em uma maquina so, que e o caso do
projeto hoje, isso nao faz diferenca.

ESCALADA (a regra de hoje, menos punitiva que a janela antiga):

    5 erros ->  30 s      5 erros -> 2 min     5 erros -> 4 min
    5 erros ->  1 min     5 erros -> 3 min     5 erros -> 5 min (teto)

Depois de vencer o bloqueio a pessoa ganha 5 tentativas de novo, mas o nivel
NAO volta ao inicial: ele so reseta no acerto (zerar). Errar as 5 de novo e o
que faz o tempo subir, e depois do sexto bloqueio o tempo fica em 5 minutos
para sempre. Assim quem erra de boa-fede passa por um bloqueio de 30 s, e so
quem insiste escala.

O tempo que falta e exibido na tela em contagem regressiva (ver
_aguardar_desbloqueio em modules/login.py). Aqui so importa dizer QUANTO
falta e QUANDO o nivel sobe.
"""
import ipaddress
import math
import threading
import time

import streamlit as st

# Quantas tentativas erradas antes do primeiro bloqueio. Cinco da para digitar
# e corrigir uma chave de 12 caracteres sem tomar bloqueio por descuido.
MAX_TENTATIVAS = 5

# Duracao de cada bloqueio, em segundos, por nivel (1o, 2o, 3o...). O ultimo
# valor tambem e o teto: depois de chegar em 5 minutos, errar de novo fica
# em 5 minutos -- e la e onde a escada para.
ESPERAS_SEGUNDOS = (30, 60, 120, 180, 240, 300)

# Teto de clientes guardados ao mesmo tempo. Ver _conter_memoria.
MAX_CLIENTES = 5000

# Nomes das acoes, para nao repetir string magica na tela.
CHAVE_PROFESSOR = "chave_professor"

# Senha de login. Antes nao tinha limite nenhum aqui: o modulo ja era generico
# por causa deste parametro, e a acao da chave era a unica ligada.
#
# A acao LOGIN e contada em dois alvos ao mesmo tempo: a conta atacada
# (estavel, nao cai com F5) e o cliente atacante (barra varredura). Ver
# _montar_chave.
LOGIN = "login"

# Cada chave vale um dicionario:
#   {"falhas": erros desde o ultimo bloqueio, "nivel": proximo bloqueio,
#    "bloqueio_ate": momento monotonic em que o bloqueio vence,
#    "ultimo": momento da ultima falha, so para ordenar a limpeza}
_estado = {}
_tranca = threading.Lock()


def _ip_aceitavel(ip):
    """Diz se o valor de st.context.ip_address serve como identificador.

    Precisa ser str E parsear como IP. Sem essa checagem, qualquer objeto
    truthy vira chave do limite, e o str() dele pode mudar a cada requisicao.

    Medido: sob AppTest, st.context.ip_address devolve um MagicMock, que e
    truthy e tem um id() proprio. A chave virava `ip:<MagicMock name=... id=...>`
    e mudava a cada rerun, entao cada tentativa contava como um cliente novo e
    o limite nunca disparava -- sete tentativas, sete orcamentos novos de cinco.
    O limitador falhava ABERTO, que e a direcao errada para um controle de
    seguranca. Validando o tipo, o teste cai no proximo identificador e o
    limite volta a valer.
    """
    if not isinstance(ip, str):
        return False
    try:
        ipaddress.ip_address(ip.strip())
    except ValueError:
        return False
    return True


def _identificar_cliente():
    """
    Devolve o melhor identificador de cliente que o Streamlit expoe.

    A ordem e IP, depois cabecalho de proxy, depois o cookie XSRF. Em teste
    local nao existe IP: medido, st.context.ip_address vem None e nao ha
    X-Forwarded-For, porque so existe proxy quando ha algo na frente. Sobra o
    cookie, que e do navegador -- abrir outra aba nao zera o contador, mas
    limpar os cookies zera.

    Em deploy com proxy na frente, o IP aparece e passa a ser o identificador
    sem precisar mudar nada aqui.
    """
    ip = getattr(st.context, "ip_address", None)
    if _ip_aceitavel(ip):
        return f"ip:{ip.strip()}"

    cabecalhos = getattr(st.context, "headers", None) or {}
    encaminhado = cabecalhos.get("X-Forwarded-For")
    if encaminhado:
        # Mesmo cuidado com o cabecalho: so aceita se for um IP de verdade.
        primeiro = encaminhado.split(",")[0].strip()
        if _ip_aceitavel(primeiro):
            return f"proxy:{primeiro}"

    for parte in (cabecalhos.get("Cookie") or "").split(";"):
        parte = parte.strip()
        if parte.startswith("_streamlit_xsrf="):
            return f"xsrf:{parte}"

    # Sem IP e sem cookie: cai num balde so. Melhor que nao limitar, e
    #_register guarda o cliente como anonimo.
    return "anonimo"


def _bloqueado(estado, agora):
    """O estado esta valendo bloqueio neste instante?"""
    ate = estado.get("bloqueio_ate")
    return ate is not None and agora < ate


def espera_do_nivel(nivel):
    """Segundos de espera do nivel pedido, com teto no ultimo da escada."""
    indice = min(max(1, int(nivel)), len(ESPERAS_SEGUNDOS)) - 1
    return ESPERAS_SEGUNDOS[indice]


def _conter_memoria():
    """
    Impede que o dicionario cresca sem fim.

    Com o cookie como identificador, um cliente que vaie o cookie a cada
    tentativa cria uma entrada nova por vez. Sem teto, isso vira consumo de
    memoria dirigido por terceiro.
    """
    if len(_estado) <= MAX_CLIENTES:
        return

    agora = time.monotonic()

    # 1. Entrada que nao significa nada: sem falhas, sem bloqueio e no nivel
    #    inicial. As demais guardam o nivel, que so o acerto pode zerar --
    #    jogar fora uma delas abriria a escada para quem esta esperando.
    inuteis = [
        chave for chave, estado in _estado.items()
        if not estado["falhas"]
        and not estado.get("nivel", 1) > 1
        and not _bloqueado(estado, agora)
    ]
    for chave in inuteis:
        del _estado[chave]

    if len(_estado) <= MAX_CLIENTES:
        return

    # 2. Ainda acima do teto: joga fora os mais antigos, comeca pelos que nao
    #    estao bloqueados -- perder um bloqueio e abrir a porta.
    por_idade = sorted(_estado, key=lambda chave: _estado[chave]["ultimo"])
    ordem = sorted(por_idade, key=lambda chave: _bloqueado(_estado[chave], agora))
    for chave in ordem:
        if len(_estado) <= MAX_CLIENTES:
            return
        del _estado[chave]


def _montar_chave(acao, alvo=None):
    """
    Monta a chave do dicionario: (acao, alvo).

    Sem "alvo", quem e identificado e o cliente que esta atacando (IP, proxy
    ou cookie). Com "alvo", o que se conta e a conta que esta sendo atacada, e
    nao quem ataca.

    As duas identificacoes sao necessarias porque cada uma falha de um jeito:

    - so o cliente nao segura nada, porque o identificador disponivel (o cookie
      XSRF) rotaciona a cada carregamento de pagina. Medido: F5 devolve o
      contador cheio.
    - so o alvo nao segura contra varredura, que e uma tentativa em cada conta
      de uma vez. Com 300 contas, o atacante faz 300 palpites por nivel.

    Por isso o login conta nos dois e barra se qualquer um dos dois estourar.
    """
    return (acao, alvo if alvo is not None else _identificar_cliente())


def excedeu(acao, alvo=None):
    """Diz se o alvo esta bloqueado AGORA, com o tempo ainda correndo."""
    agora = time.monotonic()
    with _tranca:
        estado = _estado.get(_montar_chave(acao, alvo))
        if estado is None:
            return False
        return _bloqueado(estado, agora)


def registrar_falha(acao, alvo=None):
    """Conta uma tentativa errada e arma o bloqueio quando faltam 5.

    Erro DURANTE o bloqueio e ignorado: na tela o botao esta desabilitado, e
    contar aqui so estenderia a espera de quem ja esta esperando -- o contrario
    de menos punitivo.
    """
    agora = time.monotonic()
    chave = _montar_chave(acao, alvo)
    with _tranca:
        estado = _estado.get(chave)
        if estado is None:
            estado = {"falhas": 0, "nivel": 1, "bloqueio_ate": None, "ultimo": agora}
            _estado[chave] = estado

        if _bloqueado(estado, agora):
            return

        estado["falhas"] += 1
        estado["ultimo"] = agora

        if estado["falhas"] >= MAX_TENTATIVAS:
            # O nivel de ANTES do bloqueio e o que decide a espera. Depois
            # ele sobe, e so o acerto (zerar) devolve ao inicial.
            estado["bloqueio_ate"] = agora + espera_do_nivel(estado["nivel"])
            estado["falhas"] = 0
            estado["nivel"] = min(
                estado["nivel"] + 1, len(ESPERAS_SEGUNDOS)
            )

        _conter_memoria()


def zerar(acao, alvo=None):
    """Apaga o estado depois do acerto: unico caminho de volta ao nivel 1."""
    chave = _montar_chave(acao, alvo)
    with _tranca:
        _estado.pop(chave, None)


def restantes(acao, alvo=None):
    """Quantas tentativas sobram antes do PROXIMO bloqueio. 0 se bloqueado."""
    agora = time.monotonic()
    with _tranca:
        estado = _estado.get(_montar_chave(acao, alvo))
        if estado is None:
            return MAX_TENTATIVAS
        if _bloqueado(estado, agora):
            return 0
        return max(0, MAX_TENTATIVAS - estado["falhas"])


def bloqueio_restante(acao, alvo=None):
    """Segundos inteiros até o bloqueio vencer. 0 quando nao esta bloqueado.

    Arredonda para CIMA: o contador comeca mostrando a espera inteira
    ("0:30") em vez de pular para "0:29" no primeiro tique.
    """
    agora = time.monotonic()
    with _tranca:
        estado = _estado.get(_montar_chave(acao, alvo))
        if estado is None or estado.get("bloqueio_ate") is None:
            return 0
        return max(0, math.ceil(estado["bloqueio_ate"] - agora))


def formatar_tempo(segundos):
    """Vira segundos em "0:47" / "1:05", o formato da contagem regressiva."""
    segundos = max(0, int(segundos))
    return "%d:%02d" % (segundos // 60, segundos % 60)
