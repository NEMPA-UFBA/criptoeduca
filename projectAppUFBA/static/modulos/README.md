# Material dos módulos de aprendizagem

Esta pasta guarda os PDFs que cada módulo de aprendizagem exibe.

Os **dados** dos módulos (título, resumo, quiz) não ficam aqui: ficam em
[`dados/modulos.json`](../../dados/modulos.json), que é o arquivo que a
pessoa responsável pelo conteúdo edita. Veja o
[README dos dados](../../dados/README.md).

## Como nomear os arquivos

O nome do arquivo tem que ser **exatamente** o `slug` do módulo declarado em
`dados/modulos.json`, com a extensão `.pdf`:

| Módulo | Arquivo esperado |
|---|---|
| Fundamentos de Segurança e Criptografia | `fundamentos-seguranca-criptografia.pdf` |
| Senhas Fortes e Autenticação | `senhas-e-autenticacao.pdf` |
| Phishing e Engenharia Social | `phishing-e-engenharia-social.pdf` |
| Pagamentos Eletrônicos e Pix Seguro | `pagamentos-e-pix-seguro.pdf` |

O `slug` serve para três coisas ao mesmo tempo: chave do botão na tela,
identificador na rota da página e nome do arquivo. Por isso ele não pode ter
acento, espaço nem caractere especial.

**Os quatro PDFs já estão nesta pasta**, como material de teste: são
versões geradas automaticamente, com o texto real do tema, para que a
exibição dentro do app possa ser conferida antes de o material definitivo
ser escrito. Substitua cada arquivo pelo PDF verdadeiro, com o **mesmo
nome**, e nada mais precisa ser feito — a página do módulo passa a
mostrar o novo conteúdo na hora.

## Onde isso é usado

O nome do arquivo fica no campo `pdf` de cada módulo em
`dados/modulos.json`:

```json
{
  "slug": "senhas-e-autenticacao",
  "titulo": "Senhas Fortes e Autenticação",
  "pdf": "senhas-e-autenticacao.pdf",
  "quiz": [ ... ]
}
```

## Arquivo faltando

A página do módulo **não quebra** quando o PDF não está na pasta: ela mostra
um aviso de "material em preparação". Isso é de propósito — o repositório
pode ficar sem o PDF enquanto a equipe termina de escrever, e o app continua
abrindo.

## Tamanho

PDF muito pesado trava a página, porque o arquivo inteiro é carregado no
navegador. Para material de leitura de一章, um arquivo de até 10 MB é
razoável. Se passar disso, vale exportar com as imagens em baixa resolução.
