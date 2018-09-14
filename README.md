# TrenitaliaAPI

Reverse engineering dell'API dell'applicazione di **Trenitalia per Android**. Il contenuto di questo repository è il frutto di una ricerca personale, non esiste alcuna affiliazione con Trenitalia o con altri organi delle Ferrovie dello Stato. Distribuito con [licenza MIT](https://github.com/jacopo-j/TrenitaliaAPI/LICENSE).

## Documenti

* Per informazioni dettagliate su come ho ottenuto questo materiale leggi [**il post sul mio blog**](https://blog.jacopojannone.com).
* Per una documentazione *empirica* dell'API vedi [**la Wiki**](https://github.com/jacopo-j/TrenitaliaAPI/wiki).

## Esempio

```python
from trenitalia import *

tb = TrenitaliaBackend()

# Ricerca di una stazione
tb.search_station("Milano Centrale")

# Info su un treno in tempo reale
tb.train_info("9600")



```
