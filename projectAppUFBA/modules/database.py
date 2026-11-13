from contextlib import contextmanager
import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2.pool import ThreadedConnectionPool
import json
import bcrypt
import streamlit as st
import os
import logging
from streamlit.errors import StreamlitSecretNotFoundError
from dotenv import load_dotenv

# Carrega as variáveis do .env (se o arquivo existir)
load_dotenv()

logger = logging.getLogger(__name__)

DB_POOL_MAX_CONNECTIONS = 10
DB_CONNECT_TIMEOUT_SECONDS = 10

# Caminho de segurança (fallback) para o SQLite local
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data.db")
FALLBACK_URL = f"sqlite:///{DB_PATH}"

# APP_ENV pode vir do ambiente local ou dos Secrets do Streamlit.
APP_ENV = os.environ.get("APP_ENV")
if not APP_ENV:
    try:
        APP_ENV = st.secrets.get("APP_ENV")
    except StreamlitSecretNotFoundError:
        APP_ENV = None
APP_ENV = APP_ENV.strip().lower() if isinstance(APP_ENV, str) else None

# 1. Tenta pegar a URL do .env
DATABASE_URL = os.environ.get("DATABASE_URL")

# 2. Se não achar, tenta pegar dos Secrets (útil para quando for pro Streamlit Cloud)
if not DATABASE_URL:
    try:
        DATABASE_URL = st.secrets.get("DATABASE_URL")
    except StreamlitSecretNotFoundError:
        DATABASE_URL = None

@st.cache_resource
def _pool_postgres():
    """Cria um pool compartilhado e seguro para as threads do Streamlit."""
    dsn = DATABASE_URL
    if not dsn:
        try:
            postgres_secrets = st.secrets["postgres"]
        except (KeyError, StreamlitSecretNotFoundError):
            postgres_secrets = None
        if postgres_secrets:
            dsn = postgres_secrets.get("url")

    if not dsn:
        raise RuntimeError(
            "Nenhuma credencial de banco de dados (DATABASE_URL ou "
            "[postgres].url) foi encontrada."
        )

    return ThreadedConnectionPool(
        minconn=1,
        maxconn=DB_POOL_MAX_CONNECTIONS,
        dsn=str(dsn),
        connect_timeout=DB_CONNECT_TIMEOUT_SECONDS,
    )


@contextmanager
def conectar():
    """Empresta uma conexao do pool e sempre a devolve ao terminar."""
    pool = _pool_postgres()
    conn = pool.getconn()
    try:
        yield conn
    finally:
        pool.putconn(conn)

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
    with conectar() as conn:
        _criar_tabelas(conn)


def _criar_tabelas(conn):
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            username TEXT PRIMARY KEY,
            nome TEXT NOT NULL,
            email TEXT NOT NULL,
            tipo TEXT NOT NULL,
            password TEXT NOT NULL,
            foto_perfil BYTEA,
            primeiro_acesso INTEGER DEFAULT 1
        )
    ''')

    # 2. Inspeciona as colunas existentes na tabela
    #c.execute("SELECT * FROM information_schema.columns WHERE table_name = 'usuarios'")
    # colunas_existentes = [coluna[1] for coluna in c.fetchall()]
    # #apagado por redundancia, pois o comando abaixo ja cria as colunas caso nao existam, entao não precisa inspecionar
   
    # 3. Adiciona as colunas faltantes sem apagar dados
    c.execute("ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS primeiro_acesso INTEGER DEFAULT 1")
    c.execute("ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS email TEXT DEFAULT ''")
    c.execute("ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS tipo TEXT DEFAULT 'Aluno'")
    c.execute("ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS foto_perfil BYTEA")
        
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
    except psycopg2.IntegrityError:
        pass

    # Tabela para o Mural Criptografado
    c.execute("""
        CREATE TABLE IF NOT EXISTS mural (
            id SERIAL PRIMARY KEY,
            ativo INTEGER DEFAULT 1,
            username TEXT,
            mensagem_criptografada TEXT,
            data TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    c.execute("SELECT * FROM information_schema.columns WHERE table_name = 'mural'")
    colunas_mural = [coluna[1] for coluna in c.fetchall()]
    if "username" not in colunas_mural:
        c.execute("ALTER TABLE mural ADD COLUMN IF NOT EXISTS username TEXT DEFAULT ''")
    if "ativo" not in colunas_mural:
        c.execute("ALTER TABLE mural ADD COLUMN IF NOT EXISTS ativo INTEGER DEFAULT 1")

    # Tabela dos Conteudos da Coordenacao.
    # E o caminho pelo qual o Administrador (e o Professor) publicam material
    # para os alunos. Segue o mesmo padrao do mural: nada e apagado, a linha
    # so muda ativo para 0, entao o historico do que foi publicado fica.
    c.execute("""
        CREATE TABLE IF NOT EXISTS conteudos (
            id SERIAL PRIMARY KEY,
            titulo TEXT NOT NULL,
            corpo TEXT NOT NULL,
            autor TEXT,
            ativo INTEGER DEFAULT 1,
            data TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    c.execute("SELECT * FROM information_schema.columns WHERE table_name = 'conteudos'")
    colunas_conteudos = [coluna[1] for coluna in c.fetchall()]
    if "autor" not in colunas_conteudos:
        c.execute("ALTER TABLE conteudos ADD COLUMN IF NOT EXISTS autor TEXT DEFAULT ''")
    if "ativo" not in colunas_conteudos:
        c.execute("ALTER TABLE conteudos ADD COLUMN IF NOT EXISTS ativo INTEGER DEFAULT 1")

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
            c.execute("ALTER TABLE conteudos ADD COLUMN IF NOT EXISTS %s %s"
                      % (nome_coluna, definicao))

    # A LGPD deixou de ser pergaminho: virou o Modulo 5, uma aula teorica.
    # As linhas antigas nao sao apagadas (o texto pode ter sido editado pela
    # coordenacao), apenas inativadas, para nao aparecerem mais na pagina
    # "Exemplos de Crimes Digitais". O UPDATE e idempotente.
    c.execute(
        "UPDATE conteudos SET ativo = 0 WHERE chave = ANY(%s)",
        (
            [
                "lei-geral-protecao-dados",
                "principios-da-lgpd",
                "responsabilidade-protecao-dados",
                "importancia-lgpd-organizacoes",
            ],
        ),
    )

    # --- MODULOS CRIADOS PELA PLATAFORMA ---
    #
    # Os modulos originais continuam em dados/modulos.json. Esta tabela
    # guarda apenas os modulos novos, criados pela pagina "Gerenciar
    # Modulos". O campo "autor" e o username de quem criou, e e ele que
    # limita a edicao/exclusao: o criador mexe no proprio modulo, o
    # Administrador mexe em todos.
    #
    # O quiz fica em uma coluna de texto com JSON, do mesmo jeito que os
    # blocos dos pergaminhos. A lista de perguntas e pequena e nao tem
    # consulta por dentro dela, entao uma tabela separada so criaria
    # juncoes para nada.
    c.execute("""
        CREATE TABLE IF NOT EXISTS modulos (
            id SERIAL PRIMARY KEY,
            slug TEXT NOT NULL UNIQUE,
            titulo TEXT NOT NULL,
            resumo TEXT DEFAULT '',
            icone TEXT DEFAULT '📘',
            nivel TEXT DEFAULT '',
            dificuldade TEXT DEFAULT '',
            duracao TEXT DEFAULT '',
            cor TEXT DEFAULT '#4F46E5',
            pdf TEXT DEFAULT '',
            quiz TEXT DEFAULT '[]',
            categoria TEXT DEFAULT 'Outros',
            ordem INTEGER DEFAULT 900,
            autor TEXT NOT NULL,
            ativo INTEGER DEFAULT 1,
            data TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    c.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = 'modulos'"
    )
    colunas_modulos = [linha[0] for linha in c.fetchall()]
    for nome_coluna, definicao in (
        ("slug", "TEXT"),
        ("titulo", "TEXT"),
        ("resumo", "TEXT DEFAULT ''"),
        ("icone", "TEXT DEFAULT '📘'"),
        ("nivel", "TEXT DEFAULT ''"),
        ("dificuldade", "TEXT DEFAULT ''"),
        ("duracao", "TEXT DEFAULT ''"),
        ("cor", "TEXT DEFAULT '#4F46E5'"),
        ("pdf", "TEXT DEFAULT ''"),
        ("quiz", "TEXT DEFAULT '[]'"),
        ("categoria", "TEXT DEFAULT 'Outros'"),
        ("ordem", "INTEGER DEFAULT 900"),
        ("autor", "TEXT DEFAULT ''"),
        ("ativo", "INTEGER DEFAULT 1"),
        ("data", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
    ):
        if nome_coluna not in colunas_modulos:
            c.execute(
                "ALTER TABLE modulos ADD COLUMN IF NOT EXISTS %s %s"
                % (nome_coluna, definicao)
            )

    # Tabela do progresso de cada modulo de aprendizagem.
    #
    # Uma linha por tentativa de quiz. Nao apaga a anterior: o historico fica
    # para a equipe ver a evolucao, e o que a tela mostra e a melhor nota de
    # cada modulo. Este registro e autoavaliacao do aluno -- nao e nota nem
    # avaliacao formal de professor.
    c.execute("""
        CREATE TABLE IF NOT EXISTS progresso_modulos (
            id SERIAL PRIMARY KEY,
            username TEXT NOT NULL,
            modulo TEXT NOT NULL,
            acertos INTEGER NOT NULL,
            total INTEGER NOT NULL,
            data TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    c.execute("SELECT * FROM information_schema.columns WHERE table_name = 'progresso_modulos'")
    colunas_progresso = [coluna[1] for coluna in c.fetchall()]
    if "modulo" not in colunas_progresso:
        c.execute("ALTER TABLE progresso_modulos ADD COLUMN IF NOT EXISTS modulo TEXT DEFAULT ''")
    if "username" not in colunas_progresso:
        c.execute("ALTER TABLE progresso_modulos ADD COLUMN IF NOT EXISTS username TEXT DEFAULT ''")

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
            "INSERT INTO usuarios (username, nome, email, tipo, password) VALUES (%s, %s, %s, %s, %s)",
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
   #Criação da tabela de seguidores, que registra quem segue quem. A chave primária é composta pelos dois usernames, garantindo que não haja duplicatas.
    c.execute('''
        CREATE TABLE IF NOT EXISTS seguidores (
            seguidor_username TEXT NOT NULL,
            seguido_username TEXT NOT NULL,
            data_inicio TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (seguidor_username, seguido_username)
        )
    ''')

    # Garante a restrição única para tabelas criadas anteriormente sem a chave primária
    try:
        c.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_leituras_user_modulo ON leituras (username, modulo)"
        )
    except psycopg2.IntegrityError:
        conn.rollback()  # Reverte a transação se houver erro de integridade

    # --- EXEMPLOS DE CRIMES PRÉ-COLOCADOS ---
    #
    # Vem do arquivo dados/exemplos_crime.json, que o professor edita
    # sem tocar em código. A semeadura é idempotente pela "chave": um
    # exemplo cuja chave já está na tabela não é criado de novo. É o
    # mesmo esquema do admin acima -- o que já existe não é reescrito.
    #
    # O que o professor edita depois pela página "Gerenciar Conteúdos →
    # Exemplos de Golpe" vale mais do que o que está no arquivo: por isso a
    # semeadura não sobrescreve uma linha que já existe.
    _semear_exemplos_crime(c)

    conn.commit()


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
    """Insere no banco exemplos do JSON que ainda nao existem pela chave.

    Recebe o cursor ja aberto, porque quem chama e o criar_tabelas, que
    abre e fecha a conexao uma vez so.

    O banco e a fonte da verdade para exemplos existentes: eles nao sao
    atualizados nem inativados quando o JSON muda ou deixa de listar uma chave.
    """
    # O import e aqui dentro, e nao no topo do arquivo: o modulo dos
    # exemplos nao precisa do banco, e o banco nao precisa do modulo de
    # leitura para nada alem disto. Importar aqui evita qualquer
    # dependencia circular entre os dois.
    from modules.exemplos_crime import (
        carregar_exemplos,
        linhas_para_texto,
    )

    exemplos, _ = carregar_exemplos()

    for exemplo in exemplos:
        texto_blocos = blocos_para_texto(exemplo.get("blocos"))
        texto_sinais = linhas_para_texto(exemplo["sinais"])
        texto_protecao = linhas_para_texto(exemplo["protecao"])

        c.execute("SELECT id FROM conteudos WHERE chave = %s", (exemplo["chave"],))
        if c.fetchone():
            continue

        c.execute(
            "INSERT INTO conteudos (titulo, corpo, autor, ativo, chave, icone, "
            "categoria, exemplo, sinais, protecao, origem, blocos) "
            "VALUES (%s, %s, %s, 1, %s, %s, %s, %s, %s, %s, 'pre_colocado', %s)",
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

@st.cache_data(ttl=300, show_spinner=False)
def obter_primeiro_acesso(username):
    """Le o status de primeiro acesso sem repetir a consulta a cada rerun."""
    if not username:
        return 1
    with conectar() as conn:
        c = conn.cursor()
        c.execute(
            "SELECT primeiro_acesso FROM usuarios WHERE username = %s",
            (username,),
        )
        resultado = c.fetchone()
        conn.rollback()
    return resultado[0] if resultado else 1


def atualizar_primeiro_acesso(username):
    """Atualiza o status de primeiro acesso do aluno para 0 após o primeiro envio ao mural."""
    with conectar() as conn:
        c = conn.cursor()
        c.execute("UPDATE usuarios SET primeiro_acesso = 0 WHERE username = %s", (username,))
        conn.commit()
    obter_primeiro_acesso.clear()


def salvar_mensagem_mural(username, mensagem_criptografada):
    """Salva a mensagem associada ao usuário que a enviou"""
    with conectar() as conn:
        c = conn.cursor()
        c.execute(
            "INSERT INTO mural (username, mensagem_criptografada, ativo) VALUES (%s, %s, 1)",
            (username, mensagem_criptografada)
        )
        conn.commit()
    carregar_mural.clear()


@st.cache_data(ttl=300, show_spinner=False)
def carregar_mural():
    """Carrega todas as mensagens ativas para exibição pública.

    A lista muda somente quando alguém publica ou inativa uma mensagem.
    Por isso ela fica em cache e é invalidada pelas duas escritas abaixo,
    em vez de consultar o banco a cada rerun do mural.
    """
    with conectar() as conn:
        c = conn.cursor()
        c.execute("SELECT id, username, mensagem_criptografada, data FROM mural WHERE ativo = 1 ORDER BY id DESC")
        dados = c.fetchall()
        conn.rollback()
    return dados


def inativar_mensagem_mural(msg_id):
    """Inativa qualquer mensagem (Apenas para Professores e Admins)"""
    with conectar() as conn:
        c = conn.cursor()
        c.execute("UPDATE mural SET ativo = 0 WHERE id = %s", (msg_id,))
        conn.commit()
    carregar_mural.clear()


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
    with conectar() as conn:
        c = conn.cursor()
        c.execute(
            "INSERT INTO conteudos (titulo, corpo, autor, ativo, chave, icone, "
            "categoria, exemplo, sinais, protecao, blocos, origem) "
            "VALUES (%s, %s, %s, 1, '', %s, %s, %s, %s, %s, %s, 'publicado')",
            (
                titulo,
                corpo,
                autor,
                icone,
                categoria,
                exemplo,
                sinais,
                protecao,
                blocos_para_texto(blocos),
            ),
        )
        conn.commit()
    carregar_pergaminhos.clear()
    carregar_conteudos.clear()


@st.cache_data(ttl=300, show_spinner=False)
def carregar_conteudos():
    """Carrega todos os conteudos ativos, do mais novo para o mais antigo.

    Devolve tuplas no formato antigo (id, titulo, corpo, autor, data),
    porque a lista de "Gerenciar Conteúdos → Exemplos de Golpe" usa esse
    formato. A pagina dos pergaminhos usa carregar_pergaminhos(), que traz
    os campos do crime.
    """
    with conectar() as conn:
        c = conn.cursor()
        c.execute("SELECT id, titulo, corpo, autor, data FROM conteudos WHERE ativo = 1 ORDER BY id DESC")
        dados = c.fetchall()
        conn.rollback()
    return dados


@st.cache_data(ttl=300, show_spinner=False)
def carregar_pergaminhos():
    """Carrega os exemplos ativos, na ordem gravada.

    Devolve dicionarios, e nao tuplas, porque a pagina dos pergaminhos
    usa muitos campos de cada exemplo e a tupla de dez posicoes vira
    uma lista de indices dificil de ler. A ordem e por id: os
    pre-colocados vem primeiro, na ordem do arquivo, e o que a
    coordenacao publica depois entra no fim.

    Esta funcao e somente leitura. A semeadura dos exemplos do arquivo
    dados/exemplos_crime.json fica em _criar_tabelas(), que e chamada na
    preparacao do banco: carregar uma pagina nao deve abrir transacao de
    escrita no banco.
    """
    with conectar() as conn:
        c = conn.cursor()
        c.execute(
            "SELECT id, titulo, corpo, autor, data, icone, categoria, exemplo, "
            "sinais, protecao, chave, origem, blocos FROM conteudos "
            "WHERE ativo = 1 ORDER BY id ASC"
        )
        linhas = c.fetchall()
        conn.rollback()

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
    with conectar() as conn:
        c = conn.cursor()
        c.execute(
            "UPDATE conteudos SET titulo = %s, corpo = %s, icone = %s, "
            "categoria = %s, exemplo = %s, sinais = %s, protecao = %s, "
            "blocos = %s WHERE id = %s",
            (
                titulo,
                corpo,
                icone,
                categoria,
                exemplo,
                sinais,
                protecao,
                blocos_para_texto(blocos),
                conteudo_id,
            ),
        )
        conn.commit()
    carregar_pergaminhos.clear()
    carregar_conteudos.clear()


def inativar_conteudo(conteudo_id):
    """Inativa um conteudo (Apenas para Professores e Admins)."""
    with conectar() as conn:
        c = conn.cursor()
        c.execute("UPDATE conteudos SET ativo = 0 WHERE id = %s", (conteudo_id,))
        conn.commit()
    carregar_pergaminhos.clear()
    carregar_conteudos.clear()


# ---------------------------------------------------------------------------
# Modulos criados pela plataforma
# ---------------------------------------------------------------------------
#
# Os modulos originais continuam em dados/modulos.json. A tabela "modulos"
# guarda somente os que nascem na pagina "Gerenciar Conteudos -> Modulos".
# As funcoes abaixo sao o CRUD dessa tabela.
#
# O quiz e gravado como JSON de uma lista de:
#   {"enunciado": "...", "alternativas": ["..."], "certa": 0}
# O indice "certa" aqui e ZERO-based, que e o formato que o resto do app
# usa internamente. A conversao para o formato do JSON (1-based) acontece
# so na hora de gravar um modulo que veio do arquivo.


def _quiz_do_texto(texto):
    """Le a coluna "quiz" de volta como lista, tolerando lixo no banco.

    O banco nao precisa derrubar a tela por causa de um quiz corrompido:
    a pergunta invalida e descartada e as demais continuam valendo.
    """
    if not texto:
        return []
    try:
        dados = json.loads(texto)
    except (ValueError, TypeError):
        return []
    if not isinstance(dados, list):
        return []

    prontos = []
    for questao in dados:
        if not isinstance(questao, dict):
            continue
        enunciado = str(questao.get("enunciado") or "").strip()
        alternativas = questao.get("alternativas")
        if not enunciado or not isinstance(alternativas, list) or len(alternativas) < 2:
            continue
        alternativas = [str(alternativa) for alternativa in alternativas]
        certa = questao.get("certa")
        if (
            not isinstance(certa, int)
            or isinstance(certa, bool)
            or not (0 <= certa < len(alternativas))
        ):
            certa = 0
        prontos.append({
            "enunciado": enunciado,
            "alternativas": alternativas,
            "certa": certa,
        })
    return prontos


def _quiz_para_texto(quiz):
    """Serializa a lista de perguntas para a coluna de texto."""
    return json.dumps(quiz or [], ensure_ascii=False)


@st.cache_data(ttl=300, show_spinner=False)
def listar_modulos_banco():
    """Devolve os modulos criados na plataforma, do mais antigo ao mais novo.

    O quiz volta como lista, e nao como texto: quem chama (o carregador
    dos modulos) espera o mesmo formato dos modulos do JSON.

    O catalogo e publico e o mesmo para todos os perfis, por isso ele tem
    uma unica entrada de cache -- sem o username na chave. O cache e
    invalidado por salvar_modulo, atualizar_modulo e excluir_modulo.
    """
    with conectar() as conn:
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as c:
                c.execute(
                    "SELECT id, slug, titulo, resumo, icone, nivel, dificuldade, "
                    "duracao, cor, pdf, quiz, categoria, ordem, autor, data "
                    "FROM modulos WHERE ativo = 1 ORDER BY id ASC"
                )
                linhas = c.fetchall()
            # Consulta so de leitura: encerra a transacao para a conexao
            # voltar limpa ao pool.
            conn.rollback()
        except Exception:
            # Deixa a conexao limpa para voltar ao pool: uma transacao
            # abortada contaminaria a proxima consulta que a reaproveitar.
            conn.rollback()
            raise

    prontos = []
    for linha in linhas:
        registro = dict(linha)
        registro["quiz"] = _quiz_do_texto(registro.get("quiz"))
        prontos.append(registro)
    return prontos


def salvar_modulo(
    slug,
    titulo,
    resumo,
    icone,
    nivel,
    dificuldade,
    duracao,
    cor,
    pdf,
    quiz,
    autor,
    categoria="Outros",
):
    """Cria um modulo novo. Devolve (id, None) ou (None, motivo).

    O "motivo" e uma chave curta que a tela traduz em portugues:
    "slug_duplicado" ou o texto do erro inesperado.

    A categoria e validada pelo chamador (a tela usa a lista de
    modules/modulos.py). O valor fica no banco para o catalogo saber em que
    aba o modulo aparece.
    """
    with conectar() as conn:
        c = conn.cursor()
        try:
            c.execute(
                "INSERT INTO modulos (slug, titulo, resumo, icone, nivel, "
                "dificuldade, duracao, cor, pdf, quiz, autor, categoria, ativo) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 1) "
                "RETURNING id",
                (
                    slug,
                    titulo,
                    resumo,
                    icone,
                    nivel,
                    dificuldade,
                    duracao,
                    cor,
                    pdf,
                    _quiz_para_texto(quiz),
                    autor,
                    categoria,
                ),
            )
            novo_id = c.fetchone()[0]
            conn.commit()
            listar_modulos_banco.clear()
            return novo_id, None
        except psycopg2.IntegrityError:
            conn.rollback()
            return None, "slug_duplicado"
        except Exception as erro:
            conn.rollback()
            logger.exception("Falha ao criar modulo")
            return None, str(erro)


def atualizar_modulo(
    modulo_id,
    slug,
    titulo,
    resumo,
    icone,
    nivel,
    dificuldade,
    duracao,
    cor,
    pdf,
    quiz,
    solicitante,
    tipo,
    categoria="Outros",
):
    """Reescreve um modulo do banco respeitando quem criou.

    O Administrador pode editar qualquer modulo. Os demais so podem
    editar a linha cujo "autor" e o proprio username -- a condicao vai
    no WHERE, e nao so na tela, para a regra nao depender da interface.
    """
    with conectar() as conn:
        c = conn.cursor()
        parametros = (
            slug,
            titulo,
            resumo,
            icone,
            nivel,
            dificuldade,
            duracao,
            cor,
            pdf,
            _quiz_para_texto(quiz),
            categoria,
        )
        try:
            if tipo == "Administrador":
                c.execute(
                    "UPDATE modulos SET slug = %s, titulo = %s, resumo = %s, "
                    "icone = %s, nivel = %s, dificuldade = %s, duracao = %s, "
                    "cor = %s, pdf = %s, quiz = %s, categoria = %s "
                    "WHERE id = %s",
                    parametros + (modulo_id,),
                )
            else:
                c.execute(
                    "UPDATE modulos SET slug = %s, titulo = %s, resumo = %s, "
                    "icone = %s, nivel = %s, dificuldade = %s, duracao = %s, "
                    "cor = %s, pdf = %s, quiz = %s, categoria = %s "
                    "WHERE id = %s AND autor = %s",
                    parametros + (modulo_id, solicitante),
                )
            if c.rowcount <= 0:
                conn.rollback()
                return False, "sem_permissao"
            conn.commit()
            listar_modulos_banco.clear()
            return True, None
        except psycopg2.IntegrityError:
            conn.rollback()
            return False, "slug_duplicado"
        except Exception as erro:
            conn.rollback()
            logger.exception("Falha ao atualizar modulo")
            return False, str(erro)


def excluir_modulo(modulo_id, solicitante, tipo):
    """Exclui um modulo do banco. Admin pode todos; os demais so os proprios.

    Devolve (ok, motivo), como atualizar_modulo: "sem_permissao" quando a
    linha nao existe ou nao e do solicitante, ou o texto do erro inesperado.
    """
    with conectar() as conn:
        c = conn.cursor()
        try:
            if tipo == "Administrador":
                c.execute("DELETE FROM modulos WHERE id = %s", (modulo_id,))
            else:
                c.execute(
                    "DELETE FROM modulos WHERE id = %s AND autor = %s",
                    (modulo_id, solicitante),
                )
            if c.rowcount <= 0:
                conn.rollback()
                return False, "sem_permissao"
            conn.commit()
            listar_modulos_banco.clear()
            return True, None
        except Exception as erro:
            conn.rollback()
            logger.exception("Falha ao excluir modulo")
            return False, str(erro)


def registrar_leitura(username, modulo):
    """Marca que o aluno terminou de ler o material de um modulo.

    Registrar duas vezes nao faz mal: a chave primaria e (username,
    modulo), entao o INSERT repetido atualiza a data e nao duplica a
    linha. Por isso a funcao usa INSERT OR REPLACE em vez de checar
    antes.
    """
    with conectar() as conn:
        c = conn.cursor()
        c.execute(
             """
             INSERT INTO leituras (username, modulo) VALUES (%s, %s)
             ON CONFLICT (username, modulo) DO UPDATE SET data = CURRENT_TIMESTAMP
        """,
        (username, modulo)
        )
        conn.commit()
    carregar_estado_modulos.clear()
    modulo_lido.clear()
    modulos_lidos.clear()


@st.cache_data(ttl=300, show_spinner=False)
def modulo_lido(username, modulo):
    """Diz se o aluno ja terminou de ler o material de um modulo.

    E o que libera o quiz. Devolve True ou False, nunca None: quem
    chama so precisa da resposta.
    """
    if not username:
        return False
    with conectar() as conn:
        c = conn.cursor()
        c.execute(
            "SELECT 1 FROM leituras WHERE username = %s AND modulo = %s",
            (username, modulo),
        )
        achou = c.fetchone() is not None
    return achou


@st.cache_data(ttl=300, show_spinner=False)
def modulos_lidos(username):
    """Devolve o conjunto de modulos que o aluno ja terminou de ler."""
    if not username:
        return set()
    with conectar() as conn:
        c = conn.cursor()
        c.execute("SELECT modulo FROM leituras WHERE username = %s", (username,))
        return {linha[0] for linha in c.fetchall()}


@st.cache_data(ttl=300, show_spinner=False)
def carregar_estado_modulos(username):
    """Carrega leituras e progresso do aluno com uma consulta ao banco.

    O resultado fica em cache por pouco tempo e e invalidado quando o aluno
    registra uma leitura ou uma tentativa de quiz.
    """
    if not username:
        return {}, set()

    with conectar() as conn:
        try:
            c = conn.cursor()
            c.execute(
                "SELECT 'leitura' AS tipo, modulo, NULL::INTEGER AS acertos, "
                "NULL::INTEGER AS total, NULL::TIMESTAMP AS data, "
                "NULL::INTEGER AS ordem "
                "FROM leituras WHERE username = %s "
                "UNION ALL "
                "SELECT 'progresso' AS tipo, modulo, acertos, total, data, id "
                "FROM progresso_modulos WHERE username = %s "
                "ORDER BY ordem NULLS FIRST",
                (username, username),
            )
            linhas = c.fetchall()
            conn.rollback()
        except Exception:
            conn.rollback()
            raise

    lidos = set()
    progresso = {}
    ordens_progresso = {}
    for tipo, modulo, acertos, total, data, ordem in linhas:
        if tipo == "leitura":
            lidos.add(modulo)
            continue
        if (
            modulo not in progresso
            or acertos > progresso[modulo]["acertos"]
            or (
                acertos == progresso[modulo]["acertos"]
                and ordem < ordens_progresso[modulo]
            )
        ):
            progresso[modulo] = {
                "acertos": acertos,
                "total": total,
                "data": data,
            }
            ordens_progresso[modulo] = ordem
    return progresso, lidos


def salvar_progresso_modulo(username, modulo, acertos, total):
    """Registra uma tentativa de quiz de um modulo.

    Guarda uma linha por tentativa e nao apaga as anteriores: o historico
    fica para a equipe ver a evolucao do aluno. O que a tela usa e a melhor
    nota de cada modulo, calculada em carregar_estado_modulos.

    Este e um registro de autoavaliacao -- nao e nota nem avaliacao formal
    de professor.
    """
    with conectar() as conn:
        c = conn.cursor()
        c.execute(
            "INSERT INTO progresso_modulos (username, modulo, acertos, total) VALUES (%s, %s, %s, %s)",
            (username, modulo, acertos, total),
        )
        conn.commit()
    carregar_estado_modulos.clear()
    carregar_progresso_modulos.clear()


@st.cache_data(ttl=300, show_spinner=False)
def carregar_progresso_modulos(username):
    """Devolve {slug_do_modulo: melhor resultado} do usuario.

    "Melhor resultado" e o que tem mais acertos -- e nao a ultima tentativa.
    Refazer o quiz depois de errar nao deve apagar o quanto a pessoa ja
    tinha acertado.

    Devolve dicionario vazio, e nao None, quando o usuario ainda nao fez
    nenhum quiz: quem chama so precisa do .get().
    """
    with conectar() as conn:
        c = conn.cursor()
        c.execute(
            "SELECT modulo, acertos, total, data FROM progresso_modulos "
            "WHERE username = %s ORDER BY id",
            (username,),
        )
        linhas = c.fetchall()

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
    with conectar() as conn:
        c = conn.cursor()
        c.execute("SELECT nome, tipo, password FROM usuarios WHERE username = %s", (username_digitado,))
        resultado = c.fetchone()

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
    with conectar() as conn:
        c = conn.cursor()
        try:
            # 1. Conflitos verificados antes de gravar, para dizer qual foi.
            c.execute("SELECT 1 FROM usuarios WHERE username = %s", (username,))
            if c.fetchone():
                return "usuario_duplicado"

            c.execute("SELECT 1 FROM usuarios WHERE email = %s", (email,))
            if c.fetchone():
                return "email_duplicado"

            # 2. Gravação
            senha_bytes = senha_pura.encode('utf-8')
            salt = bcrypt.gensalt()
            hash_bytes = bcrypt.hashpw(senha_bytes, salt)
            hash_str = hash_bytes.decode('utf-8')

            c.execute(
                "INSERT INTO usuarios (username, nome, email, tipo, password) VALUES (%s, %s, %s, %s, %s)",
                (username, nome, email, tipo, hash_str)
            )
            conn.commit()
            return "ok"
        except psycopg2.IntegrityError:
            # Duas submissões com o mesmo e-mail ao mesmo tempo: o índice único
            # barrou mesmo com a checagem acima. Mesma resposta da checagem.
            return "email_duplicado"

@st.cache_data(ttl=300, show_spinner=False)
def obter_dados_perfil(username):
    """Consulta puramente relacional para resgatar apenas o nome e a foto de perfil do usuário."""
    if not username:
        return None
    with conectar() as conn:
        c = conn.cursor()
        # Busca estritamente as 2 colunas necessárias (sem carregar o e-mail)
        c.execute("SELECT nome, foto_perfil FROM usuarios WHERE username = %s", (username,))
        resultado = c.fetchone()
        if not resultado:
             return None
        nome, foto = resultado
        return nome, (bytes(foto) if foto is not None else None)

def atualizar_perfil(username, nova_senha, senha_atual, novo_nome): # Função para atualizar o usuário
    with conectar() as conn: # Inicia o contexto conectando-se ao PostgreSQL de forma otimizada
        c = conn.cursor() # Instancia o ponteiro de navegação no banco
       # Se o usuário preencheu campos para trocar a senha
        if nova_senha and senha_atual:
            # Puxa o hash da senha antiga salva no banco[cite: 1, 5]
            c.execute("SELECT password FROM usuarios WHERE username = %s", (username,))
            hash_do_banco = c.fetchone()[0].encode('utf-8')
            
            # MÉTODO SEGURO: Verifica se a senha atual digitada confere com o hash original[cite: 1, 5]
            if not bcrypt.checkpw(senha_atual.encode('utf-8'), hash_do_banco):
                # Recusa a alteração se a senha antiga estiver errada
                return "senha_atual_incorreta"
            
            # Se passou, criptografa a NOVA senha[cite: 1, 5]
            salt = bcrypt.gensalt()
            novo_hash = bcrypt.hashpw(nova_senha.encode('utf-8'), salt).decode('utf-8')
            c.execute(
                "UPDATE usuarios SET nome=%s, password=%s WHERE username=%s",
                (novo_nome, novo_hash, username)
            )
        else:
            # Atualiza apenas informações gerais e foto (sem mexer na senha)
            c.execute(
                "UPDATE usuarios SET nome=%s WHERE username=%s",
                (novo_nome, username)
            )
        conn.commit() # Confirma efetivamente a gravação da transação na base de dados
        obter_dados_perfil.clear() # Limpa o cache de perfil para refletir as mudanças
        c.close() # Destrói o cursor liberando recursos locais do servidor

def buscar_usuarios(termo): # Função para ler registros parecidos com o termo de busca
    with conectar() as conn: # Empresta a conexão do Pool
        c = conn.cursor() # Cria o cursor de execução
        # Realiza uma busca tolerante a maiúsculas/minúsculas usando o comparador ILIKE do PostgreSQL limitando sobrecarga a 20 linhas
        c.execute("SELECT nome, tipo FROM usuarios WHERE nome ILIKE %s LIMIT 20", (f"%{termo}%",))
        resultados = c.fetchall() # Descarrega em memória local todos os registros capturados pela query
        c.close() # Encerra o objeto cursor
        return resultados # Retorna a lista contendo as tuplas do formato (nome, tipo)

def seguir_usuario(seguidor, seguido):
    with conectar() as conn:
        c = conn.cursor()
        # Utiliza ON CONFLICT para não gerar erro caso o usuário clique duas vezes (PostgreSQL nativo)
        c.execute("""
            INSERT INTO seguidores (seguidor_username, seguido_username) 
            VALUES (%s, %s)
            ON CONFLICT (seguidor_username, seguido_username) DO NOTHING
        """, (seguidor, seguido))
        conn.commit()

def buscar_usuarios(termo):
    with conectar() as conn:
        c = conn.cursor()
        # Ajuste o SELECT para retornar o username (chave primária) usado na ação de seguir
        c.execute("SELECT username, nome, tipo FROM usuarios WHERE nome ILIKE %s LIMIT 20", (f"%{termo}%",))
        return c.fetchall()

def atualizar_foto(username, foto_bytes):
    foto_db = psycopg2.Binary(foto_bytes) if foto_bytes else None
    with conectar() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE usuarios SET foto_perfil = %s WHERE username = %s",
            (foto_db, username),
        )
        conn.commit()
        obter_dados_perfil.clear()  # Limpa o cache para refletir a nova foto