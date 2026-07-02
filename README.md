# analisi_almalaurea

Script Python per scaricare dati occupazionali da AlmaLaurea, salvarli in CSV puliti e generare grafici statici su occupazione e retribuzione dei laureati.

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Le dipendenze servono per leggere le pagine HTML di AlmaLaurea, creare dataset tabellari e produrre grafici PNG.

## Flusso Di Lavoro

1. Scarica i dati da AlmaLaurea.

```powershell
python scraper/download_dati_almalaurea.py
```

2. Crea i CSV pronti per analisi e grafici.

```powershell
python scraper/crea_struttura_dataset_almalaurea.py
```

3. Genera i grafici.

```powershell
python charts/main.py
```

4. Crea i JSON per una dashboard web o per altri riusi statici.

```powershell
python scraper/crea_export_dashboard_almalaurea.py
```

Per scaricare i dati e rigenerare i JSON con un solo comando, usa il runner unico:

```powershell
python scraper/genera_json_almalaurea.py
```

Il comando scarica l'ultimo anno AlmaLaurea disponibile con le distanze `1`, `3` e `5` anni dalla laurea, include dettaglio per classe e corso quando AlmaLaurea lo pubblica, e rigenera:

- `outputs/web/almalaurea_dashboard_data.json`
- `outputs/web/almalaurea_metadata.json`
- `outputs/web/almalaurea_timeseries_data.json`

Il runner non usa argomenti da terminale: per rebuild completo, solo export JSON o test veloci, modifica le costanti in cima a `scraper/genera_json_almalaurea.py`.

## Configurazione Dati

La parte dati e' divisa in tre file:

- `scraper/utils.py`: funzioni comuni per download, parsing e scrittura CSV
- `scraper/download_dati_almalaurea.py`: configurazione ed esecuzione dello scarico
- `scraper/crea_struttura_dataset_almalaurea.py`: creazione dei CSV pronti a partire dal master
- `scraper/crea_export_dashboard_almalaurea.py`: creazione dei JSON statici usati dalla dashboard web

In `scraper/download_dati_almalaurea.py` le variabili principali sono:

- `USE_LATEST_SURVEY_YEAR`: se `True`, usa l'ultimo anno disponibile sul sito AlmaLaurea
- `SURVEY_YEARS`: se valorizzata, scarica piu' anni di indagine, ad esempio `[2022, 2023, 2024, 2025]`
- `YEARS_AFTER_DEGREE`: distanze temporali dalla laurea, ad esempio `[1, 3, 5]`
- `DEFINITIONS`: definizioni occupazionali da scaricare, ad esempio `["restrictive", "broad"]`
- `INCLUDE_DEGREE_CLASS_DATA`: se `True`, include anche le righe per classe di laurea
- `LIMIT_GROUPS` e `LIMIT_COURSE_TYPES`: utili per test rapidi; per lo scarico completo lasciale a `None`

Nel vecchio endpoint statistico AlmaLaurea il parametro `anno` e' un codice interno che precede di un anno l'anno pubblico dell'indagine. Per esempio, la XXVIII indagine pubblicata nel 2026 viene consultata con `anno=2025`.

Il rapporto tra codice interno e coorte resta:

```text
anno laurea = anno endpoint - anni dalla laurea
```

## Output Dati

I file principali finiscono in `outputs/dati`.

Esempio con survey 2025:

- `outputs/dati/almalaurea_occupazione__survey_2025__annolau_1_5__defs_restrictive_broad.csv`
- `outputs/dati/almalaurea_lookups__survey_2025.csv`
- `outputs/dati/ready/almalaurea_survey_2025__laureati_2024__annolau_1__broad__boxplot.csv`
- `outputs/dati/ready/almalaurea_survey_2025__laureati_2024__annolau_1__broad__scatter.csv`
- `outputs/dati/ready/almalaurea_survey_2025__laureati_2020__annolau_5__broad__boxplot.csv`
- `outputs/dati/ready/almalaurea_survey_2025__laureati_2020__annolau_5__broad__scatter.csv`

Il master CSV contiene anche campi tecnici utili per filtrare e ricostruire l'origine dei dati:

- anno di indagine
- anni dalla laurea
- coorte di laurea
- definizione occupazionale
- ateneo
- gruppo disciplinare
- tipo di corso
- eventuale classe di laurea
- numero di laureati
- tasso di occupazione
- retribuzione mensile netta
- quota di laureati di primo livello iscritti a un corso di secondo livello
- URL sorgente AlmaLaurea

Nel codice:

- `broad` indica la definizione meno restrittiva di occupato, che include anche le attivita' di formazione retribuite
- `restrictive` indica la definizione restrittiva, che esclude quelle attivita'

## Grafici

La generazione dei grafici si configura in `charts/main.py`.

Se `INPUT_CSV = None`, viene usato automaticamente il master CSV AlmaLaurea piu' recente presente in `outputs/dati`.

Il batch standard produce:

- boxplot della retribuzione per gruppo disciplinare
- scatter occupazione/retribuzione per gruppo disciplinare
- varianti per le distanze temporali configurate, ad esempio 1 e 5 anni dalla laurea
- varianti per i tipi di corso configurati, ad esempio totale, laurea di primo livello, LM ciclo unico, LM biennale

Ogni PNG riporta nel sottotitolo il filtro applicato, ad esempio:

- `filtro: totale`
- `filtro: tipo corso: LM biennale`

I grafici sono salvati in `outputs/grafici` e la cartella contiene solo file PNG.

I CSV aggregati usati per controllare gli scatter sono salvati in `outputs/dati/aggregati_grafici`.

## Export JSON

Lo script `scraper/crea_export_dashboard_almalaurea.py` legge automaticamente i master CSV presenti in `outputs/dati` e scrive:

- `outputs/web/almalaurea_dashboard_data.json`
- `outputs/web/almalaurea_metadata.json`
- `outputs/web/almalaurea_timeseries_data.json`

Questi file sono pensati per essere consumati da dashboard statiche, notebook o altri strumenti che leggono JSON gia' pronti.

Quando esistono piu' master CSV per lo stesso anno, ad esempio uno storico `annolau_1_5` e uno nuovo `annolau_1_3_5`, l'export usa automaticamente il file piu' completo.

Se in `outputs/dati` sono presenti master CSV di piu' anni, l'export web usa due livelli:

- dashboard dettagliata: ultimi 10 anni di indagine disponibili, con filtri granulari come ateneo, gruppo, tipo corso e classe di laurea
- serie storiche: tutti gli anni scaricati dal 2008 in poi, senza dettaglio per classe di laurea, per mantenere il dataset leggero e confrontabile

Per le lauree di primo livello, il JSON include anche la quota di laureati iscritti a un corso di secondo livello. Questo aiuta a leggere correttamente il tasso di occupazione a 1 anno dalla laurea, che puo' essere piu' basso quando molti laureati proseguono con la magistrale.

## Note Sui Dati

Non tutte le combinazioni di anno, distanza dalla laurea, gruppo disciplinare e tipo corso sono disponibili sul sito AlmaLaurea.
Quando una combinazione non e' pubblicata o non e' coerente per AlmaLaurea, lo script la salta e continua lo scarico delle altre viste.

Per esempio, alcuni gruppi disciplinari non hanno dati per `LM ciclo unico`; in quel caso i relativi punti non compaiono nei grafici filtrati.

I PNG includono fonte, anno AlmaLaurea, elaborazione e nota metodologica sulla coorte osservata.
