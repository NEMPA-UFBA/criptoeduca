# criptoeduca

Aplicativo gamificado para letramento digital e prevenção de golpes cibernéticos.
Projeto de Pesquisa (FENIC) — NEMPA/UFBA e Colégio Estadual Álpio Franca.

> **Nota sobre a linha de descrição:** a versão anterior do README dizia
> "via Aritmética Modular". O código do repositório não usa Aritmética Modular
> em lugar nenhum — nenhuma biblioteca de criptografia assimétrica, nenhum
> cálculo modular. O que existe é bcrypt para senhas e uma chave diária
> derivada por HMAC-SHA256. A descrição foi corrigida para não prometer uma
> técnica que o app não implementa.

---

## O que é

Uma plataforma educacional em Streamlit para uso no Colégio Estadual Álpio
Franca, com três perfis de acesso:

| Perfil | O que enxerga |
|---|---|
| **Aluno** | Painel principal, exemplos de crimes digitais (os pergaminhos), mural de criptografia, progresso, módulos |
| **Professor** | Painel geral, gerenciamento de aulas (publicação dos exemplos de crime), notas, mural, módulos |
| **Administrador** | Painel da coordenação, gerenciamento de aulas, notas, mural, módulos |

O cadastro de Professor exige uma **chave de 12 caracteres válida para o dia**,
distribuída pela coordenação dentro do sistema. Aluno se cadastra sem chave.

---

## Rodando

Requisitos: Python 3.10 ou superior.

```bash
# 1. Dependências
pip install streamlit bcrypt

# 2. Segredos (só é obrigatório se o banco ainda não tiver o usuário admin)
cp .streamlit/secrets.example.toml .streamlit/secrets.toml
# edite o ADMIN_SENHA no arquivo criado
# o CHAVE_SEGREDO é opcional, mas veja a seção "A chave do dia" abaixo

# 3. Subir o app
streamlit run app.py
```

O app abre em `http://localhost:8501`.

### Sobre o `.streamlit/secrets.toml`

O arquivo é lido pelo Streamlit automaticamente — no Community Cloud, local e
em self-hosted — e já está no `.gitignore`, então o valor de verdade nunca
entra no Git. O `secrets.example.toml` é a documentação do que o app espera.

A senha do `admin` é lida **uma única vez**: no primeiro boot, só se o banco
ainda não tiver esse usuário. Depois disso o que autentica é o hash bcrypt no
banco, e o segredo não é mais consultado. Como o `plataforma.db` do
repositório já contém o admin, o `secrets.toml` não é necessário para rodar
o app em uso normal.

Não existe senha padrão no código. Se o banco estiver vazio e o segredo
faltar, o app levanta `RuntimeError` explicando o que fazer, em vez de criar
um administrador com senha conhecida.

O `CHAVE_SEGREDO` é lido a **cada** execução, e é opcional: sem ele o app usa um
segredo padrão que está no código-fonte. A diferença é de segurança, não de
funcionamento — o app sobe dos dois jeitos. Enquanto o Painel da Coordenação
estiver exibindo o aviso de "chave derivada do segredo padrão", a chave do dia
é adivinhável por quem tiver uma cópia do repositório.

---

## Estrutura

```
projectAppUFBA/
├── app.py                     # roteamento por perfil e as seis páginas
├── plataforma.db              # SQLite (versionado)
├── .streamlit/
│   └── secrets.example.toml   # modelo do gerenciador de segredos
├── dados/
│   ├── modulos.json           # OS MÓDULOS — quem escreve o curso mexe aqui
│   ├── exemplos_crime.json    # OS EXEMPLOS DE CRIMES (os pergaminhos)
│   └── README.md              # como editar o JSON, passo a passo
├── static/
│   └── modulos/               # PDFs do material de cada módulo
└── modules/
    ├── login.py               # login, cadastro, validações, chave do dia
    ├── database.py            # conexão, tabelas, hash, verificação
    ├── ratelimit.py           # limitador de tentativas em memória
    ├── modulos.py             # leitor do JSON (dados, não layout)
    ├── exemplos_crime.py      # leitor dos exemplos de crime
    ├── mainmenu.py            # home dos módulos: o "Mapa de Missões"
    ├── paginaModulo.py        # página individual do módulo
    ├── leitura.py             # página de leitura: o botão que libera o quiz
    ├── quiz.py                # o quiz do módulo, com gabarito
    ├── pergaminhos.py         # os pergaminhos: exemplos de crimes digitais
    ├── estilo.py              # folha de estilo da identidade visual
    └── sessaoInterativa.py    # mural criptografado
```

### `dados/modulos.json`

**O manifesto dos módulos é um JSON, não um arquivo Python.** Quem escreve o
conteúdo do curso não precisa programar: abre o arquivo num editor de
texto, altera e salva. O arquivo vem comentado, com a explicação de cada
campo, e a documentação completa está em
[`dados/README.md`](projectAppUFBA/dados/README.md).

Cada módulo tem `slug`, `titulo`, `resumo`, `icone`, `nivel`,
`dificuldade`, `duracao`, `cor`, `pdf` e `quiz`. O `slug` serve para três
coisas ao mesmo tempo: chave do botão na tela, identificador na página e
nome do arquivo de PDF (`static/modulos/<slug>.pdf`).

O campo `certa` do quiz aceita o **número** da alternativa (contando a
partir de 1) ou o **texto** dela — o número é mais seguro para quem digita
à mão.

O quiz fica **fora** de `static/` de propósito: `static/` é servida
publicamente pelo Streamlit, e as respostas certas ficariam legíveis na URL.

**Erro no JSON não derruba o app.** O arquivo é lido a cada execução, os
comentários de linha inteira (`//`) são aceitos, e o que estiver errado
aparece na tela em português — com linha e coluna, no caso de erro de
sintaxe. Os módulos válidos continuam aparecendo normalmente.

Duas armadilhas do editor de texto já são tratadas pelo leitor, porque
atingem justamente quem edita o arquivo:

- **BOM** — o Bloco de Notas do Windows 11 grava três bytes invisíveis no
  começo do arquivo, e o `json.loads` recusaria o arquivo inteiro. O leitor
  usa `utf-8-sig`, que aceita com BOM e sem BOM.
- **ANSI / Windows-1252** — o Bloco de Notas antigo salva assim. O leitor
  tenta UTF-8 primeiro e, se falhar, lê em Windows-1252 e avisa na tela que o
  ideal é salvar em UTF-8.

### `modules/modulos.py`

Só o leitor: tira os comentários, faz o `json.loads`, valida cada módulo e
cada pergunta, e traduz os problemas para frases que a pessoa que editou o
arquivo entende. Devolve sempre duas coisas: a lista de módulos que puderam
ser lidos e a lista de problemas.

Um módulo quebrado é descartado, e os outros continuam aparecendo.

### `modules/mainmenu.py` e `modules/paginaModulo.py`

A home é o **Mapa de Missões**: cards em grade, com ícone, nível,
dificuldade, tempo estimado, e uma caixa de progresso ("X de Y módulos
concluídos"). O botão "Iniciar módulo" grava o `slug` em `st.session_state` e
a mesma rota da sidebar passa a desenhar a página do módulo; o botão "Voltar
ao mapa" apaga o `slug` e a home volta. Não é uma segunda página no menu: é
a mesma rota com um estado.

A página do módulo já tem o cabeçalho (título, resumo, badges), a seção de
material e a seção de quiz. **O PDF não aparece na página do módulo** —
ele fica na **página de leitura**, que é onde o aluno lê e aperta
"Concluir a leitura". Mostrar o PDF nos dois lugares dava duas saídas
para o mesmo material, e o aluno lia o PDF na página do módulo achando
que já tinha lido, que é justamente o que a leitura existe para
impedir. O **quiz já funciona**, e só aparece depois que o aluno
conclui a leitura (ver `modules/leitura.py` e `modules/quiz.py`).

Quem escreve o conteúdo do curso edita `dados/modulos.json` e coloca os
PDFs em `static/modulos/`. Nenhuma mudança de código é necessária para
adicionar, remover ou reescrever um módulo.

Os quatro PDFs de teste já estão em `static/modulos/`, com o nome igual ao
`slug` de cada módulo. Substituir o arquivo pelo PDF verdadeiro, com o
**mesmo nome**, já resolve: a página passa a mostrar o novo conteúdo.

### `modules/pergaminhos.py` e `dados/exemplos_crime.json`

A página **Exemplos de Crimes Digitais** mostra os golpes como
**pergaminhos**: rolinhas de papel que a pessoa clica para abrir. Ao
clicar em outro, o anterior fecha — só um fica aberto por vez.

O visual tem três peças, todas em CSS (nenhuma imagem):

- **A roleta** — o botão do Streamlit pintado de papel enrolado, com
  gradiente vertical que imita o cilindro e duas varas de madeira nas
  pontas (os pseudo-elementos `::before` e `::after`).
- **A folha** — o papel aberto, com manchas de idade (vários
  gradientes radiais), borda rasgada (o `clip-path` serra o contorno em
  dentes irregulares) e a sombra projetada por `drop-shadow`, que
  respeita o recorte — por isso a sombra fica no *wrapper*
  (`.ce-pergaminho-sombra`) e não na folha, que o `clip-path` cortaria.
- **A tinta** — Georgia, em sépia, com os rótulos das seções em caixa
  alta e filete, como no documento antigo.

O acordeão **não** é o `st.expander` do Streamlit, porque o expander
deixa dois abertos ao mesmo tempo. Quem controla é
`st.session_state["pergaminho_aberto"]`, que guarda o id do pergaminho
aberto: clicar no que já está aberto fecha, clicar em outro troca. O
`key` do botão muda conforme o estado (`pergaminho_3` /
`pergaminho_aberto_3`), e é daí que o CSS distingue a roleta fechada da
aberta — o seletor é por atributo (`[class*="st-key-pergaminho_"]`),
porque a classe real inclui o id.

O conteúdo dos pergaminhos vem de dois lugares, e os dois são a mesma
coisa na tela:

- **`dados/exemplos_crime.json`** — os exemplos pré-colocados, semeados no
  primeiro boot. O texto que vem no arquivo é **lorem ipsum** de propósito:
  é um molde, e o que o Professor escreve vale mais do que o que está no
  arquivo. A semeadura é idempotente pela `chave`: um exemplo que já
  existe não é recriado, então a edição feita na tela **não é
  sobrescrita** no próximo boot.
- **A publicação em "Gerenciar Aulas"** — o que o Professor e a
  Coordenação publicam ali vira pergaminho, na mesma lista.

A página antiga "Conteúdos" do Aluno **não existe mais**: ela virou a
página dos pergaminhos. E o item de menu "Sessões Interativas" virou
**"Mural de Criptografia"**, que é o que a página sempre foi.

### `modules/leitura.py` e `modules/quiz.py`

O caminho do aluno em um módulo é: **página do módulo → página de leitura
→ botão "Concluir a leitura" → página do módulo, agora com o quiz
liberado.**

A **página de leitura** (`modules/leitura.py`) mostra o material do
módulo com o botão que libera o quiz. Não há scroll, não há progresso,
não há "você já leu o suficiente": o aluno lê e aperta. É um botão, do
começo ao fim.

A leitura é registrada na tabela `leituras` (uma linha por aluno e
módulo), e não só na sessão — assim a liberação sobrevive ao fechamento
do navegador. O `INSERT OR REPLACE` faz o registro ser idempotente:
reler o mesmo módulo não duplica a linha.

O **quiz** (`modules/quiz.py`) só aparece para quem já concluiu a
leitura. Quem não concluiu vê o aviso de bloqueado, que diz o que
fazer. As perguntas vêm do manifesto (`dados/modulos.json`), e cada
tentativa vira uma linha em `progresso_modulos` — o histórico fica, e a
tela usa a melhor nota.

**O resultado substitui o formulário, e não aparece abaixo dele.** São
dois estados que não coexistem: sem resultado, as perguntas e o botão
"Ver meu resultado"; com resultado, a nota, o gabarito e o botão
"Tentar de novo". Isso é o que garante que o gabarito **não aparece
antes de o aluno terminar de responder** — na primeira versão, as
perguntas e o gabarito ficavam na mesma tela, e o aluno via a resposta
certa de uma pergunta que ainda não tinha respondido.

Por isso o quiz **não usa `st.form`**: dentro de um form, marcar uma
alternativa não re-executa o script, e o estado do widget ficava velho.
E cada alternativa começa **desmarcada** (`index=None`) — sem isso o
Streamlit marcava a primeira opção como resposta antes de o aluno
escolher qualquer coisa.

**O PDF fica só na página de leitura, e é somente-leitura.** A URL do
`<iframe>` leva `#toolbar=0`, que esconde a barra de ferramentas do
visualizador nativo do navegador — e com ela a **caneta de anotação**,
com que o aluno "editava" o material do professor desenhando por cima.
Medido: sem o parâmetro, a barra (`1000x56`) e a caneta (`32x32`) ficam
visíveis; com ele, nenhum dos dois aparece. Não há botão de baixar o
arquivo: ele entregava o material do professor na mão do aluno.

**Por que a leitura é uma página do app e não um arquivo solto em
`static/`:** porque a sessão do Streamlit morre quando o navegador sai
do app e volta. Com uma página estática, o aluno voltaria deslogado e
teria que entrar de novo — medido no navegador, não é teoria. Dentro do
app, a sessão vive e o botão "Voltar" leva ao mesmo módulo.

### `modules/estilo.py`

A paleta e as regras de identidade do CriptoEduca num lugar só: fundo
`#0f172a`, painel `#1e293b`, roxo `#4F46E5`, ciano `#38bdf8`, âmbar
`#f59e0b`. A Press Start 2P fica restrita aos títulos — em texto corrido
ela é pixelada demais para ler.

Duas armadilhas do `st.markdown` com HTML, ambas medidas no navegador:

- linha começando com 4 espaços vira **bloco de código** (a indentação do
  próprio Python conta);
- linha em branco no meio do HTML **encerra o bloco HTML**, e o resto volta
  a ser Markdown — sobrando um `</div>` escrito na tela.

Por isso `estilo.html_bruto()` tira a indentação e remove as linhas em
branco de todo HTML montado pelo app.

### `modules/database.py`

- `conectar()` — abre o SQLite.
- `criar_tabelas()` — cria a tabela se faltar, **soma colunas** novas sem
  apagar dados e garante o índice único de e-mail.
- `cadastrar_usuario(...)` — devolve um motivo (`"ok"`, `"usuario_duplicado"`,
  `"email_duplicado"`) em vez de `True`/`False`, para que a tela possa
  distinguir os dois casos de duplicidade.
- `verificar_login(...)` — compara a senha com bcrypt e devolve
  `(nome, tipo)`. O `tipo` é o que faz o menu lateral existir.

### `modules/ratelimit.py`

Limitador em **memória de processo**, com janela deslizante:

| Parâmetro | Valor |
|---|---|
| `MAX_TENTATIVAS` | 5 |
| `JANELA_SEGUNDOS` | 300 (5 minutos) |
| `MAX_CLIENTES` | 5000 |

Identificação do cliente, em ordem de preferência: IP do contexto do Streamlit,
cabeçalho `X-Forwarded-For` (proxy), cookie `_streamlit_xsrf`. Sem nenhum
deles, `"anonimo"` — que é o caso de várias pessoas no mesmo computador, e por
isso o limite é grosseiro, não individual.

O IP só é aceito se for `str` **e** parsear como endereço ( `_ip_aceitavel` ).
Isso não é preciosismo: a checagem existe porque `_identificar_cliente()` usava
`if ip:`, que passa qualquer objeto truthy, e o `str()` do objeto entrava na
chave do contador. Sob `AppTest`, `st.context.ip_address` é um `MagicMock` —
verdadeiro, com um `id()` novo a cada requisição. O limite passou a contar
uma tentativa por cliente, cada cliente com cinco chances, e nunca fechou. Um
limitador que falha aberto é pior que um limitador ausente, porque promete
proteção que não dá.

Duas ações distintas, com contadores independentes:

- `CHAVE_PROFESSOR` — protege a chave de cadastro do Professor.
- `LOGIN` — protege o login, e conta em **dois alvos**: a conta atacada e o
  cliente atacante. Só a conta não segura contra ataque de varredura; só o
  cliente não sobrevive a F5. Ver "Limitações" abaixo.

O contador zera **só no acerto**. Quem entra legitimamente nunca herda
bloqueio de outra pessoa.

### `modules/login.py`

- `render_login()` — as duas abas, com `clear_on_submit=True` nas duas.
- `obter_chave_professor_diaria()` — 12 caracteres, válidos até 23:59:59 do dia.
  Derivada por HMAC-SHA256 do `CHAVE_SEGREDO` com a data como mensagem, então
  é a mesma para toda a escola no mesmo dia e muda sozinho à meia-noite.
  Aceita em maiúsculas ou minúsculas, e tolera espaço nas pontas.
- `chave_equivale(digitada, valida)` — a comparação tolerante acima, isolada
  para poder ser testada sem tela.

### A chave do dia

12 caracteres do alfabeto `0-9A-Z` (10 dígitos e 26 letras), derivadas por
HMAC-SHA256, com o `CHAVE_SEGREDO` como chave e a data (`YYYY-MM-DD`) como
mensagem.

| | Antes | Agora |
|---|---|---|
| Tamanho | 6 dígitos | 12 caracteres |
| Alfabeto | 10 | 36 |
| Combinações | 900.000 | 4.738.381.338.321.616.896 |
| Geração | `random.Random(semente).randint(...)` | HMAC-SHA256 com rejeição |

Ganho de cerca de 5 trilhões de vezes no espaço de busca. A troca de `random`
por HMAC não é "sorteio melhor": `random` é um Mersenne Twister, que não foi
desenhado para segurança, e semeá-lo com um texto conhecido torna a sequência
previsível para quem conhece a semente. Na chave HMAC o segredo é a chave da
própria função, e quem não tem o segredo não consegue nem recomeçar o cálculo.
A amostragem por rejeição descarta os bytes que dariam viés de módulo, já que
256 não é múltiplo de 36 — medido: 36 símbolos usados, 3.000 dias de amostra,
contagens entre 906 e 1.075 para 1.000 esperadas, que é ruído normal.

Só **maiúsculas**, porque a chave é digitada por quem copiou de um quadro ou leu
em voz alta, e maiúscula de minúscula não se distingue no papel nem na fala.

---

## Segurança: o que está feito e o que não está

Vale ser explícito, porque parte do que parece proteção não é.

### Feito

- Senhas com **bcrypt**, nunca texto puro, nunca no código.
- **Índice único de e-mail**: o mesmo e-mail não pode abrir duas contas.
- **Rate limit** no login e na chave do Professor, com janela deslizante real
  (medida, não só teórica).
- Senha **não fica na tela** depois do envio — `clear_on_submit` nos dois
  formulários.
- A chave do dia **só aparece dentro do Painel da Coordenação**, que exige
  login de Administrador. Ela não é exibida na tela pública de cadastro, e
  portanto não há o que adivinhar.
- `.streamlit/secrets.toml` e `.env` no `.gitignore`.

### Não é proteção de verdade

**O rate limit é contornável por F5.** O identificador de cliente disponível é
o cookie `_streamlit_xsrf`, e ele **rotaciona a cada carregamento de página**.
Medido: após 5 falhas, um F5 devolve o contador cheio. O limite protege contra
o aluno distraído e o curioso, não contra alguém determinado.

- **Login**: mitigado. Como a conta atacada não muda com F5, o limite por
  conta sobrevive ao recarregamento.
- **Chave do Professor**: o F5 ainda zera o contador, porque a conta ainda não
  existe e não há "alvo" a contar — no colégio todo mundo sai pelo mesmo IP
  também. **O que mudou foi o custo de adivinhar:** com 12 caracteres são 4,7
  quintilhões de combinações, então recomeçar a contagem não compra nada.
  Zerar o contador só ajuda se a chave fosse adivinhável, e ela não é mais.
  Enquanto o `CHAVE_SEGREDO` não for configurado, porém, a chave é *calculada*
  por quem tiver o repositório — aí o limite continua decorativo, e o Painel
  da Coordenação avisa isso na tela.

**Nenhuma tela atualiza sozinha sem `run_every`.** O Streamlit só redesenha
quando o script roda, e o script só roda com interação. Deixado isso como
estava, um usuário bloqueado ficava com o botão cinza para sempre, mesmo
depois de a janela vencer — e a reação natural a uma tela travada é F5, que
zerava o contador. Os dois sintomas eram o mesmo defeito. Hoje **os dois
formulários** estão dentro de `st.fragment(run_every="5s")`, que existe
nativamente no Streamlit 1.64 e não acrescenta dependência. Medido: 9 redesenhos
em 21 s parado, sendo dois fragmentos defasados meio ciclo.

O fragmento traz um efeito que precisou de conserto: ele redesenha o formulário
inteiro a cada ciclo, e o tratamento do envio não roda junto, então **toda
mensagem de retorno sumia em menos de 5 s** — inclusive o "Conta criada com
sucesso!". O resultado do último envio passou a ser guardado em
`session_state` e redesenhado a cada passada, até a próxima tentativa ou até a
pessoa trocar de perfil.

**O travamento visual não é o que barra.** O atributo `disabled` chega um ciclo
depois do contador estourar. Quem clicar nessa janela é barrado pela lógica, no
topo da cadeia de validação, antes de a chave ser olhada. Medido com o
`disabled` forçado no ambiente de teste: 10 cliques seguidos deixaram o contador
em 5 — nenhum contou, e a chave errada nunca chegou a ser comparada.

**O e-mail único passou a confirmar mais informação.** Antes do índice
único, a tela dizia "este e-mail já está cadastrado" e o nome de usuário
ficava livre para teste. Agora ela diz as duas coisas. É uma troca: integridade
dos dados contra uma enumeração de usuários.

**A senha é validada só por forma** (1 maiúscula, 1 minúscula, 1 número), não
por força real. E não há recuperação de senha: quem esquece está perdido.

---

## Decisões que valem registro

**Por que o rate limit é em memória, e não no banco.** O contador é descartável
por definição: a única coisa que importa é "quantas vezes nos últimos 5
minutos". Gravar isso transformaria tentativa de login em registro permanente
de comportamento de usuário, e `plataforma.db` está versionado no Git. Em
memória, o contador morre com o processo, e o pior caso é alguém esperar o
servidor reiniciar.

**Por que desabilitar só o campo da chave, e não o formulário inteiro.**
Desabilitar tudo mataria o seletor de perfil junto, e um Professor bloqueado não
conseguiria nem se cadastrar como Aluno. O limite é da chave; só a chave e o
botão desabilitam. Medido: cliente com o contador estourado se cadastra como
Aluno sem problema.

**Por que o seletor de perfil é `st.radio`, e não `st.selectbox`.** Nesta
versão do Streamlit o `selectbox` virou um campo de busca: aceita digitação
livre e filtra a lista enquanto a pessoa escreve. Medido: digitando
"Coordenador" o campo mostra a palavra, a lista responde "No results", e o
valor é descartado na saída, voltando para "Aluno" sozinho. Não quebrava nada —
o valor inválido nunca chegava ao banco — mas a pessoa vê o que digitou
aparecer e sumir sem explicação, num campo que decide se a chave aparece. Com
duas opções, o radio mostra as duas e resolve em um clique, sem digitação.

**Por que o seletor de perfil ficou fora do formulário, e o campo da chave
dentro.** Dentro de `st.form` o Streamlit agrupa tudo e nada redesenha até o
envio, então condicionar o campo da chave ao perfil só valeria *depois* de
enviar — pior que mostrar sempre. Fora do form, cada troca de perfil redesenha
na hora.

O campo da chave, ao contrário, **precisa** ficar dentro do form. Ele já esteve
fora, e o cadastro de Professor estava quebrado por causa disso: no envio o
servidor recebia o campo da chave **sempre vazio** e rejeitava a chave certa.
Medido no navegador, com a chave do dia digitada e registrada em log:
`recebido='' valida='B3247UPY2KM8'`. A lição é sobre método — o `AppTest` não
pegou nada disso em rodadas inteiras de teste, porque escreve o estado dos
widgets direto no servidor, sem passar pelo navegador. Lógica e programa são
coisas diferentes, e só uma das duas foi testada.

Efeito colateral bom do perfil fora do form: `clear_on_submit` só limpa o que
está dentro do form, o que faz o perfil sobreviver ao envio.

**Por que a senha do admin foi para `st.secrets` e a chave do dia também.**
A senha é credencial real, de um usuário que existe. A semente da chave já foi
deixada no código numa rodada anterior, com o argumento de que não é segredo de
ninguém — o que era verdade para um número de 6 dígitos, mas parou de valer
quando a chave passou a ter 12 caracteres. O que decide não é o tamanho da
semente, é o da chave: a 900 mil combinações, derivar era inútil; a 4,7
quintilhões, derivar é o único jeito de quebrar. Então o `CHAVE_SEGREDO` é lido
do `secrets.toml` quando existe, com o valor do código como reserva — o app
continua subindo sem o arquivo, e o Painel da Coordenação avisa na tela quando
está usando a reserva.

---

## Correções da validação de usabilidade

Apontamentos da equipe de validação, com o que foi feito:

| # | Apontamento | Situação |
|---|---|---|
| 1 | A chave do dia aparece na tela pública | **Corrigido** — saiu o `st.info` da aba de cadastro e a função `render_admin()` morta, que também exponha a chave. A distribuição ficou só no Painel da Coordenação. |
| 2 | O campo da chave aparece mesmo para Aluno | **Corrigido** — o campo agora só é renderizado quando o perfil é Professor, e reage na hora à troca. |
| 3 | E-mail pode ser duplicado | **Corrigido** — `CREATE UNIQUE INDEX` em `database.py`. SQLite não tem `ALTER TABLE ... ADD CONSTRAINT`, então o índice é o caminho. |
| 4 | Sem modo escuro / não responsivo | **Corrigido** — CSS em `login.py` e `layout="wide"`. |
| 5 | Todos os perfis recebem o menu do Aluno | **Corrigido** — `app.py` tem menu próprio para Administrador e Professor, e cobre os seis itens. |
| 6 | Credenciais no código | **Corrigido** — senha do admin para `st.secrets`, função morta `garantir_usuario_admin()` removida. |

### Achados depois da lista

Não vieram da equipe de validação, apareceram testando no navegador:

| Achado | Situação |
|---|---|
| O `selectbox` de perfil aceita texto livre | **Corrigido** — virou `st.radio`, que só oferece Aluno ou Professor. |
| O cadastro de Professor **não funcionava no navegador** | **Corrigido** — o campo da chave estava fora do `st.form`, e no envio o servidor o recebia vazio. Bug anterior, invisível para o `AppTest`. |
| A chave do dia tinha 6 dígitos | **Corrigido** — 12 caracteres alfanuméricos derivados por HMAC-SHA256. |
| A tela de travada do cadastro nunca se destravava sozinha | **Corrigido** — o fragmento de 5 s que existia no login foi colocado também no cadastro. |
| As mensagens de retorno sumiam em menos de 5 s | **Corrigido** — o resultado do envio passou a ser guardado em `session_state`. |
| O rate limit **falhava aberto** | **Corrigido** — `_identificar_cliente()` aceitava qualquer objeto truthy como IP, e o `str()` dele entrava na chave do limite. Sob `AppTest`, `st.context.ip_address` é um `MagicMock`: a chave mudava a cada requisição, cada tentativa contava como cliente novo e o limite nunca disparava. Agora só passa `str` que parseia como IP (`_ip_aceitavel`). |

Sobre esse último: o navegador travava certo desde a rodada anterior, e o
`AppTest` é que acusou a divergência. O que destapou não foi o teste passar,
foi ele passar **com 7 tentativas erradas e nenhuma trava** — a única coisa
incoerente era o número "Restam 4 tentativas" parado em todos os envios. Um
teste que dá "ok" num controle de segurança é motivo para desconfiar, porque
o modo de falha do limite é abrir e não fechar.

Detalhe para quem for escrever teste do limitador: **cada `AppTest` é um
cliente diferente** (o `_streamlit_xsrf` gira por instância). Cenário que
precisa de acumulamento tem que reusar uma única instância e enviar várias
vezes, senão o teste mede o limitador errado. E `run_every` não roda no
`AppTest`, então o destravamento automático do campo continua sendo coisa de
navegador.

---

## Estado

Branch `Nicolas`. O trabalho de segurar a chave de 12 caracteres, o rate limit
corrigido e os dois formulários está commitado.

**`requirements.txt` continua faltando.** `streamlit` e `bcrypt` não estão
declarados em lugar nenhum, o que bloqueia deploy fora desta máquina. É o
pendente mais concreto da lista.

**A suíte de teste não está no repositório.** A rodada 3 escreveu 49
verificações (`AppTest`) cobrindo a chave, o perfil, o rate limit e o login,
todas passando, e o arquivo foi parar em pasta temporária. Ele precisa de
`tests/` e de um `requirements-dev.txt` para valer alguma coisa; deixar fora
significa que o próximo "limpar temporária" apaga o trabalho.

**A página de módulos foi redesenhada** (item 1 da lista de implementação da
missão). A home virou o "Mapa de Missões", com cards em grade, identidade
visual própria e caixa de progresso; a página individual do módulo existe,
**a visualização do PDF dentro dela já funciona** — os quatro PDFs de teste
estão em `projectAppUFBA/static/modulos/`, com o nome igual ao `slug` de
cada módulo — e **o quiz já está integrado**, protegido pela leitura: o
aluno abre a "página de leitura", lê o material, aperta "Concluir a
leitura" e o quiz destrava. O lugar de cada arquivo está descrito em
`projectAppUFBA/static/modulos/README.md` — e, enquanto um PDF não estiver
lá, a página avisa que o material está em preparação em vez de quebrar.

**A página de crimes digitais substituiu a de Conteúdos**, e o item
"Sessões Interativas" do menu virou "Mural de Criptografia".

**Conta de demonstração.** O `plataforma.db` versionado tem um usuário
`admin`. A senha inicial não está no repositório — quem precisar recriar o
banco deve definir `ADMIN_SENHA` no `secrets.toml`.