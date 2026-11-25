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

## Touch Bar: editor di fnstrip (scheda Touch Bar)

Modifica `~/.config/fnstrip/config.toml` (renderer fnstrip della modalità display) senza scrivere TOML:

- **Aspetto**: tema (classico, pastello, mono, arcobaleno, **OLED**), riga principale (comandi oppure Esc + F1-F12), °C/°F,
  animazione all'avvio.
- **Colori personalizzati** sopra il tema (sfondo, tasti, scritte, tasto acceso, cursori...): clic per scegliere,
  clic destro per tornare al colore del tema.
- **Riga extra** (doppio tocco su Fn, fino a 10 pulsanti): aggiungi, togli e riordina interruttori (microfono, webcam
  virtuale, VPN con i tuoi comandi) e indicatori (CPU, memoria, disco, rete, batteria, temperatura, ventole); per gli
  interruttori si possono cambiare comando e comando di stato. Anteprima schematica della riga.
- **Salva e applica**: controlla i valori, salva (la versione precedente resta in `config.toml.bak`), riavvia il
  renderer se la barra è in modalità display e riporta nel registro gli eventuali errori segnalati da fnstrip.

**OLED** è un preset del manager, non un tema di fnstrip (che ne ha quattro compilati): `theme = "mono"` più tutti i
`[colors]` (sfondo e tasti `#000000`, scritte `#ffffff`, tasto premuto `#404040`, icone spente `#707070`, cursori
`#1a1a1a`, volume muto `#101010`). Tasto acceso e riempimento dei cursori restano grigi (`#2e2e2e`, `#1a1a1a`) perché fnstrip ci disegna sopra le icone con il
colore delle scritte. Si riconosce rileggendo il file; cambiando un colore a mano diventa "Mono" con colori propri.

I commenti scritti a mano nel file vengono rigenerati; le chiavi che il manager non conosce vengono conservate.

## Touch Bar in diretta, screenshot e video

Pulsante **Touch Bar in diretta…** nella scheda Touch Bar (o voce del menu dell'icona): una finestra mostra lo schermo
della barra in tempo reale, ingrandito, con il punto toccato in rosso; **Cattura PNG** salva il fotogramma a
risoluzione piena (2170×60) in Immagini, **Registra video** un MP4 (H.264, 30 fps) in Video. Da terminale:
`macbook-manager touchbar-screenshot [file.png]`. [F] Provata sul 14,3 il 24/11/2026: vista in diretta controllata dall'utente; PNG,
video di 3 s a 30 fps e pulizia della RAM verificati.

Come funziona: usa la registrazione di debug di fnstrip (`src/record.rs`): finché esiste `$XDG_RUNTIME_DIR/fnstrip-record`,
fnstrip aggiunge ogni fotogramma inviato alla barra a `~/.cache/fnstrip-record/frames.raw` (XRGB8888) e scrive tocchi e
invii in `events.log`. Per non consumare l'SSD (~0,5 MB a fotogramma, fino a 60 al secondo nelle animazioni) quella cartella
diventa un collegamento a `/run/user/<uid>` (RAM) finché la cattura è attiva, e i file ripartono da zero oltre 64 MB;
chiudendo la finestra tutto viene rimosso. Solo in modalità display con fnstrip, senza root.

Limite: fnstrip invia un fotogramma solo quando qualcosa cambia; all'apertura, finché la barra è ferma, la finestra chiede
di toccarla (o di cambiare volume/luminosità). Poi mostra sempre l'ultimo, che è quello sullo schermo.

## Ottimizzazione (scheda Ottimizzazione)

Elenca le app Chromium/Electron e le **web app** installate dal browser (Brave, Discord, Claude Desktop, Sidra, …) con
lo stato di ciascuna (ottimizzata / da ottimizzare), le app in esecuzione con la GPU attiva o spenta e lo stato del
servizio. **Ottimizza tutte** applica in un colpo le correzioni verificate il 24/11/2026 (`docs/gpu.md`):
`AMD_DEBUG=notiling` solo per queste app (restano su Wayland e usano la Radeon), riattivazione dell'accelerazione di
Claude Desktop, servizio utente che ottimizza le app installate dopo. **Annulla ottimizzazioni** toglie tutto. Usa
`fix-chromium-gpu` installato accanto al manager (copia di `scripts/fix-chromium-gpu.sh`, gira come utente). Dopo
l'ottimizzazione le app vanno chiuse del tutto e riaperte.

## App Chromium/Electron (gruppo App)

Controlla dal vivo i processi GPU di Chromium/Electron (Brave, Discord, Claude Desktop, …) e segnala quelli con
l'accelerazione spenta (`--use-gl=disabled`: sotto Wayland crollano con i buffer tiled della Radeon, vedi `docs/gpu.md`), con l'azione che
rilancia `~/.local/lib/macbookpro14-3/fix-chromium-gpu` (installato da `scripts/fix-chromium-gpu.sh`).

## Touch ID (modalità display, dopo `scripts/install-touchid.sh`)

Scheda **Stato**, gruppo Touch ID: servizi (xART, relay della keybag), **attivazioni del relay in questo avvio** (giallo da
50, rosso da 65: T1Bridge si blocca a ~68 per avvio, issue #14) e stato di sudo e schermata di blocco. Scheda **Azioni**:
impronta per sudo sì/no, impronta nella schermata di blocco sì/no (con avviso sul limite), **Gestisci impronte** (apre
Impostazioni di sistema → Utenti, dove si registrano e cancellano le dita), **Prova impronta** (`fprintd-verify`, esito nel
registro), **Impronte registrate** (`fprintd-list`). Gli interruttori usano `/usr/local/bin/touchid-pam`.

## Azioni (`macbook-manager actions`, `macbook-manager run <id>`)

| Gruppo | Azioni |
|---|---|
| Touch Bar | modalità display (subito) / tastiera (salvata, attiva dopo lo spegnimento: il manager propone di spegnere), riavvia il renderer, renderer fnstrip/T1Bridge o tiny-dfr (dopo `scripts/install-tiny-dfr.sh`), webcam virtuale on/off |
| Sospensione | S3 (deep) / s2idle |
| Energia | Radeon in risparmio a batteria sì/no, turbo CPU a batteria sì/no (`power.conf` + riapplica) |
| Rete e audio | ricarica il driver Wi-Fi, ripristina l'audio delle chiamate Bluetooth (CVSD) |
| Manutenzione | app Chromium/Electron: correzione GPU (`fix-chromium-gpu`), ricompila i driver DKMS per il kernel in uso, spegni il Mac (azzera anche il T1) |

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
