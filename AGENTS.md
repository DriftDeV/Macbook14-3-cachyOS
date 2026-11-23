# AGENTS.md — contesto per le sessioni di Claude (e altri agenti)

Leggi questo file prima di toccare la repo. Aggiornalo quando cambia qualcosa di importante.

## Scopo

Riunire in una sola repo tutto ciò che serve (pacchetti, moduli DKMS, patch, configurazioni,
script) per avere **CachyOS (Arch) il più possibile funzionante sul MacBook Pro 14,3**
(15" 2017, Touch Bar con chip **T1**, i7-7820HQ, Radeon Pro 555/560, **senza T2**).
L'utente vuole abbandonare macOS (Mac non più supportato) e punta al "100% senza compromessi".
**Non è raggiungibile oggi**: Touch ID, ibernazione, grafica della Touch Bar e il consumo della dGPU
restano limiti. Non promettere il 100%. Touch ID e grafica della Touch Bar esistono sul T1 tramite T1Bridge
(configurazione USB 2), ma sono incompatibili con lo stack attuale e senza sospensione: vedi `docs/t1bridge.md`.
**Grafica della Touch Bar [F] provata a runtime** (23/11/2026; ora `scripts/install-touchbar-display.sh` + `touchbar-mode`):
grafica, tocco, volume, sospensione (passaggio automatico a modalità tastiera) e webcam (H.264; Discord via v4l2loopback).
Renderer fnstrip (`scripts/install-fnstrip.sh`) provato e funzionante.

Obiettivo secondario: installare CachyOS **da macOS, senza chiavetta USB** (partizione live sul disco interno).

La macchina su cui lavora l'utente **è proprio un MacBookPro14,3** (macOS 15, Darwin 24.6, SIP in configurazione
personalizzata con kext signing disattivato). L'utente scrive in italiano: rispondi in italiano.

## Mappa della repo

| Percorso | Contenuto |
|---|---|
| `install.sh` | installazione su CachyOS già installato; usa sempre `--dry-run` prima |
| `macos/prepare.sh` | da macOS: backup, download ISO, ridimensiona APFS, crea `COSLIVE` + partizione Linux, estrae ISO |
| `scripts/` | `lib.sh`, `backup-esp.sh`, `install-touchbar.sh`, `install-audio.sh`, `install-wifi.sh`, `install-wifi-nvram.sh`, `install-sleep.sh`, `sleep-test.sh`, `install-power.sh`, `install-bt.sh`, `bt-sco-route.py`, `build-t1bridge.sh`, `install-touchbar-display.sh`, `touchbar-mode.sh`, `install-fnstrip.sh`, `set-kwin-brightness-curve.sh`, `t1-reenumerate.sh` |
| `config/` | mkinitcpio, libinput, kde, sleep, power, systemd, udev, tmpfiles, networkmanager, modprobe, `sources.conf` (sorgenti esterne; Touch Bar pinnata) |
| `pkgs/`, `dkms/` | PKGBUILD (`macbookpro14-3-meta`, `apple-ibridge-dkms`), `dkms.conf` di riserva, `t1bridge-appletbdrm`, `t1bridge-uvc` |
| `patches/` | `touchbar/`: port di apple-ibridge a Linux 7.3 + `LLVM=1` automatico; README con le candidate |
| `docs/` | report di ricerca e note per componente; indice in `docs/README.md` |

## Regole per chi lavora qui

1. **Sicurezza dei dischi.** `macos/prepare.sh` modifica le partizioni di questo Mac. Non lanciarlo con
   `--execute` di tua iniziativa: serve una richiesta esplicita dell'utente nella chat, backup fatto e
   alimentatore collegato. Le conferme scritte (`RIDIMENSIONA`, `ROLLBACK`) le scrive l'utente, non tu.
   Non cancellare mai la ESP di macOS (`disk0s1`): contiene il firmware T1 (Touch Bar, webcam, ALS).
2. **Onestà sullo stato.** Quasi nulla è stato provato su hardware reale: fanno eccezione Touch Bar (`docs/touchbar.md`)
   sospensione (`docs/sleep.md`), audio (`docs/audio.md`) e Wi-Fi (`docs/wifi.md`).
   Marca come **[F] fatto / [I] inferenza / [NV] non verificato / [C] conflitto**. Non dichiarare "risolto"
   ciò che deriva solo da fonti secondarie.
3. **Non inventare.** Nomi di moduli, branch, URL, parametri: se non sono in `docs/`, verificali o marcali [NV].
   Non mettere nella repo né ridistribuire il file NVRAM Wi-Fi (licenza poco chiara): `install-wifi.sh` lo genera
   sulla macchina dalla SROM del chip.
4. **Niente sorgenti non fidate eseguite alla cieca.** I repo 2026 citati sono piccoli, si citano a vicenda e in
   parte sono scritti con IA: leggi il codice prima di integrarlo; pinna a un commit dopo averlo verificato.
5. **Commit/push solo su richiesta dell'utente.** Messaggi di commit con la riga `Co-Authored-By` richiesta dal sistema.
6. Mantieni gli script compatibili: `macos/prepare.sh` con **bash 3.2** (quella di macOS); gli script Linux con bash moderna.
   Controlla con `bash -n` e `shellcheck` (la CI lo fa).

## Fatti da non dimenticare (correzioni emerse dalla ricerca)

- Codec audio: **CS8409** [F] (subsystem `0x106b3900`), non CS4208. **Audio [F] funziona** (speaker, cuffie, microfoni)
  con dnlbtz `offlineDkmsDeb` `11febcf` + `patches/audio/`; il fork ha sorgenti kernel solo per la serie 7.3.
- Webcam: USB dietro l'iBridge → `uvcvideo`. **`facetimehd` non serve.** [F] Provata in Discord il 23/11/2026.
  Tasti funzione/multimediali dalla Touch Bar [F] funzionano.
- Il 14,3 **non ha il T2**: ignora `t2linux` e le pagine CachyOS sui T2.
- Bootloader su EFI Apple: rEFInd o GRUB `--removable`. systemd-boot e Limine sconsigliati.
- Il kernel `linux-cachyos` non ha una cartella di patch utente: preferire DKMS + header.
- L'ISO desktop più recente trovata sul mirror a fine novembre 2026 è `261122` (3,2 GB, entra in FAT32); lo script
  risolve da solo la cartella più nuova.
- **Touch Bar [F] funziona** sul 14,3 con `nonderbe` branch **`t1-fixes`** + `patches/touchbar/`, installata con DKMS e
  provata dopo riavvio (23/11/2026).
  Il branch di default di nonderbe NON ha le correzioni. Linux 7.3 ha tolto `struct acpi_driver`.
  `linux-cachyos` è compilato con clang (serve `LLVM=1`), `linux-cachyos-lts` con gcc.
- **Sospensione [F] funziona** (s2idle + rimozione dei port Thunderbolt `8086:1578` + NVMe senza D3cold): prove
  pm_test, RTC e coperchio riuscite il 23/11/2026. Default del firmware è S3 (`deep`), che con la Radeon non riparte.
- **Wi-Fi 5 GHz [F] funziona** con `scripts/install-wifi.sh` (dnlbtz/mbp143-wifi v1.1.0: NVRAM dalla SROM + firmware
  patchato): da ~21 a ~290 Mbit/s, -45 dBm. Resta a 40 MHz invece di 80 (ipotesi: regdom IT, vedi `docs/wifi.md`).
- **Trackpad [F]**: quirk `config/libinput/local-overrides.quirks` (tastiera SPI e Touch Bar interne) installato in
  `/etc/libinput/` e funzionante (disabilita durante la digitazione). Vedi `docs/input.md`.
- **Luminosità automatica [F]**: sensore Touch Bar 0-5000 lux (stanza 1-4); KWin 6.8 la gestisce con una curva
  appresa: `scripts/set-kwin-brightness-curve.sh` scrive una curva di partenza prima di KWin. Provata: 35-100 %.
- **Bluetooth [F]**: A2DP (AAC) OK; profilo headset (audio + microfono) funziona solo con CVSD dopo `scripts/install-bt.sh` (comando Broadcom
  SCO via HCI, chip su UART `BCM2E7C`); mSBC muto e disattivato in WirePlumber. Vedi `docs/audio.md`.
- **GPU [F]**: nessuno switch automatico; schermo e desktop sempre sulla Radeon (`card2`, eDP-2), Intel sospesa e senza eDP
  (`disabling eDP`), Radeon 7-9 W a riposo, runtime PM non disponibile. Opzioni in `docs/gpu.md`.
- **Consumi [F]** (`docs/power.md`): unica leva netta a riposo = Radeon `manual`+`POWER_SAVING`+PCIe 2,5 GT/s (-1,5 W);
  `scripts/install-power.sh` la applica a batteria. Slider KDE e turbo non cambiano nulla a riposo. ~18 W ≈ 4 h.
- `sudo` non funziona dalla shell di Claude (serve la password). Dal 23/11 pomeriggio funziona nel pannello Terminale
  dell'app (`run_in_terminal`, l'utente scrive la password); altrimenti Konsole.
- Il vecchio submodule `macbook-pro-touchbar-driver` (commit `42034ae`) è stato rimosso: senza `.gitmodules` e senza commit pubblico.
- Il dry-run su questo Mac ha mostrato: container APFS `disk1` da ~500 GB, **7 snapshot locali di Time Machine**
  (il limite minimo del resize è uguale alla dimensione attuale finché non vengono eliminati).

## Stato della sessione (aggiornato il 23 novembre 2026)

- **CachyOS è installato e avviato sul 14,3** (kernel 7.3.5-2-cachyos + LTS 6.18, KDE Plasma 6.8 Wayland).
  Funzionano: Wi-Fi 2,4 + 5 GHz, Touch Bar + sensore di luce (DKMS, dopo riavvio), webcam, sospensione s2idle (coperchio),
  audio (speaker, cuffie, microfono interno e cuffie; DKMS installato, avvio a freddo da confermare).
  Le note sotto su `prepare.sh` sono storiche.

- Repo pubblicata su `DriftDeV/Macbook14-3-cachyOS`, branch `main`. Le modifiche a `macos/prepare.sh` (creazione della
  partizione Linux con `diskutil addPartition ... %noformat% 0`, flag `--no-target`) possono non essere ancora in un commit.
- L'utente ha chiesto di far girare `./macos/prepare.sh prepare --linux-gb 120 --helper-gb 8 --execute` in un terminale
  (partizione live da 8 GB + 112 GB Linux, da eliminare/riusare dopo l'installazione). Al momento della scrittura
  lo script era fermo alla richiesta della password `sudo` per il backup dell'ESP.
- **Backup Time Machine non verificato**: il disco "Sandisk" non era montato. L'utente è stato avvisato.
- **Per sapere cosa è successo davvero**, non fidarti di questo file: controlla `diskutil list` e `ls ~/cachyos-mbp143/`.
- La procedura `prepare.sh` è **mai stata completata né provata**: non è noto se la ISO estratta si avvia dal disco interno
  (possibili problemi: bootloader dentro `efiboot.img`, righe di ricerca diverse in `grub.cfg`, blocco del kernel da FAT32).
  Tieni a portata una tastiera USB-C: `applespi` nel live non è garantito.

## Da fare (priorità)

1. Verificare l'avvio live dal disco interno e correggere `prepare.sh` secondo quanto emerge.
2. Driver Touch Bar e audio anche per il kernel LTS 6.18 (audio: `vendorKernel 6.18`); entrambi i REF sono pinnati.
3. Filter-chain PipeWire di `dnlbtz/mbp143-audio`; sospensioni lunghe e USB-C collegato in sleep; override `39-usbmuxd.rules`
   senza rompere gli iPhone; PKGBUILD per l'audio; repo pacman firmata con CI.
4. Ricerca kernel: patch `amdgpu` "reset VI ASIC on Apple boards" (ibernazione), runtime PM della dGPU.

## Memoria e contesto

- La ricerca completa è in `docs/` (report + 7 note): **leggila invece di rifare le ricerche**. Aggiornala se scopri qualcosa.
- Questa sessione ha anche salvato una nota di progetto nella memoria persistente di Claude Code (progetto `git`),
  che rimanda a questo file.
