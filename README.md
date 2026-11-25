# CachyOS sul MacBook Pro 14,3 (15" 2017, Touch Bar T1)

Tutto quello che serve per usare **CachyOS** (Arch) sul **MacBookPro14,3**: 15" 2017, Touch Bar con chip **T1**,
Intel i7 Kaby Lake, Radeon Pro 555/560, **senza chip T2**. Un solo script di post-installazione applica i
passaggi provati su questa macchina: driver DKMS, patch, configurazioni, servizi.

> **Stato (24 novembre 2026):** provato su un MacBookPro14,3 reale con CachyOS, kernel `7.3.5-2-cachyos`
> (clang + ThinLTO), KDE Plasma 6.8 Wayland. Quasi tutto funziona, **Touch ID compreso** (in modalità display);
> restano limiti veri (ibernazione, consumo della Radeon). È un progetto personale, scritto con l'aiuto di un assistente IA e provato su **una sola
> macchina**: leggi gli script prima di usarli. I dettagli di ogni componente sono in [`docs/`](docs/README.md).

![Touch Bar in modalità display: renderer fnstrip con il tema OLED](docs/media/touchbar-oled.png)
<sub>La Touch Bar in modalità display (renderer fnstrip, preset OLED di MacBook Manager): Esc, luminosità dello schermo e
della tastiera, media, volume. Screenshot reale a 2170×60, catturato con *Touch Bar in diretta*.</sub>

## Cosa funziona

✅ provato sulla macchina · 🟡 funziona con limiti · ❓ non verificato · ❌ non funziona

| Componente | Stato | Come | Note |
|---|---|---|---|
| Tastiera e trackpad | ✅ | `applespi` (kernel) + quirk libinput | il trackpad si disattiva mentre scrivi ([input](docs/input.md)) |
| Touch Bar, modalità **tastiera** | ✅ | `apple-ibridge` (fork nonderbe `t1-fixes`) + 3 patch nostre, DKMS | i tasti disegnati dal firmware, come in Boot Camp ([touchbar](docs/touchbar.md)) |
| Touch Bar, modalità **display** | ✅ predefinita | driver e servizi di [T1Bridge](https://github.com/standardagents/t1bridge) compilati da sorgente | grafica, cursori, temi, renderer [fnstrip](https://github.com/acmccubbin/fnstrip) ([t1bridge](docs/t1bridge.md)); necessaria per Touch ID |
| Tasti funzione e multimediali | ✅ | Touch Bar | luminosità, tastiera, volume, media, F1-F12 con Fn |
| Sensore di luce + luminosità automatica | ✅ | `apple-ib-als` / `hid_sensor_als` → `iio-sensor-proxy` → KWin | serve una curva di partenza: il sensore legge poco in luce ambiente |
| Audio: speaker, cuffie, microfono interno e cuffie | ✅ | codec **CS8409**, driver davidjo (fork dnlbtz), DKMS | ([audio](docs/audio.md)) |
| Wi-Fi 2,4 e 5 GHz | 🟡 | `brcmfmac` + NVRAM generato dalla calibrazione del chip + firmware patchato | da ~21 a ~290 Mbit/s; canale a 40 MHz invece di 80 ([wifi](docs/wifi.md)) |
| Bluetooth: musica | ✅ | kernel (Broadcom su UART) | A2DP con AAC |
| Bluetooth: chiamate (cuffie + microfono) | 🟡 | comando Broadcom per l'audio SCO via HCI | solo CVSD (qualità telefonica); mSBC muto |
| Webcam | ✅ | `uvcvideo` (**non** `facetimehd`) | in modalità display solo H.264: Discord con `t1-webcam on` |
| Sospensione (coperchio, S3) | ✅ | S3 (`deep`) come macOS, ventole ferme; Thunderbolt scollegato prima dello sleep + NVMe senza D3cold | notte intera provata: 8 h, 17 mAh (~0,03 W), nessun risveglio spontaneo ([sleep](docs/sleep.md)) |
| Energia | 🟡 | a batteria Radeon in risparmio, CPU senza turbo | ~18 W a riposo ≈ 4 ore ([power](docs/power.md)) |
| Grafica | 🟡 | sempre sulla Radeon | la Intel non può pilotare lo schermo; nessuno switch ([gpu](docs/gpu.md)) |
| Thunderbolt / USB-C, monitor esterni | ❓ | kernel | non provati |
| Kernel LTS (`linux-cachyos-lts`) | ❓ | | mai avviato; DKMS compila la Touch Bar in modalità tastiera, non l'audio né la modalità display |
| Ibernazione | ❌ | | `amdgpu` non riparte (serve una patch non ancora nel kernel) |
| Spegnere la Radeon | ❌ | | 7-9 W anche a riposo, è la causa principale dell'autonomia ridotta |
| Touch ID | ✅ solo in modalità display | servizi Touch ID di T1Bridge + libfprint/fprintd patchati, dati di fabbrica dalla ESP Apple | registrazione, verifica, sudo, schermata di blocco, dopo la sospensione (~10 s per tornare pronto). **Non disponibile in modalità tastiera** (il T1 espone il Secure Enclave solo nella configurazione USB 2). Limite noto: ~68 riconoscimenti per avvio, poi serve uno spegnimento completo ([touchid](docs/touchid-t1.md)) |

## 1. Installare CachyOS su questo Mac

**Prima di tutto:** fai un backup di macOS (Time Machine) e **non cancellare mai la partizione EFI di Apple**
(`EFI/APPLE`): contiene il firmware del T1. Senza, Touch Bar, webcam e sensore di luce smettono di funzionare
insieme. Linux può (e conviene) avere una sua partizione EFI separata.

Su questa macchina CachyOS è stato installato **da macOS, senza chiavetta USB**, con
[`macos/prepare.sh`](macos/prepare.sh): ridimensiona il contenitore APFS, crea una partizione FAT32 `COSLIVE` con
l'ISO estratta e una partizione per Linux. Il disco risultante è:

| Partizione | Contenuto |
|---|---|
| EFI (300 MB) | ESP di Apple, intatta |
| APFS | macOS |
| `LINUXEFI` (~500 MB, FAT32) | ESP di Linux con GRUB, montata su `/boot/efi` |
| `COSLIVE` (7 GB, FAT32) | il live usato per l'installazione (si può eliminare dopo) |
| `CachyOS` (btrfs) | il sistema |

```bash
./macos/prepare.sh prepare --linux-gb 120          # da macOS: mostra il piano, non cambia niente
./macos/prepare.sh prepare --linux-gb 120 --execute
```

Poi riavvia tenendo premuto **Option (⌥)**, scegli "EFI Boot" e installa con Calamares in partizionamento manuale
(partizione Linux su `/`, una partizione EFI propria per GRUB). Note:

- Bootloader: **GRUB** (provato) o rEFInd. systemd-boot e Limine sono sconsigliati sugli EFI Apple.
- Tieni a portata una tastiera USB-C: la tastiera interna nel live non è garantita.
- La procedura passo passo di `prepare.sh` non è stata documentata dall'inizio alla fine: in alternativa usa una
  chiavetta USB con l'ISO di CachyOS, il risultato è lo stesso.
- All'accensione, **Option (⌥)** permette di scegliere tra macOS e CachyOS.

## 2. Post-installazione

Su CachyOS appena installato (collegato all'alimentatore, Wi-Fi 2,4 GHz già funzionante):

```bash
sudo pacman -Syu        # poi riavvia: il kernel in uso deve essere quello installato
git clone https://github.com/DriftDeV/Macbook14-3-cachyOS && cd Macbook14-3-cachyOS
sudo ./install.sh --dry-run     # mostra cosa farà
sudo ./install.sh               # chiede la modalità della Touch Bar (predefinita: display, con Touch ID)
```

Alla fine **spegni completamente** il Mac, aspetta ~30 secondi e riaccendi (il T1 riparte pulito).

`install.sh` esegue, nell'ordine, questi passi (ognuno è uno script in [`scripts/`](scripts/) e si può rilanciare):

| Passo | Cosa fa |
|---|---|
| `backup` | copia l'ESP di Apple e il firmware T1 in `/var/backups/macbookpro14-3` (indispensabile) |
| `packages` | pacchetti necessari e header di ogni kernel installato |
| `input` | quirk libinput (trackpad disattivato mentre scrivi) |
| `touchbar` | Touch Bar in modalità tastiera (DKMS), sempre installata: è la base di sicurezza |
| `audio` | driver CS8409 (DKMS) |
| `sleep` | S3 sui kernel >= 7.3 (s2idle di ripiego), hook Thunderbolt/Wi-Fi, NVMe senza D3cold, ibernazione disattivata |
| `power` | a batteria Radeon in risparmio e CPU senza turbo; piena potenza con l'alimentatore |
| `bluetooth` | audio delle chiamate (SCO via HCI), mSBC disattivato in WirePlumber |
| `brightness` | curva di partenza della luminosità automatica di KWin |
| `touchbar-display` | modalità display (predefinita): compila T1Bridge, installa driver e servizi (e fnstrip) |
| `touchid` | solo in modalità display: servizi Touch ID di T1Bridge, rete privata del T1, libfprint/fprintd, regola ufw per xART, interruttori PAM (`touchid-pam`); sudo e schermata di blocco restano con la password finché non li attivi |
| `apps` | da utente: app Chromium/Electron (Brave, Discord, web app…) con `AMD_DEBUG=notiling`, perché sotto Wayland il loro processo GPU crolla con i buffer tiled della Radeon; servizio che lo riapplica alle app nuove |
| `manager` | MacBook Manager: GUI e icona nella barra di sistema con stato e azioni rapide ([manager/README.md](manager/README.md)) |
| `wifi` | per ultimo (la connessione cade ~20 s): NVRAM dal chip, firmware, impostazioni NetworkManager |

Opzioni utili:

```bash
sudo ./install.sh --yes --fnstrip                   # senza domande: display, Touch ID, fnstrip
sudo ./install.sh --yes --touchbar keyboard         # Touch Bar come in Boot Camp, niente Touch ID
sudo ./install.sh --only audio,bluetooth            # rifà solo alcuni passi
sudo ./install.sh --skip wifi
```

Se un passo fallisce gli altri proseguono; il riepilogo dice cosa rifare. Registro: `/var/log/macbookpro14-3-install.log`.

## 3. Uso quotidiano

Il modo più semplice è **MacBook Manager** (menu delle applicazioni o icona nella barra di sistema): stato di driver,
Touch Bar, sospensione, Wi-Fi, batteria e temperature, con le azioni qui sotto a un clic; nella scheda
**Ottimizzazione** un pulsante ottimizza tutte le app Chromium/Electron e le web app. Da terminale:
`macbook-manager status`, `macbook-manager actions`, `macbook-manager run <azione>`. Dettagli in
[manager/README.md](manager/README.md).

| Cosa | Comando |
|---|---|
| Touch ID (modalità display) | dopo il primo riavvio: `sudo scripts/install-touchid.sh import`; registra un dito da **Impostazioni di sistema → Utenti** (o MacBook Manager → Azioni → Touch ID); prova con `fprintd-verify`; sudo e schermata di blocco: MacBook Manager → Azioni → Touch ID, oppure `sudo touchid-pam sudo on`, `sudo touchid-pam lockscreen on`; rollback: `sudo scripts/install-touchid.sh undo` |
| Modalità della Touch Bar | `sudo touchbar-mode status` · `sudo touchbar-mode set display` · `sudo touchbar-mode set keyboard` (salva; attiva dopo uno spegnimento completo, l'unico modo di azzerare il T1) |
| Webcam per Discord/browser (modalità display) | `t1-webcam on` / `t1-webcam off`, poi scegli "T1 camera (Discord)" |
| Screenshot/video della Touch Bar (modalità display) | MacBook Manager → Touch Bar → **Touch Bar in diretta…**, oppure `macbook-manager touchbar-screenshot` |
| Renderer tiny-dfr (alternativo a fnstrip) | `sudo scripts/install-tiny-dfr.sh`, poi `sudo touchbar-mode renderer tiny-dfr` (o MacBook Manager → Azioni); indietro: `sudo touchbar-mode renderer t1bridge`; configurazione `/etc/tiny-dfr/config.toml` ([dettagli](docs/t1bridge.md)) |
| Renderer fnstrip | `scripts/install-fnstrip.sh` (`--undo` per togliere); configurazione dalla scheda **Touch Bar** di MacBook Manager, oppure a mano in `~/.config/fnstrip/config.toml` e poi `systemctl --user restart macbookpro14-3-touchbar-renderer` |
| Energia a batteria | `/etc/macbookpro14-3/power.conf`; registro `journalctl -t macbookpro14-3-power` |
| Prova della sospensione | `scripts/sleep-test.sh check` · `sudo scripts/sleep-test.sh real 60` · dopo una notte: `scripts/sleep-test.sh report` |
| Tornare a s2idle (fino al riavvio) | `sudo systemctl stop macbookpro14-3-sleep-mode` |
| Curva della luminosità automatica | `scripts/set-kwin-brightness-curve.sh --force` (poi logout/login) |

## 4. Problemi noti e rimedi

- **Touch Bar spenta ma il tocco funziona**, oppure il T1 compare come `05ac:1281` (recovery): spegnimento completo,
  ~30 s, riaccensione. Succede anche tornando dalla modalità display a quella tastiera senza riavvio.
- **Niente audio dopo un avvio**: se `grep Subsystem /proc/asound/card*/codec#0` dà `0x10138409` invece di
  `0x106b3900` è il bug noto del 14,3: reset della NVRAM o avvio da Option.
- **5 GHz deboli dopo un riavvio da macOS**: spegni macOS invece di riavviarlo.
- **Sospensione che sembra bloccata**: aspetta almeno 3 minuti prima di forzare lo spegnimento.
- **Aggiornamento del kernel**: DKMS ricompila da solo. Il driver audio e il driver webcam della modalità display
  hanno sorgenti solo per la serie 7.3: con una serie nuova servirà aggiornarli (la Touch Bar torna in modalità
  tastiera da sola se la modalità display non compila).
- **`usbmuxd`** (iPhone): la sua regola udev può spegnere il T1; gli script avvisano se lo trovano.
- **Touch ID non riconosce più il dito** dopo un uso intenso: è il limite di ~68 riconoscimenti per avvio di T1Bridge
  (issue #14; il contatore è in MacBook Manager). Si sblocca con la password; per riaverlo serve uno spegnimento
  completo. Con l'impronta nella schermata di blocco il limite arriva prima. Dopo la sospensione Touch ID torna pronto
  in ~10 s: la schermata di blocco riprova da sola.
- **Brave (e altre app Chromium/Electron) a scatti, CPU alta**: sotto Wayland il loro processo GPU crolla con i buffer
  "tiled" della Radeon e l'accelerazione si spegne. Rimedio provato, restando su Wayland: `scripts/fix-chromium-gpu.sh`
  (passo `apps` di `install.sh`, da utente, `--undo` per togliere) dà `AMD_DEBUG=notiling` solo a queste app, web app di
  Brave comprese, e un servizio lo riapplica alle app che installi dopo; MacBook Manager segnala quelle ancora con la GPU
  spenta. YouTube in VP9 lo decodifica la CPU (la Radeon non sa farlo); in H.264 la Radeon (CPU 24 % invece di ~80 %)
  ([gpu](docs/gpu.md)).
- **Touch ID in modalità tastiera**: non disponibile. Si torna alla modalità display con `sudo touchbar-mode set display`.

## Struttura della repo

```
install.sh              post-installazione (sudo ./install.sh --dry-run)
macos/prepare.sh        da macOS: partizione live sul disco interno, senza USB
scripts/                un installer per componente, touchbar-mode, sleep-test, build T1Bridge/fnstrip
manager/                MacBook Manager: comando, GUI Qt, helper polkit
config/                 sorgenti esterne fissate (sources.conf), udev, systemd, sleep, power, NetworkManager,
                        WirePlumber, KDE, libinput, T1Bridge
dkms/                   driver display e webcam della modalità display (T1Bridge, Linux 7.3)
patches/                patch nostre per la Touch Bar e l'audio
docs/                   risultati per componente e report di ricerca (indice: docs/README.md)
pkgs/                   PKGBUILD non aggiornati (non usati da install.sh)
```

Le sorgenti esterne sono **fissate a un commit** e il loro codice è stato letto prima dell'uso
([`config/sources.conf`](config/sources.conf)). Il file NVRAM del Wi-Fi non è nella repo: viene generato sulla
macchina dalla calibrazione del chip.

## Crediti

- Touch Bar (tastiera): roadrunner2/cb22 → marc-git → F13-Kr1pt0n → **nonderbe** (`t1-fixes`).
- Touch Bar (display), webcam H.264: **T1Bridge** (Andrew Boyd, Standard Agents), `appletbdrm` di Kerem Karabay.
- Renderer: **fnstrip** (Alex McCubbin); alternativo: **tiny-dfr** (Asahi Linux), sul T1 come in heymaaz/mbp-t1-touchbar.
- Audio: **davidjo/snd_hda_macbookpro**, fork **dnlbtz**.
- Wi-Fi: **dnlbtz/mbp143-wifi**; impostazioni di scansione da **mihneadevries/mbp14-3-linux-wifi-fix**.
- Sospensione: **mihneadevries/mbp14-3-linux-sleep-fix**.
- Tracker storico: Dunedan/mbp-2016-linux.

Ognuno resta con la sua licenza (GPL-2.0 per i moduli del kernel, MIT per gli altri, vedi i singoli file).
