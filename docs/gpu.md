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

## Opzioni (non provate) [NV]

1. **Così com'è**: stabile, tutto funziona (sospensione, uscite video), costo ~7-9 W.
2. **Ridurre il consumo della Radeon**: profilo energetico / `power_dpm_force_performance_level=low` (sclk fisso al minimo).
   Reversibile al volo; risparmio da misurare.
3. **Solo Intel**: far credere al firmware di avviare macOS (`apple_set_os.efi` o `spoof_osx_version` di rEFInd), scegliere
   la Intel all'avvio (variabile EFI `gpu-power-prefs`, come `gpu-switch -i`), poi spegnere la Radeon da `vga_switcheroo`.
   Rischi: schermo nero all'avvio (rimedio [I]: reset NVRAM), uscite video USB-C/Thunderbolt probabilmente perse (cablate
   sulla Radeon [I]), sospensione e audio da riprovare. Riscontri sul 14,3 contrastanti (Dunedan #6; cschaba: schermo nero).
