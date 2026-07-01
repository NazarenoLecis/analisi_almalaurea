# Checkpoint dati AlmaLaurea 2025

Data checkpoint: 2026-07-01.

## Stato stabile già salvato

- Lo scraper ora scarica il dettaglio per classe di laurea dentro ogni ateneo, non solo sul totale nazionale.
- Il CSV 2025 contiene le nuove colonne `degree_course_code` e `degree_course`.
- L'export web include il filtro `degree_course`.
- Il caso verificato dallo screenshot è presente nel CSV e nel JSON:
  - `Cagliari`, `Medico-Sanitario e Farmaceutico`, `laurea di primo livello`, `infermieristica (L/SNT1)`, 111 laureati.
  - `Cagliari`, `Medico-Sanitario e Farmaceutico`, `laurea di primo livello`, `infermieristica (SNT/1)`, 1 laureato, metriche oscurate da AlmaLaurea.

## Cosa resta da completare

- Il recupero completo della dimensione `degree_course` su tutte le combinazioni ateneo-gruppo-tipo corso è lungo.
- Una prima esecuzione veloce ha prodotto molti warning sugli endpoint `postcorso`.
- La versione robusta usa `WORKERS = 2` per i corsi e non scarta più una combinazione quando fallisce solo `solotendine.php`.
- Il recupero robusto era arrivato circa a `1450/2383` pagine quando è stato fermato per creare questo checkpoint. Non aveva ancora scritto nuovi risultati perché lo script scrive solo a fine esecuzione.

## Come riprendere

Per completare solo il dettaglio corsi partendo dal CSV già aggiornato:

```bash
python3 -u scraper/recupera_corsi_almalaurea.py
python3 -u scraper/crea_export_dashboard_almalaurea.py
```

Per rigenerare tutto da zero:

```bash
python3 -u scraper/download_dati_almalaurea.py
python3 -u scraper/crea_export_dashboard_almalaurea.py
```

## Verifica rapida

```bash
python3 - <<'PY'
import json
from pathlib import Path

payload = json.loads(Path("outputs/web/almalaurea_dashboard_data.json").read_text())
for course in ["infermieristica (L/SNT1)", "infermieristica (SNT/1)"]:
    matches = [
        row
        for row in payload["records"]
        if row.get("university") == "Cagliari"
        and row.get("degree_course") == course
    ]
    print(course, len(matches))
PY
```
