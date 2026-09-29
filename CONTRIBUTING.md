# Padrões de Contribuição e Controle de Versão

Este documento estabelece as diretrizes de versionamento para o projeto CriptoEduca (NEMPA/UFBA). Todos os colaboradores devem aderir às práticas abaixo.

## 1. Fluxo de Branches

A branch `main` é o ambiente de produção. Sob nenhuma hipótese commits devem ser feitos diretamente nela.

1. Sincronize seu ambiente local antes de iniciar o trabalho:
   git checkout main
   git pull origin main

2. Crie uma branch específica para a sua tarefa. Utilize nomes curtos e descritivos:
   git checkout -b feature/tela-login
   git checkout -b fix/erro-banco-dados

3. Após finalizar o trabalho na sua branch, envie para o repositório remoto:
   git push -u origin feature/tela-login

4. Acesse o GitHub e abra um "Pull Request" (PR) apontando para a `main`. Solicite a revisão de um colega ou orientador antes do "Merge".

## 2. Padrões de Commit

Adotamos a convenção de "Conventional Commits". Cada commit deve iniciar com um tipo específico que indica a intenção da mudança, seguido de dois pontos e a descrição em letras minúsculas.

Tipos permitidos:
- `feat:` Adição de uma nova funcionalidade (ex: feat: integra banco sqlite no cadastro).
- `fix:` Correção de um bug (ex: fix: impede o cadastro de emails duplicados).
- `docs:` Alterações na documentação (ex: docs: atualiza readme com instrucoes de instalacao).
- `style:` Formatação de código, sem alterar a lógica (ex: style: ajusta identacao no backend).
- `refactor:` Refatoração de código que não adiciona recurso nem corrige bug (ex: refactor: reorganiza as rotas de autenticacao).
- `test:` Adição ou correção de testes (ex: test: adiciona teste unitario para o bcrypt).
- `chore:` Tarefas de manutenção ou configuração de ambiente (ex: chore: adiciona biblioteca fastapi no requirements).