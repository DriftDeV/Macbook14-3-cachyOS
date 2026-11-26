# Omarchy (Hyprland) sul MacBookPro14,3

Parti della repo che servono **solo su Omarchy**. La procedura completa (chiavetta, installazione, firmware del T1,
post-installazione) è nel [README principale](../README.md#installare-omarchy); driver e servizi comuni stanno in
`scripts/`, `config/`, `dkms/` e sono installati da `install.sh` come su CachyOS.

| File | A cosa serve |
|---|---|
| [`prepare-usb.sh`](prepare-usb.sh) | prepara da macOS o da Linux la chiavetta di installazione: ISO estratta (avvio per etichetta `OMARCHY`), copia verificata di `EFI/APPLE` (firmware del T1) e `EFI/OC` con `ripristina.sh`, Wi-Fi della live, copia della repo. Senza `--execute` mostra solo il piano |
| [`wifi-live.sh`](wifi-live.sh) | copiato sulla chiavetta: Wi-Fi a 5 GHz nella live (NVRAM e firmware pronti, oppure generati dal chip) |
| [`omabar/`](omabar/README.md) | OmaBar, renderer della Touch Bar che segue il tema di Omarchy (Rust) |
| [`install-omabar.sh`](install-omabar.sh) | compila e installa OmaBar (passo `omabar` di `install.sh`, solo su Omarchy) e la skill `/omabar` |
| [`hypr-phantom-display`](hypr-phantom-display) | servizio di sessione (passo `hyprland` di `install.sh`): con lo schermo sulla Intel disattiva in Hyprland l'eDP "collegato" ma vuoto della Radeon, solo se 4 condizioni sono vere insieme (0×0 in Hyprland, eDP senza EDID né modalità, scheda PCI, altro eDP vero su un'altra GPU); `--check` spiega la decisione |
| [`claude-skill/omabar/`](claude-skill/omabar/SKILL.md) | skill di Claude Code per personalizzare la Touch Bar da qualunque sessione |

Perché la live va su chiavetta: l'installatore di Omarchy esclude il disco da cui è partita, quindi una live sul disco
interno non trova dove installare [F, 26/11/2026]. L'installatore usa tutto il disco e cancella la partizione EFI di
Apple: il firmware del T1 (Touch Bar, Touch ID, webcam, sensore di luce) va rimesso con `ripristina.sh`; OpenCore
(schermo sulla Intel) con `scripts/opencore.sh install` (comune ai due sistemi).

Stato: Omarchy in uso su questo Mac dal 26/11/2026 (kernel `7.2.15-omarchy`): driver, Touch Bar con OmaBar, Wi-Fi a
5 GHz, guardia del T1 [F]. `prepare-usb.sh` provato su Linux con un disco immagine (formattazione, ISO di prova, copia
della EFI con 200 file verificati, Wi-Fi pronto) [F]; su macOS e con una ISO vera [NV]; `--embed-wifi` e
`wifi-live.sh` nella live [NV].
