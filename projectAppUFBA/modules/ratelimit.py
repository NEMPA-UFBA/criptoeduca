"""
Limite de tentativas por cliente, com estado compartilhado entre sessoes.

Por que nao em st.session_state: o contador vive na sessao do navegador, e
abrir outra aba comeca do zero. Quem esta tentando adivinhar a chave do
Professor abre outra aba. O estado precisa ser do processo, nao da sessao.

Por que nao no SQLite: o contador e descartavel por definicao -- so vale
enquanto a janela esta aberta. Gravar no banco transformaria tentativa de
acesso em registro permanente, e o arquivo esta versionado no Git.

O estado vive na memoria do processo, entao some quando o servidor reinicia e
nao e compartilhado entre replicas. Em uma maquina so, que e o caso do
projeto hoje, isso nao faz diferenca.
"""
import threading
import time
from collections import deque

import streamlit as st

# Quantas chaves erradas o mesmo cliente pode mandar dentro da janela antes de
# ficar bloqueado. Cinco da para digitar e corrigir uma chave de seis digitos
# sem tomar bloqueio por descuido.
MAX_TENTATIVAS = 5
JANELA_SEGUNDOS = 300

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

_tentativas = {}
_tranca = threading.Lock()


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
    if ip:
        return f"ip:{ip}"

    cabecalhos = getattr(st.context, "headers", None) or {}
    encaminhado = cabecalhos.get("X-Forwarded-For")
    if encaminhado:
        return f"proxy:{encaminhado.split(',')[0].strip()}"

    for parte in (cabecalhos.get("Cookie") or "").split(";"):
        parte = parte.strip()
        if parte.startswith("_streamlit_xsrf="):
            return f"xsrf:{parte}"

    # Sem IP e sem cookie: cai num balde so. Melhor que nao limitar, e
    #_register guarda o cliente como anonimo.
    return "anonimo"


def _descartar_velhos(registro, agora):
    """Tira de dentro da janela o que ja passou. Registro fica ordenado."""
    corte = agora - JANELA_SEGUNDOS
    while registro and registro[0] <= corte:
        registro.popleft()


def _conter_memoria():
    """
    Impede que o dicionario cresca sem fim.

    Com o cookie como identificador, um cliente que vaia o cookie a cada
    tentativa cria uma entrada nova por vez. Sem teto, isso vira consumo de
    memoria dirigido por terceiro.
    """
    if len(_tentativas) <= MAX_CLIENTES:
        return

    agora = time.monotonic()
    vencidas = [chave for chave, registro in _tentativas.items()
                if not registro or registro[-1] <= agora - JANELA_SEGUNDOS]
    for chave in vencidas:
        del _tentativas[chave]

    if len(_tentativas) <= MAX_CLIENTES:
        return

    # Ainda acima do teto: joga fora as entradas mais antigas.
    por_idade = sorted(_tentativas.items(), key=lambda par: par[1][-1])
    excesso = len(_tentativas) - MAX_CLIENTES
    for chave, _ in por_idade[:excesso]:
        del _tentativas[chave]


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
      de uma vez. Com 300 contas, o atacante faz 300 palpites por janela.

    Por isso o login conta nos dois e barra se qualquer um dos dois estourar.
    """
    return (acao, alvo if alvo is not None else _identificar_cliente())


def excedeu(acao, alvo=None):
    """Diz se o alvo ja esgotou as tentativas da acao dentro da janela."""
    agora = time.monotonic()
    chave = _montar_chave(acao, alvo)
    with _tranca:
        registro = _tentativas.get(chave)
        if registro is None:
            return False
        _descartar_velhos(registro, agora)
        if not registro:
            del _tentativas[chave]
            return False
        return len(registro) >= MAX_TENTATIVAS


def registrar_falha(acao, alvo=None):
    """Conta uma tentativa errada para o alvo desta acao."""
    agora = time.monotonic()
    chave = _montar_chave(acao, alvo)
    with _tranca:
        registro = _tentativas.get(chave)
        if registro is None:
            registro = deque()
            _tentativas[chave] = registro
        _descartar_velhos(registro, agora)
        registro.append(agora)
        _conter_memoria()


def zerar(acao, alvo=None):
    """Limpa o contador depois de um acerto, para nao penalizar quem acertou."""
    chave = _montar_chave(acao, alvo)
    with _tranca:
        _tentativas.pop(chave, None)


def restantes(acao, alvo=None):
    """Quantas tentativas ainda sobram na janela. Serve para a mensagem."""
    agora = time.monotonic()
    chave = _montar_chave(acao, alvo)
    with _tranca:
        registro = _tentativas.get(chave)
        if registro is None:
            return MAX_TENTATIVAS
        _descartar_velhos(registro, agora)
        return max(0, MAX_TENTATIVAS - len(registro))
