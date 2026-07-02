# analisi_almalaurea

Script Python per scaricare dati occupazionali da AlmaLaurea, salvarli in CSV puliti e generare export JSON statici per dashboard e analisi.

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Le dipendenze servono per leggere le pagine HTML di AlmaLaurea, costruire dataset tabellari e produrre grafici PNG.

## Download completo

Il comando principale e' il runner unico:

```powershell
python scraper/genera_json_almalaurea.py
```

Per default il runner scarica tutti gli anni pubblicati da AlmaLaurea, usa le distanze `1`, `3` e `5` anni dalla laurea, include dettaglio per ateneo, gruppo disciplinare, tipo di corso, classe di laurea e corso di laurea quando AlmaLaurea lo pubblica, poi rigenera gli export web.

I file principali generati sono:

- `outputs/dati/almalaurea_occupazione__survey_<anno>__annolau_1_3_5__defs_restrictive_broad.csv`
- `outputs/dati/almalaurea_lookups__survey_<anno>.csv`
- `outputs/web/almalaurea_dashboard_data.json`
- `outputs/web/almalaurea_metadata.json`
- `outputs/web/almalaurea_timeseries_data.json`

Il runner non usa argomenti da terminale. Per cambiare il perimetro del run modifica le costanti in cima a `scraper/genera_json_almalaurea.py`:

- `SURVEY_YEARS_TO_DOWNLOAD = "all"` scarica tutti gli anni disponibili
- `SURVEY_YEARS_TO_DOWNLOAD = None` scarica solo l'ultimo anno disponibile
- `SURVEY_YEARS_TO_DOWNLOAD = [2023, 2024, 2025]` scarica solo gli anni indicati
- `DOWNLOAD_DATA = False` salta il download e rigenera solo i JSON dai CSV gia' presenti
- `EXPORT_JSON = False` scarica i CSV senza rigenerare i JSON web

## Script principali

La parte dati e' concentrata in quattro file:

- `scraper/utils.py`: funzioni comuni per download, parsing, normalizzazione, warning e scrittura CSV
- `scraper/download_dati_almalaurea.py`: configurazione ed esecuzione dello scarico AlmaLaurea
- `scraper/crea_export_dashboard_almalaurea.py`: creazione dei JSON statici usati dalla dashboard web
- `scraper/genera_json_almalaurea.py`: runner unico per download completo ed export JSON

In `scraper/download_dati_almalaurea.py` le variabili principali sono:

- `SURVEY_YEAR`: anno da usare quando non si scarica una lista di anni
- `SURVEY_YEARS`: lista opzionale di anni da scaricare usando direttamente lo script di download
- `USE_LATEST_SURVEY_YEAR`: se `True`, usa l'ultimo anno disponibile sul sito AlmaLaurea quando non e' stata indicata una lista di anni
- `YEARS_AFTER_DEGREE`: distanze temporali dalla laurea, per esempio `[1, 3, 5]`
- `DEFINITIONS`: definizioni occupazionali da scaricare, per esempio `["restrictive", "broad"]`
- `INCLUDE_DEGREE_CLASS_DATA`: include le righe per classe di laurea
- `INCLUDE_DEGREE_COURSE_DATA`: include le righe per corso di laurea
- `LIMIT_GROUPS` e `LIMIT_COURSE_TYPES`: utili per test rapidi; per il download completo devono restare a `None`

Nel vecchio endpoint statistico AlmaLaurea il parametro `anno` e' un codice interno che precede di un anno l'anno pubblico dell'indagine. Per esempio, la XXVIII indagine pubblicata nel 2026 viene consultata con `anno=2025`.

Il rapporto tra codice interno e coorte resta:

```text
anno laurea = anno endpoint - anni dalla laurea
```

## Output dati

I master CSV finiscono in `outputs/dati`.

Esempio con survey 2025:

- `outputs/dati/almalaurea_occupazione__survey_2025__annolau_1_3_5__defs_restrictive_broad.csv`
- `outputs/dati/almalaurea_lookups__survey_2025.csv`

Il master CSV contiene campi tecnici utili per filtrare e ricostruire l'origine dei dati:

- anno di indagine
- anni dalla laurea
- coorte di laurea
- definizione occupazionale
- ateneo
- gruppo disciplinare
- tipo di corso
- classe di laurea
- corso di laurea
- numero di laureati
- tasso di occupazione
- retribuzione mensile netta
- quota di laureati di primo livello iscritti a un corso di secondo livello
- URL sorgente AlmaLaurea

Nel codice:

- `broad` indica la definizione meno restrittiva di occupato, che include anche le attivita' di formazione retribuite
- `restrictive` indica la definizione restrittiva, che esclude quelle attivita'

## Export JSON

Lo script `scraper/crea_export_dashboard_almalaurea.py` legge automaticamente i master CSV presenti in `outputs/dati` e scrive:

- `outputs/web/almalaurea_dashboard_data.json`
- `outputs/web/almalaurea_metadata.json`
- `outputs/web/almalaurea_timeseries_data.json`

Questi file sono pensati per dashboard statiche, notebook o altri strumenti che leggono JSON gia' pronti.

Quando esistono piu' master CSV per lo stesso anno, ad esempio uno storico `annolau_1_5` e uno nuovo `annolau_1_3_5`, l'export usa automaticamente il file piu' completo.

Se in `outputs/dati` sono presenti master CSV di piu' anni, l'export web usa due livelli:

- dashboard dettagliata: ultimi 10 anni di indagine disponibili, con filtri granulari come ateneo, gruppo, tipo corso, classe di laurea e corso di laurea
- serie storiche: tutti gli anni scaricati dal 2008 in poi, senza dettaglio per classe di laurea e corso di laurea, per mantenere il dataset leggero e confrontabile

Per le lauree di primo livello, il JSON include anche la quota di laureati iscritti a un corso di secondo livello. Questo aiuta a leggere correttamente il tasso di occupazione a 1 anno dalla laurea, che puo' essere piu' basso quando molti laureati proseguono con la magistrale.

## Grafici opzionali

La generazione dei grafici si configura in `charts/main.py`.

Se `INPUT_CSV = None`, viene usato automaticamente il master CSV AlmaLaurea piu' recente presente in `outputs/dati`.

Il batch standard produce:

- boxplot della retribuzione per gruppo disciplinare
- scatter occupazione/retribuzione per gruppo disciplinare
- varianti per le distanze temporali configurate
- varianti per i tipi di corso configurati

I grafici sono salvati in `outputs/grafici` e i CSV aggregati usati per controllare gli scatter sono salvati in `outputs/dati/aggregati_grafici`.

## Note sui dati

Non tutte le combinazioni di anno, distanza dalla laurea, gruppo disciplinare, tipo corso, classe di laurea e corso di laurea sono disponibili sul sito AlmaLaurea.

Quando una combinazione non e' pubblicata o non e' coerente per AlmaLaurea, lo script la salta e continua lo scarico delle altre viste, riportando un warning nel log di esecuzione.
