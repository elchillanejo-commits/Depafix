# Procesados 2026-07-24: [lista de ROLs]

## Deploy 2026-07-24 (rama feature/endpoint-subida-pdf)

Endpoint `POST /api/procurador/subir_pdf` desplegado en producción (Railway, servicio `Depafix`, https://depafix-production.up.railway.app).

- Push a GitHub destrababo generando un PAT nuevo con scope `workflow` (el anterior no lo tenía; los workflows `.github/workflows/deploy.yml` y `test.yml` venían de varios commits atrás en la rama, no solo el último, así que un `amend` no alcanzaba).
- Bug encontrado y corregido en el mismo deploy: `.dockerignore` excluía todo `config/` del build de Docker, así que `config/legal_rules.json` nunca llegaba al contenedor (`[Errno 2] No such file or directory: '/app/config/legal_rules.json'`, visto en `error_logs` id=6/7). Fix: commit `b306e75`, se sacó la línea `config` de `.dockerignore`.
- Deploy hecho con `railway up` desde `/home/ibar/Proyectos/DepaFix-endpoint-worktree` (no hay auto-deploy por webhook desde GitHub pese a que el servicio tiene `source.repo` configurado -- confirmado: dos pushes seguidos no dispararon build nuevo).
- Probado en producción: `curl -X POST .../api/procurador/subir_pdf` con `C-6000-2023_demanda_fisco.pdf` devolvió `{"ok":true,"compliance_log_id":5,...}` (mismo id que ya existía, confirma idempotencia por `idempotency_key`). Dashboard `/procurador/dashboard` responde 200.
- Pendiente (fuera de esta sesión): mergear `feature/endpoint-subida-pdf` a la rama de producción real cuando corresponda -- el repo local tiene branches `main`, `master` y `feature/endpoint-subida-pdf` coexistiendo, confirmar con el usuario cuál es la fuente de verdad antes de mergear.
- Nota aparte, no tocada en este deploy: `depafix-trading-worker` mostraba "Deploy failed" en Railway al momento de este trabajo -- revisar por separado.

## Deploy final 2026-07-24: merge a master

`feature/endpoint-subida-pdf` mergeado a `master` (commit `872b629`, merge sin conflictos). `main` queda divergida a propósito -- tiene 3 commits propios de fixes de trading (`PipelineVelas`/exchange) que `master` no tiene; no se reconciliaron en este deploy, decisión explícita del usuario. El checkout compartido `/home/ibar/Proyectos/DepaFix` sigue parado en `main`. Este archivo se versionó por primera vez en git en este commit (antes era una nota local sin trackear).
