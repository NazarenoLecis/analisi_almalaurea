# analisi_almalaurea

Strumenti per estrarre dati occupazionali dal sito AlmaLaurea e rigenerare dataset/grafici comparabili alle dashboard Tableau.

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Le dipendenze in `requirements.txt` servono per leggere l'HTML AlmaLaurea e generare i grafici.

## Dati AlmaLaurea

La parte dati e' divisa in tre file:

- `scraper/utils.py`: funzioni comuni
- `scraper/download_dati_almalaurea.py`: download dal sito AlmaLaurea e salvataggio del master CSV
- `scraper/crea_struttura_dataset_almalaurea.py`: creazione dei CSV pronti a partire dal master

Configura le variabili in `scraper/download_dati_almalaurea.py`, poi esegui:

```powershell
python scraper/download_dati_almalaurea.py
```

Per un test rapido, imposta in `scraper/download_dati_almalaurea.py`:

```python
LIMIT_GROUPS = 2
LIMIT_COURSE_TYPES = 2
```

Per l'estrazione completa, rimetti entrambe a `None`.
La configurazione predefinita usa sempre l'ultimo anno disponibile sul sito AlmaLaurea:

```python
USE_LATEST_SURVEY_YEAR = True
```

La variabile `YEARS_AFTER_DEGREE` definisce a quanti anni dalla laurea leggere i dati, ad esempio `[1, 3, 5]`.
Il rapporto tra anno di indagine e coorte e': `anno laurea = anno indagine - anni dalla laurea`.

Poi crea la struttura pronta:

```powershell
python scraper/crea_struttura_dataset_almalaurea.py
```

Output:

- `outputs/dati/almalaurea_occupazione__survey_2025__annolau_1_5__defs_restrictive_broad.csv`
- `outputs/dati/almalaurea_lookups__survey_2025.csv`
- `outputs/dati/ready/almalaurea_survey_2025__laureati_2020__annolau_5__broad__boxplot.csv`
- `outputs/dati/ready/almalaurea_survey_2025__laureati_2020__annolau_5__broad__scatter.csv`
- `outputs/dati/ready/almalaurea_survey_2025__laureati_2024__annolau_1__broad__boxplot.csv`
- `outputs/dati/ready/almalaurea_survey_2025__laureati_2024__annolau_1__broad__scatter.csv`

Il dataset principale contiene sia la definizione restrittiva sia quella meno restrittiva di occupato.
Nel codice, `broad` indica la definizione meno restrittiva: tra gli occupati sono incluse anche le attivita' di formazione retribuite.
`restrictive` indica la definizione restrittiva: quelle attivita' di formazione retribuite sono escluse.
Quando `INCLUDE_DEGREE_CLASS_DATA = True`, il master CSV include anche le righe a livello di `degree_class`, cioe' classe di laurea/corso, oltre alle righe aggregate per ateneo e gruppo disciplinare.
I file in `outputs/dati/ready` sono quelli piu' comodi da usare direttamente per i grafici: una base lunga per i boxplot e una base aggregata per gli scatter.

## Grafici

```powershell
python charts/main.py
```

Configura definizione, anni e liste di filtri direttamente in `charts/main.py`.
Se `INPUT_CSV = None`, i grafici usano automaticamente il master CSV AlmaLaurea piu' recente presente in `outputs/dati`.
Il batch replica le 4 strutture degli esempi ricevuti: boxplot e scatter per le due distanze temporali configurate, ad esempio 1 e 5 anni dalla laurea.
Dato che localmente non ci sono i filtri interattivi di Tableau, per ogni struttura vengono prodotti piu' PNG: una vista totale e una vista per ciascun `tipo corso` configurato.
Ogni PNG riporta nel sottotitolo il filtro applicato, ad esempio `filtro: totale` oppure `filtro: tipo corso: LM biennale`.

Output:

- `outputs/grafici/boxplot__s2025__l2024__a1__broad__u_all__g_all__t_all.png`
- `outputs/grafici/scatter__s2025__l2024__a1__broad__u_all__g_all__t_all__split_disciplinary_group.png`
- `outputs/grafici/boxplot__s2025__l2024__a1__broad__u_all__g_all__t_lm_biennale.png`
- `outputs/grafici/scatter__s2025__l2024__a1__broad__u_all__g_all__t_lm_biennale__split_disciplinary_group.png`
- file analoghi per le altre viste disponibili.

La cartella `outputs/grafici` contiene solo PNG.
I CSV aggregati usati per controllare gli scatter sono salvati in `outputs/dati/aggregati_grafici`.
Gli scatter del batch standard usano sempre la suddivisione per gruppo disciplinare: un punto corrisponde a un gruppo, il colore identifica lo stesso gruppo e la dimensione della bolla rappresenta il numero di laureati.
I dati a livello di classe di laurea possono restare nel master CSV, ma non vengono trasformati automaticamente in PNG per evitare grafici locali non confrontabili con gli esempi Tableau.
I PNG includono fonte, elaborazione e nota metodologica sulla coorte osservata.
