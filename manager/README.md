# MacBook Manager

Stato e azioni rapide del MacBookPro14,3 in un posto solo: finestra Qt, icona nella barra di sistema di KDE e
comando `macbook-manager`. Riusa quello che installano gli script della repo; non sostituisce `install.sh`.

```bash
sudo scripts/install-manager.sh          # oppure: sudo ./install.sh --only manager
```

Installa `pyside6`, il programma in `/usr/local/lib/macbookpro14-3/manager/`, il link `/usr/local/bin/macbook-manager`,
la voce "MacBook Manager" nel menu, l'icona nella barra di sistema all'avvio della sessione (`--no-tray` per non
averla) e la policy polkit. `--undo` rimuove tutto.

## Cosa mostra (scheda Stato, `macbook-manager status`)

| Gruppo | Voci | Da dove |
|---|---|---|
| Driver | Touch Bar (tastiera e display), audio CS8409, webcam H.264: compilati per il kernel in uso? | `dkms status` |
| Touch Bar | modalità attuale e salvata, renderer, webcam virtuale | `/run/macbookpro14-3/touchbar/mode`, `touchbar.conf`, unità utente |
| Sospensione | S3 o s2idle, sospensioni di questo avvio e risvegli a coperchio chiuso | `systemd-analyze cat-config`, journal |
| Rete | SSID, banda, larghezza di canale, segnale, velocità | `iw` |
| Energia | batteria (W, autonomia, salute, cicli), Radeon (W, °C, profilo), impostazioni a batteria, CPU e ventole | `/sys` (BAT0, hwmon amdgpu/coretemp/applesmc), `power.conf` |

Semaforo: verde a posto, giallo avviso, rosso da sistemare (con il pulsante **Correggi** quando c'è un'azione che
risolve, per esempio "ricompila i driver" dopo un aggiornamento del kernel). La scheda **Sospensioni** elenca ogni
sospensione con durata, modalità, batteria consumata e causa del risveglio (`macbook-manager sleep-report`).

## Azioni (`macbook-manager actions`, `macbook-manager run <id>`)

| Gruppo | Azioni |
|---|---|
| Touch Bar | modalità display (subito) / tastiera (salvata, attiva dopo lo spegnimento: il manager propone di spegnere), riavvia il renderer, webcam virtuale on/off |
| Sospensione | S3 (deep) / s2idle |
| Energia | Radeon in risparmio a batteria sì/no, turbo CPU a batteria sì/no (`power.conf` + riapplica) |
| Rete e audio | ricarica il driver Wi-Fi, ripristina l'audio delle chiamate Bluetooth (CVSD) |
| Manutenzione | ricompila i driver DKMS per il kernel in uso, spegni il Mac (azzera anche il T1) |

L'opzione già attiva è spuntata e non cliccabile. Le azioni non disponibili (componente non installato) non compaiono.

## Sicurezza

Le azioni di sistema passano da `pkexec macbook-manager-helper <id>`: la policy
`org.macbookpro14-3.manager.helper` autorizza solo quel file (password di amministratore, ricordata qualche minuto).
L'helper accetta un solo argomento, l'id di un'azione di `macbook_manager/actions.py`: nessun argomento libero,
nessuna shell, moduli importati solo dalla cartella di installazione di root. Per aggiungere un'azione si modifica
`actions.py` nella repo e si reinstalla.

## Sviluppo

Dalla repo, senza installare: `manager/macbook-manager status` (le azioni root funzionano solo installate, perché
pkexec accetta solo il percorso della policy). Solo libreria standard di Python, più PySide6 per la GUI.
