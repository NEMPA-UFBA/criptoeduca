# Material dos módulos de aprendizagem

Esta pasta guarda os PDFs que cada módulo de aprendizagem exibe.

Os **dados** dos módulos (título, resumo, quiz) não ficam aqui: os
módulos originais ficam em
[`dados/modulos.json`](../../dados/modulos.json), e os criados pela
página **Gerenciar Conteúdos → Módulos** ficam na tabela `modulos` do banco.
Veja o [README dos dados](../../dados/README.md).

## Como nomear os arquivos

O nome do arquivo tem que ser **exatamente** o `slug` do módulo declarado em
`dados/modulos.json`, com a extensão `.pdf`:

| Módulo | Aba | Arquivo esperado |
|---|---|---|
| Definição e História | Criptografia | `definicao-e-historia.pdf` |
| Cifras Clássicas | Criptografia | `cifras-classicas.pdf` |
| Laboratório: Criptografia AES-128-GCM | Criptografia | `laboratorio-aes-128-gcm.pdf` |
| Senhas Fortes e Autenticação | Segurança Digital | `senhas-e-autenticacao.pdf` |
| Criptografia Assimétrica | Segurança Digital | `criptografia-assimetrica.pdf` |
| Phishing e Engenharia Social | Segurança Digital | `phishing-e-engenharia-social.pdf` |
| Pagamentos Eletrônicos e Pix Seguro | Segurança Digital | `pagamentos-e-pix-seguro.pdf` |
| LGPD | Legislação e Impacto | `lgpd.pdf` |
| Aritmética Modular | Matemática Aplicada | `aritmetica-modular.pdf` |

O `slug` serve para três coisas ao mesmo tempo: chave do botão na tela,
identificador na rota da página e nome do arquivo. Por isso ele não pode ter
acento, espaço nem caractere especial.

**Os PDFs dos módulos novos são placeholders propositais.** Eles estão em
branco, avisando que o conteúdo definitivo será publicado pela equipe, para
que a estrutura, a leitura e o quiz possam ser testados antes dos textos de
Yasmim, Alana e Daniel. Quando o material verdadeiro chegar, substitua cada
arquivo pelo PDF final, com o **mesmo nome**, e nada mais precisa ser feito —
a página do módulo passa a mostrar o novo conteúdo na hora.

Os módulos 1 a 5 e a Aritmética Modular usam um **quiz de teste** com uma
pergunta; a resposta está no próprio aviso do PDF. O laboratório AES e os
módulos complementares (Phishing e Pix) continuam com o material e os quizzes
que já existiam.

Os arquivos `criptografia.pdf` e `fundamentos-seguranca-criptografia.pdf`
continuam na pasta como fonte do conteúdo que havia antes da reorganização;
eles não são mais referenciados por nenhum módulo.

O módulo `laboratorio-aes-128-gcm` é especial: o PDF dele é o material de
leitura que libera o quiz e, depois do quiz, o botão do laboratório de
cifrar e decifrar. Ele só pode ser alterado no código (`dados/modulos.json`
e este PDF), nunca pela tela de gerenciamento.

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

O envio pela página **Gerenciar Conteúdos → Módulos** aceita PDF de até
**20 MB**. Acima disso o arquivo é recusado antes de ser gravado. O teto existe
porque o PDF inteiro é carregado no navegador: um arquivo muito pesado
trava a leitura, principalmente no celular. Para material de leitura,
10 MB ou menos já é bastante; se passar disso, vale exportar com as
imagens em baixa resolução.
