import streamlit as st
import base64
import binascii
import json
import re
import hmac
import hashlib
import os
import uuid
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit
from streamlit.errors import StreamlitSecretNotFoundError
from psycopg2 import OperationalError
from modules.database import verificar_login, cadastrar_usuario
from modules.leitura import CHAVE_LEITURA
from modules import ratelimit
from modules.estilo import aplicar_css
from modules.carregamento import CHAVE_TRANSICAO, aquecer_cache_do_login
# As regras de senha moram em modules/senhas.py (uma cópia só para cadastro e
# troca de senha). Reexportadas aqui para quem já importava de login.py.
from modules.senhas import requisitos_senha, validar_forca_senha  # noqa: F401

# Alfabeto da chave do Professor: 36 símbolos, 10 dígitos e 26 letras.
#
# Só maiúsculas, de propósito. A chave é digitada por uma pessoa que copiou de
# um quadro ou leu em voz alta, e maiúscula/minúscula não se distinguem no
# papel nem na fala. Com 12 posições são 36^12 = 4.738.381.338.321.616.896
# combinações, contra as 900 mil da chave numérica de 6 dígitos.
ALFABETO_CHAVE = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"

TAMANHO_CHAVE = 12

_COOKIE_LOGIN = "usuario_logado"
_DURACAO_COOKIE_LOGIN = timedelta(days=30)


def _segredo_cookie_login():
    segredo = os.environ.get("COOKIE_SECRET")
    if not segredo:
        try:
            segredo = st.secrets["COOKIE_SECRET"]
        except (KeyError, StreamlitSecretNotFoundError):
            return None

    if not isinstance(segredo, str) or len(segredo.encode("utf-8")) < 32:
        return None
    return segredo.encode("utf-8")


def opcoes_cookie_login(url):
    if not isinstance(url, str):
        return None

    url_acesso = urlsplit(url)
    if url_acesso.scheme == "https":
        return {"secure": True, "same_site": "none"}
    if url_acesso.scheme == "http" and url_acesso.hostname in {
        "localhost",
        "127.0.0.1",
        "::1",
    }:
        return {"secure": False, "same_site": "lax"}
    return None


def ler_cookie_login(cookie_manager):
    """Lê o cookie de login já na PRIMEIRA execução da página.

    Antes a leitura era cookie_manager.get(). O valor dele vem de um
    componente (um iframe) que só responde depois que a página já foi
    desenhada uma vez. Na abertura do app (ou no F5) a primeira execução não
    via cookie nenhum e desenhava o login; o componente respondia, o app rodava
    de novo e trocava para o menu. Era o login piscando e sendo coberto pelo
    menu, e uma execução inteira a mais de espera.

    st.context.cookies traz os cookies que o navegador mandou ao abrir a
    conexão, então já estão lá na primeira execução. O componente fica como
    reserva (ambiente sem st.context, como os testes).

    Segurança: nada muda. O valor, venha de onde vier, ainda passa por
    restaurar_cookie_login, que confere a assinatura HMAC e a validade.
    Depois do logout, st.context.cookies ainda guarda o cookie antigo até a
    página ser recarregada; por isso app.py só lê o cookie quando
    _ignorar_cookie_login não está marcado (o logout marca).

    Também não chama cookie_manager.get(): ele emite um st.markdown de
    estilo que ocupa uma posição na página (ver enviar_cookie_login).
    """
    try:
        valor = st.context.cookies.get(_COOKIE_LOGIN)
    except Exception:  # sem contexto de requisição
        valor = None
    if valor is None:
        valor = cookie_manager.cookies.get(_COOKIE_LOGIN)
    return valor


def apagar_cookie_login(cookie_manager, key):
    """Apaga o cookie de login (usado quando ele chega inválido).

    Não usa cookie_manager.delete(): ele faz `del cookies[nome]` e quebra com
    KeyError quando o valor veio de st.context.cookies e o componente ainda
    não tinha respondido (o dicionário dele está vazio na 1ª execução).
    """
    cookie_manager.cookie_manager(
        method="delete", cookie=_COOKIE_LOGIN, key=key, default=False
    )
    cookie_manager.cookies.pop(_COOKIE_LOGIN, None)


def enviar_cookie_login(cookie_manager, valor, expira_em, key, opcoes):
    # Não chama mais cookie_manager._remove_extra_spacing(). Aquele método
    # emite um st.markdown com <style> que OCUPA uma posição na página; como
    # este envio só acontece em algumas execuções (logo depois do login e no
    # logout), a página inteira mudava de posição entre uma execução e a
    # seguinte, e o Streamlit desenhava a tela nova por cima da antiga. O
    # iframe do componente agora fica dentro do contêiner fixo "vaga_cookie"
    # de app.py, que o CSS esconde por inteiro.
    #
    # O wrapper retorna None; o componente retorna a confirmação do navegador.
    resultado = cookie_manager.cookie_manager(
        method="set",
        cookie=_COOKIE_LOGIN,
        value=valor,
        options={
            "path": "/",
            "expires": expira_em.isoformat(),
            "secure": opcoes["secure"],
            "sameSite": opcoes["same_site"],
        },
        key=key,
        default=False,
    )
    cookie_manager.cookies[_COOKIE_LOGIN] = valor
    return resultado


def criar_cookie_login(username, nome_usuario, tipo_usuario):
    segredo = _segredo_cookie_login()
    if segredo is None:
        return None

    expira_em = datetime.now(timezone.utc) + _DURACAO_COOKIE_LOGIN
    payload = {
        "username": username,
        "nome_usuario": nome_usuario,
        "tipo_usuario": tipo_usuario,
        "exp": int(expira_em.timestamp()),
    }
    payload_codificado = base64.urlsafe_b64encode(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).decode("ascii").rstrip("=")
    assinatura = hmac.new(
        segredo, payload_codificado.encode("ascii"), hashlib.sha256
    ).hexdigest()
    return f"{payload_codificado}.{assinatura}", expira_em


def restaurar_cookie_login(valor_cookie):
    segredo = _segredo_cookie_login()
    if segredo is None or not isinstance(valor_cookie, str) or len(valor_cookie) > 4096:
        return None

    try:
        payload_codificado, assinatura = valor_cookie.rsplit(".", 1)
        if not re.fullmatch(r"[0-9a-f]{64}", assinatura):
            return None
        assinatura_esperada = hmac.new(
            segredo, payload_codificado.encode("ascii"), hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(assinatura, assinatura_esperada):
            return None

        payload_bytes = base64.urlsafe_b64decode(
            payload_codificado + "=" * (-len(payload_codificado) % 4)
        )
        payload = json.loads(payload_bytes.decode("utf-8"))
    except (ValueError, TypeError, UnicodeDecodeError, binascii.Error):
        return None

    if not isinstance(payload, dict):
        return None
    if not all(
        isinstance(payload.get(chave), str) and payload[chave]
        for chave in ("username", "nome_usuario", "tipo_usuario")
    ):
        return None
    if type(payload.get("exp")) is not int:
        return None
    if payload["exp"] <= int(datetime.now(timezone.utc).timestamp()):
        return None

    return {
        "username": payload["username"],
        "nome_usuario": payload["nome_usuario"],
        "tipo_usuario": payload["tipo_usuario"],
    }


def validar_email_formato(email):
    """Valida se o e-mail tem um formato padrão (ex: usuario@dominio.com)."""
    padrao = r"^[\w\.-]+@[\w\.-]+\.\w+$"
    return bool(re.fullmatch(padrao, email))

def segredo_da_chave_padrao():
    return "chaveDev2026"


def _segredo_da_chave():
    """Lê o segredo que deriva a chave do dia, preferindo o gerenciador.

    Se o .streamlit/secrets.toml existir com CHAVE_SEGREDO, usa ele. Sem o
    arquivo, cai no padrão do código — e o app continua funcionando, que é o
    que importa para a escola não ter que configurar nada.

    A diferença é de segurança, não de funcionamento: com o segredo no arquivo
    a chave deixa de ser derivável de quem tem o repositório. Sem ele, a chave
    de 12 caracteres continua muito mais difícil de adivinhar que a de 6, mas
    ainda é calculável por qualquer pessoa que leia o código.
    """
    try:
        return st.secrets["CHAVE_SEGREDO"]
    except Exception:
        return segredo_da_chave_padrao()


def segredo_da_chave_configurado():
    """Diz se a chave está sendo derivada de um segredo de verdade."""
    try:
        return st.secrets["CHAVE_SEGREDO"] != segredo_da_chave_padrao()
    except Exception:
        return False


def obter_chave_professor_diaria(segredo_sistema=None, data_referencia=None):
    """Devolve a chave do Professor válida para o dia, com 12 caracteres.

    A chave é determinística: mesma data e mesmo segredo dão a mesma chave
    para toda a escola, que é o que permite a coordenação distribuí-la pelo
    Painel e o formulário de cadastro conferi-la.

    A derivação é por HMAC-SHA256 e não por `random.Random(semente)`, que era o
    que existia antes. A diferença não é sorteio melhor: `random` é um
    Mersenne Twister, um gerador que não foi desenhado para segurança, e semeá-lo
    com um texto conhecido torna a sequência totalmente previsível para quem
    conhece a semente. Aqui o segredo é a chave do HMAC, e quem não tem o
    segredo não consegue nem recomeçar o cálculo.
    """
    if segredo_sistema is None:
        segredo_sistema = _segredo_da_chave()
    if data_referencia is None:
        data_referencia = datetime.now()

    dia = data_referencia.strftime("%Y-%m-%d")
    segredo = segredo_sistema.encode("utf-8")
    marca = dia.encode("utf-8")

    tamanho_alfabeto = len(ALFABETO_CHAVE)
    # 256 não é múltiplo de 36, e o resto sobraria favorecendo os primeiros
    # símbolos do alfabeto. O corte em múltiplo de 36 descarta esse resto.
    teto = (256 // tamanho_alfabeto) * tamanho_alfabeto

    caracteres = []
    rodada = 0
    while len(caracteres) < TAMANHO_CHAVE:
        resumo = hmac.new(segredo, marca + (b"|%d" % rodada), hashlib.sha256).digest()
        for octeto in resumo:
            if octeto >= teto:
                continue
            caracteres.append(ALFABETO_CHAVE[octeto % tamanho_alfabeto])
            if len(caracteres) == TAMANHO_CHAVE:
                break
        rodada += 1

    return "".join(caracteres)


def chave_equivale(digitada, valida):
    """Compara a chave que a pessoa digitou com a do dia.

    Maiúsculas e espaços à toa não contam como erro. A chave tem 12 caracteres
    e vai ser copiada de um quadro; exigir caixa exata só queima uma das 5
    tentativas com um erro que a pessoa não consegue nem ver, porque o campo é
    mascarado.
    """
    # hmac.compare_digest compara em tempo constante: o tempo da resposta não
    # depende de quantos caracteres iniciais estão certos. Com "==", o Python
    # para no primeiro caractere diferente, e medindo o tempo daria (em tese)
    # para descobrir a chave do dia letra por letra. O limite de 5 tentativas
    # já torna isso impraticável; aqui fica fechado também na origem.
    return hmac.compare_digest(
        (digitada or "").strip().upper().encode("utf-8"),
        (valida or "").strip().upper().encode("utf-8"),
    )


# Onde o resultado do último envio do cadastro fica guardado entre as passadas
# do fragmento. Ver _formulario_cadastro para o porquê.
_CHAVE_DO_RESULTADO = "_cadastro_resultado"
_CHAVE_DO_PERFIL = "_cadastro_resultado_perfil"
_CHAVE_MENSAGEM_LOGIN = "_cadastro_mensagem_login"
_ABAS_LOGIN = "abas_login"
_ABA_ENTRAR = "Entrar"
_ABA_CRIAR = "Criar Conta"

# Campos do cadastro. Fora do st.form, cada um precisa de key própria: é pela
# key que o callback de envio lê os valores e limpa tudo depois do sucesso.
_CAMPOS_CADASTRO = (
    "cadastro_chave",
    "cadastro_nome",
    "cadastro_usuario",
    "cadastro_email",
    "cadastro_email_confirm",
    "cadastro_senha",
    "cadastro_senha_confirm",
)

# Regex do e-mail no navegador (parâmetro validate do st.text_input). Aceita
# espaço só nas pontas porque o callback _tirar_espacos remove esses espaços
# logo depois: sem essa folga, um espaço deixado pelo preenchimento automático
# barraria o e-mail com "inválido" em vez de ser simplesmente corrigido.
_REGEX_EMAIL_NAVEGADOR = r"^\s*[^@\s]+@[^@\s]+\.[^@\s]+\s*$"


def _guardar_resultado(nivel, texto):
    """Guarda (nivel, texto) do último envio, para sobreviver ao tique de 5s.

    `nivel` é o nome do método de st: "error", "warning" ou "success".
    """
    st.session_state[_CHAVE_DO_RESULTADO] = (nivel, texto)


def render_admin():
    """APAGADA de propósito.

    Esta função nunca foi chamada: app.py importa apenas render_login e
    obter_chave_professor_diaria. O que ela fazia de útil — mostrar a chave do
    dia para a coordenação — já existe em app.py, dentro de "Painel da
    Coordenação", que é item de menu do Administrador e portanto exige login.

    Fica o registro porque os dois pontos de exibição da chave foram este e o
    st.info que estava na aba pública de cadastro. Os dois foram removidos
    juntos de propósito: enquanto qualquer um deles existisse, a chave do dia
    estava legível por quem não devia, e o rate limit da chave não protegia
    nada, porque não havia o que adivinhar.

    Nada de render_admin é chamado hoje. Se voltar a ser necessário, o lugar
    certo é o Painel da Coordenação em app.py, com verificação de perfil.
    """


# ---------------------------------------------------------------- login ----

def _alvo_da_conta(usuario_digitado):
    """Normaliza o usuário para virar chave de contador.

    Lower e strip porque 'Admin', 'admin' e ' admin ' são a mesma conta. Sem
    isso o próprio limite de tentativa seria contornável mudando a
    capitalização do campo de usuário a cada tentativa.
    """
    return "conta:%s" % (usuario_digitado or "").strip().lower()


def _chave_cliente():
    """Prefixo do alvo que identifica o cliente, não a conta."""
    return "cliente:%s" % ratelimit._identificar_cliente()


def _situacao_login(usuario_digitado):
    """Diz se o login está barrado e por quê.

    Conta a falha nos dois alvos: a conta atacada e o cliente atacante. Barra
    se qualquer um dos dois estourar. Ver _montar_chave no módulo de rate
    limit para por que os dois são necessários.

    Sem alvo (campo de usuário vazio) só vale o limite de cliente, porque não
    há conta a ser contada ainda.
    """
    alvos = [_chave_cliente()]
    if usuario_digitado and usuario_digitado.strip():
        alvos.append(_alvo_da_conta(usuario_digitado))
    barrado = any(ratelimit.excedeu(ratelimit.LOGIN, alvo) for alvo in alvos)
    sobra = min(ratelimit.restantes(ratelimit.LOGIN, alvo) for alvo in alvos)
    return barrado, sobra, alvos


def _registrar_falha_login(usuario_digitado):
    alvos = [_chave_cliente()]
    if usuario_digitado and usuario_digitado.strip():
        alvos.append(_alvo_da_conta(usuario_digitado))
    for alvo in alvos:
        ratelimit.registrar_falha(ratelimit.LOGIN, alvo)


def _zerar_login(usuario_digitado):
    for alvo in (_chave_cliente(), _alvo_da_conta(usuario_digitado)):
        ratelimit.zerar(ratelimit.LOGIN, alvo)


# ------------------------------------------------------- sessão ----
#
# O st.session_state vive na SESSÃO DO NAVEGADOR, não na conta. Quando
# alguém sai e outra pessoa entra na mesma aba (o computador da escola
# é exatamente isso), tudo que o usuário anterior deixou de lá continua
# valendo para o novo: o módulo aberto, o resultado do quiz, a leitura
# em curso. Medido na prática, o segundo aluno caía direto na página do
# módulo que o primeiro tinha aberto e via o GABARITO do primeiro no
# lugar das perguntas do quiz dele -- e não dava para responder, porque
# a tela de resultado substitui as perguntas.
#
# O banco não tem nada a ver com isso: progresso e leituras são por
# usuário e estão corretos. O vazamento é só da sessão, e é ele que
# esta limpeza fecha.
#
# Chaves que pertencem a quem está logado. "leitura_em_curso" é o
# CHAVE_LEITURA do módulo de leitura, importado para não virar uma
# segunda definição do mesmo nome.
_CHAVES_DO_USUARIO = (
    "username",
    "nome_usuario",
    "tipo_usuario",
    "primeiro_acesso",
    "modulo_selecionado",
    CHAVE_LEITURA,
    "navegar_para",
    "voltar_para_menu",
)


def limpar_sessao_do_usuario(com_widgets=False):
    """Apaga da sessão tudo o que pertencia à conta anterior.

    Chamada em dois pontos, de propósito:

      1. No logout confirmado (app.py): a sessão já sai sem nenhum
         dado da pessoa que foi embora.
      2. No login com sucesso (aqui): a garantia de que a conta nova
         não herda nada, mesmo quando o logout é contornado (F5 no
         meio do caminho, aba que ficou aberta, etc.).

    `com_widgets=True` apaga também as chaves que pertencem a widgets
    já desenhados na tela: o "menu" do radio lateral e as chaves
    "quiz_<slug>_<n>" dos rádios do quiz. Essas só podem ser mexidas
    quando o widget não existe na tela neste momento -- no login isso
    é verdade (a tela pública não tem nem o menu nem o quiz), mas no
    logout o menu lateral está desenhado, então ali a chamada é sem
    widgets e as chaves de widget são varridas no login seguinte, que
    é quando o menu e o quiz são recriados.

    As chaves "quiz_resultado_*" (a nota da tentativa) não são de
    widget: são estado puro, apagadas nos dois pontos.
    """
    for chave in _CHAVES_DO_USUARIO:
        st.session_state.pop(chave, None)

    if com_widgets:
        st.session_state.pop("menu", None)

    for chave in [
        c for c in list(st.session_state)
        if c.startswith("quiz_resultado_")
        or (com_widgets and c.startswith("quiz_"))
    ]:
        st.session_state.pop(chave, None)


# Redesenho automático SÓ enquanto há bloqueio.
#
# O Streamlit só redesenha quando o script roda, e o script só roda com
# interação do usuário. Sem um redesenho automático, o botão ficava cinza
# indefinidamente depois do bloqueio, mesmo com a janela já vencida em memória,
# e a reação natural a uma tela travada é F5, que rotaciona o cookie XSRF e
# zera o contador.
#
# Antes, os dois formulários tinham run_every="5s" o tempo todo: todo visitante
# parado na tela de login rodava os dois fragmentos a cada 5 s, para sempre, e
# o de cadastro ainda recalculava o HMAC da chave do dia. Agora o timer existe
# só enquanto alguém está bloqueado. Este fragmento é chamado dentro do
# formulário apenas nesse caso; quando a janela vence, ele pede um rerun do app
# e deixa de ser desenhado, e o próprio Streamlit cancela o timer no navegador
# (stop_auto_rerun). Tela de login parada não custa nada.
@st.fragment(run_every="10s")
def _aguardar_desbloqueio(acao, alvos):
    """Libera o formulário sozinho quando a janela de bloqueio vence."""
    if not any(ratelimit.excedeu(acao, alvo) for alvo in alvos):
        st.rerun()


@st.fragment
def _formulario_login():
    with st.form("form_login", clear_on_submit=True):
        # clear_on_submit: a senha digitada não fica na tela depois do envio.
        # Custo aceito: quem erra a senha reescreve o usuário.
        usuario_input = st.text_input("Usuário")
        senha_input = st.text_input("Senha", type="password")

        login_bloqueado, _sobra, alvos = _situacao_login(usuario_input)

        if login_bloqueado:
            st.warning(
                "Login temporariamente bloqueado por excesso de tentativas. "
                f"A janela se renova sozinha em {ratelimit.JANELA_SEGUNDOS // 60} minutos."
            )

        btn_entrar = st.form_submit_button("Entrar", disabled=login_bloqueado)

        if btn_entrar:
            # A instrução de cadastro já cumpriu o papel assim que a pessoa
            # tenta entrar. Some na mesma hora, inclusive se errar a senha.
            st.session_state.pop(_CHAVE_MENSAGEM_LOGIN, None)

            # O bloqueio fica no topo da cadeia: quem está bloqueado não gasta
            # consulta ao banco.
            if login_bloqueado:
                st.error(
                    "Muitas tentativas de login. "
                    f"Tente de novo em {ratelimit.JANELA_SEGUNDOS // 60} minutos."
                )

            # Senha só de espaços conta como vazia: no login os espaços não
            # contam (ver senha_confere em modules/senhas.py).
            elif not (usuario_input and senha_input and senha_input.strip()):
                # Não conta tentativa: campo vazio não é palpite, é engano.
                st.error("Por favor, preencha o usuário e a senha.")

            else:
                try:
                    # O bcrypt leva ~0,25 s de propósito, e o banco pode estar
                    # "acordando". O spinner mostra que o clique foi recebido.
                    with st.spinner("Verificando seus dados..."):
                        credenciais = verificar_login(usuario_input, senha_input)
                except OperationalError:
                    st.error(
                        "Não foi possível acessar o banco de dados agora. "
                        "Tente novamente em alguns instantes."
                    )
                    return

                if credenciais:
                    nome_usuario, tipo_usuario = credenciais
                    # Antes de gravar as chaves da conta nova, apaga tudo o
                    # que a sessão ainda guarda da anterior. Sem isto o
                    # aluno B caía na página do módulo que o A tinha aberto
                    # e o quiz dele abria com o resultado e o gabarito do A.
                    limpar_sessao_do_usuario(com_widgets=True)
                    st.session_state.pop("_ignorar_cookie_login", None)
                    st.session_state["usuario_logado"] = True
                    st.session_state["nome_usuario"] = nome_usuario
                    # Sem isso o perfil nunca chegava ao menu: app.py decide
                    # os itens por tipo_usuario, que ficava vazio para todo
                    # mundo e fazia todos caírem no menu do Aluno.
                    st.session_state["tipo_usuario"] = tipo_usuario
                    st.session_state["username"] = usuario_input
                    cookie_login = criar_cookie_login(
                        usuario_input, nome_usuario, tipo_usuario
                    )
                    if cookie_login is None:
                        st.session_state["_cookie_login_aviso"] = (
                            "A sessão está autenticada, mas a retenção de login está "
                            "desativada. Configure COOKIE_SECRET no `.env` local ou "
                            "em `.streamlit/secrets.toml`."
                        )
                    else:
                        opcoes_cookie = opcoes_cookie_login(st.context.url)
                        if opcoes_cookie is None:
                            st.session_state["_cookie_login_aviso"] = (
                                "A retenção de login exige HTTPS. Em desenvolvimento, "
                                "acesse o app por http://localhost:8501."
                            )
                        else:
                            valor_cookie, expira_em = cookie_login
                            st.session_state["_cookie_login_pendente"] = {
                                "valor": valor_cookie,
                                "expira_em": expira_em,
                                "opcoes": opcoes_cookie,
                                "key": uuid.uuid4().hex,
                            }
                    # Zera só no acerto: quem entrou não está sob ataque, e uma
                    # sessão legítima não pode herdar bloqueio de outra.
                    _zerar_login(usuario_input)
                    # Começa a buscar, em paralelo, o que a primeira tela vai
                    # pedir (perfil, primeiro acesso e dados da página
                    # inicial). Ver modules/carregamento.py.
                    aquecer_cache_do_login(usuario_input, tipo_usuario)
                    # Pede a tela de transição (barra de carregamento com a
                    # lateral recolhida) entre o login e o menu. Ver
                    # marcar_transicao_do_login em modules/carregamento.py.
                    st.session_state[CHAVE_TRANSICAO] = True
                    st.success("Login efetuado com sucesso!")
                    st.rerun(scope="app")
                else:
                    # Usuário inexistente e senha errada contam no mesmo
                    # contador: a tela não distingue os dois casos, e o
                    # limitador não deve virar oráculo de quem existe.
                    _registrar_falha_login(usuario_input)
                    _bloqueado, sobra, _ = _situacao_login(usuario_input)
                    st.error(
                        "Usuário ou senha incorretos. "
                        + (
                            f"Este login está bloqueado por {ratelimit.JANELA_SEGUNDOS // 60} minutos. "
                            if _bloqueado
                            else f"Restam {sobra} tentativa(s) em {ratelimit.JANELA_SEGUNDOS // 60} minutos. "
                        )
                    )
                    if _bloqueado:
                        # O bloqueio começou nesta tentativa. Sem o rerun, o
                        # botão só desabilitaria na próxima interação, porque o
                        # `disabled` é avaliado quando o formulário é desenhado.
                        # O aviso de bloqueio do formulário substitui este erro.
                        st.rerun()

    if login_bloqueado:
        _aguardar_desbloqueio(ratelimit.LOGIN, alvos)

# Mesmo esquema do login: sem timer permanente.
#
# Dois cuidados, os mesmos que o timer de 5 s resolvia antes:
# - na 5ª chave errada o campo e o botão precisam aparecer desabilitados já no
#   redesenho seguinte. Com a validação num callback (_cadastrar) isso é de
#   graça: o callback roda ANTES do fragmento ser desenhado, então o `disabled`
#   já é avaliado com o bloqueio registrado;
# - o botão precisa voltar sozinho quando a janela vence. Isso é feito por
#   _aguardar_desbloqueio, chamado só enquanto a chave está bloqueada.


def _tirar_espacos(campo):
    """Callback dos campos de e-mail: remove espaços e quebras de linha.

    Roda como on_change, ou seja, ANTES do redesenho, que é o único momento em
    que o Streamlit permite gravar na key de um widget sem erro. Só e-mail passa
    por aqui: senha nunca é alterada (ver modules/senhas.py).
    """
    valor = st.session_state.get(campo)
    if isinstance(valor, str):
        st.session_state[campo] = re.sub(r"\s+", "", valor)


def _cadastrar():
    """Callback do botão "Finalizar Cadastro": valida, grava e encaminha.

    Por que callback e não `if st.button(...)`:
    - o guia do projeto (07/11) proíbe mexer em st.session_state no corpo da
      renderização; aqui toda escrita acontece antes do desenho;
    - limpar os campos e trocar a aba exige gravar nas keys de widgets, o que
      só é permitido antes de eles existirem na passada. Antes isso era feito
      com flags + st.rerun(), custando duas execuções por cadastro; agora é uma.
    """
    estado = st.session_state
    tipo_usuario = estado.get("perfil_cadastro", "Aluno")
    chave_prof = estado.get("cadastro_chave", "") if tipo_usuario == "Professor" else ""
    nome = estado.get("cadastro_nome", "")
    novo_usuario = estado.get("cadastro_usuario", "")
    email = estado.get("cadastro_email", "")
    email_confirm = estado.get("cadastro_email_confirm", "")
    senha = estado.get("cadastro_senha", "")
    senha_confirm = estado.get("cadastro_senha_confirm", "")

    # Nenhum envio começa com o aviso antigo na tela. O perfil vai junto para o
    # aviso ser descartado se a pessoa trocar de cadastro depois.
    estado[_CHAVE_DO_RESULTADO] = None
    estado[_CHAVE_DO_PERFIL] = tipo_usuario

    # 1. Bloqueio da chave do Professor: topo da cadeia, quem está bloqueado
    #    não gasta validação nem recebe dica sobre os outros campos.
    if tipo_usuario == "Professor" and ratelimit.excedeu(ratelimit.CHAVE_PROFESSOR):
        _guardar_resultado(
            "error",
            "Muitas tentativas de chave incorretas. "
            f"Tente de novo em {ratelimit.JANELA_SEGUNDOS // 60} minutos."
        )
        return

    # 2. Preenchimento dos campos básicos
    if not (nome and novo_usuario and email and email_confirm and senha and senha_confirm):
        _guardar_resultado("error", "Por favor, preencha todos os campos do formulário.")
        return

    # 3. Chave dinâmica do Professor
    if tipo_usuario == "Professor" and not chave_equivale(
        chave_prof, obter_chave_professor_diaria()
    ):
        ratelimit.registrar_falha(ratelimit.CHAVE_PROFESSOR)
        restantes = ratelimit.restantes(ratelimit.CHAVE_PROFESSOR)
        _guardar_resultado(
            "error",
            "Chave de verificação do Professor inválida ou expirada. "
            + (
                f"Tente de novo em {ratelimit.JANELA_SEGUNDOS // 60} minutos."
                if restantes == 0
                else f"Restam {restantes} tentativa(s) em "
                     f"{ratelimit.JANELA_SEGUNDOS // 60} minutos."
            )
        )
        return

    # 4. E-mail. A validação do navegador (validate=) é conforto para quem
    #    digita; esta é a que vale, porque o navegador pode ser contornado.
    if email != email_confirm:
        _guardar_resultado("error", "Os e-mails digitados não coincidem.")
        return
    if not validar_email_formato(email):
        _guardar_resultado("error", "Por favor, informe um e-mail válido.")
        return

    # 5. Confirmação antes da força: se as duas não batem, dizer "falta uma
    #    maiúscula" não resolve nada.
    if senha != senha_confirm:
        _guardar_resultado("error", "As senhas digitadas não coincidem.")
        return

    # 6. Força da senha, incluindo o teto de 72 bytes do bcrypt.
    if not validar_forca_senha(senha):
        _guardar_resultado(
            "error",
            "A senha deve ter no mínimo 6 caracteres, com pelo menos uma letra "
            "maiúscula, uma minúscula e um número, sem espaços e com no máximo 72 bytes."
        )
        return

    # 7. Gravação
    motivo = cadastrar_usuario(
        username=novo_usuario,
        nome=nome,
        email=email,
        tipo=tipo_usuario,
        senha_pura=senha,
    )
    if motivo == "email_duplicado":
        _guardar_resultado("warning", "Este e-mail já está cadastrado nesta plataforma.")
        return
    if motivo != "ok":
        _guardar_resultado("warning", "Este nome de usuário já está em uso.")
        return

    # Sucesso. Só zera a chave para Professor: Aluno não tem chave para limpar.
    if tipo_usuario == "Professor":
        ratelimit.zerar(ratelimit.CHAVE_PROFESSOR)
    for campo in _CAMPOS_CADASTRO:
        estado.pop(campo, None)
    estado[_CHAVE_MENSAGEM_LOGIN] = (
        "Conta criada com sucesso! Agora entre com seu usuário e senha na aba Entrar."
    )
    estado[_ABAS_LOGIN] = _ABA_ENTRAR
    # O botão está dentro de um fragmento, e por padrão só o fragmento
    # redesenharia. As abas ficam FORA dele, então é preciso o app inteiro:
    # st.rerun() dentro de callback (Streamlit 1.64) pede exatamente isso, sem
    # interromper nada, e substitui a passada que o fragmento faria.
    st.rerun()


@st.fragment
def _formulario_cadastro():
    # st.radio, e não st.selectbox: nesta versão do Streamlit o selectbox virou
    # um campo de busca, que aceita digitação livre e filtra a lista enquanto a
    # pessoa escreve. Com duas opções, o radio mostra as duas e resolve em um
    # clique, sem digitação nenhuma.
    #
    # persist_state="session": as abas agora só desenham a aba aberta (ver
    # _render_login), e um widget que não é desenhado perde o valor. Com isto,
    # ir até "Entrar" e voltar não apaga o que já foi preenchido. (O escopo
    # "page" seria o natural, mas no teste com AppTest ele descartou o valor ao
    # reaparecer; "session" foi o que se comportou como esperado.)
    tipo_usuario_input = st.radio(
        "Perfil de Acesso",
        ["Aluno", "Professor"],
        key="perfil_cadastro",
        horizontal=True,
        persist_state="session",
    )

    chave_bloqueada = False

    if tipo_usuario_input == "Professor":
        # O bloqueio vale para a CHAVE, não para o cadastro inteiro, e por isso
        # só este campo e o botão desabilitam: assim um Professor bloqueado
        # ainda se cadastra como Aluno, e o radio continua vivo para a troca.
        chave_bloqueada = ratelimit.excedeu(ratelimit.CHAVE_PROFESSOR)

        if chave_bloqueada:
            st.warning(
                "Chave do Professor bloqueada por excesso de tentativas. "
                "Vale só para o cadastro com chave, não afeta o Aluno. "
                f"Tente de novo em {ratelimit.JANELA_SEGUNDOS // 60} minutos."
            )
            _aguardar_desbloqueio(ratelimit.CHAVE_PROFESSOR, [None])

    # Sem st.form: dentro dele o Streamlit só devolve os valores no submit, e
    # nada do que depende de digitação (borda do e-mail, checklist da senha)
    # poderia atualizar antes do envio.
    with st.container(key="form_cadastro"):
        if tipo_usuario_input == "Professor":
            # Sem max_chars de propósito: o Streamlit corta o valor no limite e
            # o corte acontece antes do strip() da comparação, o que rejeitava a
            # chave correta colada com espaço. A tolerância a caixa e a espaço
            # nas pontas fica em chave_equivale.
            #
            # Sem persist_state: segredo não fica guardado enquanto escondido.
            st.text_input(
                f"Chave de Verificação ({TAMANHO_CHAVE} caracteres)",
                type="password",
                key="cadastro_chave",
                help=(
                    "Bloqueada por excesso de tentativas. Aguarde a janela."
                    if chave_bloqueada
                    else "Solicite a chave diária à coordenação. "
                         "Pode digitar em maiúsculas ou minúsculas."
                ),
                disabled=chave_bloqueada,
            )

        st.text_input("Nome Completo", key="cadastro_nome", persist_state="session")
        st.text_input("Nome de Usuário", key="cadastro_usuario", persist_state="session")

        # type="email": teclado de e-mail no celular, preenchimento automático
        # do navegador e validação de formato antes de o valor sair da página.
        for rotulo, campo in (
            ("E-mail", "cadastro_email"),
            ("Confirme o E-mail", "cadastro_email_confirm"),
        ):
            st.text_input(
                rotulo,
                key=campo,
                type="email",
                placeholder="voce@exemplo.com",
                validate=(_REGEX_EMAIL_NAVEGADOR, "Digite um e-mail válido, como nome@exemplo.com."),
                on_change=_tirar_espacos,
                args=(campo,),
                persist_state="session",
            )

        email_input = st.session_state.get("cadastro_email", "")
        email_confirm_input = st.session_state.get("cadastro_email_confirm", "")

        # Aviso ANTES de enviar: assim que os dois campos estão preenchidos e
        # divergem, os dois ficam com borda vermelha e a mensagem aparece. O
        # botão também desabilita. Isto só DESENHA; não grava estado nenhum.
        emails_divergem = bool(
            email_input and email_confirm_input and email_input != email_confirm_input
        )
        if emails_divergem:
            st.markdown(
                '<style>'
                '.st-key-cadastro_email [data-testid="stTextInputRootElement"],'
                '.st-key-cadastro_email_confirm [data-testid="stTextInputRootElement"],'
                '.st-key-cadastro_email [data-testid="stTextInputRootElement"]:focus-within,'
                '.st-key-cadastro_email_confirm [data-testid="stTextInputRootElement"]:focus-within {'
                'border-color: #ef4444 !important;'
                'box-shadow: 0 0 0 2px #ef4444 !important;'
                '}'
                '</style>',
                unsafe_allow_html=True,
            )
            st.markdown(
                '<p class="erro-email">Os e-mails digitados não coincidem.</p>',
                unsafe_allow_html=True,
            )

        # Por que o espaço é barrado pelo checklist e não por validate= (como
        # no e-mail): no navegador, valor reprovado no validate NÃO é enviado.
        # O servidor ficaria com a última versão sem espaço, e o checklist
        # mostraria tudo verde enquanto o campo tem um espaço. Validando aqui,
        # o servidor vê exatamente o que foi digitado e o ✗ aparece na hora.
        #
        # live="300ms": o valor chega ao servidor 300 ms depois de a pessoa
        # parar de digitar, e não só no Enter/saída do campo. É isso que faz o
        # checklist ser de fato em tempo real. O custo é uma passada deste
        # fragmento por pausa, que é barata (nada de banco aqui).
        st.text_input(
            "Nova Senha",
            type="password",
            key="cadastro_senha",
            live="300ms",
            help="Mínimo de 6 caracteres, com maiúscula, minúscula e número. Sem espaços.",
        )

        requisitos = requisitos_senha(st.session_state.get("cadastro_senha", ""))

        def _item_checklist(texto, ok):
            classe = "ok" if ok else "falta"
            marca = "✓" if ok else "✗"
            return f'<span class="senha-item {classe}">{marca} {texto}</span>'

        itens = (
            _item_checklist("Letra maiúscula", requisitos["maiuscula"])
            + _item_checklist("Letra minúscula", requisitos["minuscula"])
            + _item_checklist("Número", requisitos["numero"])
            + _item_checklist("Mínimo de 6 caracteres", requisitos["tamanho"])
            # Sempre visível, ao contrário do teto de bytes: espaço é uma regra
            # que a pessoa pode quebrar sem saber, então ela precisa vê-la antes.
            + _item_checklist("Sem espaços", requisitos["sem_espaco"])
        )
        # O teto do bcrypt só aparece quando é ultrapassado: ninguém precisa
        # ler "no máximo 72 bytes" enquanto digita uma senha normal.
        if not requisitos["limite"]:
            itens += _item_checklist(
                "Longa demais: máximo de 72 bytes (acentos e emojis ocupam mais de 1)",
                False,
            )
        st.markdown(f'<div class="senha-requisitos">{itens}</div>', unsafe_allow_html=True)

        # A senha é digitada duas vezes de propósito. Num campo mascarado não
        # dá para reler o que foi escrito, e não há "esqueci minha senha" nesta
        # plataforma para consertar um erro de digitação depois.
        st.text_input(
            "Confirme a Nova Senha",
            type="password",
            key="cadastro_senha_confirm",
        )

        st.button(
            "Finalizar Cadastro",
            key="btn_cadastrar",
            disabled=chave_bloqueada or emails_divergem,
            width="stretch",
            on_click=_cadastrar,
        )

    # O aviso do último envio fica fora do cartão: sobrevive a redesenho do
    # fragmento e some se o perfil mudou desde o envio.
    _resultado = st.session_state.get(_CHAVE_DO_RESULTADO)
    if _resultado and st.session_state.get(_CHAVE_DO_PERFIL) == tipo_usuario_input:
        _nivel, _texto = _resultado
        getattr(st, _nivel)(_texto)

    # NÃO há código de teste da chave aqui. A chave do dia é distribuída apenas
    # pelo Painel da Coordenação (app.py), que exige login de Administrador.


def render_login():
    # Antes esta função abria o próprio contêiner (key "pagina_login"). Agora
    # quem abre é app.py: o contêiner "tela_login" existe em TODA execução,
    # logado ou não, sempre na mesma posição, e é dentro dele que o login é
    # desenhado. Assim, na troca para o menu, os restos do formulário ficam
    # dentro de um contêiner que o CSS esconde, em vez de aparecerem por baixo
    # do menu. Ver "VAGAS FIXAS DO TOPO" em app.py.
    _render_login()


def _render_login():
    # O CSS da tela de login fica em static/css/login.css.
    aplicar_css("login.css")

    st.markdown(
        '<p class="login-title">Acesso ao CriptoEduca</p>'
        '<p class="login-subtitle">Entre com suas credenciais ou crie sua conta para continuar</p>',
        unsafe_allow_html=True,
    )
    # on_change="rerun" faz as abas guardarem estado na key, que é o que deixa
    # o callback _cadastrar trocar para "Entrar" por código. O preço é que cada
    # troca de aba roda o script. Para esse preço virar ganho, só a aba ABERTA
    # é desenhada (.open): antes as duas rodavam em toda passada, inclusive o
    # cálculo da chave do dia e os timers de bloqueio da aba escondida.
    aba_login, aba_cadastro = st.tabs(
        [_ABA_ENTRAR, _ABA_CRIAR],
        key=_ABAS_LOGIN,
        on_change="rerun",
    )
    if aba_login.open:
        with aba_login:
            # A instrução do cadastro aparece aqui, na tela de login, e some
            # quando a pessoa tenta entrar (ver _formulario_login).
            mensagem_login = st.session_state.get(_CHAVE_MENSAGEM_LOGIN)
            if mensagem_login:
                st.success(mensagem_login)
            with st.container(key="aba_login"):
                _formulario_login()

    if aba_cadastro.open:
        with aba_cadastro:
            with st.container(key="aba_cadastro"):
                _formulario_cadastro()
