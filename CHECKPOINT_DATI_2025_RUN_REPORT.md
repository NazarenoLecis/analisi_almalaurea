# Report recupero AlmaLaurea 2025

Comandi eseguiti:

```bash
python3 -u scraper/recupera_corsi_almalaurea.py
python3 -u scraper/crea_export_dashboard_almalaurea.py
```

## Verifica Cagliari infermieristica

CSV rows: 57498
JSON records: 132428

```json
{
  "csv_counts": {
    "infermieristica (L/SNT1)": 2,
    "infermieristica (SNT/1)": 2
  },
  "json_counts": {
    "infermieristica (L/SNT1)": 2,
    "infermieristica (SNT/1)": 2
  },
  "missing": []
}
```

## Warning e combinazioni saltate

Righe rilevate nei log: 1

Prime 200 righe rilevate:

- `recupero_corsi_almalaurea_2025.log:45` WARNING: skipped degree courses annolau=1 ateneo=tutti gruppo=14 corstipo=L reason=Could not fetch https://www2.almalaurea.it/cgi-php/universita/statistiche/visualizza.php?anno=2025&corstipo=L&ateneo=tutti&facolta=tutti&gruppo=14&livello=tutti&area4=tutti&pa=tutti&classe=tutti&postcorso=tutti&annolau=1&isstella=0&condocc=tutti&iscrls=tutti&disaggregazione=postcorso&LANG=it&CONFIG=occupazione
