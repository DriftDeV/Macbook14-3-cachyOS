# AGENTS.md — contesto per le sessioni di Claude (e altri agenti)

Leggi questo file prima di toccare la repo. Aggiornalo quando cambia qualcosa di importante.

## Scopo

Riunire in una sola repo tutto ciò che serve (pacchetti, moduli DKMS, patch, configurazioni,
script) per avere **CachyOS (Arch) il più possibile funzionante sul MacBook Pro 14,3**
(15" 2017, Touch Bar con chip **T1**, i7-7820HQ, Radeon Pro 555/560, **senza T2**).
L'utente vuole abbandonare macOS (Mac non più supportato) e punta al "100% senza compromessi".
**Non è raggiungibile oggi**: ibernazione e il consumo della dGPU restano limiti. Non promettere il 100%.
**Touch ID [F] funziona** (24/11/2026) solo in modalità display (configurazione USB 2), con i servizi Touch ID di T1Bridge
installati da `scripts/install-touchid.sh`: vedi `docs/touchid-t1.md`. In modalità tastiera non è disponibile.
**Grafica della Touch Bar [F] provata a runtime** (23/11/2026; ora `scripts/install-touchbar-display.sh` + `touchbar-mode`):
grafica, tocco, volume, sospensione (passaggio automatico a modalità tastiera) e webcam (H.264; Discord via v4l2loopback).
Renderer fnstrip (`scripts/install-fnstrip.sh`) provato e funzionante.
**tiny-dfr [F]** (25/11/2026) come renderer alternativo in modalità display: `scripts/install-tiny-dfr.sh` +
`touchbar-mode renderer tiny-dfr|t1bridge`, con `patches/tiny-dfr/` (nome del sensore, luminosità in software per non
togliere l'ALS a `hid-sensor-hub`) e tocco via `hid-multitouch` `new_id`. Vedi `docs/t1bridge.md`.
Luminosità della barra in modalità display: nessun controllo hardware (report HID 2 di 0xff12 accettato ma senza effetto,
25/11/2026); il manager la regola per entrambi i renderer (tiny-dfr: `ActiveBrightness`; fnstrip: colori scuriti).

Obiettivo secondario: installare CachyOS **da macOS, senza chiavetta USB** (partizione live sul disco interno).

La macchina su cui lavora l'utente **è proprio un MacBookPro14,3** (macOS 15, Darwin 24.6, SIP in configurazione
personalizzata con kext signing disattivato). L'utente scrive in italiano: rispondi in italiano.

## Mappa della repo

| Percorso | Contenuto |
|---|---|
| `install.sh` | post-installazione su CachyOS appena installato, **senza domande** (dal 25/11/2026): installa tutto (display con fnstrip predefinito + tiny-dfr inattivo, Touch ID, DSP audio, manager, Wi-Fi); modalità e renderer si scelgono da MacBook Manager. `--only/--skip`, riepilogo, registro in `/var/log/macbookpro14-3-install.log`; prima `--dry-run` (16 passi ok in prova) |
| `macos/prepare.sh` | da macOS: backup, download ISO, ridimensiona APFS, crea `COSLIVE` + partizione Linux, estrae ISO |
| `scripts/` | `lib.sh`, `backup-esp.sh`, `install-touchbar.sh`, `install-audio.sh`, `install-audio-dsp.sh` (pkgs bankstown-lv2 + mbp143-audio con makepkg da utente), `install-wifi.sh`, `install-wifi-nvram.sh`, `install-sleep.sh`, `sleep-test.sh`, `install-power.sh`, `install-bt.sh`, `bt-sco-route.py`, `build-t1bridge.sh`, `install-touchbar-display.sh`, `touchbar-mode.sh`, `install-fnstrip.sh`, `set-kwin-brightness-curve.sh`, `t1-reenumerate.sh`, `install-manager.sh`, `install-touchid.sh`, `install-tiny-dfr.sh`, `touchid-pam.sh`, `fix-chromium-gpu.sh` (app Chromium/Electron: `AMD_DEBUG=notiling` su Wayland, da utente) |
| `config/` | mkinitcpio, libinput, kde, sleep, power, systemd, udev, tmpfiles, networkmanager, modprobe, `sources.conf` (sorgenti esterne; Touch Bar pinnata) |
| `manager/` | MacBook Manager: `macbook-manager` (stato/azioni, CLI + GUI PySide6 con icona nella barra di sistema, editor di fnstrip in `fnstrip.py`/`gui_fnstrip.py`, Touch Bar in diretta/screenshot/video in `tbcapture.py`/`gui_live.py` dalla registrazione di debug di fnstrip, scheda Touch Bar che si adatta al renderer (`gui_touchbar.py`, editor tiny-dfr in `tinydfr.py`/`gui_tinydfr.py`), scheda Ottimizzazione delle app Chromium/web app in `optimize.py`/`gui_optimize.py` con `fix-chromium-gpu`, scheda Audio con preset e regolazioni sicure del DSP degli altoparlanti in `audio.py`/`gui_audio.py` + script WirePlumber `config/wireplumber/macbook-manager-audio.lua` che le riapplica), helper root via pkexec che accetta solo gli id di `actions.py`; installato da `scripts/install-manager.sh` |
| `pkgs/`, `dkms/` | PKGBUILD (`macbookpro14-3-meta`, `apple-ibridge-dkms`, `mbp143-audio` DSP degli altoparlanti + `bankstown-lv2` bassi psicoacustici), `dkms.conf` di riserva, `t1bridge-appletbdrm`, `t1bridge-uvc`, `t1bridge-ncm` (rete privata per Touch ID) |
| `patches/` | `touchbar/`: port di apple-ibridge a Linux 7.3 + `LLVM=1` automatico; README con le candidate; `audio/`; `tiny-dfr/` (T1) |
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
  Altoparlanti = 2 tweeter + 2 woofer, DSP solo software (CoreAudio). **`mbp143-audio` [F]** (25/11/2026, `pkgs/mbp143-audio/`,
  commit `aa4d8c1` letto): crossover + EQ di Apple via filter-chain, suono migliore; costo ~19 % di un core e ~+1,5 W perché
  il filtro non si sospende mai (l'utente lo tiene così). Con **bankstown** (Asahi, `pkgs/bankstown-lv2/`) in testa al
  grafo degli altoparlanti [F]. Lato sinistro con guasto hardware intermittente. Vedi `docs/audio.md`.
- Webcam: USB dietro l'iBridge → `uvcvideo`. **`facetimehd` non serve.** [F] Provata in Discord il 23/11/2026.
  Glitch "a pioggia" [F] corretti il 25/11 (Discord senza glitch, confermato): buffer da 270 KB troppo piccoli per l'H.264 della camera
  (`uvcvideo-t1-h264-big-frames.patch`). I sorgenti di `dkms/*/src/` erano esclusi da `.gitignore` (regola `src/`): ora no.
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
- **Sospensione [F]: S3 (`deep`)** + rimozione dei port Thunderbolt `8086:1578` + NVMe senza D3cold. s2idle NON è un vero
  sonno qui (niente S0ix nel firmware: ventole accese, Package C3, risvegli ogni 30-40 min). S3 sul 7.3.5: Radeon riparte,
  ventole ferme (23/11/2026); attivato solo su kernel >= 7.3 da `macbookpro14-3-sleep-mode.service`. Notte intera [F]
  24/11: 481 min, 17 mAh (~0,03 W), 0 risvegli spontanei, tutto ripartito (`macbook-manager sleep-report`).
- **Wi-Fi 5 GHz [F] funziona** con `scripts/install-wifi.sh` (dnlbtz/mbp143-wifi v1.1.0: NVRAM dalla SROM + firmware
  patchato): da ~21 a ~290 Mbit/s, -45 dBm. Resta a 40 MHz invece di 80 (ipotesi: regdom IT, vedi `docs/wifi.md`).
- **Trackpad [F]**: quirk `config/libinput/local-overrides.quirks` (tastiera SPI e Touch Bar interne) installato in
  `/etc/libinput/` e funzionante (disabilita durante la digitazione). Vedi `docs/input.md`.
- **Luminosità automatica [F]**: sensore Touch Bar 0-5000 lux (stanza 1-4); KWin 6.8 la gestisce con una curva
  appresa: `scripts/set-kwin-brightness-curve.sh` scrive una curva di partenza prima di KWin. Provata: 35-100 %.
- **Bluetooth [F]**: A2DP (AAC) OK; profilo headset (audio + microfono) funziona solo con CVSD dopo `scripts/install-bt.sh` (comando Broadcom
  SCO via HCI, chip su UART `BCM2E7C`); mSBC muto e disattivato in WirePlumber. Vedi `docs/audio.md`.
- **Chromium/Electron sotto Wayland [F]**: il processo GPU crolla (SIGILL) con i buffer tiled della Radeon Polaris e
  l'accelerazione si spegne (Brave, Discord, Claude Desktop, Sidra). Rimedio su Wayland: `AMD_DEBUG=notiling` solo per
  queste app con `scripts/fix-chromium-gpu.sh` (riconoscimento automatico, web app comprese, servizio `.path`). VP9 = CPU
  (la Radeon non lo decodifica), H.264 = Radeon. XWayland (versione precedente) non usava la Intel per il video.
  Claude Desktop salva "accelerazione disattivata" dopo i crolli: il lanciatore la riattiva.
- **GPU [F]**: nessuno switch automatico; schermo e desktop sempre sulla Radeon (`card2`, eDP-2), Intel sospesa e senza eDP
  (`disabling eDP`), Radeon 7-9 W a riposo, runtime PM non disponibile. Opzioni in `docs/gpu.md`.
  **Schermo sulla Intel [F] (25/11/2026)**: avvio da OpenCore (OCLP 3.0.0, "Windows GMUX" = `SignalAppleOS`) +
  `gpu-power-prefs=01` → i915 `eDP-1`, KWin sulla Intel, luminosità via gmux funzionante. Radeon ancora accesa (~7 W,
  seconda GPU di KWin): l'utente non vuole spegnerla (romperebbe le uscite e il resto). Sospensione e uscite esterne da
  riprovare. Senza OpenCore la Intel resta cieca.
- **Consumi [F]** (`docs/power.md`): unica leva netta a riposo = Radeon `manual`+`POWER_SAVING`+PCIe 2,5 GT/s (-1,5 W);
  `scripts/install-power.sh` la applica a batteria. Slider KDE e turbo non cambiano nulla a riposo. ~18 W ≈ 4 h.
- **Touch ID [F]** (24/11/2026): `scripts/install-touchid.sh` (install/status/import/undo, passo `touchid` di `install.sh`
  in modalità display, ora predefinita) + `touchid-pam` (interruttori sudo e schermata di blocco, anche nel manager).
  xART lo avvia `touchbar-mode` (la regola udev di T1Bridge non scatta con la rete rinominata `t1ncm`); la prima
  registrazione fallisce con "prepare device keybag failed", la seconda riesce. Mai il pacchetto `t1bridge-dkms`.
- **MacBook Manager [F]** (`manager/`, 23-24/11/2026): GUI, icona nella barra di sistema, azioni con password via polkit
  provate (Touch Bar display/tastiera, spegnimento), editor fnstrip + preset OLED, Touch Bar in diretta/PNG/video. Il T1 si azzera SOLO con lo spegnimento completo (porta USB, reset
  USB, S3 provati invano; ACPI `FRST` = recovery, da non usare): `touchbar-mode set keyboard` salva soltanto.
- `sudo` non funziona dalla shell di Claude (serve la password). Dal 23/11 pomeriggio funziona nel pannello Terminale
  dell'app (`run_in_terminal`, l'utente scrive la password); altrimenti Konsole.
- Il vecchio submodule `macbook-pro-touchbar-driver` (commit `42034ae`) è stato rimosso: senza `.gitmodules` e senza commit pubblico.
- Il dry-run su questo Mac ha mostrato: container APFS `disk1` da ~500 GB, **7 snapshot locali di Time Machine**
  (il limite minimo del resize è uguale alla dimensione attuale finché non vengono eliminati).

## Stato della sessione (aggiornato il 23 novembre 2026)

- **Installazione**: CachyOS installato dal live sul disco interno (partizioni `COSLIVE` 7 GB e `LINUXEFI` con GRUB su
  `/boot/efi`; ESP Apple `nvme0n1p1` intatta) [I dalle partizioni]. README riscritto con stato verificato e istruzioni.
- **`install.sh` riscritto** come post-install unico (backup ESP Apple, pacchetti, input, touchbar, audio, sleep, power,
  bluetooth, brightness, touchbar-display, wifi per ultimo). [F] Rilancio reale su questa macchina il 23/11/2026
  (`--yes --touchbar display --fnstrip`): 11 passi ok, idempotente (curva KWin non riscritta, power.conf conservato,
  Wi-Fi tornato da solo). Non ancora provato su un'installazione davvero nuova.

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

0. ~~Prova di Touch ID~~ **fatta il 24/11/2026 [F]** (registrazione, verifica, sospensione, sudo, schermata di blocco).
   Restano: riavvio con impronte salvate e **coesistenza con macOS** (spegnimento → macOS → Linux), giornata intera
   con la schermata di blocco (limite #14). Procedura originale:, seguendo `docs/touchid-t1.md` (procedura reversibile in
   10 passi dal passo 0: backup ESP con verifica di `FDRData`, solo componenti userspace, **mai `t1bridge-dkms`**, regola
   ufw limitata all'interfaccia del T1, un dito diverso da quelli di macOS, spegnimento completo a ogni cambio di sistema,
   PAM solo per sudo alla fine). Script pronto (solo dry-run): `sudo scripts/install-touchid.sh` → `status` → spegnimento
   completo → `import` → registrazione a mano; rollback `sudo scripts/install-touchid.sh undo`.
1. Verificare l'avvio live dal disco interno e correggere `prepare.sh` secondo quanto emerge.
2. Driver Touch Bar e audio anche per il kernel LTS 6.18 (audio: `vendorKernel 6.18`); entrambi i REF sono pinnati.
3. Filter-chain PipeWire di `dnlbtz/mbp143-audio`; sospensioni lunghe e USB-C collegato in sleep; override `39-usbmuxd.rules`
   senza rompere gli iPhone; PKGBUILD per l'audio; repo pacman firmata con CI.
4. Ricerca kernel: patch `amdgpu` "reset VI ASIC on Apple boards" (ibernazione), runtime PM della dGPU.

## Memoria e contesto

- La ricerca completa è in `docs/` (report + 7 note): **leggila invece di rifare le ricerche**. Aggiornala se scopri qualcosa.
- Questa sessione ha anche salvato una nota di progetto nella memoria persistente di Claude Code (progetto `git`),
  che rimanda a questo file.
