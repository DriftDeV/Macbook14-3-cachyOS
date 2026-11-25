# Consumi e autonomia su MacBookPro14,3: misure

Data: 23 novembre 2026. CachyOS, kernel `7.3.5-2-cachyos`, KDE Plasma 6.8, luminosità 30 % (308/1023),
Wi-Fi a 5 GHz, desktop fermo con browser e app di Claude aperti. Batteria A1820: 72,5 Wh a piena carica
(94 % della capacità di progetto, 181 cicli). Tag come in [`README.md`](README.md).

## Come misurare

- Batteria: `current_now × voltage_now` di `BAT0`, media di 30 campioni a 1 s. Livello e autonomia: usare UPower
  (`upower -i …`), che è quello che mostra KDE: `percentage` è la carica, `capacity` è la salute.
- Radeon: `hwmon/power1_input` di `amdgpu` (sensore della GPU, più stabile della batteria).
- Le misure della batteria derivano di 1-3 W in pochi minuti: confrontare A/B/A e fidarsi delle differenze grandi.

## Risultati [F]

| Leva | Effetto misurato |
|---|---|
| Slider di KDE Bilanciato ↔ Risparmio (power-profiles-daemon) | nessuna differenza a riposo (20,5-21,3 contro 20,6-20,9 W); cambia solo l'EPP della CPU (`balance_power` ↔ `power`), che conta sotto carico. Non agisce sulla Radeon. |
| Radeon `auto` ↔ `low` (livello forzato) | nessuna: a riposo è già al clock minimo (214 MHz, mclk 300 MHz), ~7-9 W comunque |
| **Radeon `manual` + profilo `POWER_SAVING`** (+ PCIe 2,5 GT/s richiesto) | **-1,5 W** sulla Radeon (8,66 → 7,16 W), unica leva netta. Con lo script installato: 7,21 W con il PCIe rimasto a 8 GT/s (la richiesta di 2,5 GT/s non prende, nemmeno ripetuta): il risparmio viene da manual + POWER_SAVING |
| CPU senza turbo / limitata al 60 % | nessuna a riposo (taglia i picchi sotto carico) |
| Tastiera retroilluminata 102/255 → 0 | ~-0,5 W (nel rumore) |
| Bluetooth spento | non distinguibile dal rumore |
| ABM (`panel_power_savings`) | non applicabile: `Device or resource busy` (KWin tiene il controllo del colore) |

Note: per cambiare `pp_power_profile_mode` sulla Radeon serve prima `power_dpm_force_performance_level=manual`
(altrimenti EINVAL). ASPM L1 è già attivo sul collegamento della Radeon.

A riposo con la leva Radeon: ~18,3 W → con 72,5 Wh circa **4 ore**. Senza: ~20,5 W → circa 3,5 ore.

**Schermo sulla Intel [F] (25/11/2026**, OpenCore + `gpu-power-prefs=1`, vedi `gpu.md`): 5 min a riposo, 150 campioni a
2 s, luminosità 35 % (359/1023), Wi-Fi acceso, app di Claude aperta ma ferma, leva Radeon attiva (`manual`, PCIe a 8 GT/s).
Batteria **media 17,0 W, mediana 16,3 W** (min 15,4, picchi fino a 25,9); dal contatore di carica (123 mAh in 300 s) ~18 W.
Radeon invariata a **7,0 W** (resta accesa come seconda GPU di KWin). Rispetto ai ~18,3 W di prima: circa **-1,5/-2 W**,
dentro la deriva di 1-3 W della batteria ma con la mediana sotto il minimo precedente; ~4-4,5 ore con 72,5 Wh. Il risparmio
non viene dalla Radeon e **non dal Panel Self Refresh**: debugfs di i915 (25/11) dice `Sink support: PSR = no` (il pannello
non lo supporta). **FBC spenta**: `pixel format not supported` sul piano primario. Il formato è già a 8 bit:
`i915_display_info` mostra `AB24` (ABGR8888, con alfa) e modificatore `0x100000000000004` (Y-tiled con CCS, compressione
di rendering già attiva); la FBC di Kaby Lake accetta solo formati senza alfa [I: XRGB/XBGR8888]. Provato
`KWIN_DRM_PREFER_COLOR_DEPTH=24` (drop-in del servizio `plasma-kwin_wayland`, nuovo accesso): stesso formato, FBC ancora
spenta, tolto. KWin non ha un'opzione per scegliere il formato senza alfa. DMC `kbl_dmc_ver1_04` caricato, `DC3 -> DC5` 6 volte,
`DC5 -> DC6` mai. Origine dei ~1,5-2 W in meno: ignota [I: forse solo rumore della batteria, o meno lavoro della Radeon
senza scanout].
Il grosso del consumo resta la Radeon (~7 W anche al minimo); l'unico modo di toglierlo è spegnerla (vedi `gpu.md`).

## Automatismo: `scripts/install-power.sh`

- `power-source.sh` (in `/usr/local/lib/macbookpro14-3/`), chiamato da una regola udev al collegamento/scollegamento
  dell'alimentatore, dal servizio `macbookpro14-3-power-source` all'avvio e dall'hook di sleep dopo il risveglio.
- A batteria: Radeon `manual` + `POWER_SAVING` + PCIe al minimo; CPU senza turbo. Con l'alimentatore: Radeon `auto`
  con `3D_FULL_SCREEN`, turbo attivo. Scelte in `/etc/macbookpro14-3/power.conf`. Log: `journalctl -t macbookpro14-3-power`.
- Lato KDE (da fare nelle Impostazioni → Gestione energetica): profilo energetico per alimentazione e luminosità della
  tastiera a batteria.

## Da verificare [NV]

- Autonomia reale su una carica completa con l'automatismo attivo.
- Prestazioni grafiche a batteria con PCIe al minimo (video, browser) e passaggio pulito tra i due stati.

## Grafico e report della batteria [F] (25/11/2026)

MacBook Manager, scheda **Batteria** (dettagli in `manager/README.md`): cronologia di UPower e journal, registratore ogni
minuto con i fattori (Radeon, GPU dello schermo, luminosità, filtro audio, Touch Bar, app), report per ogni sessione a
batteria. Prime sessioni ricostruite dalla cronologia: 18,5-21,4 W di media nelle giornate normali (autonomia stimata
3 h 24 - 3 h 54 con la batteria piena), 27 W il pomeriggio del 25/11 (compilazioni, musica con il DSP audio, Claude).
Salute 94 % a 184 cicli (72,3/76,8 Wh secondo UPower).

