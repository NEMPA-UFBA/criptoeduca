"""Carrega os modulos de aprendizagem do arquivo dados/modulos.json.

Por que JSON e nao Python: quem escreve o conteudo do curso nao e
programador. O manifesto dos modulos (titulo, resumo, nivel, quiz) fica em
um arquivo de texto que qualquer pessoa abre no Bloco de Notas, edita e
salva. Nao ha codigo para mexer, nenhuma funcao para chamar, nenhuma
indentacao para acertar.

Este arquivo faz a parte chata: ler o JSON, tirar os comentarios, checar se
os campos obrigatorios existem e explicar o que esta errado -- em portugues
e sem traceback. Um JSON com erro nao derruba o app: a pagina de modulos
mostra o que precisa ser corrigido e segue com os modulos que prestam.

O quiz fica neste arquivo, e nao em static/, por um motivo: static/ e
servido publicamente pelo Streamlit. Se as respostas certas ficassem la,
qualquer aluno abriria a URL e leria as respostas antes de responder.
"""

import json
import os
import re

# Pasta base do app. Os caminhos sao resolvidos a partir dela, e nao do
# diretorio de onde o processo foi iniciado -- o app pode ser subir de
# outro lugar.
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CAMINHO_JSON = os.path.join(BASE_DIR, "dados", "modulos.json")
PASTA_PDFS = os.path.join(BASE_DIR, "static", "modulos")

# Slug: minusculas, numeros e hifen. E o que vira nome de arquivo do PDF
# e chave de botao, entao nao pode ter espaco, acento nem barra.
RE_SLUG = re.compile(r"^[a-z0-9-]+$")


def _tirar_comentarios(texto):
    """Remove as linhas de comentario (// no inicio da linha).

    JSON padrao nao aceita comentario. Como o arquivo e feito para ser
    editado por gente que nao e da area, os comentarios sao a documentacao
    do proprio arquivo -- e valem mais do que a rigidez do formato.

    So linhas inteiras sao tratadas: um "//" no fim de uma linha de texto
    seria apagado junto com o texto, e o titulo de um modulo pode conter
    barra (uma URL, por exemplo).
    """
    linhas = []
    for linha in texto.splitlines():
        if linha.lstrip().startswith("//"):
            continue
        linhas.append(linha)
    return "\n".join(linhas)


def _carregar_questao(questao, onde, erros):
    """Valida uma pergunta do quiz. Devolve a pergunta pronta ou None."""
    if not isinstance(questao, dict):
        erros.append("%s: a pergunta precisa ser um objeto com 'enunciado', "
                     "'alternativas' e 'certa'." % onde)
        return None

    enunciado = (questao.get("enunciado") or "").strip()
    if not enunciado:
        erros.append("%s: faltou o 'enunciado' da pergunta." % onde)
        return None

    alternativas = questao.get("alternativas")
    if not isinstance(alternativas, list) or len(alternativas) < 2:
        erros.append("%s: a pergunta '%s' precisa de pelo menos duas "
                     "alternativas." % (onde, enunciado))
        return None

    # A resposta certa pode ser o NUMERO da alternativa (contando a partir
    # de 1) ou o TEXTO exato dela. O numero e mais facil de acertar sem
    # copiar letra por letra; o texto serve para quem prefere.
    certa = questao.get("certa")
    indice = None
    if isinstance(certa, bool):
        erros.append("%s: o campo 'certa' da pergunta '%s' deve ser o número "
                     "da alternativa (1, 2, 3...) ou o texto dela."
                     % (onde, enunciado))
        return None
    if isinstance(certa, int):
        if 1 <= certa <= len(alternativas):
            indice = certa - 1
        else:
            erros.append("%s: a resposta correta da pergunta '%s' está no "
                         "número %s, mas a pergunta só tem %d alternativas "
                         "(de 1 a %d)."
                         % (onde, enunciado, certa, len(alternativas),
                            len(alternativas)))
            return None
    elif isinstance(certa, str):
        tentativa = certa.strip()
        if tentativa in [str(a).strip() for a in alternativas]:
            indice = [str(a).strip() for a in alternativas].index(tentativa)
        else:
            erros.append("%s: a resposta correta da pergunta '%s' ('%s') não "
                         "é nenhuma das alternativas." % (onde, enunciado,
                                                          tentativa))
            return None
    else:
        erros.append("%s: faltou o campo 'certa' da pergunta '%s'."
                     % (onde, enunciado))
        return None

    return {
        "enunciado": enunciado,
        "alternativas": [str(a) for a in alternativas],
        "certa": indice,
    }


def _carregar_modulo(bruto, posicao, erros):
    """Valida um modulo. Devolve o modulo pronto, ou None se estiver ruim.

    Um modulo quebrado nao derruba os outros: ele e descartado e o
    problema aparece na tela.
    """
    onde = "Módulo %d" % posicao

    if not isinstance(bruto, dict):
        erros.append("%s: cada módulo precisa ser um objeto entre chaves "
                     "{ }." % onde)
        return None

    slug = (bruto.get("slug") or "").strip().lower()
    if not slug:
        erros.append("%s: faltou o 'slug' (o nome curto do módulo)." % onde)
        return None
    if not RE_SLUG.match(slug):
        erros.append("%s: o slug '%s' só pode ter letra minúscula, número "
                     "e hífen (ex.: senhas-e-autenticacao)." % (onde, slug))
        return None

    titulo = (bruto.get("titulo") or "").strip()
    if not titulo:
        erros.append("%s ('%s'): faltou o 'titulo'." % (onde, slug))
        return None

    resumo = (bruto.get("resumo") or "").strip()

    # O PDF e opcional: enquanto o material nao estiver pronto, a pagina
    # avisa em vez de quebrar. O campo pode ser so o nome do arquivo
    # ("aula.pdf") ou um caminho com pasta ("static/modulos/aula.pdf").
    pdf = (bruto.get("pdf") or "").strip()
    if pdf:
        pdf = pdf.replace("\\", "/")
        if "/" in pdf:
            pdf = pdf.rsplit("/", 1)[-1]

    quiz = []
    bruto_quiz = bruto.get("quiz")
    if bruto_quiz is not None:
        if not isinstance(bruto_quiz, list):
            erros.append("%s ('%s'): o 'quiz' precisa ser uma lista de "
                         "perguntas." % (onde, slug))
        else:
            for i, questao in enumerate(bruto_quiz, start=1):
                carregar = _carregar_questao(
                    questao, "%s ('%s'), pergunta %d" % (onde, slug, i), erros
                )
                if carregar:
                    quiz.append(carregar)

    return {
        "slug": slug,
        "titulo": titulo,
        "resumo": resumo,
        "icone": (bruto.get("icone") or "📘").strip(),
        "nivel": (bruto.get("nivel") or "").strip(),
        "dificuldade": (bruto.get("dificuldade") or "").strip(),
        "duracao": (bruto.get("duracao") or "").strip(),
        "cor": (bruto.get("cor") or "#4F46E5").strip(),
        "pdf": pdf,
        "quiz": quiz,
    }


def carregar_modulos():
    """Devolve (modulos, erros).

    modulos e a lista dos modulos que puderam ser lidos; erros e a lista de
    problemas encontrados no arquivo, em portugues. Os dois vao juntos: a
    tela mostra os modulos que valem e o que precisa ser corrigido.
    """
    erros = []

    if not os.path.isfile(CAMINHO_JSON):
        return [], [
            "Não achei o arquivo de módulos em '%s'. Ele deve existir, com os "
            "módulos dentro." % os.path.join("dados", "modulos.json")
        ]

    # Leitura do arquivo em UTF-8. utf-8-sig e nao utf-8 porque o Bloco de
    # Notas do Windows salva com BOM (tres bytes no comeco), e o json.loads
    # recusaria o arquivo inteiro com "Unexpected UTF-8 BOM".
    #
    # Se o arquivo estiver em outra codificacao (o Bloco de Notas antigo
    # salva em ANSI/Windows-1252), a leitura em UTF-8 quebra. Nesses
    # casos a leitura em Windows-1252 e tentada, e a pagina avisa que o
    # ideal e salvar como UTF-8 -- porque da proxima vez o texto pode
    # sair diferente.
    texto = None
    codificacao_usada = None
    for codificacao in ("utf-8-sig", "cp1252"):
        try:
            with open(CAMINHO_JSON, "r", encoding=codificacao) as arquivo:
                texto = arquivo.read()
            codificacao_usada = codificacao
            break
        except UnicodeDecodeError:
            continue
        except OSError as erro:
            return [], ["Não consegui abrir o arquivo de módulos: %s" % erro]

    if texto is None:
        return [], [
            "O arquivo dados/modulos.json está em uma codificação que o app "
            "não entende. Salve o arquivo como UTF-8 (no Bloco de Notas: "
            "Arquivo > Salvar como > Codificação: UTF-8)."
        ]

    if codificacao_usada == "cp1252":
        # Leu, mas na codificacao antiga do Windows. Funciona, porem o
        # texto pode sair diferente da proxima vez. Vale avisar.
        erros.append(
            "O arquivo dados/modulos.json está salvo em Windows-1252 (ANSI) "
            "e foi lido assim. Funciona, mas o ideal é salvar como UTF-8 "
            "(Bloco de Notas: Arquivo > Salvar como > Codificação: UTF-8) "
            "para os acentos saírem sempre iguais."
        )

    try:
        dados = json.loads(_tirar_comentarios(texto))
    except json.JSONDecodeError as erro:
        return [], [
            "O arquivo dados/modulos.json tem um erro de escrita: %s "
            "(linha %s, coluna %s). Confira as vírgulas e as aspas."
            % (erro.msg, erro.lineno, erro.colno)
        ]

    if not isinstance(dados, dict):
        return [], ["O arquivo dados/modulos.json deve começar com { e ter "
                    "a lista \"modulos\" dentro."]

    lista = dados.get("modulos")
    if lista is None:
        return [], ["Faltou a lista \"modulos\" no arquivo dados/modulos.json."]
    if not isinstance(lista, list):
        return [], ["A lista \"modulos\" do arquivo dados/modulos.json "
                    "precisa ser uma lista (entre colchetes [ ])."]

    modulos = []
    slugs_vistos = set()
    for posicao, bruto in enumerate(lista, start=1):
        modulo = _carregar_modulo(bruto, posicao, erros)
        if modulo is None:
            continue
        if modulo["slug"] in slugs_vistos:
            erros.append("Dois módulos têm o mesmo slug ('%s'). Cada slug "
                         "precisa ser único." % modulo["slug"])
            continue
        slugs_vistos.add(modulo["slug"])
        modulos.append(modulo)

    return modulos, erros


def modulo_por_slug(slug, modulos=None):
    """Devolve o módulo com aquele slug, ou None se não existir.

    None e não uma exceção: a página do módulo é chamada com o slug que
    veio da sessão, e um valor corrompido na sessão não pode derrubar o
    app inteiro.
    """
    if modulos is None:
        modulos, _ = carregar_modulos()
    for modulo in modulos:
        if modulo["slug"] == slug:
            return modulo
    return None


def caminho_pdf(modulo):
    """Caminho absoluto do PDF do módulo, ou None se não houver PDF."""
    if not modulo or not modulo.get("pdf"):
        return None
    return os.path.join(PASTA_PDFS, modulo["pdf"])


def pdf_disponivel(modulo):
    """Diz se o arquivo de PDF do módulo existe de fato na pasta."""
    caminho = caminho_pdf(modulo)
    return bool(caminho) and os.path.isfile(caminho)
