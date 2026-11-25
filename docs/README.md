# Documentazione e ricerche

Ricerca svolta il 23 novembre 2026 con 7 ricercatori in parallelo più un report di sintesi.
Le note grezze sono in [`research_notes/Linux MacBookPro143 supporto hardware/`](research_notes/Linux%20MacBookPro143%20supporto%20hardware/);
la sintesi (in italiano, con tag di affidabilità) è [`research-report.md`](research-report.md).

**Legenda dei tag** (usata nel report): **[F]** fatto con fonte · **[I]** inferenza · **[NV]** non verificato · **[C]** fonti in conflitto.

**Limiti generali:** nessuna prova su hardware reale; Arch Wiki e AUR erano bloccati (Anubis) e non sono stati letti;
la maggior parte dei repo del 2026 è piccola, si cita a vicenda ed è in parte scritta con aiuto di IA; quasi tutti i test
recenti sono su 14,2 o 13,x, non su 14,3.

## Indice per componente

| Componente | Note grezze | Esito in breve |
|---|---|---|
| Tastiera, trackpad, Touch Bar T1, ALS | `touchbar_keyboard_trackpad.md` + **[`touchbar.md`](touchbar.md), [`input.md`](input.md) (provati sulla macchina)** | `applespi` è nel kernel dal 5.3. La Touch Bar funziona solo con DKMS fuori dal kernel (`apple-ibridge`, `apple-ib-tb`, `apple-ib-als`), fragile. `tiny-dfr` non vale per la modalità tastiera; in modalità display funziona con patch ([`t1bridge.md`](t1bridge.md), 25/11/2026). |
| Audio | `research_notes/.../audio.md` + **[`audio.md`](audio.md) (provato sulla macchina)** | Codec **CS8409** confermato sulla macchina. Funziona con `davidjo/snd_hda_macbookpro` (fork dnlbtz). Bug del subsystem id al boot; microfono debole. |
| Wi-Fi, Bluetooth, webcam, periferiche | `wifi_bt_camera_peripherals.md` + **[`wifi.md`](wifi.md) (Wi-Fi provato sulla macchina)** | Wi-Fi BCM43602 con `brcmfmac`: il file NVRAM di scheda serve per i 5 GHz. Webcam USB via iBridge con `uvcvideo`, **non** `facetimehd`. Il firmware T1 sta nell'ESP Apple. |
| GPU, energia, ventole, sospensione | `gpu_power_thermal.md` + **[`sleep.md`](sleep.md), [`gpu.md`](gpu.md), [`power.md`](power.md) (misurati sulla macchina)** | dGPU Radeon mai in runtime suspend (~7 W). Sospensione parziale: s2idle + hook. Ibernazione rotta. Poche fonti verificate sul 14,3. |
| Firmware del T1, disco tutto per Linux | **[`t1-firmware.md`](t1-firmware.md) (fatto sulla macchina, 25/11/2026)** | Il T1 carica il firmware dalla ESP di Apple a ogni accensione. Guardia con checksum a ogni avvio; macOS cancellato, una sola ESP (Apple, 512 MiB) con OpenCore + GRUB, btrfs su due partizioni. |
| CachyOS: kernel, pacchetti, bootloader | `cachyos_packaging_bootloader.md` | Niente cartella di patch utente in `linux-cachyos`: meglio DKMS + header. Su EFI Apple: rEFInd o GRUB `--removable`. |
| Installazione da macOS senza USB | `install_from_macos_no_usb.md` | Plausibile: `diskutil apfs resizeContainer`, FAT32 con ISO estratta, Option all'avvio. **Non esiste un esempio completo documentato** su Mac Intel. |
| Progetti esistenti | `existing_projects_survey.md` | Roadrunner2 e Dunedan sono fermi al 2024. Repo vivi 2026: `cschaba/macbookpro14-3-linux`, `nohzafk/omarchy-macbookpro-t1`, `mihneadevries/mbp14-3-linux-sleep-fix`, `dnlbtz/mbp143-audio` e `mbp143-wifi`, `AJ-dev-i60/t1-touchbar`. |

## Correzioni rispetto alle ipotesi iniziali

- Il codec audio non è un CS4208 ma (con ogni probabilità) un **CS8409**.
- `facetimehd` **non serve**: la webcam è USB.
- Il 14,3 **non ha il chip T2**: le patch `t2linux` e le pagine CachyOS sui T2 non valgono.
- Il submodule `macbook-pro-touchbar-driver` (commit `42034ae`) non aveva `.gitmodules` né un commit pubblico trovato: rimosso.
  Il candidato più probabile era `F13-Kr1pt0n/macbook-pro-touchbar-driver`.

## T1Bridge (Touch ID, grafica della Touch Bar)

[`t1bridge.md`](t1bridge.md): analisi in sola lettura di `standardagents/t1bridge` e del renderer `acmccubbin/fnstrip`.
Correzione: il T1 ha solo layout fissi nella configurazione USB 1; nella 2 espone un display come i T2.

## Touch ID sul T1 (ricerca del 24 novembre 2026)

[`touchid-t1.md`](touchid-t1.md): report in italiano con tag [F]/[I]/[NV]/[C], da 4 ricerche parallele (note grezze in
[`research_notes/Touch ID T1 su Linux/`](research_notes/Touch%20ID%20T1%20su%20Linux/): protocollo, stato di T1Bridge,
rischi e rollback, altri progetti). In breve: Touch ID sul T1 funziona sotto Linux solo con T1Bridge v0.1.12 (comandi
biometrici BridgeXPC in chiaro su TCP 52032, xART su TCP 61500, prerequisito i dati FDR della ESP Apple); su questa
macchina il trasporto (configurazione USB 2) c'è già. Incognite: convivenza con le impronte di macOS e sospensione
2→1→2. Contiene la procedura di prova reversibile in 10 passi e il rollback. Prova pianificata per il 25/11/2026
con `scripts/install-touchid.sh` (install/status/import/undo).

## Conflitti aperti tra le fonti

- Indirizzo PCI per `d3cold_allowed`: su 14,3 `01:00.0` è la Radeon, non l'SSD → si cerca per classe PCI (`config/udev/90-macbookpro14-3-nvme-no-d3cold.rules`).
- Sospensione: s2idle con rimozione delle porte Thunderbolt (14,3) contro `pcie_ports=compat` (14,2, senza dGPU).
  Sul 14,3 la prima strada funziona ([`sleep.md`](sleep.md)); `pcie_ports=compat` non è stato provato.
- iGPU Intel: Dunedan la dà funzionante, cschaba riporta schermo nero con il pannello sulla Intel.
- `tb_mode` / `fnmode` della Touch Bar: valori diversi tra fonti; modalità display non testata sul 14,3.

## Procedura di test in corso

Vedi la sezione "Stato della sessione" in [`../AGENTS.md`](../AGENTS.md).
