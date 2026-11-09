# Relatório de Avaliação Científica — Monitor de Incidentes P&G (`og-monitor`)

## 1. Desempenho no *Golden Dataset* (`N = 40` notícias rotuladas: 20 acidentes reais + 20 casos de ruído/pegadinhas)

| Arquitetura Avaliada | VP | FP | VN | FN | Acurácia | Precisão (*Precision*) | Revocação (*Recall*) | F1-Score |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **Estágio 1: Apenas Pré-Filtro SQL/Regex (`dbt`)** | 20 | 13 | 7 | 0 | 67.5% | 60.6% | 100.0% | 75.5% |
| **Estágio 1 + 2: Arquitetura Híbrida (`dbt` + IA Groq)** | 20 | 0 | 20 | 0 | **100.0%** | **100.0%** | **100.0%** | **100.0%** |

### Interpretação Metodológica para o TCC
- **Papel do Pré-Filtro SQL (`dbt`)**: Projetado para maximizar a **Revocação (*Recall* = 100.0%)**, garantindo que nenhum acidente operacional real seja descartado prematuramente (`FN = 0`). Por ser puramente léxico, ele barra o ruído óbvio (`VN = 7`), mas admite casos ambíguos (`FP = 13`, como *"Acidente na Avenida Petrobras"*, *"Condenação judicial por explosão de 2015"* ou *"Carreta com biodiesel na BR-101"*).
- **Papel do Agente LLM (`Groq / gpt-oss-120b`)**: Atua como filtro semântico fino sobre as candidatas admitidas pelo SQL, eliminando os falsos positivos (`FP` cai de `13` para `0`) e elevando a **Precisão de 60.6% para 100.0%** e o **F1-Score de 75.5% para 100.0%**.

## 2. Eficiência Operacional na Base Real Coletada (PostgreSQL)

- **Notícias brutas coletadas (`raw.noticias`)**: `275`
- **Notícias avaliadas na janela ativa (`DIAS_RETROATIVOS`)**: `89`
- **Descartadas em `< 1s` pelo Pré-Filtro SQL (`dbt`)**: `70` (**78.7% de redução de custo/chamadas à API de IA**)
- **Enviadas ao Agente LLM (`Groq`)**: `19`

## 3. Exemplos de Falsos Positivos do Regex Corrigidos pela IA Semântica

| ID | Categoria | Título da Notícia | Nota SQL | Pré-Filtro SQL | Decisão Final (IA) |
|---:|---|---|---:|---|---|
| 21 | `pegadinha_nome_rua` | Acidente deixa trânsito lento na Avenida Petrobras, em Ilhéus nessa quinta (5) | `+11` | ⚠️ Admitida (FP) | ✅ Descartada (VN) |
| 23 | `pegadinha_judicial_retrospectiva` | Petrobras é condenada a pagar R$ 1 milhão a sobrevivente de explosão em plataforma que matou nove | `+12` | ⚠️ Admitida (FP) | ✅ Descartada (VN) |
| 25 | `pegadinha_simulado` | Defesa Civil do Estado participa de simulado de emergência de vazamento em duto da Transpetro | `+4` | ⚠️ Admitida (FP) | ✅ Descartada (VN) |
| 26 | `pegadinha_rodoviario_comercial` | Carreta com biodiesel tomba, pega fogo e interdita BR-101 na divisa entre Bahia e Sergipe | `+6` | ⚠️ Admitida (FP) | ✅ Descartada (VN) |
| 27 | `pegadinha_tecnologia` | Petrobras contrata drone de combate a incêndio na Recap | `+8` | ⚠️ Admitida (FP) | ✅ Descartada (VN) |
| 28 | `pegadinha_tecnologia` | Navio de 53 metros vai reforçar a proteção das operações da Petrobras contra vazamentos de petróleo | `+8` | ⚠️ Admitida (FP) | ✅ Descartada (VN) |
| 29 | `pegadinha_crime_furto` | PF prende quadrilha que causou vazamento ao furtar óleo diesel de duto da Petrobras em Duque de Caxias | `+9` | ⚠️ Admitida (FP) | ✅ Descartada (VN) |
| 30 | `pegadinha_mercado_financeiro` | Ações da Petrobras caem 3% na bolsa B3 após rumores de paralisação e acidente no exterior | `+3` | ⚠️ Admitida (FP) | ✅ Descartada (VN) |
| 31 | `pegadinha_politica_sindical` | FUP manifesta solidariedade às vítimas de violência política nestas eleições | `+5` | ⚠️ Admitida (FP) | ✅ Descartada (VN) |
| 32 | `pegadinha_curiosidade_offshore` | A regra dos 124 kg: por que trabalhadores de plataformas no mar estão sendo barrados antes de subir no helicóptero | `+8` | ⚠️ Admitida (FP) | ✅ Descartada (VN) |
| 35 | `pegadinha_juridico_mpf` | Petrobras faz três descobertas na Margem Equatorial, mas enfrenta pressão do MPF após vazamento anterior | `+8` | ⚠️ Admitida (FP) | ✅ Descartada (VN) |
| 37 | `pegadinha_inovacao_robo` | Criaram um cão-robô para trabalhar em locais onde uma faísca pode provocar explosão e a Petrobras testou | `+8` | ⚠️ Admitida (FP) | ✅ Descartada (VN) |
| 40 | `pegadinha_judicial_antigo` | Sobrevivente de explosão em navio-plataforma da Petrobras receberá R$ 1 milhão por danos morais | `+12` | ⚠️ Admitida (FP) | ✅ Descartada (VN) |
