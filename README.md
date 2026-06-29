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

## Configurazione Dati

La parte dati e' divisa in tre file:

- `scraper/utils.py`: funzioni comuni per download, parsing e scrittura CSV
- `scraper/download_dati_almalaurea.py`: configurazione ed esecuzione dello scarico
- `scraper/crea_struttura_dataset_almalaurea.py`: creazione dei CSV pronti a partire dal master

In `scraper/download_dati_almalaurea.py` le variabili principali sono:

- `USE_LATEST_SURVEY_YEAR`: se `True`, usa l'ultimo anno disponibile sul sito AlmaLaurea
- `YEARS_AFTER_DEGREE`: distanze temporali dalla laurea, ad esempio `[1, 5]`
- `DEFINITIONS`: definizioni occupazionali da scaricare, ad esempio `["restrictive", "broad"]`
- `INCLUDE_DEGREE_CLASS_DATA`: se `True`, include anche le righe per classe di laurea
- `LIMIT_GROUPS` e `LIMIT_COURSE_TYPES`: utili per test rapidi; per lo scarico completo lasciale a `None`

Il rapporto tra anno di indagine e coorte e':

```text
anno laurea = anno indagine - anni dalla laurea
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

## Note Sui Dati

Non tutte le combinazioni di anno, distanza dalla laurea, gruppo disciplinare e tipo corso sono disponibili sul sito AlmaLaurea.
Quando una combinazione non e' pubblicata o non e' coerente per AlmaLaurea, lo script la salta e continua lo scarico delle altre viste.

Per esempio, alcuni gruppi disciplinari non hanno dati per `LM ciclo unico`; in quel caso i relativi punti non compaiono nei grafici filtrati.

I PNG includono fonte, anno AlmaLaurea, elaborazione e nota metodologica sulla coorte osservata.
