# dbt do Monitor de Incidentes de P&G

Projeto dbt em arquitetura medalhão (`bronze` → `prata` → `ouro`) sobre o schema `raw`, que o Python alimenta.
A explicação completa do funcionamento está em [`docs/ARQUITETURA.md`](../docs/ARQUITETURA.md).

```powershell
venv\Scripts\dbt.exe run   --project-dir dbt --profiles-dir dbt --select tag:pre_ia    # fila de notícias da IA
venv\Scripts\dbt.exe build --project-dir dbt --profiles-dir dbt --select tag:pos_ia    # prata + ouro + testes
venv\Scripts\dbt.exe docs generate --project-dir dbt --profiles-dir dbt                # grafo de linhagem
```

Os termos do pré-filtro ficam em `macros/termos_pre_filtro.sql`.
