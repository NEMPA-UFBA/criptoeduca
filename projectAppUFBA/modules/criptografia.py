"""Criptografia do mural: AES-128-GCM com chave derivada da frase do usuario.

O que fica gravado no banco e so o envelope abaixo, nunca a chave:

    aes-gcm-v1$<iteracoes>$<salt_b64>$<nonce_b64>$<ciphertext+tag_b64>

- O salt (16 bytes) e o nonce (12 bytes) sao sorteados a cada mensagem.
- A chave AES de 16 bytes vem do PBKDF2-HMAC-SHA256 da frase digitada.
- O GCM autentica o texto: chave errada ou ciphertext alterado levantam
  InvalidTag em vez de devolver lixo.

O prefixo e o numero de iteracoes ficam dentro do proprio envelope para que
mensagens antigas continuem decifraveis se os parametros mudarem no futuro.
"""

import base64
import os

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

PREFIXO = "aes-gcm-v1"
ITERACOES_PADRAO = 600_000
TAM_SALT = 16
TAM_NONCE = 12
TAM_CHAVE = 16  # 16 bytes = AES-128

# Limite de sanidade para o numero de iteracoes lido do envelope. Sem isso,
# um envelope forjado no banco poderia pedir bilhoes de iteracoes e travar a
# pagina. O valor gravado pelo app e sempre ITERACOES_PADRAO.
ITERACOES_MIN = 100_000
ITERACOES_MAX = 2_000_000


def _b64_codificar(dados):
    return base64.urlsafe_b64encode(dados).decode("ascii")


def _b64_decodificar(texto):
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
    """Cifra a mensagem e devolve o envelope pronto para o banco."""
    salt = os.urandom(TAM_SALT)
    nonce = os.urandom(TAM_NONCE)
    chave_bytes = derivar_chave(chave, salt, iteracoes)
    ciphertext = AESGCM(chave_bytes).encrypt(nonce, mensagem.encode("utf-8"), None)
    return "$".join(
        (
            PREFIXO,
            str(iteracoes),
            _b64_codificar(salt),
            _b64_codificar(nonce),
            _b64_codificar(ciphertext),
        )
    )


def decifrar(payload, chave):
    """Abre o envelope e devolve o texto original.

    Levanta ValueError se o envelope nao for deste formato e InvalidTag se a
    chave estiver errada ou o ciphertext tiver sido alterado.
    """
    partes = payload.split("$", 4)
    if len(partes) != 5 or partes[0] != PREFIXO:
        raise ValueError("Formato de mensagem desconhecido.")

    try:
        iteracoes = int(partes[1])
    except ValueError as erro:
        raise ValueError("Envelope com numero de iteracoes invalido.") from erro

    if not (ITERACOES_MIN <= iteracoes <= ITERACOES_MAX):
        raise ValueError("Envelope com numero de iteracoes fora do limite.")

    salt = _b64_decodificar(partes[2])
    nonce = _b64_decodificar(partes[3])
    ciphertext = _b64_decodificar(partes[4])

    chave_bytes = derivar_chave(chave, salt, iteracoes)
    texto = AESGCM(chave_bytes).decrypt(nonce, ciphertext, None)
    return texto.decode("utf-8")


def ciphertext_visivel(payload):
    """Devolve so o ciphertext+tag, sem versao/iteracoes/salt/nonce.

    E o que o mural mostra na tela. O envelope completo continua no banco,
    porque e ele que o decifrar precisa. Se o payload nao estiver no formato
    esperado (mensagem antiga, por exemplo), devolve o texto como veio.
    """
    partes = payload.split("$", 4)
    if len(partes) != 5 or partes[0] != PREFIXO:
        return payload
    return partes[4]
