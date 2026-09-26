import streamlit as st
import re
import random
from datetime import datetime
from modules.database import verificar_login, cadastrar_usuario
from modules import ratelimit

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

def obter_chave_professor_diaria(segredo_sistema="chaveDev2026"):
    """
    Gera uma chave numérica aleatória de 6 dígitos válida por 24h.
    Usa a data atual (YYYY-MM-DD) + segredo do sistema como semente.
    """
    data_hoje = datetime.now().strftime("%Y-%m-%d")
    semente = f"{segredo_sistema}_{data_hoje}"
    
    # Instancia um gerador aleatório isolado com a semente do dia
    gerador = random.Random(semente)
    
    # Gera um número fixo de 6 dígitos para o dia de hoje
    return str(gerador.randint(100000, 999999))

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
            font-size: 30px !important;
            font-weight: 700;
            color: #f1f5f9;
            margin-bottom: 0.4rem;
            line-height: 1.2;
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
            min-height: 40px;
            display: flex;
            align-items: center;
            justify-content: center;
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
        /* O seletor antigo usava div[data-baseweb="select"], atributo que não
           existe nesta versão do Streamlit: a regra nunca casou e o seletor
           ficava com a cor padrão, destoando dos campos de texto. */
        [data-testid="stForm"] [data-testid="stSelectbox"] [role="group"] {
            background-color: #1e2430;
            border-radius: 10px;
        }

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
            transition: background-color 0.2s, transform 0.1s;
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
                font-size: 26px !important;
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
                font-size: 22px !important;
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
            [data-testid="stForm"] [data-testid="stSelectbox"] input {
                font-size: 16px !important;
            }

            /* No celular o botão é o alvo de toque mais importante da tela */
            [data-testid="stForm"] [class*="st-key-FormSubmitter"] button {
                min-height: 48px;
            }
        }

        @media (max-width: 360px) {
            div.stMarkdown p.login-title {
                font-size: 20px !important;
            }
            [data-testid="stTabs"] [role="tab"] {
                font-size: 13px;
                padding: 0.6rem 0.2rem;
            }
        }

        /* Quem pede menos animação não recebe transição */
        @media (prefers-reduced-motion: reduce) {
            [data-testid="stForm"] [class*="st-key-FormSubmitter"] button {
                transition: none;
            }
            [data-testid="stForm"] [class*="st-key-FormSubmitter"] button:active {
                transform: none;
            }
        }
    </style>
    """, unsafe_allow_html=True)

    st.markdown(
        '<p class="login-title">Acesso à Plataforma Educativa</p>'
        '<p class="login-subtitle">Entre com suas credenciais ou crie sua conta para continuar</p>',
        unsafe_allow_html=True,
    )
    aba_login, aba_cadastro = st.tabs(["Entrar", "Criar Conta"])
    with aba_login:
        _formulario_login()

    with aba_cadastro:
            # Obtém a chave válida para o dia de hoje
       chave_valida_hoje = obter_chave_professor_diaria()

       # O selectbox fica FORA do formulário, de propósito. Dentro de st.form o
       # Streamlit agrupa tudo e nada redesenha até o envio, então condicionar o
       # campo da chave ao perfil só apareceria depois de enviar — pior que
       # mostrar sempre. Fora do form, cada troca de perfil reroda a tela na hora.
       #
       # Efeito colateral bom: clear_on_submit só limpa widgets dentro do form, o
       # que o perfil sobrevive ao envio. Antes o perfil voltava para "Aluno" a
       # cada tentativa, e era por isso que o aviso de bloqueio precisava ficar
       # independente do perfil.
       tipo_usuario_input = st.selectbox("Perfil de Acesso", ["Aluno", "Professor"], key="perfil_cadastro")

       # Só existe quando o perfil é Professor. Precisa do default antes do if
       # porque a cadeia de validação mais abaixo lê esta variável em todos os
       # caminhos, e sem o default o perfil Aluno levanta NameError.
       chave_prof_input = ""

       if tipo_usuario_input == "Professor":
                # O bloqueio vale para a CHAVE, não para o cadastro inteiro, e
                # por isso só este campo e o botão desabilitam: assim um Professor
                # bloqueado ainda se cadastra como Aluno, e o selectbox continua
                # vivo para permitir a troca.
                chave_bloqueada = ratelimit.excedeu(ratelimit.CHAVE_PROFESSOR)

                # Com o selectbox fora do form o perfil não reseta mais, então o
                # aviso pode ficar amarrado a ele: some junto com o campo, que é
                # o comportamento esperado. O texto segue dizendo que vale só
                # para o cadastro com chave, porque o limite é da chave.
                if chave_bloqueada:
                    st.warning(
                        "Chave do Professor bloqueada por excesso de tentativas. "
                        "Vale só para o cadastro com chave, não afeta o Aluno. "
                        f"Tente de novo em {ratelimit.JANELA_SEGUNDOS // 60} minutos."
                    )

                chave_prof_input = st.text_input(
                    "Chave de Verificação de 6 dígitos",
                    type="password",
                    help=(
                        "Bloqueada por excesso de tentativas. Aguarde a janela."
                        if chave_bloqueada
                        else "Solicite a chave diária à coordenação."
                    ),
                    disabled=chave_bloqueada,
                )
       else:
                chave_bloqueada = False

       with st.form("form_cadastro", clear_on_submit=True):
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
                    # 1. Bloqueio por excesso de tentativas na chave do Professor.
                    #    Fica no topo da cadeia de propósito: quem está bloqueado
                    #    não gasta validação nem recebe dica sobre os outros campos.
                    if tipo_usuario_input == "Professor" and ratelimit.excedeu(ratelimit.CHAVE_PROFESSOR):
                        st.error(
                            "Muitas tentativas de chave incorretas. "
                            f"Tente de novo em {ratelimit.JANELA_SEGUNDOS // 60} minutos."
                        )

                    # 2. Preenchimento dos campos básicos
                    elif not (nome_input and novo_usuario_input and email_input and email_confirm_input and nova_senha_input):
                        st.error("Por favor, preencha todos os campos do formulário.")

                    # 3. Validação da Chave Dinâmica do Professor
                    elif tipo_usuario_input == "Professor" and chave_prof_input != chave_valida_hoje:
                        ratelimit.registrar_falha(ratelimit.CHAVE_PROFESSOR)
                        st.error(
                            "Chave de verificação do Professor inválida ou expirada. "
                            f"Restam {ratelimit.restantes(ratelimit.CHAVE_PROFESSOR)} "
                            f"tentativa(s) em {ratelimit.JANELA_SEGUNDOS // 60} minutos."
                        )

                    # 4. Validação de e-mail
                    elif email_input != email_confirm_input:
                        st.error("Os e-mails digitados não coincidem.")
                    elif not validar_email_formato(email_input):
                        st.error("Por favor, informe um e-mail válido.")

                    # 5. Validação da força da senha
                    elif not validar_forca_senha(nova_senha_input):
                        st.error("A senha deve conter pelo menos uma letra maiúscula, uma minúscula e um número.")

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
                            # Só zera no sucesso, e só para Professor: quem
                            # cadastro de Aluno não tem chave para limpar.
                            if tipo_usuario_input == "Professor":
                                ratelimit.zerar(ratelimit.CHAVE_PROFESSOR)
                            st.success("Conta criada com sucesso! Faça login na aba ao lado.")
                        elif motivo == "email_duplicado":
                            st.warning("Este e-mail já está cadastrado nesta plataforma.")
                        else:
                            st.warning("Este nome de usuário já está em uso.")

            # NÃO há código de teste da chave aqui. A chave do dia é distribuída
            # apenas pelo Painel da Coordenação (app.py), que exige login de
            # Administrador. Enquanto este st.info existiu, a chave estava
            # impressa na aba pública de cadastro, para qualquer visitante, antes
            # de digitar qualquer coisa — o que anulava o rate limit da chave,
            # já que não há o que adivinhar.