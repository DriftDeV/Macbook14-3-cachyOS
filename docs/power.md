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
