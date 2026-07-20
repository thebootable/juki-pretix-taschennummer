# pretix-bagnumbers (Grundgerüst)

Fortlaufende **Taschennummern** mit konfigurierbaren Nummernkreisen pro Produkt,
damit die nummerierten Taschen vor Ort sauber vergeben werden können.

## Funktionsweise
- **Nummernkreise** (Name, Start, optional Ende) werden pro Event angelegt.
- **Zuordnung am Produkt**: Über das `item_forms`-Signal erscheint auf jeder
  Produktseite ein Feld "Nummernkreis". Produkte ohne Zuordnung erhalten keine Nummer.
- **Vergabe** bei `order_placed`: kleinste freie Nummer >= Start, race-condition-sicher
  über `SELECT ... FOR UPDATE` auf dem Nummernkreis + UniqueConstraint als Sicherheitsnetz.
- **Freigabe bei Stornierung** (`order_canceled`, Teilstorno via `order_changed`):
  die Nummer wird gelöscht und bei der nächsten Vergabe wiederverwendet (Lückenauffüllung).
- **Reaktivierung** (`order_reactivated`): es wird eine NEUE Nummer vergeben
  (kleinste freie), kein Restore der alten -- die kann inzwischen belegt sein.
- **Bestell-Split** (`order_split`): neue Positionen im abgespaltenen Auftrag
  erhalten neue Nummern.
- **Backend**: Untermenü "Taschennummern" unter Einstellungen mit Übersicht über
  Nummernkreise, konfigurierte Produkte (mit Sprunglink zur Produktseite) und
  vergebene Nummern inkl. manueller Änderung (mit Duplikatsprüfung).
- **Ticketdruck**: Variable `bagnumber` ("Taschennummer") im PDF-Ticket-Designer.
- **Export**: eigener Exporter "Taschennummern" (ListExporter).
- **REST-API**: Nummer erscheint als `bag_number` im `plugin_details`-Feld der
  OrderPosition-API (`orderposition_api_details`-Signal).
- **Event-Klonen**: Kreise und Zuordnungen werden mitkopiert, Nummern nicht.

Signal-Namen sind gegen die pretix-Doku Stand 2026.7 geprüft
(`layout_text_variables` und `order_reactivated` liegen in `pretix.base.signals`).

## Vor dem ersten Start
```bash
pip install -e .
python -m pretix makemigrations pretix_bagnumbers
python -m pretix migrate
```

## Entschiedene Punkte
- **API-Performance**: 1 Query pro Position im `orderposition_api_details`-Receiver
  ist fuer die erwartete Eventgroesse akzeptabel -- bewusst so belassen.
- **Logging**: Vergabe, Freigabe und manuelle Aenderung erzeugen LogEntries
  (`pretix_bagnumbers.number.assigned/released/changed`) ueber die
  `log_entry_types`-Registry und erscheinen in der Bestellhistorie.
- **Loeschen von Nummernkreisen**: Loesch-Button erscheint nur bei leeren
  Kreisen; serverseitiger Guard + PROTECT als doppeltes Netz.
- **Testmodus**: `order_gracefully_delete` gibt Nummern sofort frei (ohne Log).
- **Check-in**: Nummer wird ueber die Designer-Variable auf das Ticket
  gedruckt; keine Anzeige in der Check-in-App noetig.
