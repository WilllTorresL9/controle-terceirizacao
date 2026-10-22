# Controle de Terceirização — Casco 155 Estendida

Sistema em Streamlit para controlar peças enviadas a fornecedores externos (usinagem de caneca bruta,
usinagem de perfil acabado etc.) e o retorno delas, com indicadores por fornecedor.

## Páginas

| Página | Para que serve |
|---|---|
| 📊 Painel | KPIs do período (previsto, enviado, recebido, saldo no fornecedor, índice NC, lead time, entregas no prazo), alertas de lotes atrasados, gráfico mensal e tabela por fornecedor |
| 📤 Registrar envio | Lançamento da saída, já mostrando saldo no fornecedor e previsto do dia; bloqueia lançamento duplicado |
| 📥 Registrar recebimento | Retorno com aprovadas / não conformes / sucata + motivo; mostra os lotes pendentes daquele fornecedor e avisa se o retorno passar do saldo |
| 🔎 Consulta e rastreio | Busca por qualquer NF, OP, corrida ou palavra; lotes em aberto por fornecedor; extrato com saldo acumulado; exportação para Excel |
| 📅 Programação | Gera o previsto de um período em um clique (ex.: 75 pç/dia, seg–sex), cronograma diário do mês (equivalente às abas por fornecedor da planilha antiga) e ajuste dia a dia |
| 🏭 Cadastros | Fornecedores (serviços que realiza, lead time padrão, contato), serviços, produtos e **importação da planilha antiga** |
| 🔐 Usuários | Somente administrador: cria usuários e define perfil (admin, operador, consulta) |

## 1. Rodar no computador (modo local, sem Google)

```bash
pip install -r requirements.txt
streamlit run app.py
```

Sem o arquivo `.streamlit/secrets.toml` o sistema grava tudo em CSV na pasta `dados_local/`.
No primeiro acesso ele pede para criar o usuário administrador.

## 2. Ligar ao Google Sheets

1. Acesse <https://console.cloud.google.com>, crie um projeto e ative as APIs **Google Sheets API** e **Google Drive API**.
2. Em *IAM e administrador → Contas de serviço*, crie uma conta de serviço e gere uma **chave JSON**.
3. Crie uma planilha Google vazia e **compartilhe com o e-mail da conta de serviço como Editor**
   (o e-mail termina em `iam.gserviceaccount.com`).
4. Copie `.streamlit/secrets.toml.exemplo` para `.streamlit/secrets.toml`, cole o link da planilha
   e os campos do JSON.
5. Rode `streamlit run app.py`. As abas (`envios`, `recebimentos`, `fornecedores`, …) são criadas sozinhas.

Para publicar no Streamlit Community Cloud: suba o projeto no GitHub (o `secrets.toml` fica fora pelo
`.gitignore`), crie o app apontando para `app.py` e cole o conteúdo do `secrets.toml` em
*App settings → Secrets*.

## 3. Trazer os dados da planilha antiga

Entre como administrador → **Cadastros → Importar planilha antiga** → envie o `.xlsx`.
São importados envios, recebimentos e a programação (coluna *Previsto* das abas por fornecedor).
Registros já importados são ignorados, então pode repetir sem duplicar.

## Como os indicadores são calculados

- **Recebido** = aprovadas + não conformes + sucata
- **Saldo no fornecedor** = tudo que saiu − tudo que voltou
- **Aderência ao previsto** = enviado ÷ previsto (no painel, comparado até a data de hoje)
- **Índice de NC** = (não conformes + sucata) ÷ recebido
- **Lead time** = dias entre envio e retorno; os recebimentos são casados com os envios por ordem de
  chegada (FIFO), separadamente por fornecedor + serviço + produto
- **Entregas no prazo** = lotes que voltaram dentro do lead time padrão cadastrado para o fornecedor

## Estrutura

```
app.py                 login + menu
core/schema.py         tabelas/colunas, listas (motivos de NC, perfis) e dados iniciais
core/backends.py       Google Sheets e modo local (CSV)
core/db.py             leitura com cache, gravação e IDs
core/calc.py           regras de cálculo dos indicadores
core/importador.py     leitura da planilha Excel antiga
core/ui.py             componentes visuais
views/*.py             páginas
```

Para incluir um campo novo numa tabela, acrescente o nome em `core/schema.py`: a coluna é criada na
planilha automaticamente.
