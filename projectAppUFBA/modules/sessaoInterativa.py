"""Mural de Criptografia: cifra de substituicao individual por usuario.

Cada usuario tem um alfabeto de substituicao fixo, derivado do proprio
username. A mensagem e cifrada com esse alfabeto e publicada no mural; o
dicionario da conta fica disponivel na propria pagina, para a pessoa
cifrar e decifrar as mensagens dela.

Esta cifra e didatica, nao segura: a chave e derivada do username, que e
publico. O objetivo e mostrar, na pratica, por que uma substituicao
simples e fraca. A criptografia de alto nivel (AES-128-GCM) fica no
modulo especial "Laboratorio AES-128-GCM", que nao publica nada.

O nome do arquivo continua sessaoInterativa.py por compatibilidade com o
historico do projeto; a pagina se chama "Mural de Criptografia".
"""

import html
import random

import streamlit as st

from modules.database import (
    atualizar_primeiro_acesso,
    carregar_cifras_compartilhadas,
    carregar_mural,
    inativar_mensagem_mural,
    salvar_compartilhamento_cifra,
    salvar_mensagem_mural,
    usuario_existe,
)

# O alfabeto da cifra. A mensagem e bloqueada se tiver qualquer caractere
# fora desta lista; assim o texto cifrado nunca carrega simbolos que a cifra
# nao sabe representar.
ALFABETO = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789ÁÀÂÃÉÊÍÓÔÕÚÜÇáàâãéêíóôõúüç.,:!?()[]{}@#$%&+_=<> "

# Categorias usadas pelo filtro do dicionário. A ordem de ALFABETO não pode
# mudar: ela define o mapa de substituição já usado nas mensagens publicadas.
CATEGORIAS_DICIONARIO = (
    ("Minúsculas (a-z)", set("abcdefghijklmnopqrstuvwxyz")),
    ("Maiúsculas (A-Z)", set("ABCDEFGHIJKLMNOPQRSTUVWXYZ")),
    ("Acentuadas (á, Á...)", set("ÁÀÂÃÉÊÍÓÔÕÚÜÇáàâãéêíóôõúüç")),
    ("Números (0-9)", set("0123456789")),
    ("Símbolos e espaço", set(".,:!?()[]{}@#$%&+_=<> ")),
)


def caracteres_fora_do_alfabeto(texto):
    """Devolve os caracteres da mensagem que nao existem no alfabeto."""
    return sorted(set(texto) - set(ALFABETO))


def gerar_cifra_usuario(username):
    """Gera um dicionario de substituicao unico e fixo para o username.

    O embaralhamento usa uma semente derivada do username. Duas pessoas
    com o mesmo username teriam o mesmo alfabeto -- e e exatamente essa
    fraqueza que o mural demonstra.
    """
    originais = list(ALFABETO)
    embaralhados = list(ALFABETO)

    seed_numerica = sum(ord(c) for c in username)
    rng = random.Random(seed_numerica)
    rng.shuffle(embaralhados)

    return dict(zip(originais, embaralhados))


def criptografar_texto(texto, username):
    """Aplica a cifra de substituicao do usuario ao texto.

    Todo caractere precisa existir em ALFABETO. A validacao acontece antes,
    no formulario, para a mensagem ser recusada com uma explicacao em vez de
    chegar aqui pela metade.
    """
    mapa = gerar_cifra_usuario(username)
    return "".join(mapa[char] for char in texto)


def _css():
    st.markdown("""
        <style>
        /* Caixa de destaque da chave de criptografia */
        .cifra-box {
            background: linear-gradient(135deg, rgba(79, 70, 229, 0.1), rgba(15, 23, 42, 0.2));
            border: 1px solid rgba(79, 70, 229, 0.3);
            padding: 1.5rem;
            border-radius: 12px;
            margin-bottom: 1.5rem;
        }

        /* Estilizacao dos blocos do mural e caixas de texto */
        .stTextArea textarea {
            background-color: #0f172a !important;
            color: #f8fafc !important;
            border: 1px solid #334155 !important;
            border-radius: 8px !important;
        }

        /* Dicionário: grade que acompanha a largura da tela. No desktop
           mantém as quatro colunas; no celular reduz para duas e, em telas
           muito estreitas, para uma. */
        .mural-dic-grade {
            column-count: 4;
            column-gap: 1rem;
            margin-top: 0.75rem;
        }
        .mural-dic-item {
            display: flex;
            align-items: center;
            gap: 0.35rem;
            min-width: 0;
            padding: 0.18rem 0;
            font-size: 0.9rem;
            line-height: 1.3;
            break-inside: avoid;
        }
        .mural-dic-orig {
            color: #e2e8f0;
            min-width: 2.2rem;
            text-align: center;
        }
        .mural-dic-seta {
            color: #94a3b8;
            flex: 0 0 auto;
        }
        .mural-dic-cifra {
            color: #38bdf8;
            font-weight: 700;
            overflow-wrap: anywhere;
        }
        .mural-dic-grade code {
            background: rgba(56, 189, 248, 0.10);
            border-radius: 4px;
            padding: 0 0.22rem;
        }
        @media (max-width: 900px) {
            .mural-dic-grade {
                column-count: 3;
            }
        }
        @media (max-width: 700px) {
            .mural-dic-grade {
                column-count: 2;
                column-gap: 0.6rem;
            }
            .mural-dic-item {
                font-size: 0.82rem;
            }
        }
        @media (max-width: 380px) {
            .mural-dic-grade {
                column-count: 1;
            }
        }

        /* Efeito visual para as mensagens cifradas no mural */
        .mural-item {
            background-color: rgba(30, 41, 59, 0.4);
            border-left: 4px solid #4F46E5;
            padding: 1rem;
            border-radius: 0 8px 8px 0;
            margin-bottom: 0.75rem;
            font-family: monospace;
            overflow-wrap: anywhere;
        }
        </style>
    """, unsafe_allow_html=True)


def _mostrar_dicionario(username_atual, cifras_compartilhadas):
    """Mostra o alfabeto da conta ou de uma cifra compartilhada, em colunas."""
    donos = [username_atual] + [
        username for username in cifras_compartilhadas
        if username != username_atual
    ]

    with st.expander(
        "🔍 Ver o dicionário completo da Cifra",
        expanded=False,
    ):
        if len(donos) > 1:
            dono_dicionario = st.selectbox(
                "Dicionário exibido:",
                options=donos,
                format_func=lambda username: (
                    f"Minha cifra ({username})"
                    if username == username_atual
                    else f"Cifra compartilhada por {username}"
                ),
                key=f"mural_dicionario_dono_{username_atual}",
            )
        else:
            dono_dicionario = username_atual

        if dono_dicionario != username_atual:
            st.info(
                f"Você está vendo o dicionário de **{dono_dicionario}**. "
                "Suas mensagens continuam sendo cifradas com a sua própria "
                "cifra; isto muda apenas a exibição do dicionário."
            )

        st.write(
            "Cada caractere original à esquerda corresponde ao caractere "
            "cifrado à direita:"
        )

        mapa = gerar_cifra_usuario(dono_dicionario)
        categorias = [nome for nome, _ in CATEGORIAS_DICIONARIO]
        selecionadas = st.multiselect(
            "Filtrar por tipo de caractere:",
            options=categorias,
            default=categorias,
            key=f"mural_dicionario_filtro_{username_atual}_{dono_dicionario}",
            help=(
                "Escolha quais grupos aparecem no dicionário. "
                "O filtro não altera a cifra das mensagens."
            ),
        )

        if not selecionadas:
            st.info(
                "Selecione pelo menos um tipo de caractere para exibir "
                "o dicionário."
            )
            return

        caracteres_filtrados = set()
        for nome, caracteres in CATEGORIAS_DICIONARIO:
            if nome in selecionadas:
                caracteres_filtrados.update(caracteres)

        itens = [
            (original, cifrado)
            for original, cifrado in mapa.items()
            if original in caracteres_filtrados
        ]
        st.caption(f"{len(itens)} caracteres exibidos.")

        def _exibir(caractere):
            return "Espaço" if caractere == " " else caractere

        blocos = "".join(
            '<div class="mural-dic-item">'
            f'<code class="mural-dic-orig">{html.escape(_exibir(original))}</code>'
            '<span class="mural-dic-seta">→</span>'
            f'<code class="mural-dic-cifra">{html.escape(_exibir(cifrado))}</code>'
            '</div>'
            for original, cifrado in itens
        )
        st.markdown(
            f'<div class="mural-dic-grade">{blocos}</div>',
            unsafe_allow_html=True,
        )


def _compartilhar_cifra(username_atual):
    """Formulario para compartilhar a cifra com outro username."""
    with st.expander("🤝 Compartilhar cifra", expanded=False):
        st.write(
            "Digite o username de outra pessoa para permitir que ela veja o "
            "seu dicionário no mural. A cifra das mensagens dela continua "
            "sendo a dela."
        )

        with st.form(f"form_compartilhar_cifra_{username_atual}"):
            destinatario = st.text_input(
                "Username de quem vai receber:",
                placeholder="ex.: aluno_teste",
            )
            enviado = st.form_submit_button("Compartilhar cifra")

        if enviado:
            destinatario = destinatario.strip()

            if not destinatario:
                st.error("Digite o username de quem vai receber sua cifra.")
            elif destinatario == username_atual:
                st.error("Você não pode compartilhar a cifra com você mesmo.")
            elif not usuario_existe(destinatario):
                st.error(f"O username '{destinatario}' não foi encontrado.")
            else:
                salvar_compartilhamento_cifra(username_atual, destinatario)
                st.success(
                    f"Sua cifra foi compartilhada com {destinatario}."
                )


# Chaves de feedback exibido depois do callback. O callback roda antes de
# a tela existir, entao ele nao pode chamar st.error/st.success diretamente.
_CHAVE_ERRO = "_mural_erro"
_CHAVE_AVISO = "_mural_aviso"


def _voltar_ao_menu():
    st.session_state["voltar_para_menu"] = True


def _publicar_mensagem(username_atual, versao_form):
    """Cifra, grava e limpa o formulario como callback do envio."""
    chave_mensagem = f"mural_mensagem_{username_atual}_{versao_form}"
    mensagem = st.session_state.get(chave_mensagem, "")

    if not mensagem.strip():
        st.session_state[_CHAVE_ERRO] = (
            "Escreva alguma mensagem antes de enviar."
        )
        return

    invalidos = caracteres_fora_do_alfabeto(mensagem)
    if invalidos:
        lista = ", ".join(repr(char) for char in invalidos[:10])
        if len(invalidos) > 10:
            lista += ", ..."
        st.session_state[_CHAVE_ERRO] = (
            "A mensagem tem caracteres fora do alfabeto da cifra: %s. "
            "Remova esses caracteres e tente novamente." % lista
        )
        return

    st.session_state.pop(_CHAVE_ERRO, None)
    msg_cifrada = criptografar_texto(mensagem, username_atual)
    salvar_mensagem_mural(username_atual, msg_cifrada)

    if st.session_state.get("primeiro_acesso") == 1:
        atualizar_primeiro_acesso(username_atual)
        st.session_state["primeiro_acesso"] = 0

    # Uma versao nova do form troca a key do text_area no proximo rerun,
    # deixando o campo em branco sem clear_on_submit (que apagaria o texto
    # tambem quando a validacao falhasse).
    st.session_state["mural_form_versao"] = versao_form + 1
    st.session_state.pop(chave_mensagem, None)
    st.session_state[_CHAVE_AVISO] = (
        "Mensagem cifrada publicada no mural!"
    )


def _remover_minha_mensagem(msg_id):
    inativar_mensagem_mural(msg_id)
    st.session_state[_CHAVE_AVISO] = "Sua mensagem foi removida!"


def _inativar_mensagem_gestor(msg_id):
    inativar_mensagem_mural(msg_id)
    st.session_state[_CHAVE_AVISO] = (
        f"Mensagem {msg_id} inativada pela moderação."
    )


def render_sessao_interativa(modo_voluntario=False):
    with st.container(key="pagina_mural_criptografia"):
        _render_sessao_interativa(modo_voluntario)


def _render_sessao_interativa(modo_voluntario=False):
    username_atual = st.session_state["username"]
    _css()

    if modo_voluntario:
        st.button(
            "⬅️ Voltar para o Menu Principal",
            key=f"voltar_mural_menu_{username_atual}",
            on_click=_voltar_ao_menu,
        )

    st.title("🔐 Mural de Criptografia")

    erro = st.session_state.pop(_CHAVE_ERRO, None)
    if erro:
        st.error(erro)
    aviso = st.session_state.pop(_CHAVE_AVISO, None)
    if aviso:
        st.success(aviso)

    cifras_compartilhadas = carregar_cifras_compartilhadas(username_atual)

    # Fora do primeiro acesso obrigatorio, a pessoa ve o dicionario da
    # propria conta e entende como o mural cifra as mensagens.
    if modo_voluntario or st.session_state.get("primeiro_acesso") == 0:
        st.info(
            "🔐 Esta é a sua **chave de substituição pessoal e fixa** "
            "associada à sua conta. Ela é usada para cifrar e decifrar "
            "suas mensagens no mural."
        )
        _compartilhar_cifra(username_atual)
        _mostrar_dicionario(username_atual, cifras_compartilhadas)
    else:
        # PRIMEIRO ACESSO (modo obrigatorio). Sem este aviso, a tela era
        # so um titulo e uma caixa de texto solta: nada dizia que
        # publicar era o que liberava a plataforma.
        st.info(
            "👋 **Bem-vindo(a) ao CriptoEduca!** Este é o seu primeiro "
            "acesso. Para liberar o menu lateral e todas as páginas, "
            "publique uma mensagem cifrada: escreva algo no campo abaixo "
            "e aperte **Criptografar com sua Chave e Enviar**. Assim que a "
            "mensagem aparecer no mural, tudo fica liberado."
        )

    # A versao no key do form e o que limpa os campos depois de um envio
    # bem-sucedido. clear_on_submit=True limparia tambem quando a
    # validacao falha, e a pessoa perderia o que escreveu.
    if "mural_form_versao" not in st.session_state:
        st.session_state["mural_form_versao"] = 0
    versao_form = st.session_state["mural_form_versao"]
    chave_form = f"{username_atual}_{versao_form}"

    with st.form(f"form_mural_interativo_{chave_form}"):
        st.text_area(
            "Digite sua mensagem secreta para o mural:",
            key=f"mural_mensagem_{chave_form}",
            help=(
                "Aceita letras (com acentos), números, espaço e os sinais do "
                "alfabeto da cifra. Emojis e quebras de linha não são aceitos."
            ),
        )
        st.form_submit_button(
            "Criptografar com sua Chave e Enviar",
            key=f"mural_enviar_{chave_form}",
            on_click=_publicar_mensagem,
            args=(username_atual, versao_form),
        )

    st.markdown("---")
    st.subheader("📌 Mural de Mensagens Públicas Cifradas")

    tipo_usuario = st.session_state.get("tipo_usuario", "Aluno")
    eh_gestor = tipo_usuario in ["Professor", "Administrador"]

    filtro_decifraveis = st.checkbox(
        "🔎 Mostrar apenas mensagens decifráveis",
        key=f"mural_filtro_decifraveis_{username_atual}",
        help=(
            "Mostra suas mensagens e as mensagens de quem compartilhou a "
            "cifra com você."
        ),
    )

    mensagens = carregar_mural()
    if filtro_decifraveis:
        mensagens = [
            mensagem for mensagem in mensagens
            if (
                mensagem[1] == username_atual
                or mensagem[1] in cifras_compartilhadas
            )
        ]

    if mensagens:
        for msg_id, autor_msg, msg, data in mensagens:
            col_msg, col_botoes = st.columns([4, 1])

            with col_msg:
                # A mensagem entra em HTML cru, entao precisa de escape mesmo
                # depois de cifrada: o alfabeto agora inclui "<" e ">", que a
                # cifra troca por outros caracteres, mas o escape continua
                # sendo a protecao contra qualquer HTML vindo do banco.
                st.markdown(f"""
                    <div class="mural-item">
                        <span style="color: #94a3b8; font-size: 0.85rem;">🕒 {data}</span><br>
                        <span style="color: #38bdf8; font-size: 1.1rem; font-weight: bold;">{html.escape(msg)}</span>
                    </div>
                """, unsafe_allow_html=True)

            with col_botoes:
                # O proprio autor pode limpar/excluir a sua mensagem
                if autor_msg == username_atual:
                    st.button(
                        "🗑️ Limpar Minha",
                        key=f"limpar_{username_atual}_{msg_id}",
                        type="secondary",
                        on_click=_remover_minha_mensagem,
                        args=(msg_id,),
                    )

                # Professores e Admins podem inativar qualquer mensagem
                if eh_gestor and autor_msg != username_atual:
                    st.button(
                        "🛡️ Inativar",
                        key=f"gestor_del_{username_atual}_{msg_id}",
                        type="secondary",
                        on_click=_inativar_mensagem_gestor,
                        args=(msg_id,),
                    )
    elif filtro_decifraveis:
        st.info(
            "Nenhuma mensagem decifrável com as cifras compartilhadas com "
            "você. Peça para alguém compartilhar a cifra ou desative o filtro."
        )
    else:
        st.info("Nenhuma mensagem no mural ainda. Seja o primeiro a publicar!")
