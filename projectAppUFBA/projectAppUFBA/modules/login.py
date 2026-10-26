import streamlit as st
import re
import hmac
import hashlib
from datetime import datetime
from modules.database import verificar_login, cadastrar_usuario
from modules import ratelimit

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


# run_every é o que conserta "esperar não funciona". Medido antes: o app não
# tinha nenhum rerender automático (só dois st.rerun manuais, e st_autorefresh
# nem instalado). O Streamlit só redesenha quando o script roda, e o script só
# roda com interação do usuário — então o botão ficava cinza indefinidamente
# depois do bloqueio, mesmo com a janela já vencida em memória. A reação
# natural a uma tela travada é F5, que rotaciona o cookie XSRF e zera o
# contador. Os dois sintomas eram o mesmo defeito.
#
# st.fragment(run_every=...) existe nativamente no Streamlit 1.64 (assinatura
# verificada: run_every: int | float | timedelta | str | None), então isto não
# acrescenta dependência. O fragmento recria os widgets a cada ciclo, e o
# clear_on_submit faz o recomeço sem apagar o que o usuário já digitou.
@st.fragment(run_every="5s")
def _formulario_login():
    with st.form("form_login", clear_on_submit=True):
        # clear_on_submit: a senha digitada não fica na tela depois do envio.
        # Custo aceito: quem erra a senha reescreve o usuário.
        usuario_input = st.text_input("Usuário")
        senha_input = st.text_input("Senha", type="password")

        login_bloqueado, _sobra, _alvos = _situacao_login(usuario_input)

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

# Mesmo motivo do fragmento do login, e ainda mais visível aqui.
#
# Sem ele, o botão do cadastro ficava habilitado depois da 5ª chave errada: o
# `disabled` é avaliado quando o formulário é desenhado, e o contador só estoura
# durante o tratamento do envio, ou seja, um ciclo tarde. Medido antes da
# correção: na 5ª tentativa o contador já mostrava "Restam 0", mas campo e botão
# seguiam liberados e só travavam no clique seguinte — exatamente o "mostrar que
# não tem como digitar" que foi pedido. E, igual ao login, sem fragmento o botão
# nunca voltava sozinho quando a janela vencia: a tela ficava morta.
@st.fragment(run_every="5s")
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
            elif not (nome_input and novo_usuario_input and email_input and email_confirm_input and nova_senha_input):
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

            # 4. Validação de e-mail
            elif email_input != email_confirm_input:
                _guardar_resultado("error", "Os e-mails digitados não coincidem.")
            elif not validar_email_formato(email_input):
                _guardar_resultado("error", "Por favor, informe um e-mail válido.")

            # 5. Validação da força da senha
            elif not validar_forca_senha(nova_senha_input):
                _guardar_resultado(
                    "error",
                    "A senha deve conter pelo menos uma letra maiúscula, "
                    "uma minúscula e um número."
                )

            # 6. Salvar no banco
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
    # envio, e o tique do fragmento — que existe para travar e destravar o
    # campo da chave sozinho — redesenha o formulário inteiro sem reexecutar
    # o tratamento do envio, levando junto toda mensagem. Medido: a confirmação
    # "Conta criada com sucesso!" sumia entre 3,0s e 5,2s depois do clique.
    # Guardar em session_state faz a mensagem sobreviver ao tique e durar até
    # a próxima tentativa, que é o tempo que a pessoa precisa para ler.
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

    st.markdown("""
    <style>
        /* Centralização do conteúdo no topo */
        .block-container {
            padding-top: 3rem;
            padding-bottom: 2rem;
            max-width: 900px;
        }

        /* ---------- Superfícies ---------- */
        /* O app usa o dark theme padrão do Streamlit: o cartão branco
           original ficava ilegível sobre o fundo escuro. */
        [data-testid="stForm"] {
            background-color: #161a23;
            border: 1px solid rgba(148, 163, 184, 0.16);
            border-radius: 14px;
            padding: 2rem;
            box-shadow: 0 18px 40px -24px rgba(0, 0, 0, 0.9);
        }

        /* ---------- Cabeçalho ---------- */
        /* As classes já existiam no CSS original, mas st.title() não aceita
           classe: o elemento precisa ser emitido com p.login-title. */
        div.stMarkdown p.login-title {
            text-align: center;
            /* A Press Start 2P é monoespaçada com advance de exatamente 1 em
               por caractere, então a largura do título dá para calcular em
               vez de medir: "Acesso ao CriptoEduca" tem 21 caracteres, e a
               24px isso dá 504px (medido: 504,0px, ou 24,000px por caractere).
               O título era maior (30px) até o texto encolher de "Acesso à
               Plataforma Educativa" para o atual. Com os 29 caracteres
               antigos, 30px dava 870px contra os 900px do .block-container:
               uma sobra de 30px, e nessa margem o título quebrava e não
               quebrava conforme o tamanho da janela. A 21 caracteres não há
               mais aperto: a 30px seriam 630px contra 768px de espaço útil. */
            font-size: 24px !important;
            /* A Press Start 2P só tem o peso 400. Deixar 700 aqui fazia o
               navegador inventar um negrito falso, que borra os pixels. */
            font-weight: 400;
            /* O nome tem que ser "PressStart2P", sem espaços, e é o mesmo nome
               usado em [[theme.fontFaces]] na config.toml. Não é o nome real
               da fonte: é um apelido. O Streamlit monta a regra do @font-face
               sem aspas, e um nome com espaço geraria CSS inválido. */
            font-family: "PressStart2P", monospace;
            /* 1.4 e não 1.2: a caixa dos glyphs desta fonte é alta, e a 1.2
               as linhas de pixels se encostam. */
            line-height: 1.4;
            /* Streamlit aplica tracking negativo em alguns textos. Em fonte
               monoespaçada isso fecha a distância entre os glyphs e quebra
               a grade. */
            letter-spacing: 0;
            /* Sem isto o Chrome suaviza as bordas dos pixels e o resultado
               fica desfocado, que é justamente o oposto do pretendido. */
            -webkit-font-smoothing: none;
            color: #f1f5f9;
            margin-bottom: 0.4rem;
        }
        div.stMarkdown p.login-subtitle {
            text-align: center;
            font-size: 14px;
            color: #94a3b8;
            margin-bottom: 1.5rem;
        }

        /* ---------- Abas ---------- */
        [data-testid="stTabs"] [role="tablist"] {
            background-color: #10141c;
            border: 1px solid rgba(148, 163, 184, 0.12);
            border-radius: 10px;
            padding: 0.25rem;
            gap: 0.25rem;
        }
        [data-testid="stTabs"] [role="tab"] {
            color: #94a3b8;
            font-weight: 600;
            border-radius: 8px;
            /* O flex:1 é o que tira as abas do canto. Sem ele cada aba mede
               só o próprio texto: medido, a tablist tem 768px e as duas abas
               ocupavam 102px somadas (36px e 66px), com 666px vazios à
               direita. Com flex:1 as duas dividem a faixa inteira, e a aba
               selecionada passa a ler como um bloco e não como um rótulo
               solto grudado na esquerda. */
            flex: 1;
            /* O padding segura o rótulo longe da borda da aba. O vertical só
               passou a valer porque veio junto com o min-height: a 40px de
               altura e conteúdo de uns 19px, o min-height absorveria o
               padding e nada mudaria na tela. */
            padding: 0.6rem 1rem;
            min-height: 46px;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: background-color 0.3s ease, color 0.3s ease;
        }
        [data-testid="stTabs"] [aria-selected="true"] {
            background-color: #4F46E5;
            color: #ffffff;
        }

        /* ---------- Campos ---------- */
        /* A borda real do campo fica no elemento pai, não no input. */
        [data-testid="stForm"] [data-testid="stTextInputRootElement"] {
            background-color: #1e2430;
            border-radius: 10px;
        }
        [data-testid="stForm"] [data-testid="stWidgetLabel"] p {
            color: #e2e8f0;
            font-size: 13px;
            font-weight: 600;
        }
        /* ---------- Seletor de perfil (st.radio) ---------- */
        /* A regra antiga era para o stSelectbox do perfil. Não há mais nenhum
           seletor dentro do formulário — o único que existe é o do perfil, e
           ele foi parar fora do form de propósito (é o que faz o campo da
           chave reagir na hora). Por isso estas regras não levam
           [data-testid="stForm"]: alcançariam nada, e o radio ficaria com o
           claro do tema, destoando dos campos de texto ao lado. */
        [data-testid="stRadio"] [role="radiogroup"] {
            background-color: #1e2430;
            border-radius: 10px;
            padding: 0.4rem 0.7rem;
        }
        [data-testid="stRadio"] [role="radiogroup"] label {
            color: #e2e8f0;
            font-size: 14px;
            padding: 0.25rem 0;
        }
        /* O item marcado precisa ficar claro contra o fundo escuro, senão a
           escolha some e o usuário não sabe qual perfil está selecionado.

           Atenção ao seletor. O Streamlit 1.64 migrou o radio para React Aria
           e a marcação mudou: não existe mais [role="radio"] nem
           [aria-checked]. O estado vem em data-selected="true" e a opção é
           label[data-testid="stRadioOption"]. As duas regras que usavam
           [role="radio"] casavam com zero elementos, ou seja, o perfil
           selecionado nunca chegou a ser destacado -- os dois itens
           computavam exatamente a mesma cor e o mesmo peso. */
        [data-testid="stRadio"] [data-testid="stRadioOption"][data-selected="true"] {
            color: #ffffff;
            font-weight: 600;
        }
        /* A regra do svg foi removida junto: o radio novo não tem svg nenhum.
           O que se vê hoje é só o texto dentro de um div, então a cor do
           círculo que ela pintava não tem mais onde ser aplicada. */

        /* ---------- Botão ---------- */
        /* O seletor original (div.stButton > button) estilizava todos os
           botões do app. Este fica restrito ao botão do formulário. */
        /* O Streamlit encolhe o container do botão de propósito, para o botão
           abraçar o rótulo. Sem esta regra, width:100% no próprio botão é 100%
           dos 68px que ele já ocupa: uma circularidade. A largura é forçada
           no container, e o botão preenche. */
        [data-testid="stForm"] [data-testid="stElementContainer"] {
            width: 100%;
        }
        [data-testid="stForm"] [class*="st-key-FormSubmitter"] button {
            width: 100%;
            background-color: #4F46E5;
            color: #ffffff !important;
            font-weight: 600;
            font-size: 16px;
            border-radius: 10px;
            border: none;
            min-height: 48px;
            padding: 0.5rem 1rem;
            transition: background-color 0.3s ease, transform 0.1s ease;
        }
        [data-testid="stForm"] [class*="st-key-FormSubmitter"] button:hover {
            background-color: #4338CA;
            color: #ffffff !important;
        }
        [data-testid="stForm"] [class*="st-key-FormSubmitter"] button:active {
            transform: translateY(1px);
        }

        /* ---------- Foco ---------- */
        /* Só o halo. Uma border-color aqui foi testada e não surte efeito:
           a regra casa (:focus-within é true), mas a cor da borda continua
           a do Streamlit, com ou sem !important. O halo aparece e some com o
           foco, medido. Preferi um efeito verificável a uma declaração
           decorativa no código. */
        [data-testid="stForm"] [data-testid="stTextInputRootElement"]:focus-within {
            box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.25);
        }

        /* ---------- Campo e botão bloqueados ---------- */
        /* O CSS acima pinta o fundo do campo, então o cinza padrão de
           desabilitado do tema não apareceria: o campo continuaria com a
           mesma cara de um campo liberado. A opacidade é a diferença visível
           entre "digitável" e "não digitável", que é o que o usuário precisa
           ver. */
        [data-testid="stForm"] [data-testid="stTextInputRootElement"]:has(input:disabled) {
            opacity: 0.45;
        }
        [data-testid="stForm"] [class*="st-key-FormSubmitter"] button:disabled {
            opacity: 0.4;
            cursor: not-allowed;
        }

        /* ---------- Aba de cadastro: dica de teste ---------- */
        [data-testid="stForm"] [data-testid="stAlertContainer"] {
            background-color: rgba(79, 70, 229, 0.12);
            border: 1px solid rgba(99, 102, 241, 0.3);
        }

        /* ---------- Interatividade: hover e pressionado ---------- */
        /* As transições ficam aqui, junto dos estados que elas animam, e não
           na regra base de cada controle lá em cima: assim o par
           transition/estado aparece no mesmo lugar, em vez de a transition
           estar a duzentas linhas do :hover que ela faz existir.
           0.3s ease em tudo, menos o "afundar" do :active, que continua em
           0.1s. Um pressionar lento lê como lentidão e não como retorno; é a
           cor que precisa de 0.3s para não piscar. */
        /* Em todos os pares abaixo, a regra do item selecionado precisa ser
           separada da do não selecionado. Sem o :not(), passar o mouse sobre
           a aba que já está aberta apagaria a única pista de qual aba é a
           que está aberta. */

        /* Abas. O não selecionado ganha um fundo indigo fraco; o selecionado
           escurece, na mesma direção do botão (#4F46E5 -> #4338CA). */
        [data-testid="stTabs"] [role="tab"]:not([aria-selected="true"]):hover {
            background-color: rgba(79, 70, 229, 0.16);
            color: #e2e8f0;
        }
        [data-testid="stTabs"] [role="tab"]:not([aria-selected="true"]):active {
            background-color: rgba(79, 70, 229, 0.30);
        }
        [data-testid="stTabs"] [role="tab"][aria-selected="true"]:hover {
            background-color: #4338CA;
        }
        [data-testid="stTabs"] [role="tab"][aria-selected="true"]:active {
            background-color: #3730A3;
        }

        /* Perfil (Aluno/Professor). O transform entra na lista porque este é
           um dos controles que afunda no :active. */
        [data-testid="stRadio"] [data-testid="stRadioOption"] {
            transition: background-color 0.3s ease, color 0.3s ease,
                        transform 0.1s ease;
        }
        /* Perfil (Aluno/Professor). O realce usa o azul #38bdf8, que era a cor
           do círculo na marcação antiga; aqui ela volta no fundo, já que não
           há mais círculo para pintar. Os seletores seguem a mesma correção
           do bloco acima: stRadioOption e data-selected, nunca [role="radio"]
           nem [aria-checked]. */
        [data-testid="stRadio"] [data-testid="stRadioOption"]:not([data-selected="true"]):hover {
            background-color: rgba(56, 189, 248, 0.10);
            color: #ffffff;
            border-radius: 6px;
        }
        [data-testid="stRadio"] [data-testid="stRadioOption"]:not([data-selected="true"]):active {
            background-color: rgba(56, 189, 248, 0.20);
        }
        [data-testid="stRadio"] [data-testid="stRadioOption"]:active {
            transform: translateY(1px);
        }

        [data-testid="stForm"] [data-testid="stTextInputRootElement"] {
            transition: box-shadow 0.3s ease;
        }
        /* Campo de texto. Não é border-color: o comentário em "Foco" acima já
           registra que a cor da borda não surte efeito aqui, porque a borda é
           do elemento pai. O halo é o mesmo mecanismo do :focus-within, só
           mais fraco.
           O :not(:focus-within) é obrigatório. Esta regra e a de "Foco" têm a
           mesma especificidade, e como esta vem depois, um :hover sem o :not
           venceria o foco e trocaria o halo grosso pelo fino toda vez que o
           mouse passasse sobre o campo em foco. */
        [data-testid="stForm"] [data-testid="stTextInputRootElement"]:not(:focus-within):hover {
            box-shadow: 0 0 0 1px rgba(148, 163, 184, 0.25);
        }

        /* Botão de mostrar a senha. filter em vez de color: o ícone é um
           Material Symbols que herda a cor do campo, e brightness funciona
           sem precisar saber qual é essa cor. */
        [data-testid="stTextInputRootElement"] [data-testid="stIconMaterial"] {
            transition: filter 0.3s ease;
        }
        [data-testid="stTextInputRootElement"] [data-testid="stIconMaterial"]:hover {
            filter: brightness(1.35);
        }
        [data-testid="stTextInputRootElement"] [data-testid="stIconMaterial"]:active {
            filter: brightness(0.85);
        }

        /* ---------- Responsividade ---------- */
        @media (max-width: 768px) {
            .block-container {
                padding-top: 2rem;
                padding-bottom: 1.5rem;
            }
            [data-testid="stForm"] {
                padding: 1.5rem;
            }
            div.stMarkdown p.login-title {
                /* 21 caracteres a 20px = 420px, contra uns 736px de espaço
                   útil nesta faixa. Não é mais medida contra quebra: o
                   título já cabe em uma linha nesta altura de tela. */
                font-size: 20px !important;
            }
            /* Tablet: alvo de toque confortável, sem ser o do celular */
            [data-testid="stForm"] [class*="st-key-FormSubmitter"] button {
                min-height: 44px;
            }
        }

        @media (max-width: 480px) {
            .block-container {
                padding-top: 1.25rem;
                padding-bottom: 1rem;
                padding-left: 0.75rem;
                padding-right: 0.75rem;
            }
            [data-testid="stForm"] {
                padding: 1.1rem;
                border-radius: 12px;
                box-shadow: 0 10px 24px -16px rgba(0, 0, 0, 0.9);
            }
            div.stMarkdown p.login-title {
                /* 21 caracteres a 16px = 336px, contra uns 456px de espaço
                   útil com o padding de 0.75rem de cada lado. Mesmo assim o
                   título não quebra em nenhuma das faixas: desde que o texto
                   encolheu, a escada 20/16/14 é escala, e não é mais o que
                   segura o título em uma linha. */
                font-size: 16px !important;
                margin-bottom: 0.35rem;
            }
            div.stMarkdown p.login-subtitle {
                font-size: 13px;
                margin-bottom: 1rem;
                padding: 0 0.5rem;
            }

            /* Abas lado a lado ocupando a largura toda, com alvo de toque de 44px */
            [data-testid="stTabs"] [role="tablist"] {
                padding: 0.2rem;
                gap: 0.2rem;
            }
            [data-testid="stTabs"] [role="tab"] {
                padding: 0.7rem 0.35rem;
                font-size: 14px;
                min-height: 44px;
            }

            /* 16px evita o zoom automático do iOS ao focar o campo */
            [data-testid="stForm"] [data-testid="stTextInputRootElement"] input,
            [data-testid="stRadio"] label {
                font-size: 16px !important;
            }

            /* No celular o botão é o alvo de toque mais importante da tela */
            [data-testid="stForm"] [class*="st-key-FormSubmitter"] button {
                min-height: 48px;
            }
        }

        @media (max-width: 360px) {
            div.stMarkdown p.login-title {
                font-size: 14px !important;
            }
            [data-testid="stTabs"] [role="tab"] {
                font-size: 13px;
                padding: 0.6rem 0.2rem;
            }
        }

        /* Quem pede menos animação não recebe transição */
        /* A lista cresceu quando as transições de 0.3s entraram. Com só a do
           botão aqui, quem tem prefers-reduced-motion ligado continuava
           recebendo 0.3s de transição em todo o resto. */
        @media (prefers-reduced-motion: reduce) {
            [data-testid="stForm"] [class*="st-key-FormSubmitter"] button,
            [data-testid="stTabs"] [role="tab"],
            [data-testid="stRadio"] [data-testid="stRadioOption"],
            [data-testid="stForm"] [data-testid="stTextInputRootElement"],
            [data-testid="stTextInputRootElement"] [data-testid="stIconMaterial"] {
                transition: none;
            }
            [data-testid="stForm"] [class*="st-key-FormSubmitter"] button:active,
            [data-testid="stRadio"] [data-testid="stRadioOption"]:active {
                transform: none;
            }
        }
    </style>
    """, unsafe_allow_html=True)

    st.markdown(
        '<p class="login-title">Acesso ao CriptoEduca</p>'
        '<p class="login-subtitle">Entre com suas credenciais ou crie sua conta para continuar</p>',
        unsafe_allow_html=True,
    )
    aba_login, aba_cadastro = st.tabs(["Entrar", "Criar Conta"])
    with aba_login:
        _formulario_login()

    with aba_cadastro:
        _formulario_cadastro()