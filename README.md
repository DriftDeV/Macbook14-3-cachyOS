# Linux sul MacBook Pro 15" 2017 (MacBookPro14,3): CachyOS o Omarchy

Questa repo serve a usare Linux sul **MacBook Pro 15" del 2017 con Touch Bar** (modello **MacBookPro14,3**, chip T1,
Radeon Pro 555/560) con una di due distribuzioni basate su Arch:

- **CachyOS** con KDE Plasma: si installa accanto a macOS (o al suo posto), anche senza chiavetta;
- **Omarchy** con Hyprland: si installa **solo da chiavetta USB** e **prende tutto il disco**.

Dopo l'installazione, **un solo comando** (`install.sh`, uguale per tutti e due) installa driver, correzioni e
impostazioni provate su questo Mac: Touch Bar con grafica e Touch ID, audio migliorato, webcam, Wi-Fi a 5 GHz,
sospensione, risparmio energetico e un'app, **MacBook Manager**, per controllare tutto.

> **Stato (26 novembre 2026):** provato su un MacBookPro14,3 vero: CachyOS + KDE Plasma 6.8 (kernel `7.3.5-cachyos`,
> fino al 25/11) e Omarchy + Hyprland (kernel `7.2.15-omarchy`, dal 26/11). Quasi tutto funziona; restano due limiti veri:
> **niente ibernazione** e **autonomia di circa 4 ore** (la scheda video Radeon non si spegne mai). È un progetto
> personale, scritto con l'aiuto di un assistente IA e provato su **un solo Mac**.

![Touch Bar con OmaBar su Omarchy](docs/media/touchbar-omabar.png)
<sub>OmaBar su Omarchy: Esc, luminosità dello schermo e della tastiera, brano in riproduzione, controlli multimediali,
volume, ora e batteria; i colori seguono il tema di Omarchy. Su CachyOS il renderer predefinito è fnstrip:</sub>

![Touch Bar con fnstrip su CachyOS](docs/media/touchbar-oled.png)

**Come capire se è il tuo modello:** in macOS, menu  → Informazioni su questo Mac → Resoconto di sistema:
"Identificatore modello" deve essere **MacBookPro14,3**. Gli altri MacBook (14,1, 14,2, 2016, 2018 con chip T2) **non**
sono supportati.

## Cosa funziona

✅ funziona · 🟡 funziona con limiti · ❓ non provato · ❌ non funziona

| | Stato | Note |
|---|---|---|
| Tastiera e trackpad | ✅ | il trackpad si disattiva mentre scrivi |
| Touch Bar | ✅ | grafica completa: Esc, luminosità, volume, media, F1-F12 con Fn; renderer a scelta (fnstrip, tiny-dfr, OmaBar) |
| Touch ID | ✅ | sudo e schermata di blocco; vedi i limiti sotto |
| Audio: altoparlanti, cuffie, microfoni | ✅ | con l'elaborazione di Apple (tweeter/woofer separati, equalizzazione, protezioni) e bassi più pieni |
| Webcam | ✅ | anche in Discord e nel browser, senza disturbi |
| Wi-Fi 2,4 e 5 GHz | 🟡 | fino a ~290-400 Mbit/s; canale a 40 MHz invece di 80 |
| Bluetooth | 🟡 | musica in buona qualità (AAC); chiamate con cuffie solo in qualità telefonica |
| Sospensione (chiudendo il coperchio) | 🟡 | vera sospensione (S3) dal kernel 7.3: una notte consuma quasi niente. Con kernel più vecchi (oggi `linux-omarchy` 7.2) resta `s2idle`, che su questo Mac non spegne le ventole |
| Autonomia | 🟡 | circa 4 ore a riposo |
| Monitor esterni, Thunderbolt | ❓ | non provati |
| Ibernazione | ❌ | disattivata: la scheda video non ripartirebbe |

I dettagli tecnici di ogni componente sono in [`docs/`](docs/README.md).

## CachyOS o Omarchy?

| | CachyOS | Omarchy |
|---|---|---|
| Desktop | KDE Plasma | Hyprland (tutto da tastiera, temi coordinati) |
| Installazione | chiavetta USB, oppure **senza chiavetta** da macOS ([`cachyos/macos/prepare.sh`](cachyos/macos/prepare.sh)) | **solo chiavetta USB** ([`omarchy/prepare-usb.sh`](omarchy/prepare-usb.sh), da macOS o da Linux) |
| Accanto a macOS | sì (partizionamento manuale) | no: l'installatore usa **tutto il disco** |
| Partizione EFI di Apple (firmware del T1) | resta dov'è | **cancellata** dall'installatore: va copiata prima e rimessa dopo |
| Renderer della Touch Bar | fnstrip | OmaBar (segue il tema di Omarchy) |
| Rete | NetworkManager | iwd |
| Aggiornamenti | `sudo pacman -Syu` | `omarchy update` |
| Impronta nella schermata di blocco | MacBook Manager | configurazione di hyprlock |
| Parti specifiche nella repo | [`cachyos/`](cachyos/) | [`omarchy/`](omarchy/) |

Tutto il resto (driver, audio, sospensione, energia, Touch ID, MacBook Manager) è comune e sta in `scripts/`, `config/`,
`dkms/`, `patches/`, `pkgs/` e `manager/`.

## Prima di iniziare (per entrambi)

1. **Fai un backup completo di macOS** (Time Machine), anche se pensi di tenerlo.
2. **La partizione EFI di Apple** (la prima del disco, `EFI`) contiene il **firmware del chip T1**:
   `EFI/APPLE/EMBEDDEDOS`. Il Mac lo carica nel T1 a ogni accensione. Senza quei file **Touch Bar, Touch ID, webcam e
   sensore di luce smettono di funzionare tutti insieme**. Lì c'è anche `FDRData`, la calibrazione di fabbrica del
   sensore di impronte di *questo* Mac. Se va persa, Touch ID non si configura più: la ricrea solo una reinstallazione di
   macOS. Con CachyOS basta non toccarla; con Omarchy va **copiata prima** e **rimessa dopo**. Gli script lo fanno per
   te, ma tieni una copia anche fuori dal Mac.
3. Tieni il Mac **collegato all'alimentatore** per tutta l'installazione.
4. Se puoi, tieni a portata una **tastiera USB-C**: dalla chiavetta la tastiera interna potrebbe non funzionare, e con
   il disco cifrato (predefinito su Omarchy) la password va scritta prima che parta il sistema.
5. Calcola **circa un'ora** in tutto: lo script di post-installazione compila diversi programmi.

## Installare CachyOS

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

Da qui in poi, all'accensione, **Option (⌥)** ti fa scegliere fra macOS e CachyOS. Poi vai a
[Post-installazione](#post-installazione-uguale-per-entrambi).

<details>
<summary>Alternativa senza chiavetta (solo CachyOS, per esperti, non completamente documentata)</summary>

[`cachyos/macos/prepare.sh`](cachyos/macos/prepare.sh), lanciato da macOS, ridimensiona il disco, crea una partizione
`COSLIVE` con l'immagine di CachyOS e una partizione per Linux. È così che CachyOS è stato installato su questo Mac, ma la
procedura non è stata documentata dall'inizio alla fine. **Con Omarchy non funziona**: vedi sotto.

```bash
./cachyos/macos/prepare.sh prepare --linux-gb 120            # mostra il piano, non cambia niente
./cachyos/macos/prepare.sh prepare --linux-gb 120 --execute  # lo esegue (chiede conferme scritte)
```
</details>

## Installare Omarchy

Tre cose da sapere prima:

- **Serve una chiavetta USB.** La live di Omarchy messa sul disco interno (come si fa per CachyOS) si avvia, ma
  l'installatore esclude il disco da cui è partita: non trova nessun disco su cui installare (provato il 26/11/2026).
- **L'installatore prende tutto il disco**: macOS, altri sistemi e **la partizione EFI di Apple con il firmware del
  T1** vengono cancellati. Per questo lo script della chiavetta ne fa una copia verificata, da rimettere dopo.
- **Wi-Fi nella live**: senza il file di calibrazione (NVRAM) della scheda, il chip Broadcom parte con valori generici
  (niente 5 GHz, segnale debole). Lo script della chiavetta prepara anche questo.

### 1. Preparare la chiavetta (da macOS o da Linux)

Scarica la ISO dal sito di Omarchy (con il suo SHA-256), collega una chiavetta da almeno 8 GB (**verrà cancellata**),
scarica questa repo e, dalla sua cartella:

```bash
# Prova: individua la chiavetta e mostra il piano, senza cambiare niente.
# macOS: --device diskN (diskutil list external); Linux: --device /dev/sdX (lsblk -o NAME,TRAN,SIZE,MODEL)
sudo omarchy/prepare-usb.sh --iso ~/Downloads/omarchy-X.Y.Z-x86.iso --sha256 <hash> --device /dev/sdX
```

```bash
# Esegue: chiede di scrivere CANCELLA.
sudo omarchy/prepare-usb.sh --iso ~/Downloads/omarchy-X.Y.Z-x86.iso --sha256 <hash> --device /dev/sdX --execute
```

Lo script (funziona con la bash di macOS e su Linux; su Omarchy usa `run0` al posto di `sudo`):

- formatta la chiavetta in FAT32 (`OMARCHY`) e ci estrae la ISO, così la live resta modificabile; la live trova i suoi
  file per etichetta (`archisolabel=OMARCHY`);
- copia `EFI/APPLE` (firmware del T1 con `FDRData`) e, se c'è, `EFI/OC` (OpenCore) in `macbook14-3/efi-backup`, con
  `SHA256SUMS` verificati e lo script `ripristina.sh`. Si ferma se non trova la partizione EFI di Apple;
- prepara il Wi-Fi della live in `macbook14-3/`:
  - se lo prepari **da Linux su questo stesso Mac**, con il Wi-Fi già sistemato, copia i file di calibrazione pronti.
    Con `--embed-wifi` li mette anche **dentro la live**, e non serve lanciare niente: ci vuole `squashfs-tools`,
    qualche GB libero in `/var/tmp` e qualche minuto;
  - da macOS (o da un altro PC) mette i file per generarli nella live dal chip, con `python3` della live [non
    verificato];
- copia questa repo (`Macbook14-3-cachyOS.tar.gz`), per il post-installazione anche senza rete.

I file di calibrazione del Wi-Fi e la copia della partizione EFI sono **di questo Mac**: non condividere la chiavetta.

### 2. Installare

1. Accendi tenendo premuto **Option (⌥)** e scegli **EFI Boot**.
2. Se la live non ha già il Wi-Fi sistemato (`--embed-wifi`), da un terminale della live:
   `bash /run/archiso/bootmnt/macbook14-3/wifi-live.sh`.
3. Installa Omarchy sul disco interno, con le impostazioni predefinite (disco cifrato, Limine come bootloader).

### 3. Rimettere il firmware del T1 (subito, al primo avvio)

Nel sistema installato, con la chiavetta collegata (si monta dal file manager, oppure `udisksctl mount -b /dev/sdX1`):

```bash
run0 bash /run/media/$USER/OMARCHY/macbook14-3/efi-backup/ripristina.sh /boot
```

Controlla la copia, rimette nella partizione EFI (`/boot` su Omarchy) solo i file mancanti e segnala quelli diversi
senza toccarli. Se la copia aveva OpenCore (`EFI/OC`), ricrea anche la sua voce di avvio:
`run0 scripts/opencore.sh install` (dalla cartella della repo; senza copia lo costruisce da OpenCorePkg, vedi
*Schermo sulla scheda Intel*). Poi **spegni completamente** il Mac, aspetta 30 secondi e riaccendi: il T1 riceve il firmware solo
all'accensione. Da qui in poi la guardia installata da `install.sh` lo controlla a ogni avvio.

### 4. Cose diverse su Omarchy

- Aggiornamenti con `omarchy update` (non `pacman -Syu`). Il kernel è `linux-omarchy`: i driver si compilano lo stesso.
  Con `linux-omarchy` 7.2 la sospensione resta `s2idle`: la vera sospensione (S3) si attiva da sola dal kernel 7.3.
- Impronte: **non** usare il menu di Omarchy *Setup > Security > Fingerprint*, che installerebbe il `fprintd` normale
  al posto di quello per il T1. Registra con MacBook Manager > Azioni > *Registra un'impronta* (o `fprintd-enroll`).
  Per `sudo`: `run0 touchid-pam sudo on`. Nella schermata di blocco (hyprlock) l'impronta si regola in
  `~/.config/hypr/hyprlock.conf` (sezione `auth`, `fingerprint`).
- Il 14,3 non è nell'elenco dei Mac di Omarchy: se l'installatore mette il driver proprietario `wl`, il passo `wifi` lo
  segnala. Questa repo usa `brcmfmac`, l'unico provato a 5 GHz.
- Nel terminale di alcune app (per esempio il pannello Terminale di Claude Desktop) `sudo` è bloccato
  ("nessun nuovo privilegio"): usa **`run0`** al posto di `sudo`.
- Icona del manager, renderer della Touch Bar e limite FPS partono con la sessione di systemd (uwsm). Se non partono,
  aggiungi `macbook-manager gui --tray` all'avvio (in `~/.config/hypr/autostart.lua`).

## Post-installazione (uguale per entrambi)

Avvia il sistema, collegati al Wi-Fi e apri un terminale. Aggiorna e **riavvia** (il sistema deve usare il kernel appena
aggiornato):

```bash
sudo pacman -Syu        # su Omarchy: omarchy update
```

Prendi la repo, dalla rete oppure dalla chiavetta di Omarchy:

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

E installa (su Omarchy `run0` al posto di `sudo`):

```bash
sudo ./install.sh
```

Senza rete, con i file del Wi-Fi presi dalla chiavetta di Omarchy:
`run0 ./install.sh --wifi-files /run/media/$USER/OMARCHY/macbook14-3/wifi/mbp143-wifi`.

Non fa domande: installa tutto e riconosce da solo il sistema. Su KDE: fnstrip, NetworkManager, correzione per KWin.
Su Omarchy: OmaBar come renderer, iwd, agente polkit. Verso la fine la connessione Wi-Fi cade per una ventina di
secondi (si sta attivando il 5 GHz) e torna da sola. Se un passo non riesce gli altri vanno avanti, e il riepilogo
finale dice quale rifare. Registro completo: `/var/log/macbookpro14-3-install.log`.

Alla fine **spegni completamente** il Mac (non riavviare), aspetta **30 secondi** e riaccendi: il chip T1 deve ripartire
da zero.

## Dopo la riaccensione

1. **Apri MacBook Manager** (dal menu delle applicazioni, o l'icona nella barra di sistema). Mostra lo stato di tutto e
   ha le azioni più comuni a portata di clic (ti chiede la password quando servono i permessi di amministratore).
2. **Configura Touch ID** (una volta sola). Nel terminale, dalla cartella della repo:
   ```bash
   sudo scripts/install-touchid.sh import
   ```
   Poi registra un dito da MacBook Manager → Azioni → Touch ID (su KDE anche da Impostazioni di sistema → Utenti). Se la
   prima registrazione fallisce, riprova: è normale. Usa un dito **diverso** da quelli registrati in macOS.
3. **Scegli la Touch Bar** che preferisci, nella scheda **Touch Bar** di MacBook Manager (vedi sotto).

## La Touch Bar

Di base parte in **modalità display**, con la grafica disegnata da Linux. Dalla scheda **Touch Bar** di MacBook Manager
scegli:

- **Renderer**, cioè lo stile della barra:
  - **fnstrip / T1Bridge** (predefinito su CachyOS): temi, cursori di luminosità e volume, una riga "extra" con grafici
    (doppio tocco su Fn).
  - **tiny-dfr** (quello di Asahi Linux): più semplice, tasti funzione e multimediali, ora e batteria.
  - **OmaBar** (predefinito su Omarchy, scritto per questa repo, [`omarchy/omabar/`](omarchy/omabar/README.md)): segue i
    colori del tema di Omarchy dal vivo. Mostra il brano in riproduzione con la copertina, la batteria con lo stato di
    carica e un livello apposta per la schermata di blocco; si spegne con lo screensaver.
  
  Ognuno si personalizza dalla stessa scheda (pulsanti, colori, luminosità).
- **Modalità**:
  - **display** (consigliata): grafica di Linux, **necessaria per Touch ID**;
  - **tastiera**: i tasti fissi disegnati dal firmware, come in Boot Camp. Niente Touch ID. Il cambio diventa effettivo
    dopo uno **spegnimento completo**.

La Touch Bar non ha una luminosità propria regolabile dall'hardware: lo slider nel manager scurisce i colori.

**Con Claude Code:** `install.sh` (passo `omabar`) installa la skill **`/omabar`**. In qualunque sessione, da qualunque
cartella, puoi chiedere modifiche alla barra ("metti il tasto screenshot al posto del muto", "orologio con i secondi",
"tasti più larghi"). Claude modifica `/etc/omabar/config.toml`, controlla, mostra un'anteprima e la barra si aggiorna
da sola; se serve, cambia anche il codice e reinstalla.

## Uso quotidiano

| Cosa | Come |
|---|---|
| Stato di tutto, azioni rapide | **MacBook Manager**, oppure `macbook-manager status` nel terminale |
| Touch Bar: stile, pulsanti, luminosità | MacBook Manager → scheda **Touch Bar** (oppure `/omabar` in Claude Code) |
| Webcam in Discord o nel browser | MacBook Manager → Azioni, oppure `t1-webcam on`; poi scegli la camera "T1 camera (Discord)" nell'app |
| App lente (Brave, Discord, web app…) | MacBook Manager → scheda **Ottimizzazione** (già fatto dall'installazione per le app presenti) |
| Screenshot o video della Touch Bar | MacBook Manager → Touch Bar → **Touch Bar in diretta…** |
| Altoparlanti: preset e regolazioni | MacBook Manager → scheda **Audio**: DSP di fabbrica, con bassi, bassi intensi, notte; intensità e frequenza dei bassi, livello massimo, bilanciamento. L'uscita si chiama **MacBook Pro 14,3 Speakers**, il microfono **MacBook Pro 14,3 Microphone** |
| Risparmio energetico | automatico: a batteria la scheda video va in risparmio e la CPU senza turbo |
| CPU: turbo, frequenza, temperatura | MacBook Manager → scheda **CPU**: regole per alimentatore e batteria (turbo, frequenza massima, profilo, limite di potenza, tetto di temperatura) e stato dal vivo |
| Limite FPS a batteria | MacBook Manager → scheda **GPU**: a batteria i giochi Vulkan si fermano a 60 FPS (predefinito) e la Radeon va al minimo; con l'alimentatore tornano liberi |
| GPU: schermo, giochi, risparmio | MacBook Manager → scheda **GPU**: chi usa quale GPU, GPU dello schermo al prossimo avvio (Intel per risparmiare, Radeon per giocare), profili della Radeon, GPU per ogni applicazione |
| Batteria: grafico e report | MacBook Manager → scheda **Batteria**: carica e consumi dal vivo, sessioni a batteria con autonomia stimata e cosa ha consumato; un report arriva da solo quando ricolleghi l'alimentatore (`macbook-manager battery-report` da terminale) |

## Problemi noti e rimedi

- **Touch Bar spenta** (ma il tocco funziona), oppure strana dopo un cambio di modalità: **spegni completamente**, aspetta
  30 secondi, riaccendi. È l'unico modo per far ripartire il chip T1.
- **Touch Bar, webcam e Touch ID tutti morti dopo una reinstallazione**: manca il firmware del T1 nella partizione EFI.
  Rimettilo dalla copia (`ripristina.sh` sulla chiavetta di Omarchy, oppure `/var/backups/macbookpro14-3/` e
  `sudo /usr/local/lib/macbookpro14-3/t1-guard.sh restore`), poi spegnimento completo.
- **Nessun suono dopo l'accensione**: nel terminale `grep Subsystem /proc/asound/card*/codec#0` deve dire `0x106b3900`.
  Se dice `0x10138409` è un bug noto di questo modello: spegni e riaccendi; se non basta, reset della NVRAM (all'accensione
  tieni premuti ⌥ ⌘ P R per ~20 secondi).
- **App che smettono di suonare** dopo aver collegato o scollegato le cuffie (soprattutto i browser): premi di nuovo play.
- **Touch ID non riconosce più il dito** dopo molti usi nella stessa sessione: è un limite noto (~68 riconoscimenti per
  avvio). Sblocca con la password; Touch ID torna dopo uno spegnimento completo. Dopo la sospensione serve circa 10 secondi
  prima che sia di nuovo pronto.
- **Wi-Fi a 5 GHz debole dopo essere passati da macOS**: in macOS usa "Spegni" invece di "Riavvia".
- **La sospensione sembra bloccata**: aspetta almeno 3 minuti prima di forzare lo spegnimento.
- **Aggiornamenti del kernel**: i driver si ricompilano da soli per ogni kernel, anche per l'LTS e per le versioni future.
  Audio e webcam scaricano da kernel.org i file di quella versione esatta del kernel (serve la rete durante
  l'aggiornamento; restano in cache). Se l'aggiornamento avviene senza rete, al primo avvio con la rete un servizio
  ricompila quelli rimasti indietro e chiede di riavviare. Se un kernel futuro cambia troppo, la compilazione fallisce
  e la Touch Bar torna da sola in modalità tastiera.
- **iPhone collegato via USB**: la regola di `usbmuxd` può spegnere il T1; gli script avvisano se la trovano.
- **OpenCore non compare più dopo una reinstallazione**: la voce "OpenCore" nella NVRAM del Mac punta ancora alla vecchia
  partizione EFI, e Limine non aggiunge OpenCore da solo. Controlla con `efibootmgr -v`, togli la voce vecchia
  (`efibootmgr -b <numero> -B`) e rifalla verso la partizione EFI attuale (diventa la prima: a ogni accensione parte
  OpenCore):

  ```bash
  sudo efibootmgr -c -d /dev/nvme0n1 -p 1 -L OpenCore -l '\EFI\OC\OpenCore.efi'
  ```

  Per averlo anche nel menu di Limine, in fondo a `/boot/limine.conf`: `/OpenCore`, `protocol: efi`,
  `path: boot():/EFI/OC/OpenCore.efi` (una voce per riga).
- **`sudo` rifiutato con "nessun nuovo privilegio"**: usa `run0` al posto di `sudo` (per esempio
  `run0 ./install.sh --only audio`), oppure lancia il comando da un terminale normale.

## Tutto il disco a Linux, senza macOS (CachyOS)

Provato su questo Mac il 25/11/2026 con CachyOS: macOS cancellato, una sola partizione EFI (quella di Apple, ingrandita a
512 MB) con OpenCore e GRUB, tutto il resto a CachyOS. (Con Omarchy il disco intero è l'unica strada: vedi sopra.)

- Il chip T1 **non ha firmware proprio**: a ogni accensione il Mac glielo carica dalla cartella `EFI/APPLE/EMBEDDEDOS`
  della partizione EFI. Per questo `install.sh` (passo `kernel`) installa una **guardia**: a ogni avvio confronta i file
  del T1 con una copia di riferimento, li rimette se mancano o sono rovinati e lo segnala in MacBook Manager
  (Touch ID → *Firmware del T1*). Comandi: `sudo /usr/local/lib/macbookpro14-3/t1-guard.sh status` (oppure `check`,
  `restore`). `sudo ./install.sh --only backup` salva immagine, file e checksum della partizione EFI in
  `/var/backups/macbookpro14-3/`. **Copiali anche fuori dal Mac.**
- La partizione EFI di Apple va tenuta (mai riformattata senza aver salvato tutti i file): si può ingrandire solo
  ricreandola con lo stesso UUID e rimettendo i file verificati.
- Prima di cancellare macOS: backup Time Machine completo, avvio di Linux già spostato nella partizione EFI di Apple e
  provato con un riavvio, una copia del lanciatore di OpenCore in `EFI/BOOT/BOOTX64.EFI` come riserva. Lo spazio di
  macOS si aggiunge a btrfs come seconda partizione (`btrfs device add`), senza spostare Linux.
- Senza macOS, il firmware del T1 non si aggiorna più (non serve). Per riavere macOS: Internet Recovery (⌥ ⌘ R
  all'accensione) e Time Machine.

## Per esperti

<details>
<summary>Cosa fa install.sh, passo per passo</summary>

Ogni passo è uno script e si può rifare da solo con `sudo ./install.sh --only <passo>` (o saltare con `--skip <passo>`).

| Passo | Cosa fa |
|---|---|
| `backup` | copia l'EFI di Apple e il firmware del T1 in `/var/backups/macbookpro14-3` (indispensabile) |
| `packages` | pacchetti necessari e header di ogni kernel installato (NetworkManager solo su KDE; agente polkit su Hyprland) |
| `input` | quirk libinput (trackpad disattivato mentre scrivi) |
| `touchbar` | Touch Bar in modalità tastiera (`apple-ibridge`, DKMS): sempre installata, serve anche in sospensione |
| `audio` | driver del codec CS8409 (davidjo, fork dnlbtz, DKMS) |
| `audio-dsp` | pacchetti [`pkgs/bankstown-lv2`](pkgs/bankstown-lv2/) e [`pkgs/mbp143-audio`](pkgs/mbp143-audio/): filtro PipeWire con crossover, equalizzazione, limitatori e protezione termica di Apple, più i bassi psicoacustici di Asahi; +35 dB al microfono delle cuffie. Costa ~1,5 W |
| `sleep` | sospensione S3 (kernel >= 7.3), Thunderbolt scollegato prima della sospensione, NVMe senza D3cold, ibernazione disattivata |
| `power` | a batteria Radeon in risparmio e CPU senza turbo; piena potenza con l'alimentatore (su KDE anche MangoHud tenuto fuori da KWin, [`cachyos/kde/`](cachyos/kde/)) |
| `bluetooth` | audio delle chiamate (SCO via HCI), mSBC disattivato |
| `touchbar-display` | compila T1Bridge, installa driver display e webcam (con la correzione dei buffer H.264), servizi, `touchbar-mode`, renderer fnstrip; salva la modalità display |
| `tiny-dfr` | compila tiny-dfr con le patch per il T1; resta inattivo finché non lo scegli |
| `omabar` | solo Omarchy: compila e installa OmaBar ([`omarchy/install-omabar.sh`](omarchy/install-omabar.sh)), lo rende il renderer scelto e installa la skill `/omabar` di Claude Code |
| `touchid` | servizi Touch ID di T1Bridge, rete privata del T1, libfprint/fprintd, regola ufw, interruttori PAM (spenti finché non li attivi) |
| `kernel` | servizio che all'avvio ricompila i driver rimasti indietro dopo un aggiornamento del kernel senza rete; **guardia del firmware del T1** |
| `manager` | MacBook Manager: GUI, icona nella barra di sistema, helper con polkit ([manager/README.md](manager/README.md)) |
| `apps` | da utente: `AMD_DEBUG=notiling` per le app Chromium/Electron sotto Wayland, più un servizio per quelle installate dopo |
| `wifi` | per ultimo: NVRAM generata dalla calibrazione del chip, firmware, impostazioni di NetworkManager o iwd |

Altre opzioni: `--yes` (nessuna conferma), `--wifi-nvram FILE`, `--wifi-files DIR` (file di mbp143-wifi già scaricati,
per esempio dalla chiavetta), `--initramfs` (non provato, solo per disco cifrato), `--list`. Modalità e renderer della
Touch Bar si cambiano anche da terminale: `sudo touchbar-mode set display|keyboard`,
`sudo touchbar-mode renderer t1bridge|tiny-dfr|omabar`.
</details>

<details>
<summary>Schermo sulla scheda Intel (facoltativo, con OpenCore)</summary>

Di base lo schermo è collegato alla Radeon. Avviando Linux da **OpenCore** con `SignalAppleOS` (il firmware crede di
avviare macOS, come l'opzione "Windows GMUX" di OCLP) e la variabile EFI `gpu-power-prefs` impostata sulla Intel, lo
schermo passa alla Intel: circa 1,5-2 W in meno a riposo, luminosità funzionante. La Radeon resta comunque accesa.

```bash
sudo scripts/opencore.sh status          # OpenCore, SignalAppleOS, GPU dello schermo
sudo scripts/opencore.sh install         # OpenCore nella partizione EFI (se manca) e voce di avvio
sudo scripts/opencore.sh gpu intel       # SignalAppleOS + schermo sulla Intel dal prossimo avvio (gpu radeon per tornare)
```

La GPU si sceglie anche da MacBook Manager → scheda **GPU** (scrive la stessa variabile EFI, `gpu-power-prefs`); OpenCore
serve perché il firmware la rispetti. Se manca, `install` costruisce OpenCore da OpenCorePkg (versione fissata) con una configurazione **senza seriali**: su un
Mac vero OpenCore lascia al firmware i dati originali; i seriali servono solo ai servizi Apple dentro macOS. La
configurazione generata passa `ocvalidate` nella CI ma non è ancora stata avviata [non verificato]; quella di OCLP sì. Se
qualcosa va storto: Option (⌥) all'avvio → "EFI Boot", oppure "Reset NVRAM" dal menu di OpenCore. Sospensione e monitor
esterni non ancora riprovati con la Intel. Dettagli in [docs/gpu.md](docs/gpu.md).
</details>

<details>
<summary>Struttura della repo</summary>

```
install.sh              post-installazione, uguale per CachyOS e Omarchy (sudo ./install.sh --dry-run)
cachyos/                solo CachyOS / KDE
  macos/prepare.sh        da macOS: partizione live di CachyOS sul disco interno, senza USB
  kde/                    drop-in per KWin (MangoHud fuori dal compositor)
omarchy/                solo Omarchy / Hyprland
  prepare-usb.sh          chiavetta da macOS o Linux: ISO, copia della EFI di Apple, Wi-Fi della live, repo
  wifi-live.sh            Wi-Fi a 5 GHz nella live (copiato sulla chiavetta)
  omabar/                 OmaBar, renderer della Touch Bar (Rust), con agente di sessione
  install-omabar.sh       compila e installa OmaBar
  claude-skill/omabar/    skill /omabar di Claude Code
scripts/                comune: un installer per componente, touchbar-mode, sleep-test, build di T1Bridge, fnstrip, tiny-dfr,
                        opencore.sh (OpenCore e GPU dello schermo)
manager/                comune: MacBook Manager (comando, GUI Qt, helper polkit)
config/                 comune: sorgenti esterne fissate (sources.conf), udev, systemd, sleep, power, NetworkManager,
                        WirePlumber, libinput, T1Bridge, tiny-dfr
dkms/                   driver display, webcam e rete del T1 (modalità display)
patches/                patch nostre per Touch Bar, audio e tiny-dfr
pkgs/                   PKGBUILD: mbp143-audio e bankstown-lv2 (usati da install.sh); meta e apple-ibridge (non aggiornati)
docs/                   risultati per componente e report di ricerca (indice: docs/README.md)
.github/                CI: sintassi e ShellCheck di tutti gli script, bash 3.2 di macOS, Python, OmaBar (build, test,
                        anteprima), driver DKMS compilati contro linux e linux-lts di Arch, PKGBUILD,
                        configurazione OpenCore generata (ocvalidate)
```

Le sorgenti esterne sono **fissate a un commit** e il loro codice è stato letto prima dell'uso
([`config/sources.conf`](config/sources.conf) e i PKGBUILD). Il file NVRAM del Wi-Fi non è nella repo: viene generato sulla
macchina dalla calibrazione del chip.
</details>

## Crediti

- Touch Bar (tastiera): roadrunner2/cb22 → marc-git → F13-Kr1pt0n → **nonderbe** (`t1-fixes`).
- Touch Bar (display), webcam H.264, Touch ID: **T1Bridge** (Andrew Boyd, Standard Agents), `appletbdrm` di Kerem Karabay.
- Renderer: **fnstrip** (Alex McCubbin); **tiny-dfr** (Asahi Linux), sul T1 come in heymaaz/mbp-t1-touchbar; **OmaBar**
  (questa repo).
- Audio: **davidjo/snd_hda_macbookpro**, fork **dnlbtz**; DSP degli altoparlanti **dnlbtz/mbp143-audio**; bassi
  psicoacustici **bankstown** (James Calligeros, Asahi Linux).
- Wi-Fi: **dnlbtz/mbp143-wifi**; impostazioni di scansione da **mihneadevries/mbp14-3-linux-wifi-fix**.
- Sospensione: **mihneadevries/mbp14-3-linux-sleep-fix**.
- Omarchy: Basecamp / DHH.
- Tracker storico: Dunedan/mbp-2016-linux.

Ognuno resta con la sua licenza (GPL-2.0 per i moduli del kernel, MIT per gli altri, vedi i singoli file).
