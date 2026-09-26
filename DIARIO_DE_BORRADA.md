# Diario de trabalho

Registro das decisoes e das medicoes desta etapa do projeto. Fica fora do Git
de proposito: e rascunho de trabalho, nao documentacao do produto.

---

## Aviso importante: perda de arquivos nesta pasta

Dois arquivos ja sumiram deste diretorio sem causa identificavel, ambos trabalho
nao commitado:

1. O CSS de tema escuro e responsividade em `modules/login.py` (revertido ao
   commit `515585d`).
2. Este proprio diario.

Nao ha stash, arquivo de conflito do OneDrive nem `.orig` que permita recuperar.
A perda do CSS foi reconstruida a partir das medicoes registradas nesta
conversa.

Conclusao pratica: trabalho nao commitado neste diretorio nao e confiavel.
Commitar cedo, mesmo em branch de rascunho.

---

## Estado do repositorio

Branch `main`, HEAD `515585d loginBaseVersion`. Nada commitado nesta etapa.

Alterados:

| Arquivo | O que mudou |
|---------|-------------|
| `projectAppUFBA/app.py` | menu por perfil + conteudo das 6 paginas |
| `projectAppUFBA/modules/database.py` | perfil no login, indice unico de e-mail, motivo de recusa |
| `projectAppUFBA/modules/login.py` | rate limit integrado, campo e botao desabilitados no bloqueio, `clear_on_submit` nos dois formularios, gravacao do perfil na sessao |

Nao rastreados: `projectAppUFBA/modules/ratelimit.py`, este diario.

Intacto, conferido com `git diff --stat HEAD`: `projectAppUFBA/plataforma.db`.
Os testes rodaram sempre contra a copia em `criptoeduca-run`.

---

## Rate limit da chave do Professor: integrado

`modules/ratelimit.py` criado e ligado ao formulario. Tres insercoes no bloco
`if btn_cadastrar:`:

1. **Bloqueio no topo da cadeia.** Prepende um branch, antes de qualquer outra
   validacao. Quem esta bloqueado nao gasta processamento nem recebe dica sobre
   os outros campos.
2. **`registrar_falha` dentro do `elif` da chave**, junto do erro.
3. **`zerar` no sucesso**, so quando o perfil e Professor.

Detalhe de decisao: usei prepend no `elif` em vez de `st.stop()`. Com
`st.stop()` o resto do script nao renderiza e o `st.info` de dica sumiria junto,
o que e mudanca de alem do que foi pedido. Prefendi um branch: diff minimo,
sem surpresa de controle de fluxo.

A mensagem do erro de chave passou a mostrar o que resta
(`ratelimit.restantes`). Um limite que aparece do nada e pior que um limite
anunciado: na 5a falha a mensagem avisa "Restam 0 tentativas" antes do bloqueio.

O guard `tipo_usuario_input == "Professor"` e obrigatorio nos tres pontos:
Aluno nao tem chave para chutar e nao tem por que ser bloqueado.

### Botao e campo da chave desabilitados durante o bloqueio

`chave_bloqueada` e calculado entre o `selectbox` e o campo da chave, e aplicado
em `disabled=` no `st.text_input` da chave e no `st.form_submit_button`.

**Por que so a chave, e nao o formulario inteiro:** o bloqueio e sobre a chave.
Desabilitar o formulario inteiro deixaria um Professor bloqueado sem poder nem
se cadastrar como Aluno, porque o `selectbox` estaria morto e nao haveria como
trocar o perfil. Desabilitando so a chave, o Aluno se cadastra normalmente.

**CSS novo para o estado bloqueado.** O CSS do projeto pinta o fundo do campo
(`background-color: #1e2430`), entao o cinza padrao de desabilitado do tema nao
aparecia: o campo continuava com a mesma cara de um campo liberado. Como o
pedido e justamente que fique visivel que nao da para digitar, foram adicionadas
regras com opacidade e cursor. Medido no navegador, aplicando `disabled` num
campo real:

| Elemento | Normal | Desabilitado |
|----------|--------|--------------|
| Campo da chave (opacity) | 1 | 0.45 |
| Botao (opacity) | 1 | 0.4 |
| Botao (cursor) | pointer | not-allowed |

O `help` do campo tambem muda quando bloqueado, de "Solicite a chave diaria a
coordenacao" para "Bloqueada por excesso de tentativas. Aguarde a janela."

### Aviso do bloqueio: independente do perfil, e por que

O aviso **nao** esta amarrado a `chave_bloqueada`, e sim a
`ratelimit.excedeu(...)` direto. Motivo: com `clear_on_submit` (abaixo) o
`selectbox` volta para "Aluno" depois do envio. Um aviso amarrado ao perfil
sumiria junto, e o formulario reapareceria **habilitado** com o bloqueio ainda
valendo no modulo: o usuario veria o campo ativo, digitaria, selecionaria
Professor, e o campo desabilitaria na mao dele.

Isso cria um efeito colateral que precisou de ajuste: como o aviso aparece para
todos, um Aluno que nunca errou a chave via um aviso que parece bloqueio sobre
ele. O texto foi reescrito para dizer que vale so para o cadastro com chave:

> Chave do Professor bloqueada por excesso de tentativas. Vale so para o cadastro
> com chave, nao afeta o Aluno. Tente de novo em 5 minutos.

Verificado: com o contador estourado, o Aluno cadastra com sucesso e mesmo assim
ve o aviso, agora com o texto que impede a confusao.

| Estado | Aviso | Chave desabilitada | Botao desabilitado | Aluno cadastra |
|--------|-------|--------------------|--------------------|----------------|
| Perfil Aluno | sim | nao | nao | sim |
| Perfil Professor | sim | **sim** | **sim** | nao se aplica |

### Formulario limpo apos envio (`clear_on_submit`)

`st.form` aceita `clear_on_submit=True`. Aplicado nos dois formularios, login e
cadastro, sempre, em qualquer envio.

Motivo alem do visual: a senha digitada fica no DOM do navegador enquanto o
formulario esta na tela. Como o app e uma ferramenta de seguranca digital, o
residuo da senha na tela e o tipo de coisa que nao deveria sobrar.

Custo aceito e real: quem erra a senha no login reescreve tambem o usuario, e
errar o e-mail no cadastro obriga a redigitar os seis campos. Alguem que prefera
so limpar a senha, ou so no sucesso, precisa mexer aqui.

**Aviso tecnico importante:** `clear_on_submit` nao e comportamento do script
Python. Em `streamlit/elements/form.py` a linha 209 e
`block_proto.form.clear_on_submit = clear_on_submit`, ou seja, o valor vai no
protobuf e e tratado pelo **frontend em React**. Consequencia pratica: o
`AppTest` nao consegue verificar esse comportamento, porque nao ha frontend. Foi
preciso conferir no navegador de verdade.

### Decisoes de projeto

- **Memoria de processo, nao `st.session_state`.** Em sessao, abrir outra aba
  zera o contador; seria contornavel com F5.
- **Nem no SQLite.** O contador e descartavel por definicao; gravar no banco
  transformaria tentativa de acesso em registro permanente. E o `.db` e
  versionado no Git e contem e-mails de alunos.
- **5 tentativas / 300s.** Cinco da para corrigir uma chave de 6 digitos errada
  sem tomar bloqueio por descuido.
- **Identificacao por cadeia de fallback:** `st.context.ip_address` ->
  `X-Forwarded-For` -> cookie `_streamlit_xsrf` -> `"anonimo"`. Em teste local
  nao existe IP nem header, entao sobra o cookie, que persiste entre abas ao
  contrario da sessao.
- **Teto de `MAX_CLIENTES = 5000`**, descartando os mais antigos, para o
  dicionario nao crescer sem fim.

### Verificacao (AppTest, mesmo cliente fixado)

| Cenario | Resultado |
|---------|-----------|
| 5 chaves erradas | Restam 4, 3, 2, 1, 0 |
| 6a tentativa | "Muitas tentativas de chave incorretas. Tente de novo em 5 minutos." |
| **Sessao nova (AppTest novo), mesmo cliente** | **continua bloqueado** |
| Sessao nova como Aluno, contador estourado | nao bloqueia, cadastro passa |
| Contador zerado + chave correta | cadastra |

A terceira linha e a prova de que o estado e de processo e nao de sessao: um
`AppTest` novo e uma sessao Streamlit nova, e o bloqueio persiste.

Uma aresta que verificada e nao um bug: se o bloqueio fosse verificado antes de
tudo, um Professor que acertou a chave mas errou a forca da senha ficaria preso
sem poder corrigir. Nao acontece, porque o contador so sobe no branch da chave:
quem acerta a chave nunca passa por ele. Registrado porque e o tipo de detalhe
que alguem "corrige" depois e quebra o fluxo.

---

## Causa raiz do item 5 (menu do Administrador)

O apontamento dizia que o Administrador caia no menu do Aluno. A causa real era
mais larga, e nao era o `if/else` do `app.py`:

- `verificar_login` fazia `SELECT nome, password` — nunca buscava `tipo`.
- `login.py` gravava `usuario_logado` e `nome_usuario` na sessao, mas
  **nunca `tipo_usuario`**.

Entao `tipo_usuario` ficava `""` para todo mundo logado, e o `app.py` caia no
`else` para qualquer perfil. Nao era so o Administrador: **ninguem recebia o
menu correto**, nem o Professor. O `if/else` do menu era a consequencia, nao a
causa.

Consequencia adicional: `render_admin()` em `login.py` tem a guarda
`if st.session_state.get("tipo_usuario") != "Administrador": st.error("Acesso
negado")`. Com o perfil nunca gravado, essa funcao negava acesso **sempre**, para
todo mundo. A correcao do perfil destravou essa guarda tambem.

### Segundo bug, nao listado por ninguem

O bloco de conteudo do `app.py` so tratava as tres paginas do Aluno. Um
Professor que clicasse "Painel Geral" nao recebia nada — nem o titulo, porque
nenhum `if/elif` casava. So que corrigir o menu sem isso trocaria um menu
errado por um menu que nao abre nada.

Corrigido: as 6 paginas foram escritas, 3 por perfil. Verificado que as 9
combinacoes (3 perfis x 3 paginas) renderizam conteudo.

### Verificacao

| Perfil | `tipo_usuario` na sessao | Menu |
|--------|--------------------------|------|
| admin | `Administrador` | Painel da Coordenacao, Gerenciar Aulas, Notas dos Alunos |
| professor | `Professor` | Painel Geral, Gerenciar Aulas, Notas dos Alunos |
| aluno | `Aluno` | Painel Principal, Sessoes Interativas, Meu Progresso |

Todas as 9 paginas renderizam titulo proprio. Antes, so as 3 do Aluno tinham.

---

## Item 3 (e-mail unico): feito, e eu tinha errado no prognostico

Eu havia dito que isso exigiria recriar a tabela, porque o SQLite nao tem
`ALTER TABLE ... ADD CONSTRAINT`. Isso e verdade para *constraint*, mas existe
`CREATE UNIQUE INDEX`, que aplica a mesma restricao sobre a tabela existente sem
recriá-la nem tocar nos dados. Uma linha, nao uma migracao destrutiva. O
diagnostico estava exaggerando o esforco.

```python
try:
    c.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_usuarios_email ON usuarios (email)")
except sqlite3.IntegrityError:
    pass
```

E um indice unico, nao uma constraint na definicao da tabela, porque o
`CREATE TABLE IF NOT EXISTS` de `criar_tabelas()` e inerte para banco existente
(o schema real tem as colunas em ordem `username, nome, password, email, tipo`,
diferente do `CREATE`, o que mostra que a tabela foi montada por `ALTER TABLE`
depois). O `try/except` e deliberado: o indice e defesa em profundidade, a
checagem do formulario e o caminho normal. Se algum dado antigo impedir o
indice, o app continua funcionando pela checagem, em vez de quebrar na
inicializacao.

### Mensagem de erro correta

`cadastrar_usuario` devolvia `True`/`False` e capturava qualquer
`sqlite3.IntegrityError` como `False`. A tela acabava dizendo "Este nome de
usuario ja esta em uso" para qualquer violacao, inclusive e-mail repetido.

Agora devolve o motivo: `"ok"`, `"usuario_duplicado"` ou `"email_duplicado"`.
A checagem de conflito acontece antes da gravacao, para poder dizer qual foi. O
`except` continua tratando `IntegrityError` como e-mail duplicado, que e o caso
de corrida entre duas submissoes simultaneas.

Verificado:

| Cenario | Mensagem |
|----------|----------|
| Cadastro novo | "Conta criada com sucesso!" |
|Mesmo e-mail, usuario novo | "Este e-mail ja esta cadastrado nesta plataforma." |
| Mesmo usuario, e-mail novo | "Este nome de usuario ja esta em uso." |
| INSERT direto ignorando a checagem | barrado pelo indice: `UNIQUE constraint failed: usuarios.email` |

---

## CSS do login: restaurado e medido

Corrige o item 4 (fundo branco com texto branco no tema noturno do Streamlit).

Mudancas em relacao ao CSS original:

- Cartao branco (`#ffffff`) trocado por `#161a23`, com borda translucida.
- `st.title()` nao aceita classe. O titulo passou a ser emitido com
  `st.markdown` e `p.login-title`, que o CSS consegue estilizar.
- O seletor do botao (`div.stButton > button`) estilizava todos os botaos do
  app. Agora e restrito ao botao do formulario.
- Breakpoints em 768px, 480px e 360px, mais `prefers-reduced-motion`.

### Medicoes no navegador

Media queries respondem a largura do iframe, entao cada largura foi medida em um
iframe separado.

| Largura | Overflow | Botao | Campo | Fonte campo | Fonte botao | Aba | Titulo | Padding cartao |
|---------|----------|-------|-------|-------------|-------------|-----|--------|----------------|
| 320px   | nao      | 259px | 259px | 16px | 16px | 44px | 20px | 17.6px |
| 390px   | nao      | 329px | 329px | 16px | 16px | 44px | 22px | 17.6px |
| 768px   | nao      | 686px | 686px | 14px | 16px | 40px | 26px | 24px |
| 800px   | nao      | 702px | 702px | 14px | 16px | 40px | 30px | 32px |

Nas quatro larguras: zero overflow horizontal, botao com exatamente a mesma
largura do campo, 16px de fonte nos campos no mobile (evita o zoom automatico do
iOS), rotulo mais longo quebrando em 2 linhas sem corte.

Altura do botao: 48px no celular, 44px no tablet, 48px no desktop.

### O que a validacao encontrou depois de aparentemente estar pronta

Tres defeitos que so apareceram na medicao, nao na leitura do codigo:

1. **O botao nao ocupava a largura do campo.** Causa: o Streamlit encolhe o
   container do botao de proposito, para o botao abracar o rotulo. Entao
   `width: 100%` no proprio botao e 100% dos 68px que ele ja ocupava, uma
   circularidade. Corrigido forcando `width: 100%` no
   `[data-testid="stElementContainer"]` do formulario.

2. **Regra morta do selectbox.** O CSS usava `div[data-baseweb="select"]`, que
   nao existe nesta versao do Streamlit. A regra nunca casou e o selectbox ficava
   com a cor padrao, destoando dos campos de texto. Trocado por
   `[data-testid="stSelectbox"] [role="group"]`.

3. **`border-color` de foco sem efeito.** A regra casava, mas a cor da borda
   continuava a do Streamlit, com ou sem `!important`. A propriedade foi removida
   e ficou apenas o `box-shadow`, que aparece e some com o foco:
   `rgba(99, 102, 241, 0.25) 0px 0px 0px 3px` com foco, `none` sem.

Nota sobre checagem de seletor: `querySelector` nao consegue casar
`:focus-within`, porque e um estado e nao uma estrutura. Uma checagem que marca
esse seletor como "morto" esta errada. A prova de que a regra esta viva e a
medicao do `box-shadow` nos dois estados.

### Risco aceito

Todo o CSS depende de `data-testid` do Streamlit, que nao e API publica. O
defeito do `data-baseweb` e a prova de que isso ja quebrou: a regra casou num
atributo que existia numa versao e nao existe na atual. Um upgrade do Streamlit
pode derrubar qualquer um desses seletores em silencio, sem erro, so a aparencia
voltando ao padrao. Os seletores estao listados aqui por isso: se a tela
destoar depois de um upgrade, a lista de verificacao esta no mesmo lugar que a
regra.

---

## Como testar este app (aprendido na pratica)

**`AppTest` e a ferramenta certa para formulario, nao o navegador.** O Streamlit
1.64 usa react-aria, e o `selectbox` nao abre no browser headless: clicar no
`[role="combobox"]` nao expande, o `listbox` que aparece vem vazio e nenhum
elemento com o texto "Professor" existe no DOM. Digitar no campo escreve o texto
na tela mas **nao commita o estado do widget**: o form continua submissando como
"Aluno" e o cadastro passa sem chave nenhuma. Gastar mais tentativas nisso nao
rende.

`streamlit.testing.v1.AppTest` executa o script e expoe os widgets por indice:

```python
at = AppTest.from_file("app.py", default_timeout=30).run()
at.selectbox[0].set_value("Professor")
at.text_input[4].set_value("000001")
at.button[1].click().run()
[e.value for e in at.error]
```

Indices neste app: `text_input` 0 Usuario, 1 Senha, 2 Nome Completo, 3 Nome de
Usuario, 4 Chave, 5 E-mail, 6 Confirme, 7 Nova Senha. `button` 0 Entrar,
1 Finalizar Cadastro. `selectbox` 0 Perfil de Acesso.

**Cuidado com o rate limit no AppTest:** cada `AppTest` e um cliente diferente,
porque nao ha `st.context.ip_address` nem cookie. O contador nunca chega a 5 e
os testes passam a parecer inconsistentes ("Restam" oscilando em vez de descer).
Para testar o mesmo cliente, fixar o identificador:

```python
ratelimit._identificar_cliente = lambda: 'cliente-de-teste'
```

Isso nao enfraquece o teste da ligacao em `login.py`, que e o que importa aqui. A
identificacao de cliente foi verificada separadamente, por sonda: em teste local
`st.context.ip_address` e `None`, nao ha `X-Forwarded-For`, e o unico header
identificador e o cookie `_streamlit_xsrf`.

**`AppTest` nao ve comportamento de frontend.** Dois casos nesta etapa:

- `clear_on_submit` — gravado no protobuf, tratado pelo React. O `AppTest` reporta
  os campos ainda preenchidos depois do envio, o que parece falha mas e ausencia
  de frontend. Precisa de navegador.
- O `selectbox` tambem nao e driveavel pelo navegador (react-aria, ver acima).
  Aqui a distribuicao e o contrario: `AppTest` e o que resolve, porque
  manipula o widget sem passar pelo DOM.

Regra pratica: `AppTest` para logica de formulario e estado; navegador para CSS,
`clear_on_submit` e qualquer coisa que o React fa.

**O navegador continua sendo o ferramenta certa para CSS**, porque media query
responde a largura do iframe, e uma largura por chamada.

---

## Lista de usabilidade para a Beta: o que falta

| # | Apontamento | Estado |
|---|-------------|--------|
| 1 | Chave diaria exposta | pendente (uma linha) |
| 2 | Chave sempre visivel no cadastro do Aluno | pendente |
| 3 | E-mail sem UNIQUE | **feito** |
| 4 | Dark mode | **feito** |
| 5 | Menu do Administrador | **feito** (causa raiz era outra) |
| 6 | Credenciais no codigo | bloqueado |

### Pendencias com armadilha conhecida

**Item 1.** `login.py`, o `st.info` publico com a chave do dia.

**Item 2.** Se o campo da chave virar condicional, `chave_prof_input` deixa de
existir quando o perfil e Aluno, e a linha de validacao o referencia. Estoura
`NameError` justamente no caminho do Aluno. Precisa de um `else` com valor padrao.

**Item 6.** `garantir_usuario_admin()` tem `"Admin123!"` na linha 17 e
`criar_tabelas()` tem na linha 57. A primeira funcao e **codigo morto**, nunca
chamada. Trocar so uma deixa a senha no arquivo. O `.gitignore` **ja** tem
`.streamlit/secrets.toml` e `.env`, entao essa parte do pedido ja esta feita. A
senha em texto puro so e necessaria no primeiro boot, para criar o admin.

### Bloqueios

**Onde o app vai rodar?** Sem resposta desde o inicio. `st.secrets` funciona no
Streamlit Community Cloud e localmente com `secrets.toml`; em servidor proprio
sem configuracao ele simplesmente nao existe. Dotenv e o outro caminho e se
comporta diferente. Nao ha `requirements.txt` nem config de deploy no
repositorio, entao nao da para deduzir. Escolher errado quebra o primeiro boot
em producao.

**Branch.** O `CONTRIBUTING.md` (branch `roberto`) exige branch propria e proibe
commit direto na `main`. Estamos em `main`, sem branch criada.

## O rate limit funciona, mas nao protege (verificado no navegador)

Relato de que "o brute force protection nao esta funcionando". Investigado em vez
de discutido. O mecanismo esta correto, e a ultrasonancia esta em outro lugar.

### O contador funciona de verdade

Testado no navegador real, sem monkeypatch, com o identificador de cliente
verdadeiro do browser. Escolhendo "Professor" por teclado (ver abaixo por que o
mouse nao serviu) e mandando chave errada:

| Tentativa | Mensagem |
|-----------|----------|
| 1 a 5 | Restam 4, 3, 2, 1, **0** |
| 6 | "Chave do Professor bloqueada por excesso de tentativas." |

Na 6a, com o perfil em Professor, o campo da chave e o botao ficam
`disabled = true`, medido no DOM. O `AppTest` ja indicava isso antes; agora
tambem o navegador.

### Por que, entao, "nao funciona": o bloqueio e por cookie

Unico identificador disponivel localmente e o cookie `_streamlit_xsrf` (medido:
`st.context.ip_address` vem `None`, nao ha `X-Forwarded-For`). O cliente controla
esse cookie. **Limpar o cookie zera o contador.**

Verificado: bloqueado com o cookie `2|0dc69f8e|...`, cookie expirado, pagina
recarregada, cookie novo `2|9a607a7b|...`, e a proxima chave errada respondeu
**"Restam 4 tentativa(s)"**. Contador cheio de novo, um minuto depois do bloqueio.

Ou seja: **5 tentativas por cookie, cookies ilimitados.** Como controle de
seguranca contra forca bruta isso nao segura ninguem; so atrapalha quem digita a
chave errada por distração. Ja estava registrado como risco aceito quando o
identificador foi escolhido, mas a magnitude ("ilimitado", e nao "facil de
contornar") nao tinha sido medida.

### A chave e mostrada na propria tela

`login.py:427` tem `st.info(f"Chave válida hoje: **{chave_valida_hoje}**")`, e
`login.py:54` tem `st.metric(label="Chave Válida Hoje", value=chave_hoje)`. As
duas linhas aparecem para qualquer visitante, na aba de cadastro, antes de
qualquer digitacao. O valor tambem foi lido na tela durante o teste: "Chave
valida hoje: 821104".

Enquanto a chave for exibida, **nao ha segredo a adivinhar** e o limite de
tentativas protege uma coisa que o proprio app entregou. Este e o item 1 da
lista da Beta, e ele e anterior ao rate limit: sem fechar a exibicao, o rate
limit e enfeite.

Ordem correta de trabalho: esconder a chave, depois o rate limit faz sentido.

### O selectbox nao renderiza a opcao "Professor" (neste ambiente)

Achado incidental, e relevante: sem conseguir selecionar "Professor", o branch
da chave e inalcancavel, e o rate limit inteiro nunca dispara.

Medido com o dropdown aberto:

| Elemento | Valor |
|----------|-------|
| combobox | 764 px de largura |
| listbox | 796 x 80 (cabe 2 opcoes de 40 px) |
| wrapper interno do virtualizador | **width 0**, height 80 |
| opcoes renderizadas | 1, e com 10 px de largura |

O wrapper interno da colecao tem `style="width: 0px"` inline. O react-aria sabe
que sao duas opcoes (`aria-setsize="2"`, `aria-posinset="1"`) e a caixa externa
esta dimensionada para duas, mas so o primeiro item e renderizado, e ele sai com
a largura do texto.

**Nao e o CSS deste projeto.** Removi o `<style>` inteiro da pagina e reabri: o
dropdown continuou com so "Aluno".

**A opcao existe e da para selecionar por teclado.** Com o dropdown aberto,
`ArrowDown` move `aria-activedescendant` para `option-1` e `Enter` comita:
`valor: "Professor"`. Foi assim que o teste de forca bruta acima ficou possivel.

**Nao da para confirmar se acontece num navegador visivel.** `browser.screenshot`
exige aba visivel e este ambiente nao tem desktop, entao a confirmacao visual
ficou de fora. O que da para afirmar: e falha de medicao do virtualizador
(wrapper com 0 px), o dado chega certo no frontend, e o item e selecionavel por
teclado. Se o usuario precisa de mouse, ele nao consegue escolher Professor.

Candidatos a causa, sem hierarquia: virtualizador do react-aria medindo o popover
antes do layout, ou o popover de `st.selectbox` no Streamlit 1.64. Se for para
investigar, o caminho e trocar o `selectbox` por `st.radio` (que nao virtualiza
opcoes) e ver se o sumico de "Professor" continua.

### Os dois problemas nao sao o mesmo

Desenhar isso aqui porque e facil conflacionar. O rate limit funciona e e
verificavel. O que ele protege tem valor zero enquanto a chave estiver na tela.
E o caminho para chegar nesse branch pode estar fechado no dropdown. Tres coisas
separadas, e so a primeira foi o que foi pedida.

### O README reescrito nao esta no disco

Ao varrer os arquivos depois da investigacao da forca bruta, `README.md` apareceu
com **2 linhas** e `git diff HEAD -- README.md` vazio, ou seja, identico ao
commitado. A versao de 156 linhas descrita nesta sessao nao chegou a ficar no
arquivo, ou foi sobrescrita em 25/09 18:04:52.

Data de escrita dos arquivos, para comparar:

| Arquivo | Escrito | Linhas |
|---------|---------|--------|
| `README.md` | 25/09 18:04:52 | 2 |
| `modules/ratelimit.py` | 25/09 18:06:33 | 149 |
| `app.py` | 26/09 06:11:59 | 82 |
| `modules/database.py` | 26/09 06:16:40 | 150 |
| `modules/login.py` | 26/09 06:58:42 | 427 |
| este diario | 26/09 07:10:17 | 532 |

O resto do trabalho da Beta persistiu. O README e o unico arquivo que nao
confere. Nao foi reescrito aqui de proposito: algo externo escreveu nesse
arquivo em 25/09 e sobrescrever trabalho do usuario sem saber o que e o
contrario do combinado. Perguntar antes.

**Dois arquivos de modulo estao vazios (0 linhas):**
`modules/introducaoCriptografia.py` e `modules/mainmenu.py`. Nao foram tocados
nesta sessao. Se algum `import` os usa, quebra em tempo de execucao; se sao
restos, deletar.

## Rate limit no login: aplicado, e o que ele de fato segura

O login nao tinha limite nenhum. `verificar_login` respondia
`st.error("Usuário ou senha incorretos.")` sem contar nada, entao forca bruta de
senha era ilimitada. O modulo ja era generico por causa do parametro `acao`; a
correcao foi so ligar a acao nova.

`ratelimit.LOGIN = "login"` em `modules/ratelimit.py`, e em `login.py`:
`login_bloqueado` (297), aviso (299), botao desabilitado (305), bloqueio no topo
da cadeia (310), `zerar` no acerto (334), `registrar_falha` na falha (341) e
`restantes` na mensagem (344).

Os dois limites sao chaves separadas no mesmo dicionario, entao nao se atrapalham.
Verificado: com o login estourado a chave segue intacta e o botao "Finalizar
Cadastro" continua habilitado, e vice-versa. Os avisos tambem nao se misturam.

**A 6a tentativa e fisicamente impossivel, nao so barrada.** O `AppTest` recusa
clicar em botao desabilitado (`Cannot update a disabled button widget`), e o
navegador faz o mesmo. Diferente da chave, onde o `clear_on_submit` devolve o
perfil para "Aluno" e reabilita o botao, no login o bloqueio nao depende de
perfil: o botao fica desabilitado ate a janela fechar.

Medido no navegador, cookie real, sem monkeypatch: Restam 4, 3, 2, 1, 0.
Campos limpos apos cada envio.

O que **nao** conta como tentativa, por decisao: campo vazio. `elif not
(usuario_input and senha_input)` vem antes de qualquer consulta, entao
"Por favor, preencha o usuário e a senha." e o contador continua em 5. Isso
evita que um formulario com o usuario em branco e a senha errada consuma a
janela de um usuario legitimo. Usuario inexistente **conta**, igual a senha
errada: a tela nao distingue os dois casos e o limitador nao deve virar
oraculo de quem existe.

## Descoberta que muda o valor do controle: F5 zera o contador

Isto corrige a avaliacao feita antes nesta sessao, onde eu escrevi que o
problema era "limpar o cookie".

Medido, no navegador:

| Acao | Cookie `_streamlit_xsrf` | Contador |
|------|--------------------------|----------|
| 3 tentativas de login | `2\|8da4350c\|4c44f68...` | Restam 2 |
| F5 (reload) | `2\|e382bcc3\|22627f4...` | **Restam 4** |

O cookie **nao** rotaciona durante o uso normal (medido: `rotacionouDurante:
false` em 3 envios seguidos). Ele rotaciona **a cada carregamento de pagina**.
Cada F5 produz uma identidade de cliente nova, e a identidade nova nasce com o
contador cheio.

Ou seja: nao e preciso limpar cookie, e so recarregar. Isso e banal, e acontece
por acidente quando a conexao cai.

**Conclusao corrigida:** o que foi entregue e 5 tentativas por carregamento de
pagina. Contra pessoa digitando a mao, atrapalha um pouco. Contra ataque
automatizado, nao segura nada. A frase "5 tentativas por cookie, cookies
ilimitados" que escrevi mais acima neste diario era otimista demais: nao e por
cookie, e por carga de pagina, que e ainda mais facil de multiplicar.

### O que resolve, e o custo

A correcao nao e melhorar o identificador de cliente, e **mudar a chave do
contador de cliente para o nome de usuario sendo atacado**. O campo `usuario`
nao muda com F5, nao muda com cookie e nao muda com aba. Medido: o
identificador de cliente sobe com cada carregamento; o usuario digitado nao.

Um contador por conta daria 5 tentativas por conta a cada 5 minutos, com o
atacador variando cookie, recarregando e abrindo aba o quanto quiser. E
continua sem depender de IP, o que importa num colegio, onde muitos alunos
saem do mesmo NAT.

**O custo real disso e negacao de servico contra a conta:** qualquer um pode
trancar o login de um colega que sabe existir, de 5 em 5 minutos, sem nunca
saber a senha. A mitigacao e um limite por conta com janela maior e um contador
global por IP ao lado, o que exige IP, e IP localmente nao existe. Fica
registrado como trade-off, nao como solucao fechada.

Alternativa mais fraca e mais segura de doar: chave do IP quando existir, com o
cookie so como reserva. Sobrevive a F5, mas no deploy do colegio shared-NAT
passa a existir o problema inverso: um aluno trava todos os outros da mesma
rede. Nenhuma das duas e boa sozinha.

### Um ponto de usabilidade que ficou

Como nao ha "esqueci minha senha" nem liberating por e-mail, o bloqueio e duro:
no 5o erro a pessoa fica 5 minutos sem conseguir entrar **nem com a senha
certa**, porque o botao esta desabilitado. Para aluno que esqueceu a senha no
ultimo minuto, nao ha saida alem de esperar. Com 5 tentativas e janela de 5
minutos, o alvo e digito, nao uso real.

## Fora da lista, ainda aberto

- **`plataforma.db` esta versionado no Git e contem e-mails de alunos.**
  Exposicao de dado pessoal, maior que a senha hardcoded. Continua valendo.
- **O cadastro confirma quais usuarios existem** ("Este nome de usuario ja esta
  em uso"). O item 3 tornou a mensagem mais honesta, mas o vazamento de
  enumeracao continua: agora da para dizer tanto que o e-mail quanto que o
  usuario existem.
- **`render_admin()` e codigo morto** e duplica o que o `app.py` faz no painel
  da Coordenacao. Duas copies da mesma tela, uma delas nunca chamada.
- **Item 4: o gatilho nao e o sistema operacional**, e o tema do Streamlit, que
  por padrao segue o SO.

Observacao factual: o item 6 contraria a decisao anterior de reverter o trabalho
da chave. A justificativa mudou, agora e pedido da equipe para a Beta, o que e
motivo legitimo. So para deixar a troca registrada.

---

# Rodada 2 — o F5, a tela travada, e os itens 1, 2 e 6

Escopo acordado: os dois defeitos de rate limit que sobraram, os tres itens
pendentes da lista da equipe, o README e este diario.

## O F5 nao zera mais o login (corrigido, medido)

O problema ja estava diagnosticado acima: o identificador de cliente e o
cookie XSRF, que rotaciona a cada carga de pagina. A solucao proposta ali
— trocar a chave do contador de cliente para o nome de usuario — foi
implementada, com uma correcao importante que a proposta original nao tinha.

### Por que um alvo so nao bastava

So o alvo nao segura contra **varredura**: o ataque de tentar uma senha em
muitas contas, uma tentativa em cada. Com 300 contas na escola, sao 300
palpites por janela, que e pior que 5 tentativas contra uma conta. So o
cliente nao segura contra F5. Cada um falha de um jeito, entao o login conta
nos dois e barra se qualquer um dos dois estourar.

Medido no `AppTest`, com o cliente fixado:

| Cenario | Resultado |
|---|---|
| 5 erros na mesma conta | bloqueado, botao `disabled` |
| cliente novo (F5), mesma conta | **continua bloqueado** |
| conta que nunca errou, mesmo cliente | liberada, "Restam 4" |
| `ADMIN` maiusculo | bloqueado |
| `  admin  ` com espaco | bloqueado |
| 5 contas distintas, 1 tentativa cada, mesmo cliente | cliente bloqueado na 6a |

As tres ultimas linhas sao o motivo de `_alvo_da_conta` normalizar com
`strip().lower()`: sem isso o limite seria contornavel so mudando a
capitalizacao do campo de usuario, o que nao exige nenhuma ferramenta.

### A mudanca no modulo

`ratelimit.py` ganhou um parametro opcional `alvo` nas quatro funcoes
(`excedeu`, `registrar_falha`, `zerar`, `restantes`), resolvido em
`_montar_chave`. Sem `alvo`, o comportamento e o de antes: chave do cliente.
Com `alvo`, a chave e a do alvo. A acao da chave do Professor continua
sem `alvo`, ou seja, inalterada.

`login.py` ganhou tres funcoes privadas: `_alvo_da_conta`, `_chave_cliente` e
`_situacao_login`, que devolve `(barrado, sobra, alvos)`. A sobra mostrada e o
**minimo** entre os dois alvos, que e a resposta honesta a "quantas ainda
tenho": mostrar so a da conta esconderia que o cliente esta no fim.

## A tela travada: `st.fragment(run_every=...)`

Este era o segundo defeito, e o diagnostico estava no diario acima: nao
existia rerender automatico, so dois `st.rerun()` manuais, e `st_autorefresh`
nao estava instalado. Medido antes: 20 s parado davam DOM identico byte a
byte. O app nao tem como avisar que a janela venceu, e a reacao natural a uma
tela travada e F5 — que e justamente o que zerava o contador. Os dois
sintomas eram o mesmo defeito.

Solucao: o formulario de login virou uma funcao decorada com
`@st.fragment(run_every="5s")`. `st.fragment` existe nativamente no
Streamlit 1.64 (assinatura conferida: `run_every: int | float | timedelta |
str | None`), entao **nao acrescenta dependencia**.

Medido no navegador, sem nenhuma interacao, 20,5 s de amostragem a 200 ms:

```
reruns em ms:  2838, 7767, 12856, 17789
intervalos:    4929, 5089, 4933
```

Quatro reruns espontaneos, intervalo de 4,9 a 5,1 s. Antes: zero.

Risco avaliado antes de aplicar: `st.rerun()` dentro de um fragmento. O
`st.rerun()` do login bem-sucedido esta dentro do fragmento. Se isso
quebrasse, o login pararia de funcionar, e nao apareceria em nenhum teste de
`AppTest` que so olhasse estado. Verificado no navegador, na secao de testes
abaixo.

## Item 1 — a chave do dia sumiu da tela publica

Dois pontos de exibicao, ambos removidos:

- `login.py:459` — `st.info(f"Chave valida hoje: **{chave_valida_hoje}**")`, na
  aba de cadastro, visivel para qualquer visitante antes de digitar qualquer
  coisa.
- `login.py:35-56` — `render_admin()`, que tinha
  `st.metric(label="Chave Valida Hoje", value=chave_hoje)`.

O `render_admin()` foi **apagado**, nao comentado, com o motivo registrado no
docstring que ficou no lugar. Ele era codigo morto: `app.py` importa apenas
`render_login` e `obter_chave_professor_diaria`. O que ele fazia de util ja
existe em `app.py:55-57`, dentro do `Painel da Coordenacao`, que e item de menu
do Administrador e portanto exige login.

Por que os dois juntos: enquanto qualquer um dos dois existisse, a chave do dia
estava legivel por quem nao devia, e **o rate limit da chave nao protegia
nada, porque nao havia o que adivinhar**. O limite so ganha sentido depois
disto. A ordem estava errada no projeto: a correcao do item 1 e pre-requisito
para o rate limit da chave valer alguma coisa.

Verificado: nenhum texto com a chave na tela publica.

## Item 2 — o campo da chave so aparece para Professor

O campo era renderizado sempre, para os dois perfis. A correcao nao e um `if`
simples: **dentro de `st.form` o Streamlit agrupa tudo e nada redesenha ate o
envio**, entao condicionar dentro do formulario so valeria *depois* de enviar,
que e pior que mostrar sempre.

Solucao: o `selectbox` de perfil foi movido para fora do `st.form`, e o campo
da chave ficou logo abaixo dele, ainda fora do formulario.

```python
tipo_usuario_input = st.selectbox("Perfil de Acesso", ["Aluno", "Professor"], key="perfil_cadastro")
chave_prof_input = ""          # default antes do if
if tipo_usuario_input == "Professor":
    chave_prof_input = st.text_input("Chave de Verificacao de 6 digitos", ...)
else:
    chave_bloqueada = False
```

O default `chave_prof_input = ""` antes do `if` e obrigatorio: a cadeia de
validacao mais abaixo le esta variavel em todos os caminhos, e sem o default o
perfil Aluno levanta `NameError` — exatamente no caminho que acabamos de
tornar possivel.

### Efeito colateral que resolveu um bug antigo

`clear_on_submit` so limpa widgets **dentro** do form. Com o `selectbox`
dentro, o perfil voltava para "Aluno" depois de cada envio. Era por isso que o
aviso de bloqueio da chave precisava ser amarrado a `ratelimit.excedeu(...)`
e nao a `chave_bloqueada`: com o perfil resetado, um aviso amarrado ao perfil
sumiria junto e o formulario reapareceria habilitado com o bloqueio ainda
valendo no modulo.

Fora do form, o perfil **sobrevive ao envio**, e o aviso pode ficar amarrado a
`chave_bloqueada` normalmente. Medido no navegador: perfil `Professor` antes e
depois do envio, com os 5 campos do form limpos.

O texto do aviso continua dizendo "Vale so para o cadastro com chave, nao
afeta o Aluno", porque o limite e mesmo da chave.

## Item 6 — credenciais no codigo

Duas copias da senha `"Admin123!"`:

1. `database.py:17`, em `garantir_usuario_admin()` — **funcao morta**, nunca
   chamada por ninguem. Apagada.
2. `database.py:71`, em `criar_tabelas()` — a copia viva, chamada por
   `app.py:9`. Esta foi para `st.secrets`.

```python
def _senha_admin_inicial():
    try:
        return st.secrets["ADMIN_SENHA"]
    except Exception as erro:
        raise RuntimeError("Falta ADMIN_SENHA no gerenciador de segredos. ...") from erro
```

**Sem valor padrao no codigo, de proposito.** Um `return "Admin123!"` no
`except` seria a mesma senha com mais passos, e o `except` e justamente o
caminho que roda quando ninguem configurou nada.

### Por que isso nao quebra o app

A senha e lida **so no ramo em que o banco ainda nao tem o admin**. Como o
`plataforma.db` do repositorio ja tem, essa linha nao executa em uso normal, e
a ausencia do `secrets.toml` nao impede o app de rodar. Quem recriar o banco
do zero precisa criar o arquivo.

`st.secrets` le `.streamlit/secrets.toml` no Community Cloud, local e em
self-hosted, entao o caminho de leitura e o mesmo nos tres casos. O
`.gitignore` **ja** tinha `.streamlit/secrets.toml` e `.env` — o requisito da
equipe ja estava satisfeito, faltava so o arquivo do lado do app. Acrescentei
`.streamlit/secrets.example.toml` como modelo.

### A decisao que tomei sem pergunta

O usuario nao respondeu a pergunta sobre a semente `chaveDev2026`. **Movi so a
senha do admin e deixei a semente no codigo**, conforme a recomendacao que
tinha dado. O motivo: a semente nao e segredo de ninguem. Ela deriva um
numero de 6 digitos que o app inteiro imprime para a coordenacao de qualquer
forma e que muda todo dia. A senha do admin e credencial real, de um usuario
que existe. Tratar as duas como o mesmo tipo de segredo seria exaggerar o
risco. Registrado aqui porque foi decisao minha, nao dele.

### O `.gitignore` nao ignorava o segredo (furo de verdade)

Achei isto conferindo, nao lendo. O `.gitignore` termina com:

```
.streamlit/secrets.toml
```

Padrao com barra **no meio** e ancorado na raiz do repositorio. O `.streamlit`
deste projeto esta em `projectAppUFBA/`, nao na raiz. Confirmedo:

```
$ git check-ignore -v projectAppUFBA/.streamlit/secrets.toml
(saida vazia — nao casou)
```

Ou seja: a regra que eu tinha dado por satisfeita, e que o diario registrou
como "o requisito da equipe ja esta satisfeito", **nao ignorava nada**. Quem
criasse o `secrets.toml` com a senha do admin e rode `git add .` subiria a
senha do banco de producao para o repositorio. Era exatamente o item 6 que
esta lista de correcoes diz ter resolvido, e o buraco estava na linha que
comprovava a resolucao.

Corrigido para `**/.streamlit/secrets.toml`, que casa em qualquer nivel:

```
$ git check-ignore -v projectAppUFBA/.streamlit/secrets.toml
.gitignore:222:**/.streamlit/secrets.toml	projectAppUFBA/.streamlit/secrets.toml
```

E conferi que o `secrets.example.toml` **nao** passou a ser ignorado junto,
porque ele e a documentacao do que o app espera e nao tem valor secreto.

Licao: "esta no `.gitignore`" so vale se alguem rodou `git check-ignore` no
caminho real do arquivo. A regra parecia certa e nao pegava nada.

## Verificacao no navegador

O `AppTest` serve para logica de formulario e estado; CSS, `clear_on_submit` e
`run_every` sao coisa de frontend e so o navegador prova. Medi no navegador de
verdade, sem monkeypatch:

| O que | Resultado |
|---|---|
| Perfil Aluno | 5 campos, **sem** campo da chave |
| Troca para Professor | campo da chave aparece **antes de enviar** |
| Volta para Aluno | campo some |
| Cadastro Aluno completo | "Conta criada com sucesso" |
| Cadastro Professor, chave certa | "Conta criada com sucesso" |
| Cadastro Professor, chave errada | erro + "Restam 4" |
| 5 chaves erradas | campo e botao `disabled`, 6a impossivel |
| Aluno com a chave bloqueada | cadastra normal, botao habilitado |
| Envio do cadastro | 5 campos limpos, perfil **preservado** |
| 5 logins errados | "bloqueado", botao `disabled` |

### Um detalhe que custou uma investigacao

Na primeira leitura o `selectbox` apareceu marcado como "Professor" num
perfil novo, o que sugeria bug no default. **Nao era bug do codigo:** o Chrome
restaurou o valor do `<input>` de uma navegacao anterior. Depois do F5 o
perfil voltou para "Aluno" e o campo da chave desapareceu, como deve ser. Fica
registrado porque a leitura errada do DOM seria um falso positivo se eu nao
tivesse conferido o `value` do input.

### O DOM confirma a mudanca de estrutura

Ordem dos elementos na aba "Criar Conta", medida:

```
stTabPanel (login) -> stSelectbox -> stTextInput (Chave) -> stForm (cadastro)
```

O `selectbox` e o campo da chave estao **fora** do `stForm`. Era o objetivo.

## O que continua aberto

- **O rate limit da chave do Professor segue sem solucao boa.** Nao ha "usuario
  sendo atacado" porque a conta ainda nao existe. So ha cookie (controlado
  pelo cliente) ou IP (no colegio, shared-NAT tranca a rede inteira). Agora que
  a chave parou de ser exibida, o limite tem alguma coisa para proteger, mas o
  identificador continua ruim. Registrado como trade-off.
- **A negacao de servico contra a conta e real.** Qualquer um tranca o login de
  um colega que sabe existir, de 5 em 5 minutos, sem nunca saber a senha.
  Mitigacao exigiria IP, que nao existe localmente.
- **O `plataforma.db` continua versionado com e-mails de alunos.** Maior
  exposicao de dado pessoal que a senha hardcoded, e intocado.
- **O cadastro confirma quais usuarios existem.** Piorou com o item 3.
- **`modules/introducaoCriptografia.py` e `modules/mainmenu.py` continuam com 0
  byte.** Nenhum `import` os usa. Nao foram tocados.
- **Falta `requirements.txt`.** Nao ha no repositorio. Para deploy em outro
  lugar, `streamlit` e `bcrypt` precisam estar declarados em algum lugar.
- **O README foi reescrito** (o arquivo tinha 2 linhas, identico ao HEAD; a
  versao longa de uma sessao anterior nao estava no disco). A linha 2 deixa
  de dizer "via Aritmetica Modular", porque o codigo nao usa Aritmetica
  Modular em lugar nenhum.
