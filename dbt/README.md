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

O schema `ouro` tem SÓ o modelo estrela, para o Power BI: **1 fato** e **8 dimensões**.

`fato_incidente` tem o grão "um incidente detectado pela IA nas notícias", já cruzado com o SISO quando houve
correspondência (`num_incidente_siso` nulo = não encontrado). O SISO não entra como linhas, só como atributos do cruzamento.
Traz chaves, datas de verdade (`data_fato`, `data_publicacao`, `data_siso`), medidas (`qtd_incidente`, `vitimas`,
`qtd_noticias_do_evento`, `confianca`, `score_cruzamento`) e atributos degenerados (`id_incidente`, título, url, motivo,
sonda, poço, campo).

Todas as chaves são inteiros sequenciais `id_*` (0 = desconhecido). A ligação com datas é por `id_data_fato`,
`id_data_publicacao` e `id_data_siso`, não pela data. Dimensões: `dim_data` (3 papéis; coluna `data` para marcar como
tabela de datas), `dim_fonte`, `dim_localidade`, `dim_instalacao` (2 papéis: onde ocorreu e instalação do SISO),
`dim_empresa` (3 papéis: operadora do contrato, da instalação, empresa do SISO), `dim_tipo_evento`, `dim_severidade` e
`dim_status_cruzamento`. No Power BI: fato -> dimensão, um-para-muitos, direção única; uma relação ativa por dimensão e as
demais inativas (USERELATIONSHIP).

Fora da estrela: `prata_noticias_processadas` (uma linha por notícia processada, para acompanhar a captura) e
`prata_incidentes_ia` / `prata_incidentes_cruzados`, que alimentam a fato. Os alertas por e-mail (`alerts.py`) leem a
`fato_incidente` juntando as dimensões.
