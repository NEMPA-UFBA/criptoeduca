# Onde ficam os módulos do CriptoEduca

Esta pasta é o **único lugar** que a pessoa responsável pelo conteúdo do
curso precisa mexer. Não é preciso saber Python, não é preciso rodar
nenhum comando: é abrir o arquivo `modulos.json`, alterar e salvar.

Há dois arquivos aqui, e os dois seguem a mesma regra:

| Arquivo | O que é |
|---|---|
| `modulos.json` | Os módulos de aprendizagem, com o material e o quiz. |
| `exemplos_crime.json` | Os exemplos de crimes digitais, os pergaminhos. |

## Como adicionar um módulo

1. Abra `modulos.json` com o Bloco de Notas, o VS Code, o Notepad++, o que
   for. (Se o Bloco de Notas mostrar tudo numa linha só, use o **VS Code** ou
   o Bloco de Notas do Windows 11, que respeitam a formatação.)
2. Copie um bloco de módulo que já existe (o do Módulo 1 serve de modelo) e
   cole no fim da lista `"modulos"`.
3. Troque os valores: `slug`, `titulo`, `resumo`, `icone`, `nivel`,
   `dificuldade`, `duracao`, `cor`, `categoria`, `ordem`, `pdf` e as
   perguntas do `quiz`.
4. Coloque o PDF do material em `static/modulos/`, com o mesmo nome do
   `slug` (ex.: `slug: "senhas-e-autenticacao"` → arquivo
   `static/modulos/senhas-e-autenticacao.pdf`).
5. Salve, volte para o app e aperte **F5**. A mudança aparece na hora.

O arquivo já vem comentado, com a explicação de cada campo. Os comentários
são linhas inteiras que começam com `//`.

## As abas do catálogo

O Mapa de Missões separa os módulos em quatro abas fixas, nesta ordem:

| Aba | `categoria` |
|---|---|
| Criptografia | `"Criptografia"` |
| Segurança Digital | `"Segurança Digital"` |
| Legislação e Impacto | `"Legislação e Impacto"` |
| Matemática Aplicada | `"Matemática Aplicada"` |

A categoria é o que coloca o módulo na aba certa. Um valor desconhecido (ou
um módulo criado pela tela sem categoria escolhida) cai em **Outros**, que
só vira aba quando tem algum módulo dentro — assim o catálogo não ganha uma
aba vazia para uma exceção.

O campo `ordem` decide a posição dentro da aba: menor aparece primeiro. Os
módulos numerados usam 1, 2, 3...; os complementares e o laboratório usam
números altos (50, 51, 60) para ficarem depois. Sem `ordem`, o módulo vai
para o fim da aba.

Os módulos criados pela tela também escolhem a categoria no formulário, e o
valor fica gravado no banco.

## Uma observação sobre a LGPD

A LGPD era um conjunto de pergaminhos em `exemplos_crime.json`. Agora ela é
o **Módulo 5**, uma aula teórica com PDF próprio. O PDF atual é um
placeholder em branco, como o dos outros módulos novos; o texto definitivo
será publicado pela equipe. Os pergaminhos antigos de LGPD saíram deste
arquivo; em bancos que já tinham os exemplos, eles são inativados (não
apagados) pela preparação do banco, para não aparecerem mais na página
**Exemplos de Crimes Digitais**. O texto que estava neles continua preservado
no banco, inativo.

## Pelo app

Professor e Administrador também podem criar módulos pela página
**Gerenciar Conteúdos → Módulos**. Esses módulos novos ficam no banco (tabela
`modulos`), não neste arquivo. O JSON continua sendo a origem dos
módulos originais; o Administrador pode editá-los pela tela, e quem
criou um módulo novo pode editar e excluir o próprio.

O módulo `laboratorio-aes-128-gcm` é a exceção: ele tem `"especial": "aes"`
e **só pode ser alterado neste arquivo** (e no PDF em
`static/modulos/`). Ele aparece no gerenciador como somente leitura, sem
os botões de editar e excluir. O fluxo dele é normal — leitura, quiz e,
depois dos dois, o botão que abre o laboratório AES-128-GCM.

## O que acontece se o arquivo tiver erro

O app **não quebra**. Ele mostra um aviso expansivo com o que precisa ser
corrigido, em português, e continua funcionando com os módulos que deu para
ler. Os erros mais comuns:

| Mensagem do app | O que fazer |
|---|---|
| "tem um erro de escrita" | Falta uma vírgula ou sobrou uma aspa. A mensagem diz a linha e a coluna. |
| "faltou o 'titulo'" | O módulo precisa de `titulo`. |
| "só pode ter letra minúscula, número e hífen" | O `slug` tem acento, espaço ou maiúscula. |
| "Dois módulos têm o mesmo slug" | Cada `slug` precisa ser único. |
| "a resposta correta ... está no número N, mas a pergunta só tem M alternativas" | O número em `"certa"` está fora do alcance das alternativas da pergunta. |

## Codificação do arquivo (o detalhe que mais dá trabalho)

Duas coisas do Bloco de Notas do Windows já são tratadas pelo app, e não
precisam da sua atenção:

- **BOM** (os três bytes invisíveis no começo do arquivo): o Notepad do
  Windows 11 coloca, e o app lê do mesmo jeito.
- **ANSI / Windows-1252** (o Notepad antigo salva assim): o app lê também e
  avisa na tela que o ideal é salvar em UTF-8.

Ainda assim, o melhor é salvar sempre em **UTF-8**:
*Arquivo > Salvar como > Codificação: UTF-8*. E, se o Bloco de Notas
mostrar o arquivo todo numa linha só, use o **VS Code** — ele respeita a
formatação e mostra as cores do JSON.

## Campo `certa` (a resposta do quiz)

Valem duas formas, e as duas funcionam:

- **Número**, contando a partir de 1: `"certa": 2` é a segunda alternativa.
- **Texto exato** da alternativa: `"certa": "Garantir a confidencialidade"`.

Para quem não é da área, o número é mais seguro: não dá para errar a
digitação de uma frase longa.

## Onde ficam os PDFs

Os arquivos do material ficam em `static/modulos/`, e não nesta pasta,
porque é de lá que o app serve os arquivos ao navegador. O campo `pdf` do
módulo é só o **nome do arquivo** (o caminho completo também funciona).
Quando o Professor envia um PDF pela página **Gerenciar Conteúdos →
Módulos**, o app grava o arquivo aqui com o nome do `slug`.

Se o PDF não estiver lá, a página do módulo avisa que o material está em
preparação — o app continua funcionando.

## Uma ressalva sobre o quiz

O arquivo `modulos.json` fica **fora** de `static/` de propósito: a pasta
`static/` é servida publicamente pelo Streamlit. Se as respostas do quiz
estivessem lá, qualquer aluno abriria a URL e leria as respostas antes de
responder. Não mova o arquivo para lá.

---

# Os exemplos de crimes digitais (os pergaminhos)

`exemplos_crime.json` é a lista dos exemplos de golpe que aparecem na
página **Exemplos de Crimes Digitais**, cada um como um pergaminho que a
pessoa abre e fecha.

## Como o app usa este arquivo

Ao abrir a página **Exemplos de Crimes Digitais**, os exemplos deste arquivo
que ainda não existem no banco entram como pergaminhos. A partir daí:

- um exemplo cujo `chave` já existe **não é recriado** — o que o
  Professor editou na tela vale mais do que o que está no arquivo, e não
  é sobrescrito;
- o que o Professor publica pela tela entra **depois** dos pré-colocados,
  na mesma lista de pergaminhos.

## Cada campo

| Campo | O que é |
|---|---|
| `chave` | Identificador fixo do exemplo. Só letra minúscula, número e hífen. É o que impede o app de criar o mesmo exemplo duas vezes. |
| `titulo` | O nome do golpe, que aparece na roleta do pergaminho. |
| `icone` | Um emoji. |
| `categoria` | Agrupamento: "Financeiro", "Engenharia Social", "Roubo de Identidade". |
| `corpo` | O que é o golpe, em 2 ou 3 frases. |
| `exemplo` | A mensagem falsa, como a pessoa receberia de verdade. |
| `sinais` | Lista de sinais de alerta. |
| `protecao` | Lista do que fazer para se proteger. |

O formato é o mesmo do `modulos.json`: aspas duplas, vírgula depois de
cada item menos no último, e comentários com `//` em linhas inteiras.

## Os mesmos cuidados de codificação

BOM, ANSI/Windows-1252 e UTF-8: o app trata os três, exatamente como
faz com o `modulos.json`. Salve em **UTF-8** e use o **VS Code** se o
Bloco de Notas mostrar o arquivo todo numa linha só.
