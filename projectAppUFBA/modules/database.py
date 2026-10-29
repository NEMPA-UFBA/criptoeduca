import json
import sqlite3
import bcrypt
import streamlit as st

def conectar():
    return sqlite3.connect("plataforma.db")


def _senha_admin_inicial():
    """Le a senha do Administrador de st.secrets. Sem valor padrao no codigo.

    Esta funcao so e chamada quando o banco ainda nao tem o usuario admin, ou
    seja, uma unica vez, no primeiro boot. A senha nao e lida em nenhum outro
    momento: depois disso o que fica no banco e o hash bcrypt, e e ele que
    autentica todo mundo.

    Levanta erro em vez de devolver um valor padrao. Um default aqui
    significaria um admin com senha conhecida no codigo-fonte, que e
    exatamente o que a migracao para st.secrets veio remover.
    """
    try:
        return st.secrets["ADMIN_SENHA"]
    except Exception as erro:
        raise RuntimeError(
            "Falta ADMIN_SENHA no gerenciador de segredos. O banco ainda nao tem "
            "o usuario 'admin', entao a senha inicial e obrigatoria. Crie "
            ".streamlit/secrets.toml com ADMIN_SENHA = \"...\" (esse caminho ja "
            "esta no .gitignore) e rode de novo. Detalhe: %s" % erro
        ) from erro


def criar_tabelas():
    conn = conectar()
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            username TEXT PRIMARY KEY,
            nome TEXT NOT NULL,
            email TEXT NOT NULL,
            tipo TEXT NOT NULL,
            password TEXT NOT NULL,
            primeiro_acesso INTEGER DEFAULT 1
        )
    ''')

    # 2. Inspeciona as colunas existentes na tabela
    c.execute("PRAGMA table_info(usuarios)")
    colunas_existentes = [coluna[1] for coluna in c.fetchall()]

    # 3. Adiciona as colunas faltantes sem apagar dados
    if "primeiro_acesso" not in colunas_existentes:
        c.execute("ALTER TABLE usuarios ADD COLUMN primeiro_acesso INTEGER DEFAULT 1")

    if "email" not in colunas_existentes:
        c.execute("ALTER TABLE usuarios ADD COLUMN email TEXT DEFAULT ''")

    if "tipo" not in colunas_existentes:
        c.execute("ALTER TABLE usuarios ADD COLUMN tipo TEXT DEFAULT 'Aluno'")
        
    # --- E-MAIL ÚNICO ---
    # Índice único em vez de UNIQUE na definição da tabela: o SQLite não tem
    # ALTER TABLE ... ADD CONSTRAINT, mas CREATE UNIQUE INDEX aplica a mesma
    # restrição sobre a tabela que já existe, sem recriá-la nem tocar nos dados.
    # O CREATE TABLE IF NOT EXISTS acima é inerte para banco já criado, então
    # esta é a única forma de a restrição valer para quem já tem o banco.
    # É defesa em profundidade: o formulário já checa duplicidade antes de
    # inserir. Se algum dado antigo impedir o índice, o app segue funcionando
    # pela checagem do formulário, em vez de quebrar na inicialização.
    try:
        c.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_usuarios_email ON usuarios (email)")
    except sqlite3.IntegrityError:
        pass

    # Tabela para o Mural Criptografado
    c.execute("""
        CREATE TABLE IF NOT EXISTS mural (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ativo INTEGER DEFAULT 1,
            username TEXT,
            mensagem_criptografada TEXT,
            data TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    c.execute("PRAGMA table_info(mural)")
    colunas_mural = [coluna[1] for coluna in c.fetchall()]
    if "username" not in colunas_mural:
        c.execute("ALTER TABLE mural ADD COLUMN username TEXT DEFAULT ''")
    if "ativo" not in colunas_mural:
        c.execute("ALTER TABLE mural ADD COLUMN ativo INTEGER DEFAULT 1")

    # Tabela dos Conteudos da Coordenacao.
    # E o caminho pelo qual o Administrador (e o Professor) publicam material
    # para os alunos. Segue o mesmo padrao do mural: nada e apagado, a linha
    # so muda ativo para 0, entao o historico do que foi publicado fica.
    c.execute("""
        CREATE TABLE IF NOT EXISTS conteudos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titulo TEXT NOT NULL,
            corpo TEXT NOT NULL,
            autor TEXT,
            ativo INTEGER DEFAULT 1,
            data TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    c.execute("PRAGMA table_info(conteudos)")
    colunas_conteudos = [coluna[1] for coluna in c.fetchall()]
    if "autor" not in colunas_conteudos:
        c.execute("ALTER TABLE conteudos ADD COLUMN autor TEXT DEFAULT ''")
    if "ativo" not in colunas_conteudos:
        c.execute("ALTER TABLE conteudos ADD COLUMN ativo INTEGER DEFAULT 1")

    # Colunas do exemplo de crime, que e o que o conteudo virou.
    #
    # A tabela "conteudos" era uma lista de avisos da coordenacao. Agora cada
    # linha dela e um PERGAMINHO: um exemplo de golpe, com a mensagem falsa
    # que a pessoa receberia, os sinais de alerta e o que fazer. Por isso as
    # colunas novas sao da tabela, e nao uma tabela nova: o que a coordenacao
    # publica e o que o aluno ve, sem conversao e sem passo extra.
    #
    # "chave" e o identificador fixo do exemplo pre-colocado. E ela que
    # impede a semeadura de criar o mesmo exemplo de novo a cada boot.
    # "sinais" e "protecao" sao varias linhas, mas o SQLite nao tem lista:
    # o que existe e um texto com quebras de linha.
    colunas_crime = (
        ("chave", "TEXT DEFAULT ''"),
        ("icone", "TEXT DEFAULT '📜'"),
        ("categoria", "TEXT DEFAULT ''"),
        ("exemplo", "TEXT DEFAULT ''"),
        ("sinais", "TEXT DEFAULT ''"),
        ("protecao", "TEXT DEFAULT ''"),
        ("origem", "TEXT DEFAULT 'publicado'"),
        # O conteudo em blocos: uma lista de {tipo, texto} serializada.
        # SQLite nao tem tipo lista, entao o que existe e o proprio JSON
        # dentro de uma coluna de texto. As colunas antigas (exemplo,
        # sinais, protecao) ficaram aqui porque SQLite nao tem DROP
        # COLUMN sem recriar a tabela -- elas continuam sendo lidas para
        # conteudo publicado antes desta mudanca.
        ("blocos", "TEXT DEFAULT '[]'"),
    )
    for nome_coluna, definicao in colunas_crime:
        if nome_coluna not in colunas_conteudos:
            c.execute("ALTER TABLE conteudos ADD COLUMN %s %s"
                      % (nome_coluna, definicao))

    # Tabela do progresso de cada modulo de aprendizagem.
    #
    # Uma linha por tentativa de quiz. Nao apaga a anterior: o historico fica
    # para a equipe ver a evolucao, e o que a tela mostra e a melhor nota de
    # cada modulo. Este registro e autoavaliacao do aluno -- nao e nota nem
    # avaliacao formal de professor.
    c.execute("""
        CREATE TABLE IF NOT EXISTS progresso_modulos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            modulo TEXT NOT NULL,
            acertos INTEGER NOT NULL,
            total INTEGER NOT NULL,
            data TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    c.execute("PRAGMA table_info(progresso_modulos)")
    colunas_progresso = [coluna[1] for coluna in c.fetchall()]
    if "modulo" not in colunas_progresso:
        c.execute("ALTER TABLE progresso_modulos ADD COLUMN modulo TEXT DEFAULT ''")
    if "username" not in colunas_progresso:
        c.execute("ALTER TABLE progresso_modulos ADD COLUMN username TEXT DEFAULT ''")

    # --- ADMIN PADRÃO, SÓ SE O BANCO AINDA NÃO TIVER UM ---
    # A senha não está no código: vem de st.secrets, e só é lida neste ramo.
    # Como o banco do repositório já tem o admin, esta linha não executa, e a
    # ausência do secrets.toml não quebra o app em uso normal.
    c.execute("SELECT username FROM usuarios WHERE username = 'admin'")
    if not c.fetchone():
        senha_bytes = _senha_admin_inicial().encode('utf-8')
        salt = bcrypt.gensalt()
        hash_str = bcrypt.hashpw(senha_bytes, salt).decode('utf-8')

        c.execute(
            "INSERT INTO usuarios (username, nome, email, tipo, password) VALUES (?, ?, ?, ?, ?)",
            ("admin", "Coordenador Geral", "admin@escola.com", "Administrador", hash_str)
        )

    # --- LEITURAS CONCLUIDAS ---
    #
    # Uma linha por (aluno, modulo) que o aluno terminou de ler.
    #
    # E o que libera o quiz. A leitura e registrada AQUI, e nao so na
    # sessao, por um motivo que ja apareceu na pratica: se o registro
    # fosse so na sessao, o aluno que fechar o navegador perderia a
    # liberacao e teria que ler de novo. No banco, ela sobrevive.
    c.execute("""
        CREATE TABLE IF NOT EXISTS leituras (
            username TEXT NOT NULL,
            modulo TEXT NOT NULL,
            data TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (username, modulo)
        )
    """)

    # --- EXEMPLOS DE CRIMES PRÉ-COLOCADOS ---
    #
    # Vem do arquivo dados/exemplos_crime.json, que o professor edita
    # sem tocar em código. A semeadura é idempotente pela "chave": um
    # exemplo cuja chave já está na tabela não é criado de novo. É o
    # mesmo esquema do admin acima -- o que já existe não é reescrito.
    #
    # O que o professor edita depois pela página "Gerenciar Aulas" vale
    # mais do que o que está no arquivo: por isso a semeadura não
    # sobrescreve uma linha que já existe.
    _semear_exemplos_crime(c)

    conn.commit()
    conn.close()


def blocos_para_texto(blocos):
    """Serializa a lista de blocos para a coluna de texto do banco.

    ensure_ascii=False de proposito: sem ele o acento vira \u00e1 dentro
    da coluna, e um banco aberto no DB Browser fica ilegivel para quem
    for conferir o conteudo depois.
    """
    if not isinstance(blocos, list):
        blocos = []
    limpos = []
    for bloco in blocos:
        if not isinstance(bloco, dict):
            continue
        tipo = str(bloco.get("tipo") or "").strip().lower()
        texto = str(bloco.get("texto") or "").strip()
        if not tipo or not texto:
            continue
        limpos.append({"tipo": tipo, "texto": texto})
    return json.dumps(limpos, ensure_ascii=False)


def blocos_do_texto(texto):
    """Le a coluna "blocos" de volta como lista.

    Devolve [] em vez de levantar erro quando a coluna esta vazia ou
    corrompida: quem chama (a pagina de pergaminhos) so quer desenhar o
    que ha, e um valor estranho no banco nao pode derrubar a tela.
    """
    if not texto:
        return []
    try:
        dados = json.loads(texto)
    except (ValueError, TypeError):
        return []
    if not isinstance(dados, list):
        return []
    return [bloco for bloco in dados if isinstance(bloco, dict)]


def _semear_exemplos_crime(c):
    """Grava no banco os exemplos do arquivo dados/exemplos_crime.json.

    Recebe o cursor ja aberto, porque quem chama e o criar_tabelas, que
    abre e fecha a conexao uma vez so.

    E uma RESEMEADURA, e nao uma insercao cega: quando a "chave" ja
    existe, os campos sao reescritos com o do arquivo. O motivo e que a
    mudanca de formato (de campos fixos para blocos) deixaria as linhas
    antigas sem nada na tela, e o arquivo e a fonte da verdade do que
    e pre-colocado.

    O que NAO e tocado pelo UPDATE:

      - "ativo": se a coordenacao inativou um exemplo, ele continua
        inativado na proxima carga;
      - "autor" e "data": continuam dizendo quem publicou e quando;
      - qualquer linha de origem "publicado": essas nao estao no
        arquivo, entao nao passam por aqui.
    """
    # O import e aqui dentro, e nao no topo do arquivo: o modulo dos
    # exemplos nao precisa do banco, e o banco nao precisa do modulo de
    # leitura para nada alem disto. Importar aqui evita qualquer
    # dependencia circular entre os dois.
    from modules.exemplos_crime import (
        carregar_exemplos,
        linhas_para_texto,
    )

    exemplos, _erros = carregar_exemplos()
    for exemplo in exemplos:
        texto_blocos = blocos_para_texto(exemplo.get("blocos"))
        texto_sinais = linhas_para_texto(exemplo["sinais"])
        texto_protecao = linhas_para_texto(exemplo["protecao"])

        c.execute("SELECT id FROM conteudos WHERE chave = ?", (exemplo["chave"],))
        if c.fetchone():
            c.execute(
                "UPDATE conteudos SET titulo = ?, corpo = ?, icone = ?, "
                "categoria = ?, exemplo = ?, sinais = ?, protecao = ?, "
                "blocos = ? WHERE chave = ?",
                (
                    exemplo["titulo"],
                    exemplo["corpo"],
                    exemplo["icone"],
                    exemplo["categoria"],
                    exemplo["exemplo"],
                    texto_sinais,
                    texto_protecao,
                    texto_blocos,
                    exemplo["chave"],
                ),
            )
            continue

        c.execute(
            "INSERT INTO conteudos (titulo, corpo, autor, ativo, chave, icone, "
            "categoria, exemplo, sinais, protecao, origem, blocos) "
            "VALUES (?, ?, ?, 1, ?, ?, ?, ?, ?, ?, 'pre_colocado', ?)",
            (
                exemplo["titulo"],
                exemplo["corpo"],
                "pré-colocado",
                exemplo["chave"],
                exemplo["icone"],
                exemplo["categoria"],
                exemplo["exemplo"],
                texto_sinais,
                texto_protecao,
                texto_blocos,
            ),
        )

#Funções Novas adicionadas

def atualizar_primeiro_acesso(username):
    """Atualiza o status de primeiro acesso do aluno para 0 após o primeiro envio ao mural."""
    conn = conectar()
    c = conn.cursor()
    c.execute("UPDATE usuarios SET primeiro_acesso = 0 WHERE username = ?", (username,))
    conn.commit()
    conn.close()

def salvar_mensagem_mural(username, mensagem_criptografada):
    """Salva a mensagem associada ao usuário que a enviou"""
    conn = conectar()
    c = conn.cursor()
    c.execute(
        "INSERT INTO mural (username, mensagem_criptografada, ativo) VALUES (?, ?, 1)",
        (username, mensagem_criptografada)
    )
    conn.commit()
    conn.close()

def carregar_mural():
    """Carrega todas as mensagens ativas para exibição pública"""
    conn = conectar()
    c = conn.cursor()
    c.execute("SELECT id, username, mensagem_criptografada, data FROM mural WHERE ativo = 1 ORDER BY id DESC")
    dados = c.fetchall()
    conn.close()
    return dados

def inativar_mensagem_mural(msg_id):
    """Inativa qualquer mensagem (Apenas para Professores e Admins)"""
    conn = conectar()
    c = conn.cursor()
    c.execute("UPDATE mural SET ativo = 0 WHERE id = ?", (msg_id,))
    conn.commit()
    conn.close()


def salvar_conteudo(
    titulo,
    corpo,
    autor,
    icone="📜",
    categoria="",
    exemplo="",
    sinais="",
    protecao="",
    blocos=None,
):
    """Grava um exemplo de crime publicado pela coordenacao para os alunos.

    O autor e o username de quem publicou, do mesmo jeito que no mural: serve
    para a lista mostrar quem foi, sem precisar do nome completo.

    A "chave" fica vazia de proposito: ela so identifica os exemplos
    pre-colocados que vieram do arquivo dados/exemplos_crime.json. Um
    conteudo publicado na mao nao tem chave, e por isso a resemeadura
    nunca tenta recria-lo.

    "blocos" e o conteudo de verdade: a lista de {tipo, texto} que a
    pagina desenha. Os campos de texto corrido continuam sendo gravados
    porque o painel e as listas antigas ainda os leem.
    """
    conn = conectar()
    c = conn.cursor()
    c.execute(
        "INSERT INTO conteudos (titulo, corpo, autor, ativo, chave, icone, "
        "categoria, exemplo, sinais, protecao, origem, blocos) "
        "VALUES (?, ?, ?, 1, '', ?, ?, ?, ?, ?, 'publicado', ?)",
        (titulo, corpo, autor, icone, categoria, exemplo, sinais, protecao,
         blocos_para_texto(blocos)),
    )
    conn.commit()
    conn.close()


def carregar_conteudos():
    """Carrega todos os conteudos ativos, do mais novo para o mais antigo.

    Devolve tuplas no formato antigo (id, titulo, corpo, autor, data),
    porque a lista de "Gerenciar Aulas" usa esse formato. A pagina dos
    pergaminhos usa carregar_pergaminhos(), que traz os campos do crime.
    """
    conn = conectar()
    c = conn.cursor()
    c.execute("SELECT id, titulo, corpo, autor, data FROM conteudos WHERE ativo = 1 ORDER BY id DESC")
    dados = c.fetchall()
    conn.close()
    return dados


def carregar_pergaminhos():
    """Carrega os exemplos de crime ativos, na ordem em que foram gravados.

    Devolve dicionarios, e nao tuplas, porque a pagina dos pergaminhos
    usa muitos campos de cada exemplo e a tupla de dez posicoes vira
    uma lista de indices difficult de ler. A ordem e por id: os
    pre-colocados vem primeiro, na ordem do arquivo, e o que a
    coordenacao publica depois entra no fim.
    """
    conn = conectar()
    c = conn.cursor()
    c.execute(
        "SELECT id, titulo, corpo, autor, data, icone, categoria, exemplo, "
        "sinais, protecao, chave, origem, blocos FROM conteudos "
        "WHERE ativo = 1 ORDER BY id ASC"
    )
    linhas = c.fetchall()
    conn.close()

    chaves = (
        "id", "titulo", "corpo", "autor", "data", "icone", "categoria",
        "exemplo", "sinais", "protecao", "chave", "origem", "blocos",
    )
    # "blocos" chega do banco como texto e volta como lista: quem desenha
    # a pagina nao quer saber com o que o SQLite guarda uma lista.
    prontos = []
    for linha in linhas:
        registro = dict(zip(chaves, linha))
        registro["blocos"] = blocos_do_texto(registro.get("blocos"))
        prontos.append(registro)
    return prontos


def atualizar_conteudo(
    conteudo_id,
    titulo,
    corpo,
    icone,
    categoria,
    exemplo,
    sinais,
    protecao,
    blocos=None,
):
    """Reescreve um exemplo de crime. Usado pelo Professor e pela Coordenacao.

    A "chave" e a "origem" nao sao tocadas: a chave e o que amarra o
    exemplo pre-colocado ao arquivo de origem, e mexer nela faria a
    resemeadura criar um exemplar duplicado no proximo boot.
    """
    conn = conectar()
    c = conn.cursor()
    c.execute(
        "UPDATE conteudos SET titulo = ?, corpo = ?, icone = ?, categoria = ?, "
        "exemplo = ?, sinais = ?, protecao = ?, blocos = ? WHERE id = ?",
        (titulo, corpo, icone, categoria, exemplo, sinais, protecao,
         blocos_para_texto(blocos), conteudo_id),
    )
    conn.commit()
    conn.close()


def inativar_conteudo(conteudo_id):
    """Inativa um conteudo (Apenas para Professores e Admins)."""
    conn = conectar()
    c = conn.cursor()
    c.execute("UPDATE conteudos SET ativo = 0 WHERE id = ?", (conteudo_id,))
    conn.commit()
    conn.close()


def registrar_leitura(username, modulo):
    """Marca que o aluno terminou de ler o material de um modulo.

    Registrar duas vezes nao faz mal: a chave primaria e (username,
    modulo), entao o INSERT repetido atualiza a data e nao duplica a
    linha. Por isso a funcao usa INSERT OR REPLACE em vez de checar
    antes.
    """
    conn = conectar()
    c = conn.cursor()
    c.execute(
        "INSERT OR REPLACE INTO leituras (username, modulo) VALUES (?, ?)",
        (username, modulo),
    )
    conn.commit()
    conn.close()


def modulo_lido(username, modulo):
    """Diz se o aluno ja terminou de ler o material de um modulo.

    E o que libera o quiz. Devolve True ou False, nunca None: quem
    chama so precisa da resposta.
    """
    if not username:
        return False
    conn = conectar()
    c = conn.cursor()
    c.execute(
        "SELECT 1 FROM leituras WHERE username = ? AND modulo = ?",
        (username, modulo),
    )
    achou = c.fetchone() is not None
    conn.close()
    return achou


def modulos_lidos(username):
    """Devolve o conjunto de modulos que o aluno ja terminou de ler."""
    if not username:
        return set()
    conn = conectar()
    c = conn.cursor()
    c.execute("SELECT modulo FROM leituras WHERE username = ?", (username,))
    modulos = {linha[0] for linha in c.fetchall()}
    conn.close()
    return modulos


def salvar_progresso_modulo(username, modulo, acertos, total):
    """Registra uma tentativa de quiz de um modulo.

    Guarda uma linha por tentativa e nao apaga as anteriores: o historico
    fica para a equipe ver a evolucao do aluno. O que a tela usa e a melhor
    nota de cada modulo, calculada em carregar_progresso_modulos.

    Este e um registro de autoavaliacao -- nao e nota nem avaliacao formal
    de professor.
    """
    conn = conectar()
    c = conn.cursor()
    c.execute(
        "INSERT INTO progresso_modulos (username, modulo, acertos, total) "
        "VALUES (?, ?, ?, ?)",
        (username, modulo, acertos, total),
    )
    conn.commit()
    conn.close()


def carregar_progresso_modulos(username):
    """Devolve {slug_do_modulo: melhor resultado} do usuario.

    "Melhor resultado" e o que tem mais acertos -- e nao a ultima tentativa.
    Refazer o quiz depois de errar nao deve apagar o quanto a pessoa ja
    tinha acertado.

    Devolve dicionario vazio, e nao None, quando o usuario ainda nao fez
    nenhum quiz: quem chama so precisa do .get().
    """
    conn = conectar()
    c = conn.cursor()
    c.execute(
        "SELECT modulo, acertos, total, data FROM progresso_modulos "
        "WHERE username = ? ORDER BY id",
        (username,),
    )
    linhas = c.fetchall()
    conn.close()

    progresso = {}
    for modulo, acertos, total, data in linhas:
        if modulo not in progresso or acertos > progresso[modulo]["acertos"]:
            progresso[modulo] = {
                "acertos": acertos,
                "total": total,
                "data": data,
            }
    return progresso


def verificar_login(username_digitado, senha_digitada):
    """Busca o hash no banco e valida a senha digitada no container.

    Devolve (nome, tipo) quando a senha confere, ou None. Antes devolvia só o
    nome: o perfil nunca era lido do banco, então login.py nunca gravava
    tipo_usuario na sessão e todo mundo caía no menu do Aluno.
    """
    conn = conectar()
    c = conn.cursor()

    # 1. Busca no banco de dados o registro do usuário digitado
    c.execute("SELECT nome, tipo, password FROM usuarios WHERE username = ?", (username_digitado,))
    resultado = c.fetchone()
    conn.close()

    if resultado:
        nome_usuario, tipo_usuario, hash_do_banco_str = resultado

        # 2. Prepara os dados em formato de bytes para o bcrypt
        senha_digitada_bytes = senha_digitada.encode('utf-8')
        hash_salvo_bytes = hash_do_banco_str.encode('utf-8')

        # 3. COMPARAÇÃO EXPLÍCITA OCORRE AQUI:
        # bcrypt.checkpw extrai o salt do hash salvo e verifica a senha digitada
        if bcrypt.checkpw(senha_digitada_bytes, hash_salvo_bytes):
            return nome_usuario, tipo_usuario  # Nome e perfil para a sessão

    return None  # Retorna None se o usuário não existir ou a senha for inválida

def cadastrar_usuario(username, nome, email, tipo, senha_pura):
    """Gera o hash com bcrypt e cadastra o usuário com seu perfil no banco.

    Devolve "ok" em caso de sucesso, ou o motivo da recusa: "usuario_duplicado"
    ou "email_duplicado". Antes devolvia só True/False, e a tela acabava dizendo
    "nome de usuário já está em uso" para qualquer violação de integridade —
    inclusive e-mail repetido, que é outra situação e merece outra mensagem.
    """
    conn = conectar()
    c = conn.cursor()

    try:
        # 1. Conflitos verificados antes de gravar, para dizer qual foi.
        c.execute("SELECT 1 FROM usuarios WHERE username = ?", (username,))
        if c.fetchone():
            return "usuario_duplicado"

        c.execute("SELECT 1 FROM usuarios WHERE email = ?", (email,))
        if c.fetchone():
            return "email_duplicado"

        # 2. Gravação
        senha_bytes = senha_pura.encode('utf-8')
        salt = bcrypt.gensalt()
        hash_bytes = bcrypt.hashpw(senha_bytes, salt)
        hash_str = hash_bytes.decode('utf-8')

        c.execute(
            "INSERT INTO usuarios (username, nome, email, tipo, password) VALUES (?, ?, ?, ?, ?)",
            (username, nome, email, tipo, hash_str)
        )
        conn.commit()
        return "ok"
    except sqlite3.IntegrityError:
        # Duas submissões com o mesmo e-mail ao mesmo tempo: o índice único
        # barrou mesmo com a checagem acima. Mesma resposta da checagem.
        return "email_duplicado"
    finally:
        conn.close()