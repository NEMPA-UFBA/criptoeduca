"""Criptografia de alto nivel do laboratorio: AES-128-GCM com chave derivada
da frase do usuario.

O texto cifrado e um unico bloco base64url. Dentro dele vao, nesta ordem:

    iteracoes (4 bytes) + salt (16 bytes) + nonce (12 bytes) + ciphertext+tag

- O salt (16 bytes) e o nonce (12 bytes) sao sorteados a cada mensagem.
- A chave AES de 16 bytes vem do PBKDF2-HMAC-SHA256 da frase digitada.
- O GCM autentica o texto: chave errada ou ciphertext alterado levantam
  InvalidTag em vez de devolver lixo.

O numero de iteracoes fica dentro do proprio bloco para que mensagens antigas
continuem decifraveis se os parametros mudarem no futuro. Formatos antigos com
campos separados por "$" continuam sendo aceitos na decifracao.
"""

import base64
import os
import struct

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

PREFIXO_LEGADO = "aes-gcm-v1"
ITERACOES_PADRAO = 600_000
TAM_SALT = 16
TAM_NONCE = 12
TAM_CHAVE = 16  # 16 bytes = AES-128
TAM_CABECALHO = 4 + TAM_SALT + TAM_NONCE
TAM_MINIMO = TAM_CABECALHO + 16  # ciphertext + tag do GCM

# Limite de sanidade para o numero de iteracoes lido do texto cifrado. Sem
# isso, um bloco forjado poderia pedir bilhoes de iteracoes e travar a pagina.
# O valor gravado pelo app e sempre ITERACOES_PADRAO.
ITERACOES_MIN = 100_000
ITERACOES_MAX = 2_000_000


def _b64_codificar(dados):
    return base64.urlsafe_b64encode(dados).decode("ascii")


def _b64_decodificar(texto):
    # Tolerar espacos e quebras de linha de quem copiou o bloco.
    texto = "".join(texto.split())
    texto += "=" * (-len(texto) % 4)
    return base64.urlsafe_b64decode(texto.encode("ascii"))


def derivar_chave(chave, salt, iteracoes=ITERACOES_PADRAO):
    """Transforma a frase digitada na chave de 16 bytes que o AES usa.

    AES exige uma chave de tamanho fixo; a frase do usuario nao tem. O
    PBKDF2 resolve isso e ainda encarece a tentativa de adivinhar a frase a
    partir do ciphertext. O strip e aplicado dos dois lados (cifrar e
    decifrar), entao espaco nas pontas nao vira "chave errada".
    """
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=TAM_CHAVE,
        salt=salt,
        iterations=iteracoes,
    )
    return kdf.derive(chave.strip().encode("utf-8"))


def cifrar(mensagem, chave, iteracoes=ITERACOES_PADRAO):
    """Cifra a mensagem e devolve um unico bloco pronto para a tela."""
    salt = os.urandom(TAM_SALT)
    nonce = os.urandom(TAM_NONCE)
    chave_bytes = derivar_chave(chave, salt, iteracoes)
    ciphertext = AESGCM(chave_bytes).encrypt(nonce, mensagem.encode("utf-8"), None)
    bloco = struct.pack(">I", iteracoes) + salt + nonce + ciphertext
    return _b64_codificar(bloco)


def _decifrar_legado(payload):
    """Le o formato antigo com campos separados por "$"."""
    partes = payload.split("$")
    if len(partes) == 5 and partes[0] == PREFIXO_LEGADO:
        partes = partes[1:]
    if len(partes) != 4:
        raise ValueError("Formato de mensagem desconhecido.")

    try:
        iteracoes = int(partes[0])
        salt = _b64_decodificar(partes[1])
        nonce = _b64_decodificar(partes[2])
        ciphertext = _b64_decodificar(partes[3])
    except Exception as erro:
        raise ValueError("Texto cifrado em formato antigo invalido.") from erro

    return iteracoes, salt, nonce, ciphertext


def _separar_bloco(payload):
    """Separa iteracoes, salt, nonce e ciphertext do bloco unico."""
    try:
        dados = _b64_decodificar(payload)
    except Exception as erro:
        raise ValueError("Formato de mensagem desconhecido.") from erro

    if len(dados) < TAM_MINIMO:
        raise ValueError("Texto cifrado incompleto.")

    iteracoes = struct.unpack(">I", dados[:4])[0]
    salt = dados[4:4 + TAM_SALT]
    nonce = dados[4 + TAM_SALT:TAM_CABECALHO]
    ciphertext = dados[TAM_CABECALHO:]
    return iteracoes, salt, nonce, ciphertext


def decifrar(payload, chave):
    """Abre o texto cifrado e devolve o texto original.

    Levanta ValueError se o texto nao estiver em um formato conhecido e
    InvalidTag se a chave estiver errada ou o ciphertext tiver sido alterado.
    """
    payload = payload.strip()
    if "$" in payload:
        iteracoes, salt, nonce, ciphertext = _decifrar_legado(payload)
    else:
        iteracoes, salt, nonce, ciphertext = _separar_bloco(payload)

    if not (ITERACOES_MIN <= iteracoes <= ITERACOES_MAX):
        raise ValueError("Texto cifrado com numero de iteracoes fora do limite.")

    chave_bytes = derivar_chave(chave, salt, iteracoes)
    texto = AESGCM(chave_bytes).decrypt(nonce, ciphertext, None)
    return texto.decode("utf-8")
