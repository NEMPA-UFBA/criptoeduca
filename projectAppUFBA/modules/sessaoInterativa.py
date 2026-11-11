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
    carregar_mural,
    inativar_mensagem_mural,
    salvar_mensagem_mural,
)

# O alfabeto da cifra. Fora dele, o caractere passa intacto -- e por isso
# que a mensagem ainda pode ter "<" ou ">", que sao escapados na hora de
# montar o HTML.
ALFABETO = "abcdefghijklmnopqrstuvwxyz0123456789 .,!?"


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
    """Aplica a cifra de substituicao do usuario ao texto."""
    mapa = gerar_cifra_usuario(username)
    return "".join(mapa.get(char, char) for char in texto.lower())


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


def _mostrar_dicionario(username_atual):
    """Mostra o alfabeto de substituicao da conta, em quatro colunas."""
    mapa_usuario = gerar_cifra_usuario(username_atual)

    with st.expander(
        "🔍 Ver o dicionário completo da sua Cifra Individual",
        expanded=False,
    ):
        st.write(
            "Cada caractere original à esquerda corresponde ao caractere "
            "cifrado à direita:"
        )

        colunas = st.columns(4)
        itens = list(mapa_usuario.items())
        chunk_size = len(itens) // 4 + 1

        for indice, coluna in enumerate(colunas):
            with coluna:
                trecho = itens[indice * chunk_size:(indice + 1) * chunk_size]
                for original, cifrado in trecho:
                    exibir_original = "Espaço" if original == " " else original
                    st.markdown(f"`{exibir_original}` → **`{cifrado}`**")


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

    # Fora do primeiro acesso obrigatorio, a pessoa ve o dicionario da
    # propria conta e entende como o mural cifra as mensagens.
    if modo_voluntario or st.session_state.get("primeiro_acesso") == 0:
        st.info(
            "🔐 Esta é a sua **chave de substituição pessoal e fixa** "
            "associada à sua conta. Ela é usada para cifrar e decifrar "
            "suas mensagens no mural."
        )
        _mostrar_dicionario(username_atual)
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

    mensagens = carregar_mural()

    if mensagens:
        for msg_id, autor_msg, msg, data in mensagens:
            col_msg, col_botoes = st.columns([4, 1])

            with col_msg:
                # A mensagem entra em HTML cru, entao precisa de escape. A
                # cifra nao cobre "<" nem ">": o alfabeto dela e so letras,
                # numeros e " .,!?", e o mapa devolve qualquer caractere
                # fora do alfabeto sem trocar.
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
    else:
        st.info("Nenhuma mensagem no mural ainda. Seja o primeiro a publicar!")
