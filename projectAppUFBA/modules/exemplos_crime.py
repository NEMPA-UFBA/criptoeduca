"""Le os exemplos de crimes digitais do arquivo dados/exemplos_crime.json.

Por que JSON e nao Python: quem escreve o conteudo do curso nao e
programador. O conteudo de cada golpe fica num arquivo de texto que
qualquer pessoa abre no Bloco de Notas, edita e salva. Nao ha codigo
para mexer, nenhuma funcao para chamar.

O conteudo e uma lista de BLOCOS, e nao um monte de campos com nome
fixo. Cada bloco tem um tipo e um texto:

    { "tipo": "titulo",    "texto": "Como o golpe acontece" }
    { "tipo": "subtitulo", "texto": "Sinais de alerta" }
    { "tipo": "paragrafo", "texto": "..." }
    { "tipo": "fonte",     "texto": "Banco Central, 2026" }

A lista e ordem: o que vem primeiro e o que aparece primeiro, e os
tipos podem se repetir quantas vezes forem necessarias. Isto existe
porque o material da escola vem em documento, e um documento e
secoes, subsecoes e paragrafos na ordem em que foram escritos -- o
molde de campos fixos perdia essa ordem.

A "fonte" e o credito do texto, no rodape do pergaminho: sai pequena
e esmaecida de proposito, para assinar sem competir com o texto.

Este arquivo faz a parte chata: ler o JSON, tirar os comentarios,
checar se os campos obrigatorios existem e explicar o que esta errado
-- em portugues e sem traceback. Um JSON com erro nao derruba o app:
a pagina de crimes mostra o que precisa ser corrigido e segue com os
exemplos que prestam.

Formato antigo: arquivos (e linhas de banco) gravados com "corpo",
"exemplo", "sinais" e "protecao" continuam sendo aceitos -- eles sao
convertidos em blocos aqui, na mesma ordem em que apareciam na tela,
entao nenhum conteudo ja publicado fica vazio.

O texto do arquivo pode ser lorem ipsum de proposito: ele e o molde
que a coordenacao troca pelo conteudo real. O que o app precisa e que
o molde tenha os campos certos.
"""

import json
import os
import re

# Pasta base do app. Os caminhos sao resolvidos a partir dela, e nao do
# diretorio de onde o processo foi iniciado -- o app pode ser subir de
# outro lugar.
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CAMINHO_JSON = os.path.join(BASE_DIR, "dados", "exemplos_crime.json")

# Chave: minusculas, numeros e hifen. E o que impede o app de semear o
# mesmo exemplo duas vezes, entao nao pode ter espaco nem acento.
RE_CHAVE = re.compile(r"^[a-z0-9-]+$")

# Sinais e protecao sao listas de texto no JSON. O banco guarda como
# texto corrido, uma linha por item, entao a conversao acontece aqui.
SEPARADOR_LINHAS = "\n"

# Os quatro tipos de bloco que o pergaminho aceita. A ordem da tupla e a
# ordem em que eles aparecem no formulario de montagem.
TIPOS_BLOCO = ("titulo", "subtitulo", "paragrafo", "fonte")

# Como o tipo e escrito na tela. E por isto que a validacao e feita com
# o dicionario e nao com a tupla: o rotulo que a pessoa escolhe e este,
# e o que vai para o JSON e a chave.
ROTULO_TIPO = {
    "titulo": "Título",
    "subtitulo": "Subtítulo",
    "paragrafo": "Parágrafo",
    "fonte": "Fonte",
}


def _tirar_comentarios(texto):
    """Remove as linhas de comentario (// no inicio da linha).

    JSON padrao nao aceita comentario. Como o arquivo e feito para ser
    editado por gente que nao e da area, os comentarios sao a documentacao
    do proprio arquivo -- e valem mais do que a rigidez do formato.

    So linhas inteiras sao tratadas: um "//" no fim de uma linha de texto
    seria apagado junto com o texto, e o texto de um exemplo pode conter
    barra (uma URL, por exemplo).
    """
    linhas = []
    for linha in texto.splitlines():
        if linha.lstrip().startswith("//"):
            continue
        linhas.append(linha)
    return "\n".join(linhas)


def _lista_de_textos(bruto, onde, erros, obrigatorio=True):
    """Valida uma lista de textos. Devolve a lista, ou [] se estiver ruim."""
    if bruto is None:
        if obrigatorio:
            erros.append("%s: faltou a lista." % onde)
        return []
    if not isinstance(bruto, list):
        erros.append("%s: a lista precisa ser uma lista (entre colchetes [ ])."
                     % onde)
        return []
    itens = []
    for i, item in enumerate(bruto, start=1):
        if not isinstance(item, str):
            erros.append("%s: o item %d precisa ser um texto." % (onde, i))
            continue
        texto = item.strip()
        if texto:
            itens.append(texto)
    return itens


def _carregar_blocos(bruto, onde, erros, obrigatorio=False):
    """Valida a lista de blocos de um exemplo. Devolve a lista pronta.

    Cada item precisa ser um objeto { "tipo": ..., "texto": ... }, com um
    dos tipos conhecidos e texto nao vazio. Item ruim e descartado com
    aviso, e nao derruba os outros.
    """
    if bruto is None:
        if obrigatorio:
            erros.append("%s: faltou a lista de 'blocos'." % onde)
        return []
    if not isinstance(bruto, list):
        erros.append("%s: 'blocos' precisa ser uma lista (entre colchetes "
                     "[ ])." % onde)
        return []
    if not bruto:
        if obrigatorio:
            erros.append("%s: a lista de 'blocos' esta vazia." % onde)
        return []

    blocos = []
    for i, item in enumerate(bruto, start=1):
        if not isinstance(item, dict):
            erros.append("%s: o bloco %d precisa ser um objeto entre chaves "
                         "{ }." % (onde, i))
            continue
        tipo = str(item.get("tipo") or "").strip().lower()
        if tipo not in ROTULO_TIPO:
            erros.append("%s: o bloco %d tem um tipo que nao existe (%r). "
                         "Use um destes: %s."
                         % (onde, i, tipo, ", ".join(TIPOS_BLOCO)))
            continue
        texto = str(item.get("texto") or "").strip()
        if not texto:
            erros.append("%s: o bloco %d (%s) esta sem texto."
                         % (onde, i, ROTULO_TIPO[tipo]))
            continue
        blocos.append({"tipo": tipo, "texto": texto})

    if obrigatorio and not blocos:
        erros.append("%s: nenhum bloco valido. Confira os tipos e os textos."
                     % onde)
    return blocos


def _blocos_de_campos_antigos(bruto):
    """Monta os blocos a partir dos campos do formato antigo.

    Antes do formato de blocos, cada exemplo tinha "corpo", "exemplo",
    "sinais" e "protecao". Em vez de apagar esse conteudo, ele e
    convertido, na mesma ordem em que era lido na tela: o que ja existe
    continua aparecendo, so que como blocos.

    Converte sem registrar erro de proposito: este caminho so e
    percorrido quando nao ha "blocos" no arquivo, ou seja, quando o
    arquivo ainda esta no formato antigo -- e la as listas podem ficar
    de fora sem que nada esteja errado.
    """
    blocos = []

    corpo = str(bruto.get("corpo") or "").strip()
    if corpo:
        blocos.append({"tipo": "paragrafo", "texto": corpo})

    exemplo = str(bruto.get("exemplo") or "").strip()
    if exemplo:
        blocos.append({"tipo": "subtitulo", "texto": "Exemplo de mensagem"})
        blocos.append({"tipo": "paragrafo", "texto": exemplo})

    for rotulo, campo in (("Sinais de alerta", "sinais"),
                          ("Como se proteger", "protecao")):
        itens = _lista_de_textos(bruto.get(campo), rotulo, [], obrigatorio=False)
        if itens:
            blocos.append({"tipo": "subtitulo", "texto": rotulo})
            for item in itens:
                blocos.append({"tipo": "paragrafo", "texto": item})

    return blocos


def resumo_do_bloco(blocos):
    """O primeiro paragrafo do pergaminho.

    Serve para a coluna "corpo" do banco, que e texto corrido e que as
    listas antigas (paineis, exportacoes) continuam lendo. Se nao houver
    paragrafo, usa o texto do primeiro bloco que tiver.
    """
    for bloco in blocos:
        if bloco.get("tipo") == "paragrafo" and bloco.get("texto"):
            return bloco["texto"]
    for bloco in blocos:
        if bloco.get("texto"):
            return bloco["texto"]
    return ""


def _carregar_exemplo(bruto, posicao, erros):
    """Valida um exemplo. Devolve o exemplo pronto, ou None se estiver ruim.

    Um exemplo quebrado nao derruba os outros: ele e descartado e o
    problema aparece na tela.
    """
    onde = "Exemplo %d" % posicao

    if not isinstance(bruto, dict):
        erros.append("%s: cada exemplo precisa ser um objeto entre chaves "
                     "{ }." % onde)
        return None

    chave = (bruto.get("chave") or "").strip().lower()
    if not chave:
        erros.append("%s: faltou a 'chave' (o identificador do exemplo)." % onde)
        return None
    if not RE_CHAVE.match(chave):
        erros.append("%s ('%s'): a chave só pode ter letra minúscula, número "
                     "e hífen (ex.: golpe-pix-falso)." % (onde, chave))
        return None

    titulo = (bruto.get("titulo") or "").strip()
    if not titulo:
        erros.append("%s ('%s'): faltou o 'titulo'." % (onde, chave))
        return None

    # O conteudo: blocos do formato novo, ou os campos antigos convertidos
    # quando o arquivo ainda esta no formato antigo.
    blocos = _carregar_blocos(
        bruto.get("blocos"),
        "%s ('%s'): 'blocos'" % (onde, chave),
        erros,
    )
    if not blocos:
        blocos = _blocos_de_campos_antigos(bruto)

    return {
        "chave": chave,
        "titulo": titulo,
        "icone": (bruto.get("icone") or "📜").strip(),
        "categoria": (bruto.get("categoria") or "").strip(),
        "blocos": blocos,
        # Campos do formato antigo. Continuam saindo daqui porque o banco
        # ainda tem essas colunas e porque um arquivo velho pode trazê-los.
        # "corpo" e o resumo derivado dos blocos, e nao o que veio do
        # arquivo: as duas coisas nao precisam ser a mesma.
        "corpo": resumo_do_bloco(blocos),
        "exemplo": (bruto.get("exemplo") or "").strip(),
        "sinais": _lista_de_textos(bruto.get("sinais"),
                                   "%s ('%s'): 'sinais'" % (onde, chave),
                                   erros, obrigatorio=False),
        "protecao": _lista_de_textos(bruto.get("protecao"),
                                     "%s ('%s'): 'protecao'" % (onde, chave),
                                     erros, obrigatorio=False),
    }


def carregar_exemplos():
    """Devolve (exemplos, erros).

    exemplos e a lista dos exemplos que puderam ser lidos; erros e a lista
    de problemas encontrados no arquivo, em portugues. Os dois vao juntos:
    a tela mostra os exemplos que valem e o que precisa ser corrigido.
    """
    erros = []

    if not os.path.isfile(CAMINHO_JSON):
        return [], [
            "Não achei o arquivo de exemplos em '%s'. Ele deve existir, com os "
            "exemplos de crimes dentro." % os.path.join("dados",
                                                        "exemplos_crime.json")
        ]

    # Leitura do arquivo em UTF-8. utf-8-sig e nao utf-8 porque o Bloco de
    # Notas do Windows salva com BOM (tres bytes no comeco), e o json.loads
    # recusaria o arquivo inteiro com "Unexpected UTF-8 BOM".
    texto = None
    for codificacao in ("utf-8-sig", "cp1252"):
        try:
            with open(CAMINHO_JSON, "r", encoding=codificacao) as arquivo:
                texto = arquivo.read()
            break
        except UnicodeDecodeError:
            continue
        except OSError as erro:
            return [], ["Não consegui abrir o arquivo de exemplos: %s" % erro]

    if texto is None:
        return [], [
            "O arquivo dados/exemplos_crime.json está em uma codificação que "
            "o app não entende. Salve o arquivo como UTF-8 (no Bloco de "
            "Notas: Arquivo > Salvar como > Codificação: UTF-8)."
        ]

    try:
        dados = json.loads(_tirar_comentarios(texto))
    except json.JSONDecodeError as erro:
        return [], [
            "O arquivo dados/exemplos_crime.json tem um erro de escrita: %s "
            "(linha %s, coluna %s). Confira as vírgulas e as aspas."
            % (erro.msg, erro.lineno, erro.colno)
        ]

    if not isinstance(dados, dict):
        return [], ["O arquivo dados/exemplos_crime.json deve começar com { e "
                    "ter a lista \"exemplos\" dentro."]

    lista = dados.get("exemplos")
    if lista is None:
        return [], ["Faltou a lista \"exemplos\" no arquivo "
                    "dados/exemplos_crime.json."]
    if not isinstance(lista, list):
        return [], ["A lista \"exemplos\" do arquivo dados/exemplos_crime.json "
                    "precisa ser uma lista (entre colchetes [ ])."]

    exemplos = []
    chaves_vistas = set()
    for posicao, bruto in enumerate(lista, start=1):
        exemplo = _carregar_exemplo(bruto, posicao, erros)
        if exemplo is None:
            continue
        if exemplo["chave"] in chaves_vistas:
            erros.append("Dois exemplos têm a mesma chave ('%s'). Cada chave "
                         "precisa ser única." % exemplo["chave"])
            continue
        chaves_vistas.add(exemplo["chave"])
        exemplos.append(exemplo)

    return exemplos, erros


def linhas_para_texto(lista):
    """Junta uma lista de linhas num texto, uma por linha.

    E o inverso de _lista_de_textos, e e o que o banco guarda: os sinais
    de alerta e a protecao sao varias linhas, mas nao ha lista no
    SQLite -- o que existe e um texto com quebras de linha.
    """
    return SEPARADOR_LINHAS.join(lista)


def texto_para_linhas(texto):
    """Quebra um texto do banco em lista de linhas, sem as vazias."""
    if not texto:
        return []
    linhas = []
    for linha in texto.split(SEPARADOR_LINHAS):
        limpa = linha.strip()
        if limpa:
            linhas.append(limpa)
    return linhas
