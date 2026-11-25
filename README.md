# CachyOS sul MacBook Pro 15" 2017 (MacBookPro14,3)

Questa repo serve a usare **CachyOS** (una distribuzione basata su Arch Linux) sul **MacBook Pro 15" del 2017 con
Touch Bar** (modello **MacBookPro14,3**, chip T1, Radeon Pro 555/560). Dopo aver installato CachyOS, **un solo comando**
installa driver, correzioni e impostazioni provate su questo Mac: Touch Bar con grafica e Touch ID, audio migliorato,
webcam, Wi-Fi a 5 GHz, sospensione, risparmio energetico e un'app, **MacBook Manager**, per controllare tutto.

> **Stato (25 novembre 2026):** provato su un MacBookPro14,3 vero con CachyOS, kernel `7.3.5-2-cachyos`, KDE Plasma 6.8.
> Quasi tutto funziona; restano due limiti veri: **niente ibernazione** e **autonomia di circa 4 ore** (la scheda video
> Radeon non si spegne mai). È un progetto personale, scritto con l'aiuto di un assistente IA e provato su **un solo Mac**.

![Touch Bar in modalità display: renderer fnstrip con il tema OLED](docs/media/touchbar-oled.png)
<sub>La Touch Bar disegnata da Linux (renderer fnstrip, tema OLED di MacBook Manager): Esc, luminosità, tastiera, media,
volume. Screenshot reale a 2170×60.</sub>

**Come capire se è il tuo modello:** in macOS, menu  → Informazioni su questo Mac → Resoconto di sistema: "Identificatore
modello" deve essere **MacBookPro14,3**. Gli altri MacBook (14,1, 14,2, 2016, 2018 con chip T2) **non** sono supportati.

## Cosa funziona

✅ funziona · 🟡 funziona con limiti · ❓ non provato · ❌ non funziona

| | Stato | Note |
|---|---|---|
| Tastiera e trackpad | ✅ | il trackpad si disattiva mentre scrivi |
| Touch Bar | ✅ | grafica completa: Esc, luminosità, volume, media, F1-F12 con Fn; due stili a scelta (fnstrip o tiny-dfr) |
| Touch ID | ✅ | sudo e schermata di blocco; vedi i limiti sotto |
| Audio: altoparlanti, cuffie, microfoni | ✅ | con l'elaborazione di Apple (tweeter/woofer separati, equalizzazione, protezioni) e bassi più pieni |
| Webcam | ✅ | anche in Discord e nel browser, senza disturbi |
| Wi-Fi 2,4 e 5 GHz | 🟡 | fino a ~290 Mbit/s; canale a 40 MHz invece di 80 |
| Bluetooth | 🟡 | musica in buona qualità (AAC); chiamate con cuffie solo in qualità telefonica |
| Sospensione (chiudendo il coperchio) | ✅ | una notte intera consuma quasi niente |
| Luminosità automatica dello schermo | ✅ | dal sensore di luce della Touch Bar |
| Autonomia | 🟡 | circa 4 ore a riposo |
| Monitor esterni, Thunderbolt | ❓ | non provati |
| Ibernazione | ❌ | disattivata: la scheda video non ripartirebbe |

I dettagli tecnici di ogni componente sono in [`docs/`](docs/README.md).

## Prima di iniziare

1. **Fai un backup completo di macOS** (Time Machine). Installare Linux significa ridimensionare il disco.
2. **Non cancellare mai la partizione EFI di Apple** (la prima del disco, `EFI`): contiene il firmware del chip T1. Senza
   di essa Touch Bar, webcam e sensore di luce smettono di funzionare. Linux userà una sua partizione EFI separata.
3. Tieni il Mac **collegato all'alimentatore** per tutta l'installazione.
4. Se puoi, tieni a portata una **tastiera USB-C**: durante l'installazione dalla chiavetta la tastiera interna potrebbe
   non funzionare.
5. Calcola **circa un'ora** in tutto: lo script compila diversi programmi.

## Passo 1: installare CachyOS

Il modo consigliato è la **chiavetta USB**:

1. Scarica l'immagine desktop da [cachyos.org](https://cachyos.org/download/) e scrivila su una chiavetta (per esempio
   con balenaEtcher).
2. In macOS, con **Utility Disco**, ricava spazio per Linux (almeno 60 GB, meglio 120 GB) ridimensionando il volume di
   macOS.
3. Spegni il Mac, collega la chiavetta e accendi tenendo premuto **Option (⌥)**. Scegli **EFI Boot**.
4. Nell'installatore scegli il **partizionamento manuale**:
   - una partizione nuova di ~500 MB, FAT32, montata su `/boot/efi` (EFI di Linux);
   - una partizione per il sistema montata su `/` (btrfs va bene);
   - **non toccare** la partizione EFI di Apple né quella di macOS.
5. Come bootloader usa **GRUB** (provato). systemd-boot e Limine sono sconsigliati sui Mac.

Da qui in poi, all'accensione, **Option (⌥)** ti fa scegliere fra macOS e CachyOS.

<details>
<summary>Alternativa senza chiavetta (per esperti, non completamente documentata)</summary>

[`macos/prepare.sh`](macos/prepare.sh), lanciato da macOS, ridimensiona il disco, crea una partizione `COSLIVE` con
l'immagine di CachyOS e una partizione per Linux. È così che CachyOS è stato installato su questo Mac, ma la procedura non
è stata documentata dall'inizio alla fine.

```bash
./macos/prepare.sh prepare --linux-gb 120            # mostra il piano, non cambia niente
./macos/prepare.sh prepare --linux-gb 120 --execute  # lo esegue (chiede conferme scritte)
```
</details>

## Passo 2: lanciare lo script di post-installazione

Avvia CachyOS, collegati al Wi-Fi (all'inizio funziona solo a 2,4 GHz) e apri un terminale (Konsole). Poi:

```bash
sudo pacman -Syu
```

**Riavvia** (il sistema deve usare il kernel appena aggiornato), riapri il terminale e scarica la repo:

```bash
git clone https://github.com/DriftDeV/Macbook14-3-cachyOS
```

```bash
cd Macbook14-3-cachyOS
```

Se vuoi, guarda prima cosa farà, senza cambiare niente:

```bash
sudo ./install.sh --dry-run
```

E installa:

```bash
sudo ./install.sh
```

Non fa domande: installa tutto. Verso la fine la connessione Wi-Fi cade per una ventina di secondi (si sta attivando il
5 GHz) e torna da sola. Se un passo non riesce gli altri vanno avanti, e il riepilogo finale dice quale rifare.
Registro completo: `/var/log/macbookpro14-3-install.log`.

Alla fine **spegni completamente** il Mac (non riavviare), aspetta **30 secondi** e riaccendi: il chip T1 deve ripartire
da zero.

## Passo 3: dopo la riaccensione

1. **Apri MacBook Manager** (dal menu delle applicazioni, o l'icona nella barra di sistema). Mostra lo stato di tutto e
   ha le azioni più comuni a portata di clic (ti chiede la password quando servono i permessi di amministratore).
2. **Configura Touch ID** (una volta sola). Nel terminale, dalla cartella della repo:
   ```bash
   sudo scripts/install-touchid.sh import
   ```
   Poi registra un dito da **Impostazioni di sistema → Utenti** (oppure MacBook Manager → Azioni → Touch ID). Se la prima
   registrazione fallisce, riprova: è normale. Per usare il dito con `sudo` e nella schermata di blocco: MacBook Manager →
   Azioni → Touch ID. Usa un dito **diverso** da quelli registrati in macOS.
3. **Scegli la Touch Bar** che preferisci, nella scheda **Touch Bar** di MacBook Manager (vedi sotto).

## La Touch Bar

Di base parte in **modalità display**, con la grafica disegnata da Linux e il renderer **fnstrip**. Dalla scheda
**Touch Bar** di MacBook Manager scegli:

- **Renderer**, cioè lo stile della barra:
  - **fnstrip / T1Bridge** (predefinito): temi, cursori di luminosità e volume, una riga "extra" con grafici (doppio tocco
    su Fn). Si personalizza dalla stessa scheda (pulsanti, colori, temi, luminosità).
  - **tiny-dfr** (quello di Asahi Linux): più semplice, tasti funzione e multimediali, ora e batteria. Anche questo si
    personalizza dalla scheda.
- **Modalità**:
  - **display** (consigliata): grafica di Linux, **necessaria per Touch ID**;
  - **tastiera**: i tasti fissi disegnati dal firmware, come in Boot Camp. Niente Touch ID. Il cambio diventa effettivo
    dopo uno **spegnimento completo**.

La Touch Bar non ha una luminosità propria regolabile dall'hardware: lo slider nel manager scurisce i colori.

## Uso quotidiano

| Cosa | Come |
|---|---|
| Stato di tutto, azioni rapide | **MacBook Manager**, oppure `macbook-manager status` nel terminale |
| Touch Bar: stile, pulsanti, luminosità | MacBook Manager → scheda **Touch Bar** |
| Webcam in Discord o nel browser | MacBook Manager → Azioni, oppure `t1-webcam on`; poi scegli la camera "T1 camera (Discord)" nell'app |
| App lente (Brave, Discord, web app…) | MacBook Manager → scheda **Ottimizzazione** (già fatto dall'installazione per le app presenti) |
| Screenshot o video della Touch Bar | MacBook Manager → Touch Bar → **Touch Bar in diretta…** |
| Altoparlanti: preset e regolazioni | MacBook Manager → scheda **Audio**: DSP di fabbrica, con bassi, bassi intensi, notte; intensità e frequenza dei bassi, livello massimo, bilanciamento. L'uscita si chiama **MacBook Pro 14,3 Speakers**, il microfono **MacBook Pro 14,3 Microphone** |
| Risparmio energetico | automatico: a batteria la scheda video va in risparmio e la CPU senza turbo |

## Problemi noti e rimedi

- **Touch Bar spenta** (ma il tocco funziona), oppure strana dopo un cambio di modalità: **spegni completamente**, aspetta
  30 secondi, riaccendi. È l'unico modo per far ripartire il chip T1.
- **Nessun suono dopo l'accensione**: nel terminale `grep Subsystem /proc/asound/card*/codec#0` deve dire `0x106b3900`.
  Se dice `0x10138409` è un bug noto di questo modello: spegni e riaccendi; se non basta, reset della NVRAM (all'accensione
  tieni premuti ⌥ ⌘ P R per ~20 secondi).
- **App che smettono di suonare** dopo aver collegato o scollegato le cuffie (soprattutto i browser): premi di nuovo play.
- **Touch ID non riconosce più il dito** dopo molti usi nella stessa sessione: è un limite noto (~68 riconoscimenti per
  avvio). Sblocca con la password; Touch ID torna dopo uno spegnimento completo. Dopo la sospensione serve circa 10 secondi
  prima che sia di nuovo pronto.
- **Wi-Fi a 5 GHz debole dopo essere passati da macOS**: in macOS usa "Spegni" invece di "Riavvia".
- **La sospensione sembra bloccata**: aspetta almeno 3 minuti prima di forzare lo spegnimento.
- **Aggiornamenti del kernel**: i driver si ricompilano da soli. Audio e webcam hanno sorgenti per la serie 7.3: con una
  serie nuova del kernel potrebbero dover essere aggiornati in questa repo (la Touch Bar torna da sola in modalità tastiera
  se la modalità display non si compila).
- **iPhone collegato via USB**: la regola di `usbmuxd` può spegnere il T1; gli script avvisano se la trovano.

## Per esperti

<details>
<summary>Cosa fa install.sh, passo per passo</summary>

Ogni passo è uno script in [`scripts/`](scripts/) e si può rifare da solo con `sudo ./install.sh --only <passo>`
(o saltare con `--skip <passo>`).

| Passo | Cosa fa |
|---|---|
| `backup` | copia l'EFI di Apple e il firmware del T1 in `/var/backups/macbookpro14-3` (indispensabile) |
| `packages` | pacchetti necessari e header di ogni kernel installato |
| `input` | quirk libinput (trackpad disattivato mentre scrivi) |
| `touchbar` | Touch Bar in modalità tastiera (`apple-ibridge`, DKMS): sempre installata, serve anche in sospensione |
| `audio` | driver del codec CS8409 (davidjo, fork dnlbtz, DKMS) |
| `audio-dsp` | pacchetti [`pkgs/bankstown-lv2`](pkgs/bankstown-lv2/) e [`pkgs/mbp143-audio`](pkgs/mbp143-audio/): filtro PipeWire con crossover, equalizzazione, limitatori e protezione termica di Apple, più i bassi psicoacustici di Asahi; +35 dB al microfono delle cuffie. Costa ~1,5 W |
| `sleep` | sospensione S3, Thunderbolt scollegato prima della sospensione, NVMe senza D3cold, ibernazione disattivata |
| `power` | a batteria Radeon in risparmio e CPU senza turbo; piena potenza con l'alimentatore |
| `bluetooth` | audio delle chiamate (SCO via HCI), mSBC disattivato |
| `brightness` | curva di partenza della luminosità automatica di KWin |
| `touchbar-display` | compila T1Bridge, installa driver display e webcam (con la correzione dei buffer H.264), servizi, `touchbar-mode`, renderer fnstrip; salva la modalità display |
| `tiny-dfr` | compila tiny-dfr con le patch per il T1; resta inattivo finché non lo scegli |
| `touchid` | servizi Touch ID di T1Bridge, rete privata del T1, libfprint/fprintd, regola ufw, interruttori PAM (spenti finché non li attivi) |
| `manager` | MacBook Manager: GUI, icona nella barra di sistema, helper con polkit ([manager/README.md](manager/README.md)) |
| `apps` | da utente: `AMD_DEBUG=notiling` per le app Chromium/Electron sotto Wayland, più un servizio per quelle installate dopo |
| `wifi` | per ultimo: NVRAM generata dalla calibrazione del chip, firmware, impostazioni di NetworkManager |

Altre opzioni: `--yes` (nessuna conferma), `--wifi-nvram FILE`, `--initramfs` (non provato, solo per disco cifrato),
`--list`. La modalità e il renderer della Touch Bar si cambiano anche da terminale: `sudo touchbar-mode set
display|keyboard`, `sudo touchbar-mode renderer t1bridge|tiny-dfr`.
</details>

<details>
<summary>Schermo sulla scheda Intel (facoltativo, con OpenCore)</summary>

Di base lo schermo è collegato alla Radeon. Avviando Linux da **OpenCore Legacy Patcher** con l'opzione "Windows GMUX"
(`SignalAppleOS`) e la variabile EFI `gpu-power-prefs` impostata sulla Intel, lo schermo passa alla Intel: circa 1,5-2 W in
meno a riposo, luminosità funzionante. La Radeon resta comunque accesa. Sospensione e monitor esterni non ancora riprovati
in questa configurazione. Dettagli e come tornare indietro in [docs/gpu.md](docs/gpu.md).
</details>

<details>
<summary>Struttura della repo</summary>

```
install.sh              post-installazione (sudo ./install.sh --dry-run)
macos/prepare.sh        da macOS: partizione live sul disco interno, senza USB
scripts/                un installer per componente, touchbar-mode, sleep-test, build di T1Bridge, fnstrip, tiny-dfr
manager/                MacBook Manager: comando, GUI Qt, helper polkit
config/                 sorgenti esterne fissate (sources.conf), udev, systemd, sleep, power, NetworkManager,
                        WirePlumber, KDE, libinput, T1Bridge, tiny-dfr
dkms/                   driver display e webcam della modalità display (T1Bridge, Linux 7.3)
patches/                patch nostre per Touch Bar, audio e tiny-dfr
pkgs/                   PKGBUILD: mbp143-audio e bankstown-lv2 (usati da install.sh); meta e apple-ibridge (non aggiornati)
docs/                   risultati per componente e report di ricerca (indice: docs/README.md)
```

Le sorgenti esterne sono **fissate a un commit** e il loro codice è stato letto prima dell'uso
([`config/sources.conf`](config/sources.conf) e i PKGBUILD). Il file NVRAM del Wi-Fi non è nella repo: viene generato sulla
macchina dalla calibrazione del chip.
</details>

## Crediti

- Touch Bar (tastiera): roadrunner2/cb22 → marc-git → F13-Kr1pt0n → **nonderbe** (`t1-fixes`).
- Touch Bar (display), webcam H.264, Touch ID: **T1Bridge** (Andrew Boyd, Standard Agents), `appletbdrm` di Kerem Karabay.
- Renderer: **fnstrip** (Alex McCubbin); **tiny-dfr** (Asahi Linux), sul T1 come in heymaaz/mbp-t1-touchbar.
- Audio: **davidjo/snd_hda_macbookpro**, fork **dnlbtz**; DSP degli altoparlanti **dnlbtz/mbp143-audio**; bassi
  psicoacustici **bankstown** (James Calligeros, Asahi Linux).
- Wi-Fi: **dnlbtz/mbp143-wifi**; impostazioni di scansione da **mihneadevries/mbp14-3-linux-wifi-fix**.
- Sospensione: **mihneadevries/mbp14-3-linux-sleep-fix**.
- Tracker storico: Dunedan/mbp-2016-linux.

Ognuno resta con la sua licenza (GPL-2.0 per i moduli del kernel, MIT per gli altri, vedi i singoli file).
