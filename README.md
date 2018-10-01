# TrenitaliaAPI

Reverse engineering dell'API dell'applicazione di **Trenitalia per Android**. Il contenuto di questo repository è il frutto di una ricerca personale, non esiste alcuna affiliazione con Trenitalia o con altri organi delle Ferrovie dello Stato. Distribuito con [licenza MIT](https://github.com/jacopo-j/TrenitaliaAPI/LICENSE).

## Documenti

* Per informazioni dettagliate su come ho ottenuto questo materiale leggi [**il post sul mio blog**](https://blog.jacopojannone.com/2018/09/24/trenitalia-app-reversed.html).
* Per una documentazione *empirica* dell'API vedi [**la Wiki**](https://github.com/jacopo-j/TrenitaliaAPI/wiki/API-dell'app-Trenitalia).

Questo modulo è da considerarsi una bozza: sono stati implementati solo i metodi principali e probabilmente esistono molti casi limite che causano eccezioni non gestite. Data la complessità dei dati non è stato possibile testare ogni singola circostanza.

## Requisiti

* Python 3.7
* modulo `requests`

## Utilizzo

```python
from trenitalia import TrenitaliaBackend
from datetime import datetime

tb = TrenitaliaBackend()

# Ricerca di una stazione (restituisce una lista di risultati)
tb.search_station(name="milano",       # Nome da cercare
                  only_italian=False)  # Cerca solo stazioni italiane (default = False)

# Ricerca di una soluzione di viaggio (restituisce un generatore)
# È possibile inserire data e ora di partenza OPPURE data e ora di arrivo
tb.search_solution(origin="830008409",       # ID della stazione di origine
                   destination="830000219",  # ID della stazione di destinazione
                   dep_date=datetime.now(),  # Data e ora di partenza
                   arr_date=None,            # Data e ora di arrivo (default = None)
                   adults=1,                 # Numero di adulti (default = 1)
                   children=0,               # Numero di bambini (default = 0)
                   train_type="All",         # Può essere "All", "Frecce", "Regional" (default = "All")
                   max_changes=99,           # Massimo numero di cambi (default = 99)
                   limit=10)                 # Massimo numero di soluzioni da cercare (default = 10)

# Info su un treno in tempo reale (restituisce un dizionario)
tb.train_info(number="9600",   # Numero del treno
              dep_st=None,     # ID della stazione di origine (opzionale)
              arr_st=None,     # ID della stazione di destinazione (opzionale)
              dep_date=None)   # Data di partenza (opzionale)
              
# Tabellone arrivi/partenze (restituisce una lista di treni)
tb.timetable(station_id="830008409",   # ID della stazione
             ttype="departure")        # "departure" o "arrival"


```
