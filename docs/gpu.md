# Grafica (Intel HD 630 + Radeon Pro 560) su MacBookPro14,3: stato verificato

Data: 23 novembre 2026. CachyOS, kernel `7.3.5-2-cachyos`, KDE Plasma 6.8 Wayland, GRUB (`\EFI\cachyos\grubx64.efi`).
Tag come in [`README.md`](README.md).

## Chi fa cosa [F]

| | Intel HD 630 | Radeon Pro 555/560 (Baffin) |
|---|---|---|
| PCI / DRM | `00:02.0`, `card1`, `renderD128`, `i915` | `01:00.0`, `card2`, `renderD129`, `amdgpu` |
| `boot_vga` | 0 | **1** |
| Schermo interno | **nessuno**: `failed to retrieve link info, disabling eDP` | **`eDP-2` collegato** |
| Runtime PM | `suspended` | `control=on`, "Runtime PM not available" |

- **Non c'è commutazione automatica**: KDE (KWin), Xwayland, plasmashell, browser e terminali usano tutti `renderD129`
  (Radeon). La Intel resta sospesa.
- `apple_gmux` trovato (`gmux version 4.0.29 [indexed]`), `vga_switcheroo: enabled`, audio HDMI della Radeon
  registrato come client switcheroo. Retroilluminazione: `gmux_backlight` (308/1023 al momento della lettura).
- Senza macOS il firmware Apple collega il pannello alla Radeon e non inizializza la Intel per l'eDP: per questo i915
  non vede lo schermo (comportamento noto, vedi `research_notes/.../gpu_power_thermal.md`).

## Consumi a riposo [F]

Campioni a 1 s con il desktop fermo: `gpu_busy_percent` 0 %, sclk 320-838 MHz, mclk 300 MHz, **7,4-9,3 W** sulla Radeon
(`power1_input`); batteria in scarica a ~23 W totali (Wi-Fi attivo, luminosità 30 %). Temperatura GPU 48 °C.

## Schermo sulla Intel: OpenCore `SignalAppleOS` + `gpu-power-prefs=1` [F] (25/11/2026)

Il Mac parte da OpenCore Legacy Patcher 3.0.0 (`EFI\OC\OpenCore.efi` sulla ESP Apple, che poi avvia GRUB). L'opzione
**"Windows GMUX"** di OCLP accende `Booter > Quirks > SignalAppleOS` (sorgente OCLP, `efi_builder/graphics_audio.py`):
il firmware crede di avviare macOS per ogni sistema, come con `apple_set_os.efi`.

| Prova | Esito |
|---|---|
| Solo `SignalAppleOS` (`gpu-power-prefs` = `00 00 00 00`) | nulla cambia: `vga_switcheroo` `DIS:+:Pwr`, `IGD: :Pwr`, i915 senza eDP (`disabling eDP`) |
| `SignalAppleOS` + `gpu-power-prefs` = `01 00 00 00` (come `gpu-switch -i`), riavvio da OpenCore | **i915 `eDP-1` collegato e attivo**, `boot_vga` Intel = 1, `fbcon: i915drmfb is primary`; **KWin disegna con la Intel** (`Mesa Intel HD Graphics 630`); `card2-eDP-2` collegato ma spento (`EDID err` di amdgpu, innocuo) |

Variabile scritta da Linux (`/sys/firmware/efi/efivars/gpu-power-prefs-fa4ce28d-b62f-4c99-9cc3-6815686e30f9`, 8 byte:
attributi `07 00 00 00` + `01 00 00 00`, dopo `chattr -i`). Per tornare alla Radeon: `00 00 00 00` nello stesso modo, oppure
da macOS `sudo nvram gpu-power-prefs=%00%00%00%00`, oppure reset della NVRAM. Senza `SignalAppleOS` (avvio diretto di
GRUB) la variabile da sola non basta [I: è la combinazione documentata da `gpu-switch`/`apple_set_os`].

Primo avvio sulla Intel: Touch Bar (tiny-dfr), Touch ID e webcam partiti come prima. **Luminosità [F]**: i tasti/slider
di KDE la cambiano (scrivono `gmux_backlight`, regolata dal chip gmux e non dalla Radeon) e il pannello resta sulla Intel
(`eDP-1` attivo, nessuno switch nei log). Restano da verificare [NV]:
- **consumi**: la Radeon resta accesa (~7 W a riposo, `power_dpm_force_performance_level=auto`) perché KWin la apre come
  seconda GPU (uscite USB-C/Thunderbolt); per spegnerla serve togliere i client e usare `vga_switcheroo` (runtime PM non
  disponibile), al prezzo delle uscite esterne;
- scala dello schermo e curva della luminosità automatica (KDE vede un'uscita nuova `eDP-1`, la curva era salvata per
  `eDP-2`; al primo avvio luminosità al 100 % e automatica spenta);
- sospensione S3 e risveglio con il pannello sulla Intel; monitor esterni; app Chromium/Electron (`AMD_DEBUG=notiling`
  serviva per la Radeon).

## Opzioni [NV salvo dove indicato]

1. **Così com'è**: stabile, tutto funziona (sospensione, uscite video), costo ~7-9 W.
2. **Ridurre il consumo della Radeon**: profilo energetico / `power_dpm_force_performance_level=low` (sclk fisso al minimo).
   Reversibile al volo; risparmio da misurare.
3. **Solo Intel**: far credere al firmware di avviare macOS (`apple_set_os.efi` o `spoof_osx_version` di rEFInd), scegliere
   la Intel all'avvio (variabile EFI `gpu-power-prefs`, come `gpu-switch -i`), poi spegnere la Radeon da `vga_switcheroo`.
   Rischi: schermo nero all'avvio (rimedio [I]: reset NVRAM), uscite video USB-C/Thunderbolt probabilmente perse (cablate
   sulla Radeon [I]), sospensione e audio da riprovare. Riscontri sul 14,3 contrastanti (Dunedan #6; cschaba: schermo nero).
   **Prima metà [F] riuscita il 25/11/2026** con OpenCore (sezione sopra): schermo e desktop sulla Intel. Lo spegnimento
   della Radeon non è ancora provato.

## Browser e app Chromium/Electron: GPU spenta sulla Radeon sotto Wayland [F] (24/11/2026)

**Sintomo**: Brave a scatti, soprattutto su YouTube, CPU impegnata. **Causa**: sotto Wayland il processo GPU di Chromium
usa il nodo di rendering della Radeon (`--render-node-override=/dev/dri/renderD129`, radeonsi Polaris 11, Mesa 26.3.1) e
**crolla con SIGILL** (exit 132) circa un secondo dopo l'avvio, tre volte; poi Chromium lo avvia con `--use-gl=disabled`
e disegna tutto con la CPU. Succede dal primo avvio di CachyOS (23/11, prima della modalità display della Touch Bar) e
riguarda anche Claude Desktop, Sidra e Discord (coredump e `--use-gl=disabled` nei loro processi GPU). Le build ufficiali
non stampano il messaggio del `CHECK` e Brave non salva minidump; nemmeno i log dettagliati del processo GPU dicono nulla.

**Dove si rompe** (prove con un profilo temporaneo di Brave 1.100.58, crolli in 9 s):

| Prova | Esito |
|---|---|
| nessuna opzione (Wayland, Radeon) | 3 crolli, GPU spenta |
| `--use-angle=gl/vulkan`, `--disable-features=Vulkan`, `--disable-gpu-sandbox`, `WaylandLinuxDrmSyncobj` off, niente workaround dei driver | 3 crolli |
| `AMD_DEBUG=nodcc`, `nodcc,nohyperz,nodisplaydcc`, `MESA_LOADER_DRIVER_OVERRIDE=zink`, `GBM_BACKEND=dri` | 3 crolli |
| `--use-gl=egl` | nessun crollo ma GPU spenta (valore non valido) |
| `eglinfo -B -p surfaceless` con `DRI_PRIME=1` (fuori da Chromium) | EGL sulla Radeon funziona |
| `--ozone-platform=x11` (XWayland, Radeon) | GPU attiva |
| `--render-node-override=…pci-0000:00:02.0-render` (Wayland, Intel) | GPU attiva, ma **glitch** a schermo (immagini passate dalla Intel alla Radeon) |
| **`AMD_DEBUG=notiling` (Wayland, Radeon)** | **GPU attiva, nessun crollo, nessun glitch** (provato dall'utente) |

Quindi il crollo sta nel percorso solo-Wayland di Chromium con i **buffer "tiled" della Radeon Polaris** (GBM/dmabuf
verso KWin) [I: con `notiling` i buffer sono lineari e il problema sparisce; il `CHECK` preciso resta ignoto].
`AMD_DEBUG=notiling` va dato **solo alle app Chromium/Electron**, non a tutta la sessione (KWin e i giochi
perderebbero il tiling).

**Video** (8 s, VP9 o H.264 1080p30; CPU da `/proc/<pid>/stat`, motore video da `fdinfo`):

| Configurazione | VP9 (YouTube) | H.264 |
|---|---|---|
| predefinita (GPU spenta) | CPU 90 % di un core | — |
| Wayland + Intel (`--render-node-override`) | CPU 24-25 %, VP9 sulla Intel | CPU 24 % |
| XWayland (`--ozone-platform=x11`) | CPU 79-85 %: **la Intel non decodifica** | — |
| **Wayland + `AMD_DEBUG=notiling`** | CPU ~79 % (la Radeon non decodifica VP9) | **CPU 24 %, Radeon (UVD 34 %)** |

Correzione rispetto a una nota precedente: il 24 % "con XWayland" misurato prima era con XWayland **più**
`--render-node-override` sulla Intel ancora in `brave-flags.conf`; XWayland da solo decodifica il VP9 con la CPU.
La Radeon Pro 560 **non decodifica VP9 né AV1** (`vainfo`: H.264 e HEVC); la Intel HD 630 decodifica VP9 (profilo 0).
Per YouTube a basso consumo si può chiedere H.264 (es. estensione *h264ify*: massimo 1080p) [NV: non installata].

**Correzione installata: `scripts/fix-chromium-gpu.sh`** (da utente; passo `apps` di `install.sh`; `--list` per lo
stato, `--undo` per togliere). Riconosce le app Chromium/Electron dal programma dell'`Exec=` (anche dietro uno script
con `exec`): cartella con `chrome_100_percent.pak`/`v8_context_snapshot.bin`, runtime `electron` di sistema o avviatori
noti (Discord: `/usr/share/discord/discord` lancia l'app vera da `~/.config/discord`). Mette `env AMD_DEBUG=notiling`
davanti al programma:

| App | Come |
|---|---|
| `.desktop` di sistema (Discord, Sidra, …) | copia utente in `~/.local/share/applications` (ha la precedenza) |
| `.desktop` utente: web app/PWA di Brave o Chrome (avviano `/opt/brave-bin/brave` con il percorso completo) | `Exec` modificato |
| Brave e Claude Desktop (i loro `.desktop` li avviano per nome dal PATH) | lanciatore in `~/.local/bin` (viene prima di `/usr/bin`) |
| Claude Desktop (riscrive il suo `.desktop` a ogni avvio) | il lanciatore, ad app chiusa, rimette a `false` `isHardwareAccelerationDisabled`/`AutoDisabled` in `~/.config/Claude/claude_desktop_config.json` se l'app l'aveva spenta da sola dopo i crolli |

Il servizio utente `macbookpro14-3-chromium-x11.path` (nome storico) sorveglia `/usr/share/applications` e
`~/.local/share/applications` e riapplica lo script (copia in `~/.local/lib/macbookpro14-3/fix-chromium-gpu`) quando si
installa o aggiorna un'app o una web app; scrive solo se qualcosa cambia (niente cicli, provato con una web app finta).
La versione precedente (XWayland, `--ozone-platform=x11`) viene tolta da sola. MacBook Manager (gruppo **App**) controlla
dal vivo i processi GPU e segnala le app con `--use-gl=disabled`.

Provati [F] il 24/11/2026: Brave, Discord, Sidra e Claude Desktop su Wayland con la Radeon (`renderD129`),
`--gpu-recent-crash-count=0`, accelerazione attiva, nessun glitch; Claude Desktop ha riattivato da solo l'accelerazione
(lanciatore). Da segnalare a monte [NV]: Chromium + Polaris (GFX8) + buffer tiled
sotto Wayland.
