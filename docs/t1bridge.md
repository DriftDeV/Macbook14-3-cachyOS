# fnstrip e T1Bridge: grafica della Touch Bar e Touch ID sul T1 (analisi in sola lettura)

Data: 23 novembre 2026. Analisi del codice e della documentazione su GitHub, **niente installato né eseguito**.
Tag come in [`README.md`](README.md).

## Correzione

Le note di ricerca (cschaba) dicevano che il T1 "non ha framebuffer, 4 layout fissi". È vero solo nella
**configurazione USB 1** del T1, quella usata da questa repo (`apple-ibridge`/`apple-ib-tb`, modalità tastiera).
Nella **configurazione 2** il T1 espone un'interfaccia display (classe 0x10 "Audio/Video", interfaccia 3) che parla lo
stesso protocollo della Touch Bar dei T2, più una rete privata CDC-NCM verso il sistema del T1 (interfacce 4-5).
[F] Le interfacce corrispondono a quelle viste su questa macchina con `lsusb -v -d 05ac:8600` (config 2: 3 = classe 16,
4/5 = CDC). [C] Grafica personalizzata della Touch Bar e Touch ID sul T1 non sono quindi impossibili in assoluto.

## acmccubbin/fnstrip

- Rust, MIT, 0 stelle, creato e pubblicato l'11/11/2026, "beta", provato su **una** macchina (MacBookPro13,3).
- **Non è un driver**: è un renderer, cioè un programma utente che disegna fotogrammi XRGB8888 (fino a 40 al secondo) e li
  consegna a T1Bridge (memfd + socket seqpacket). È una copia modificata del renderer `t1-touchbar` di T1Bridge v0.1.12.
- Aggiunge temi, cursori per luminosità/volume, grafici di CPU/rete/batteria, spettro del microfono. I pulsanti personali
  eseguono comandi con `sh -c` dal file di configurazione dell'utente.
- Senza T1Bridge non fa niente.

## standardagents/t1bridge

- Rust + C, MIT (moduli kernel GPL-2.0), 54 stelle, 16 fork, 38 issue aperte, creato il 05/09/2026, ultimo push
  20/09/2026, mantenuto da Andrew Boyd. Pacchetti firmati solo per Arch, dal repo `linux.standardagents.ai`.
- Componenti:
  - `kernel/appletbdrm-t1`: il driver mainline `appletbdrm` (T2) di Linux 7.1.8 adattato al T1 (ID `0x8600`, ordine
    delle risposte, niente controllo del timestamp). Installato in `updates/dkms`, sostituisce quello del kernel. Tre patch
    pronte per l'upstream, **non inviate**.
  - `kernel/apple-t1-ncm`: adattatore CDC-NCM per la rete privata verso il T1.
  - Servizi per Touch ID (fprintd/libfprint propri, keybag, xART, SEP), import dei dati Apple
    (`EFI/APPLE/EMBEDDEDOS/FDRData` dalla ESP), driver UVC per la webcam H.264, codice di recovery/restore del T1.
- Stato dichiarato dal README per il **MacBookPro14,3**: 🟡 "enrollment confermato dopo la configurazione del firewall
  xART; copertura più ampia non confermata" (un solo tester, issue #2). Display della Touch Bar non confermato
  esplicitamente sul 14,3.
- **Sospensione: 🔴 "non funziona sulla macchina provata"** (issue #18: dopo S3 il pannello resta scuro). Sul 14,2:
  coperchio riaperto con schermo nero. Altri casi di pannello scuro: #31, #34.

## Perché non installarlo adesso

1. **Sostituisce lo stack Touch Bar che funziona** (configurazione 1, `apple-ibridge`): i due non convivono ("non scambiare
   a caldo driver T1 concorrenti").
2. **Perderemmo la sospensione**, che qui funziona (docs/sleep.md): con T1Bridge è dichiarata non funzionante.
3. Driver basato su Linux 7.1.8, non provato con 7.3 né con kernel compilati con clang (`linux-cachyos`).
4. Installa pacchetti binari da un repo di terzi, sostituisce libfprint/fprintd per tutto il sistema, apre una porta (IPv6
   TCP 61500) sul collegamento privato col T1; il codice di recovery del T1 può lasciarlo in modalità recovery
   (`05ac:1281`), secondo le note di mihneadevries, che l'hanno valutato ma non installato.
5. Regola 4 di AGENTS.md: il codice va letto prima di integrarlo; qui sono decine di migliaia di righe.

## Prova a runtime del 23/11/2026 [F]

Solo la parte Touch Bar di T1Bridge **v0.1.12** (commit `81cbdf8`), compilata da sorgente, niente installato:

- `kernel/appletbdrm-t1/appletbdrm.c` compilato per `7.3.5-2-cachyos` con `LLVM=1`, senza warning. Si aggancia solo a
  `05ac:8600` interfaccia classe 0x10 (esiste solo in configurazione 2). Letto: nessun reset USB, cambio configurazione,
  file o firmware; il comando HID "park" scatta solo in sospensione.
- `t1-touchbar-hw` e `t1-touchbar` (Rust 1.100, `cargo build --release --locked`, dipendenze esterne poche e note).
  Letti: tocco da hidraw (solo lettura), Fn dalla tastiera, tasti con uinput, logind via D-Bus; nessuna scrittura al
  T1, nessun programma esterno. Il renderer esegue `~/.config/t1bridge/renderer` se esiste e il provider del desktop.
- Script: `scripts/experimental/t1bridge-touchbar-try.sh` (tutto in `/run`: modulo, programmi, blocco di
  `apple_ib*`, regola udev che tiene il display fuori dalla sessione, unit systemd, `iio-sensor-proxy` mascherato
  `--runtime`), `t1bridge-touchbar-undo.sh`, `t1bridge-desktop-provider` (da fnstrip, MIT: volume/muto con wpctl,
  media con MPRIS). Da utente: `T1BRIDGE_DESKTOP_PROVIDER=<percorso> /run/t1test/t1-touchbar`.

Risultato:

| Funzione | Esito |
|---|---|
| T1 in configurazione 2, `appletbdrm` per `1-3:2.3` | OK (`/dev/dri/card0`, `touchbar -> card0`, non assegnato alla sessione: KWin non lo usa) |
| Grafica della Touch Bar (renderer incluso) | **funziona** |
| Tocco, Esc, luminosità schermo, retroilluminazione tastiera, media | **funzionano** |
| Volume e muto | funzionano con il provider del desktop |
| Puntatore che si muove toccando la barra | no (segnalato dall'utente) |
| Webcam | **non disponibile**: `uvcvideo` "No streaming interface" (in config 2 serve `uvcvideo-t1`, H.264) |
| Sensore di luce | presente con i driver standard (`hid_sensor_als`, `iio:device0`); `iio-sensor-proxy` fermo durante la prova |
| Sospensione | non provata (T1Bridge la dichiara non funzionante) |

Il primo tentativo si è fermato perché `apple_ib_als` era in uso da `iio-sensor-proxy`: lo script ora lo maschera.

### Ritorno a caldo alla modalità tastiera [F]

`scripts/experimental/t1bridge-touchbar-mode.sh keyboard` (configurazione 1, `apple-ibridge` ricaricato, webcam e
`iio-sensor-proxy` di nuovo attivi): driver legati senza errori, **tocco ed Esc funzionano ma la barra resta spenta**,
anche ricaricando `apple_ib_tb`. È lo stato "touch works, no light" delle note di mihneadevries: il lato display del T1
resta nello stato della configurazione 2. Cura nota: spegnimento completo (~30 s) e riaccensione.
Per la sospensione non conta (la modalità tastiera serve solo durante lo sleep), per il ritorno manuale sì.

## Sospensione e webcam in modalità display [F]

`scripts/experimental/t1bridge-touchbar-mode.sh display|keyboard|status` riunisce prova e annullamento (tutto in `/run`):

- **Sospensione**: unit temporanea `t1test-sleep.service` (`WantedBy=sleep.target`, `Before=sleep.target`,
  `StopWhenUnneeded`): prima dello sleep passa a `keyboard` (configurazione 1 + `apple-ibridge`, la strada provata in
  `docs/sleep.md`), al risveglio torna a `display`. Il renderer è un servizio utente temporaneo
  (`/run/user/<uid>/systemd/user/t1test-touchbar.service`).
  - Prova `sleep-test.sh platform`: riuscita, la Touch Bar torna con grafica e tocco.
  - Prova `sleep-test.sh real 60`: dormito 19:04:04-19:05:00, modalità display ripristinata da sola
    (`suspend_stats` 2 successi, 0 fallimenti).
- **Webcam**: in configurazione 2 la camera offre solo **H.264** 1280×720 fino a 30 fps. `uvcvideo` di Linux **7.3**
  con le due patch di T1Bridge (`kernel/uvcvideo-t1/upstream/`: parser H.264 con controlli dei limiti, niente
  autosospensione per il T1; un blocco di include adattato a mano) compilato con `LLVM=1` senza warning.
  - ffmpeg: 94 fotogrammi in 3 s; **OBS funziona** (decodifica H.264).
  - Discord e browser vogliono video non compresso: `v4l2loopback` (già nel kernel CachyOS) crea `/dev/video10`
    "T1 camera (Discord)" e il servizio utente `t1test-webcam` (ffmpeg, decodifica VA-API sulla GPU Intel, ~5 % di un
    core) la alimenta su richiesta (LED acceso mentre gira). **Discord funziona.** Da fnstrip `contrib/t1-webcam` (MIT).
- Ritorno manuale a `keyboard` senza riavvio: tocco OK, barra spenta fino allo spegnimento completo (sopra).

### Reset del T1 senza spegnere: non possibile [F] (23/11/2026)

Prova (`touchbar-mode keyboard` dalla modalità display, poi un metodo alla volta, barra osservata dall'utente):

| Metodo | Esito |
|---|---|
| porta USB interna `usb1-port3`: `disable` 1 per 3 s, poi 0 | nessuna disconnessione nel kernel (stesso device number), barra spenta |
| reset USB del dispositivo (`USBDEVFS_RESET`) | `reset high-speed USB device`, driver riagganciati, barra spenta |
| sospensione S3 di ~15 s in modalità tastiera | al risveglio solo `reset high-speed USB device`: il T1 non perde corrente, barra spenta |

Il T1 è un SoC con alimentazione propria: si azzera solo con lo spegnimento completo. L'unico reset software noto è il
metodo ACPI `FRST` usato da t1-revive (`docs/linux-recovery.md` di T1Bridge), che manda il T1 in recovery
(`05ac:1281`) da cui esce solo ricaricando il firmware: **non usarlo** [I dalla documentazione].

Di conseguenza `touchbar-mode set keyboard` dalla modalità display **salva soltanto** la scelta: la grafica resta fino
allo spegnimento completo e MacBook Manager propone di spegnere subito. `touchbar-mode keyboard` (senza `set`) fa
ancora il passaggio a caldo, usato dalla sospensione. Se la barra resta spenta in modalità tastiera dopo la modalità
display, il manager lo segnala (file `/run/macbookpro14-3/touchbar/display-this-boot`) con il pulsante "Spegni ora".

Provato dal manager il 23/11/2026 [F]: *Correggi* (display a caldo, 23:58:31) → *Modalità tastiera* (solo salvata,
grafica rimasta) → spegnimento proposto dal manager → riavvio alle 23:59:24 in modalità tastiera con la barra accesa.

## Installazione stabile (modalità sceglibile)

Gli script sperimentali (`scripts/experimental/`) sono stati sostituiti da:

| File | Ruolo |
|---|---|
| `dkms/t1bridge-appletbdrm/` | driver display T1 (sorgente T1Bridge `81cbdf8`), modulo `appletbdrm` in `updates/`, solo kernel 7.x |
| `dkms/t1bridge-uvc/` | `uvcvideo` di Linux 7.3 + patch T1 (`uvcvideo-t1-on-linux-7.3.patch`), modulo **`uvcvideo_t1`**, bloccato dal caricamento automatico, solo serie 7.3 |
| `scripts/build-t1bridge.sh` | da utente: clona T1Bridge al commit fissato (`config/sources.conf`) e compila `t1-touchbar-hw` e `t1-touchbar` |
| `scripts/install-touchbar-display.sh` | installa tutto, `--undo` toglie tutto; non cambia modalità |
| `scripts/touchbar-mode.sh` → `/usr/local/bin/touchbar-mode` | `status`, `set display\|keyboard`, `display`, `keyboard`, `boot`, `sleep-pre/post` |
| `config/t1bridge/` | unit (servizio hardware, avvio, sospensione), servizi utente (renderer, webcam virtuale), regola udev, blocco `uvcvideo_t1`, provider del desktop, comando `t1-webcam` |

Principio: la modalità **keyboard** (predefinita) non usa nessuno di questi pezzi. Se dopo un aggiornamento del kernel
i driver DKMS non compilano, `touchbar-mode` rifiuta la modalità display e la Touch Bar resta quella di sempre.
In modalità display `iio-sensor-proxy` viene riavviato sul sensore esposto da `hid_sensor_als` (driver del kernel).

## fnstrip come renderer [F]

- Codice letto (commit `4a71af6`, 18.000 righe Rust): dipende solo da `t1-platform` e `t1-touchbar-hw` di T1Bridge
  `81cbdf8`; niente rete né `unsafe`; scritture su file solo nei test (`demo_media.rs`); il file di stato di Touch ID è
  solo letto. Esegue `brightnessctl`, `busctl`, `dbus-monitor`, `pw-record`, `ffmpeg`, `systemctl`, `date`, il provider
  e, con `sh -c`, i comandi dei pulsanti del suo `config.toml` (nella configurazione predefinita solo il muto del
  microfono con `wpctl`).
- `scripts/install-fnstrip.sh` (da utente): compila con `--locked`, installa `~/.local/bin/fnstrip`, copia la
  configurazione predefinita e crea `~/.config/t1bridge/renderer`; `--undo` torna al renderer incluso.
  Serve `brightnessctl` per i cursori di luminosità e tastiera.
- Prova del 23/11/2026: animazione di avvio, controlli, cursori e riga extra **funzionano** (confermato dall'utente).
- Nota: il pulsante camera di fnstrip cerca `t1-webcam.service`; con la nostra webcam virtuale accesa
  (`macbookpro14-3-webcam`) la camera risulta occupata.

### Prove dell'installazione stabile [F]

- `install-touchbar-display.sh`: DKMS installati per `7.3.5-2-cachyos`, saltati di proposito sull'LTS 6.18; servizi di
  avvio e sospensione abilitati; scelta `TOUCHBAR_MODE=display`.
- Passaggio a caldo: restava appeso su `Expecting device /dev/dri/touchbar`, perché lo schermo era nato con la regola udev
  della prova (senza `TAG+="systemd"`), e si sbloccava solo con un unbind/rebind (segnalato dall'utente). Ora
  `touchbar-mode` fa `udevadm trigger --action=change` sullo schermo, aspetta `dev-dri-touchbar.device` e solo poi avvia
  il servizio (se non compare in ~5 s si ferma con un messaggio).
- Dopo uno spegnimento completo la modalità display **parte da sola** e fnstrip disegna sulla barra (confermato
  dall'utente il 23/11/2026); in modalità display la webcam c'è (`/dev/video0`, `/dev/video1`, `/dev/video10`).
- Al login il renderer può risultare "skipped" (`ConditionPathExists`): la sessione parte prima del servizio di avvio;
  poi `touchbar-mode` lo avvia da sé.

### Sospensione lunga: barra spenta al risveglio [F] (corretto)

Sospensione di ~18 minuti (20:51-21:08 del 23/11/2026) in modalità display: al risveglio la Touch Bar è rimasta spenta.
- `macbookpro14-3-touchbar-sleep.service: Stopping timed out. Terminating` dopo **10 s**: CachyOS imposta
  `DefaultTimeoutStopSec=10s`. Il ritorno a `display` (ExecStop) era fermo su `udevadm settle`, che dopo una
  sospensione lunga ha molti eventi da smaltire; lo schermo (`appletbdrm`, `card0`) c'era già, il servizio della barra
  non è stato avviato.
- Prima dello sleep `uvcvideo_t1` era aperto da un programma (sconosciuto): non scaricabile, e `uvcvideo` non poteva
  registrarsi (`Driver 'uvcvideo' is already registered`). Nessun danno alla sospensione.
- Correzioni: `TimeoutStartSec=120`/`TimeoutStopSec=120` nell'unit di sospensione; `touchbar-mode keyboard` lascia
  caricato `uvcvideo_t1` se è in uso (gestisce anche la configurazione 1) e non tenta `modprobe uvcvideo`.
- Ripristino senza riavvio: `sudo touchbar-mode display` (lo schermo era già in configurazione 2).
- [NV] Nuova prova di sospensione lunga con le correzioni.

## Touch ID: quadro aggiornato al 24/11/2026

Vedi [`touchid-t1.md`](touchid-t1.md). Il punto 1 e 2 di "Perché non installarlo adesso" valgono solo per il pacchetto
completo: la modalità display fornisce già la configurazione 2 e la sospensione funziona passando alla 1. Per Touch ID
mancano solo `apple-t1-ncm`, xART, relay keybag, broker e la coppia fprintd/libfprint di T1Bridge. **`t1bridge-dkms`
resta escluso** (blocca `apple_ibridge`, necessario alla sospensione).

## Da seguire

Issue #18 (sospensione) e #2 (14,3). Quando la sospensione funzionerà, valutare una prova reversibile su un'installazione
di riserva, dopo un backup verificato di `EFI/APPLE/EMBEDDEDOS/FDRData`.
