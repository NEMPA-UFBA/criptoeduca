import streamlit as st
import re
import hmac
import hashlib
from datetime import datetime
from modules.database import verificar_login, cadastrar_usuario
from modules.leitura import CHAVE_LEITURA
from modules import ratelimit
from modules.estilo import aplicar_css

# Alfabeto da chave do Professor: 36 símbolos, 10 dígitos e 26 letras.
#
# Só maiúsculas, de propósito. A chave é digitada por uma pessoa que copiou de
# um quadro ou leu em voz alta, e maiúscula/minúscula não se distinguem no
# papel nem na fala. Com 12 posições são 36^12 = 4.738.381.338.321.616.896
# combinações, contra as 900 mil da chave numérica de 6 dígitos.
ALFABETO_CHAVE = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"

TAMANHO_CHAVE = 12

def validar_email_formato(email):
    """Valida se o e-mail tem um formato padrão (ex: usuario@dominio.com)."""
    padrao = r"^[\w\.-]+@[\w\.-]+\.\w+$"
    return bool(re.fullmatch(padrao, email))

def validar_forca_senha(senha):
    """Garante que a senha tenha pelo menos 1 letra maiúscula, 1 minúscula e 1 número."""
    tem_maiuscula = any(c.isupper() for c in senha)
    tem_minuscula = any(c.islower() for c in senha)
    tem_numero = any(c.isdigit() for c in senha)
    
    return tem_maiuscula and tem_minuscula and tem_numero


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
    return (digitada or "").strip().upper() == (valida or "").strip().upper()


# Onde o resultado do último envio do cadastro fica guardado entre as passadas
# do fragmento. Ver _formulario_cadastro para o porquê.
_CHAVE_DO_RESULTADO = "_cadastro_resultado"
_CHAVE_DO_PERFIL = "_cadastro_resultado_perfil"


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
            # O bloqueio fica no topo da cadeia: quem está bloqueado não gasta
            # consulta ao banco.
            if login_bloqueado:
                st.error(
                    "Muitas tentativas de login. "
                    f"Tente de novo em {ratelimit.JANELA_SEGUNDOS // 60} minutos."
                )

            elif not (usuario_input and senha_input):
                # Não conta tentativa: campo vazio não é palpite, é engano.
                st.error("Por favor, preencha o usuário e a senha.")

            else:
                credenciais = verificar_login(usuario_input, senha_input)

                if credenciais:
                    nome_usuario, tipo_usuario = credenciais
                    # Antes de gravar as chaves da conta nova, apaga tudo o
                    # que a sessão ainda guarda da anterior. Sem isto o
                    # aluno B caía na página do módulo que o A tinha aberto
                    # e o quiz dele abria com o resultado e o gabarito do A.
                    limpar_sessao_do_usuario(com_widgets=True)
                    st.session_state["usuario_logado"] = True
                    st.session_state["nome_usuario"] = nome_usuario
                    # Sem isso o perfil nunca chegava ao menu: app.py decide
                    # os itens por tipo_usuario, que ficava vazio para todo
                    # mundo e fazia todos caírem no menu do Aluno.
                    st.session_state["tipo_usuario"] = tipo_usuario
                    st.session_state["username"] = usuario_input
                    # Zera só no acerto: quem entrou não está sob ataque, e uma
                    # sessão legítima não pode herdar bloqueio de outra.
                    _zerar_login(usuario_input)
                    st.success("Login efetuado com sucesso!")
                    st.rerun()  # Recarrega a página para entrar no sistema
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
# - na 5ª chave errada, o `disabled` já foi avaliado quando o formulário foi
#   desenhado, então o campo e o botão ficariam liberados até o clique seguinte.
#   Por isso a falha que esgota as tentativas pede um rerun na hora;
# - o botão precisa voltar sozinho quando a janela vence. Isso é feito por
#   _aguardar_desbloqueio, chamado só enquanto a chave está bloqueada.
@st.fragment
def _formulario_cadastro():
    # A chave válida para o dia. Determinística: mesma data e mesmo segredo
    # devolvem a mesma chave para a coordenação e para o formulário.
    chave_valida_hoje = obter_chave_professor_diaria()

    # O seletor de perfil fica FORA do formulário, de propósito. Dentro de
    # st.form o Streamlit agrupa tudo e nada redesenha até o envio, então
    # condicionar o campo da chave ao perfil só apareceria depois de enviar —
    # pior que mostrar sempre. Fora do form, cada troca de perfil reroda a tela
    # na hora.
    #
    # Efeito colateral bom: clear_on_submit só limpa widgets dentro do form, o
    # que o perfil sobrevive ao envio. Antes o perfil voltava para "Aluno" a
    # cada tentativa, e era por isso que o aviso de bloqueio precisava ficar
    # independente do perfil.
    #
    # st.radio, e não st.selectbox: nesta versão do Streamlit o selectbox virou
    # um campo de busca, que aceita digitação livre e filtra a lista enquanto a
    # pessoa escreve. Medido: digitando "Coordenador" o campo mostra a palavra e
    # a lista responde "No results", e o valor é descartado na saída, voltando
    # para "Aluno" sozinho. Ou seja, não quebrava nada — o valor inválido nunca
    # chegava ao banco — mas a pessoa vê o texto que digitou na tela e ele some
    # sem explicação. Num campo que decide se a chave aparece ou não, isso é
    # pior do que deixar a chave sempre visível. Com duas opções, o radio mostra
    # as duas e resolve em um clique, sem digitação nenhuma.
    tipo_usuario_input = st.radio(
        "Perfil de Acesso",
        ["Aluno", "Professor"],
        key="perfil_cadastro",
        horizontal=True,
    )

    # Só existe quando o perfil é Professor. Precisa do default antes do if
    # porque a cadeia de validação mais abaixo lê esta variável em todos os
    # caminhos, e sem o default o perfil Aluno levanta NameError.
    chave_prof_input = ""
    chave_bloqueada = False

    if tipo_usuario_input == "Professor":
        # O bloqueio vale para a CHAVE, não para o cadastro inteiro, e por isso
        # só este campo e o botão desabilitam: assim um Professor bloqueado
        # ainda se cadastra como Aluno, e o radio continua vivo para a troca.
        chave_bloqueada = ratelimit.excedeu(ratelimit.CHAVE_PROFESSOR)

        # Com o seletor fora do form o perfil não reseta mais, então o aviso pode
        # ficar amarrado a ele: some junto com o campo, que é o esperado. O texto
        # segue dizendo que vale só para o cadastro com chave, porque o limite
        # é da chave.
        #
        # O aviso fica fora do form de propósito: dentro de st.form nada é
        # desenhado antes do envio, então a pessoa bloqueio e habilitada não
        # veria nada.
        if chave_bloqueada:
            st.warning(
                "Chave do Professor bloqueada por excesso de tentativas. "
                "Vale só para o cadastro com chave, não afeta o Aluno. "
                f"Tente de novo em {ratelimit.JANELA_SEGUNDOS // 60} minutos."
            )
            _aguardar_desbloqueio(ratelimit.CHAVE_PROFESSOR, [None])

    with st.form("form_cadastro", clear_on_submit=True):
        # O campo da chave fica DENTRO do form, e isso não é um detalhe.
        #
        # Ele já esteve fora, e o cadastro de Professor estava quebrado por causa
        # disso: ao enviar, o servidor recebia o campo da chave sempre vazio e
        # rejeitava a chave certa. Medido no navegador com a chave do dia na
        # tela e no log do servidor: `recebido='' valida='B3247UPY2KM8'`. O
        # AppTest não pegou nada disso porque escreve o estado dos widgets
        # direto no servidor, sem passar pelo navegador — é a diferença entre
        # testar a lógica e testar o programa.
        #
        # O que precisa ficar fora do form é o SELETOR DE PERFIL, que é o que
        # dispara o redesenho imediato. O campo da chave só precisa aparecer
        # quando o perfil é Professor, e isso continua funcionando: o radio está
        # fora, então trocar o perfil reroda o fragmento e o form inteiro é
        # redesenhado com o campo dentro.
        if tipo_usuario_input == "Professor":
            chave_prof_input = st.text_input(
                f"Chave de Verificação ({TAMANHO_CHAVE} caracteres)",
                type="password",
                # Sem max_chars de propósito. Parece boa ideia — impedir que uma
                # chave colada com espaço no fim queime uma das 5 tentativas — mas
                # faz o contrário: o Streamlit CORTA o valor no limite, e o corte
                # acontece antes do strip() da comparação. Medido: "  b3247upy2km8 "
                # (16 caracteres) virava "  b3247upy2k" e a chave correta era
                # rejeitada. Num campo mascarado a pessoa não tem como ver o
                # erro, então é a pior forma de falha possível. A tolerância a
                # caixa e a espaço das pontas fica por conta de chave_equivale.
                help=(
                    "Bloqueada por excesso de tentativas. Aguarde a janela."
                    if chave_bloqueada
                    else "Solicite a chave diária à coordenação. "
                         "Pode digitar em maiúsculas ou minúsculas."
                ),
                disabled=chave_bloqueada,
            )

        nome_input = st.text_input("Nome Completo")
        novo_usuario_input = st.text_input("Nome de Usuário")

        email_input = st.text_input("E-mail")
        email_confirm_input = st.text_input("Confirme o E-mail")

        nova_senha_input = st.text_input(
            "Nova Senha",
            type="password",
            help="Requisitos: 1 maiúscula, 1 minúscula e 1 número."
        )

        # A senha é digitada duas vezes de propósito. Num campo mascarado não
        # dá para reler o que foi escrito, então um erro de digitação viraria
        # uma conta com uma senha que ninguém sabe qual é — e não há
        # "esqueci minha senha" nesta plataforma para consertar isso depois.
        # Segue o mesmo padrão do campo de e-mail, que já confirma.
        nova_senha_confirm_input = st.text_input(
            "Confirme a Nova Senha",
            type="password",
        )

        btn_cadastrar = st.form_submit_button("Finalizar Cadastro", disabled=chave_bloqueada)

        if btn_cadastrar:
            # Nenhum envio começa com o aviso antigo na tela. O perfil vai junto
            # para o aviso poder ser descartado se a pessoa trocar de cadastro
            # depois: senão o "Conta criada com sucesso!" do Aluno ficava na tela
            # ao lado do "Chave bloqueada" do Professor, que são coisas de
            # contextos diferentes.
            st.session_state[_CHAVE_DO_RESULTADO] = None
            st.session_state[_CHAVE_DO_PERFIL] = tipo_usuario_input

            # 1. Bloqueio por excesso de tentativas na chave do Professor. Fica no
            #    topo da cadeia de propósito: quem está bloqueado não gasta
            #    validação nem recebe dica sobre os outros campos.
            if tipo_usuario_input == "Professor" and ratelimit.excedeu(ratelimit.CHAVE_PROFESSOR):
                _guardar_resultado(
                    "error",
                    "Muitas tentativas de chave incorretas. "
                    f"Tente de novo em {ratelimit.JANELA_SEGUNDOS // 60} minutos."
                )

            # 2. Preenchimento dos campos básicos
            elif not (nome_input and novo_usuario_input and email_input and email_confirm_input and nova_senha_input and nova_senha_confirm_input):
                _guardar_resultado("error", "Por favor, preencha todos os campos do formulário.")

            # 3. Validação da Chave Dinâmica do Professor
            elif tipo_usuario_input == "Professor" and not chave_equivale(
                chave_prof_input, chave_valida_hoje
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
                if restantes == 0:
                    # Bloqueou agora: redesenha para o campo e o botão já
                    # aparecerem desabilitados. A mensagem acima está no
                    # session_state e é mostrada de novo depois do rerun.
                    st.rerun()

            # 4. Validação de e-mail
            elif email_input != email_confirm_input:
                _guardar_resultado("error", "Os e-mails digitados não coincidem.")
            elif not validar_email_formato(email_input):
                _guardar_resultado("error", "Por favor, informe um e-mail válido.")

            # 5. Confirmação da senha: as duas digitações têm que ser iguais.
            #    Vem antes da força de propósito: se as duas não batem, dizer
            #    "falta uma maiúscula" não resolve nada.
            elif nova_senha_input != nova_senha_confirm_input:
                _guardar_resultado("error", "As senhas digitadas não coincidem.")

            # 6. Validação da força da senha
            elif not validar_forca_senha(nova_senha_input):
                _guardar_resultado(
                    "error",
                    "A senha deve conter pelo menos uma letra maiúscula, "
                    "uma minúscula e um número."
                )

            # 7. Salvar no banco
            else:
                motivo = cadastrar_usuario(
                    username=novo_usuario_input,
                    nome=nome_input,
                    email=email_input,
                    tipo=tipo_usuario_input,
                    senha_pura=nova_senha_input
                )
                if motivo == "ok":
                    # Só zera no sucesso, e só para Professor: quem cadastra
                    # Aluno não tem chave para limpar.
                    if tipo_usuario_input == "Professor":
                        ratelimit.zerar(ratelimit.CHAVE_PROFESSOR)
                    _guardar_resultado(
                        "success", "Conta criada com sucesso! Faça login na aba ao lado."
                    )
                elif motivo == "email_duplicado":
                    _guardar_resultado(
                        "warning", "Este e-mail já está cadastrado nesta plataforma."
                    )
                else:
                    _guardar_resultado("warning", "Este nome de usuário já está em uso.")

    # O aviso do último envio é redesenhado aqui, fora do formulário.
    #
    # Não dá para desenhar dentro: dentro do st.form nada aparece antes do
    # envio, e qualquer redesenho do fragmento (troca de perfil, o rerun de
    # quando a chave bloqueia, ou o fim do bloqueio) redesenha o formulário
    # inteiro sem reexecutar o tratamento do envio, levando junto toda
    # mensagem. Guardar em session_state faz a mensagem sobreviver ao redesenho
    # e durar até a próxima tentativa, que é o tempo que a pessoa precisa para
    # ler.
    #
    # E some se o perfil mudou desde o envio: um aviso de Professor não tem o
    # que estar na tela quando a pessoa já passou para o cadastro de Aluno.
    _resultado = st.session_state.get(_CHAVE_DO_RESULTADO)
    if _resultado and st.session_state.get(_CHAVE_DO_PERFIL) == tipo_usuario_input:
        _nivel, _texto = _resultado
        getattr(st, _nivel)(_texto)

    # NÃO há código de teste da chave aqui. A chave do dia é distribuída apenas
    # pelo Painel da Coordenação (app.py), que exige login de Administrador.
    # Enquanto este st.info existiu, a chave estava impressa na aba pública de
    # cadastro, para qualquer visitante, antes de digitar qualquer coisa — o que
    # anulava o rate limit da chave, já que não havia o que adivinhar.


def render_login():
    with st.container(key="pagina_login"):
        _render_login()


def _render_login():
    # O CSS da tela de login fica em static/css/login.css.
    aplicar_css("login.css")

    st.markdown(
        '<p class="login-title">Acesso ao CriptoEduca</p>'
        '<p class="login-subtitle">Entre com suas credenciais ou crie sua conta para continuar</p>',
        unsafe_allow_html=True,
    )
    aba_login, aba_cadastro = st.tabs(["Entrar", "Criar Conta"])
    with aba_login:
        with st.container(key="aba_login"):
            _formulario_login()

    with aba_cadastro:
        with st.container(key="aba_cadastro"):
            _formulario_cadastro()