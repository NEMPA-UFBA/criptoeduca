# Onde ficam os módulos do CriptoEduca

Esta pasta é o **único lugar** que a pessoa responsável pelo conteúdo do
curso precisa mexer. Não é preciso saber Python, não é preciso rodar
nenhum comando: é abrir o arquivo `modulos.json`, alterar e salvar.

## Como adicionar um módulo

1. Abra `modulos.json` com o Bloco de Notas, o VS Code, o Notepad++, o que
   for. (Se o Bloco de Notas mostrar tudo numa linha só, use o **VS Code** ou
   o Bloco de Notas do Windows 11, que respeitam a formatação.)
2. Copie um bloco de módulo que já existe (o do Módulo 1 serve de modelo) e
   cole no fim da lista `"modulos"`.
3. Troque os valores: `slug`, `titulo`, `resumo`, `icone`, `nivel`,
   `dificuldade`, `duracao`, `cor`, `pdf` e as perguntas do `quiz`.
4. Coloque o PDF do material em `static/modulos/`, com o mesmo nome do
   `slug` (ex.: `slug: "senhas-e-autenticacao"` → arquivo
   `static/modulos/senhas-e-autenticacao.pdf`).
5. Salve, volte para o app e aperte **F5**. A mudança aparece na hora.

O arquivo já vem comentado, com a explicação de cada campo. Os comentários
são linhas inteiras que começam com `//`.

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

Se o PDF não estiver lá, a página do módulo avisa que o material está em
preparação — o app continua funcionando.

## Uma ressalva sobre o quiz

O arquivo `modulos.json` fica **fora** de `static/` de propósito: a pasta
`static/` é servida publicamente pelo Streamlit. Se as respostas do quiz
estivessem lá, qualquer aluno abriria a URL e leria as respostas antes de
responder. Não mova o arquivo para lá.
