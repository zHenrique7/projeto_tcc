# dbt do Monitor de Incidentes de P&G

Projeto dbt em arquitetura medalhão (`bronze` → `prata` → `ouro`) sobre o schema `raw`, que o Python alimenta.
A explicação completa do funcionamento está em [`docs/ARQUITETURA.md`](../docs/ARQUITETURA.md).

```powershell
venv\Scripts\dbt.exe run   --project-dir dbt --profiles-dir dbt --select tag:pre_ia    # fila de notícias da IA
venv\Scripts\dbt.exe build --project-dir dbt --profiles-dir dbt --select tag:pos_ia    # prata + ouro + testes
venv\Scripts\dbt.exe docs generate --project-dir dbt --profiles-dir dbt                # grafo de linhagem
```

Os termos do pré-filtro ficam em `macros/termos_pre_filtro.sql`.

## Regra de "mesmo evento" e dados consolidados (prata_classificacoes_ia)

Várias notícias descrevem o mesmo incidente. Elas viram um único evento (`chave_evento`, um hash interno da prata; a ouro expõe só `id_incidente`, número inteiro) quando (a) os tipos são compatíveis
(Incêndio/Explosão, Acidente/Fatalidade, Vazamento; Shutdown, Evacuação e Acidente genérico casam com qualquer um) e
(b) casam em uma das regras: **R1** mesmo ativo (chave normalizada: "FPSO P-40" = "P-40", "Skandy" = "Skandi") a até
5 dias; **R2** mesma bacia normalizada com um dos lados sem ativo, a até 7 dias (na Foz do Amazonas vale mesmo com
ativos diferentes: sonda, poço e bloco são o mesmo incidente); **R3** mesmo município e estado a até 1 dia;
**R4** matéria vaga (sem ativo e sem município) do mesmo estado e grupo de tipo a até 1 dia. Matéria sem data do
fato (acompanhamento) usa a janela de 45 dias. Janelas e bacias em `dbt_project.yml` (`vars`).

Os dados do evento (`*_evento`) são consolidados entre as notícias: data do fato = a mais antiga informada; tipo = o de
maior prioridade; severidade = a mais grave; ativo, bacia, operadora = primeiro valor informado; UF corrigida pela
bacia (Foz do Amazonas = AP). `prata_incidentes_ia`, `fato_incidente` e as dimensões usam esses valores.

`dim_localidade` = município+estado (em terra) ou bacia (offshore). `dim_instalacao` ganhou a origem
"Somente na notícia" (ativo que a ANP/SISO não têm); a chave 0 só sobra quando nenhuma notícia nomeia o ativo.
Obs.: a notícia-raiz do evento é a primeira CLASSIFICADA (mantém estáveis os alertas já enviados); por isso o
`classify.py` processa o lote em ordem cronológica.

## Modelo estrela (schema ouro) e tabelas intermediárias

O schema `ouro` tem SÓ o modelo estrela, para o Power BI: **3 fatos** (`fato_incidente`: um por evento físico, completa;
`fato_noticia_ia`: uma por notícia processada, com o texto extraído; `fato_siso_incidente`: um por incidente do SISO) e
**4 dimensões** (`dim_data`, `dim_fonte`, `dim_localidade`, `dim_instalacao`). Relacionamentos no Power BI: sempre
fato -> dimensão, um-para-muitos, direção única; nunca fato -> fato. `dim_data` liga por `chave_data_fato` (ativa) e por
`chave_data_publicacao` / `chave_data_primeira_obs` (inativas, usadas com USERELATIONSHIP).
`prata_incidentes_ia` e `prata_incidentes_cruzados` (antigas `incidentes_ia` e `incidentes_cruzados`) viraram
intermediárias na prata: só alimentam a `fato_incidente`, que mantém todas as colunas delas. Os alertas por e-mail (`alerts.py`) e o Power BI leem `ouro.fato_incidente`. A antiga
`noticias_acidentes_ia` foi absorvida por `fato_noticia_ia` (filtre `relevante = true`).
