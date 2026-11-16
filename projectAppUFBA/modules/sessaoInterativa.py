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

from modules.estilo import aplicar_css
from modules.database import (
    atualizar_primeiro_acesso,
    carregar_cifras_compartilhadas,
    carregar_mural,
    inativar_mensagem_mural,
    salvar_compartilhamento_cifra,
    salvar_mensagem_mural,
    listar_seguidos,
)

# O alfabeto da cifra. A mensagem e bloqueada se tiver qualquer caractere
# fora desta lista; assim o texto cifrado nunca carrega simbolos que a cifra
# nao sabe representar.
ALFABETO = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789ÁÀÂÃÉÊÍÓÔÕÚÜÇáàâãéêíóôõúüç.,:!?()[]{}@#$%&+_=<> "

# O mesmo alfabeto como expressao regular, para o NAVEGADOR recusar a mensagem
# antes do envio (parametro validate do st.text_input). So os caracteres que
# tem significado dentro de [...] sao escapados; testado nos tres modos de
# regex do navegador (sem flag, u e v). A validacao no servidor continua em
# _publicar_mensagem, porque a do navegador pode ser contornada.
_ESCAPAR_NA_REGEX = set("()[]{}/\\|-^")
PADRAO_ALFABETO = "^[" + "".join(
    "\\" + c if c in _ESCAPAR_NA_REGEX else c for c in ALFABETO
) + "]+$"

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
    # O CSS do mural fica em static/css/mural.css.
    aplicar_css("mural.css")


def _mostrar_dicionario(username_atual, cifras_compartilhadas):
    """Mostra o alfabeto da conta ou de uma cifra compartilhada, em colunas."""
    donos = [username_atual] + [
        username for username in cifras_compartilhadas
        if username != username_atual
    ]

    # on_change="rerun" + .open: o conteudo (cerca de 120 itens de HTML e o
    # filtro) so e montado com o expander aberto. Antes ele era montado a
    # cada clique no mural, mesmo fechado.
    expander = st.expander(
        "🔍 Ver o dicionário completo da Cifra",
        key=f"exp_dicionario_{username_atual}",
        on_change="rerun",
    )
    if not expander.open:
        return
    with expander:
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
    """Compartilha a cifra com alguém que a pessoa já segue."""
    # Mesmo esquema do dicionario: so consulta quem a pessoa segue quando o
    # expander esta aberto.
    expander = st.expander(
        "🤝 Compartilhar cifra",
        key=f"exp_compartilhar_{username_atual}",
        on_change="rerun",
    )
    if not expander.open:
        return
    with expander:
        seguidos = listar_seguidos(username_atual)
        if not seguidos:
            st.info(
                "Você ainda não segue ninguém. Abra **Meu Perfil → Seguir "
                "usuários**, siga alguém e volte aqui para compartilhar."
            )
            return

        st.write(
            "Escolha uma pessoa que você segue para permitir que ela veja o "
            "seu dicionário no mural. A cifra das mensagens dela continua "
            "sendo a dela."
        )
        with st.form(f"form_compartilhar_cifra_{username_atual}"):
            destinatario = st.selectbox(
                "Compartilhar com:",
                options=seguidos,
                index=None,
                placeholder="Selecione um usuário que você segue",
            )
            enviado = st.form_submit_button("Compartilhar cifra")

        if enviado:
            if not destinatario:
                st.error("Selecione um usuário para compartilhar sua cifra.")
            else:
                salvar_compartilhamento_cifra(username_atual, destinatario)
                st.success(f"Sua cifra foi compartilhada com {destinatario}.")


def _voltar_ao_menu():
    st.session_state["voltar_para_menu"] = True


def _publicar_mensagem(username_atual):
    """Cifra e grava a mensagem, como callback do envio.

    O aviso sai com st.toast direto do callback, sem guardar nada no
    session_state. Mensagem invalida normalmente nem chega aqui: o navegador
    a recusa pelo validate do campo. Esta checagem fica para quem contornar
    o navegador.
    """
    mensagem = (st.session_state.get("mural_mensagem") or "").strip()

    if not mensagem:
        st.toast("Escreva alguma mensagem antes de enviar.", icon="⚠️")
        return

    invalidos = caracteres_fora_do_alfabeto(mensagem)
    if invalidos:
        lista = ", ".join(repr(char) for char in invalidos[:10])
        if len(invalidos) > 10:
            lista += ", ..."
        st.toast(
            "A mensagem tem caracteres fora do alfabeto da cifra: %s." % lista,
            icon="⚠️",
        )
        return

    msg_cifrada = criptografar_texto(mensagem, username_atual)
    salvar_mensagem_mural(username_atual, msg_cifrada)

    if st.session_state.get("primeiro_acesso") == 1:
        atualizar_primeiro_acesso(username_atual)
        st.session_state["primeiro_acesso"] = 0

    st.toast("Mensagem cifrada publicada no mural!")


def _remover_minha_mensagem(msg_id):
    inativar_mensagem_mural(msg_id)
    st.toast("Sua mensagem foi removida!")


def _inativar_mensagem_gestor(msg_id):
    inativar_mensagem_mural(msg_id)
    st.toast(f"Mensagem {msg_id} inativada pela moderação.")


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

    # clear_on_submit limpa o campo depois do envio. Antes isso era evitado
    # porque apagaria o texto tambem quando a validacao falhava; agora a
    # validacao acontece no navegador (validate), que nem envia uma mensagem
    # invalida, entao o texto so e limpo quando a mensagem foi aceita.
    # text_input, e nao text_area: o mural ja nao aceitava quebra de linha.
    # max_chars limita o que vai para o banco e para a memoria.
    with st.form(f"form_mural_{username_atual}", clear_on_submit=True):
        st.text_input(
            "Digite sua mensagem secreta para o mural:",
            key="mural_mensagem",
            max_chars=500,
            validate=(
                PADRAO_ALFABETO,
                "Use só letras (com acentos), números, espaço e os sinais "
                "do alfabeto da cifra. Emojis não são aceitos.",
            ),
            help=(
                "Aceita letras (com acentos), números, espaço e os sinais do "
                "alfabeto da cifra. Emojis não são aceitos."
            ),
        )
        st.form_submit_button(
            "Criptografar com sua Chave e Enviar",
            on_click=_publicar_mensagem,
            args=(username_atual,),
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
