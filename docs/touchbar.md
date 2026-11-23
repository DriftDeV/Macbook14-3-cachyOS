# Touch Bar T1 su MacBookPro14,3: risultati verificati

Data: 23 novembre 2026. Macchina: MacBookPro14,3, CachyOS, KDE Plasma 6.8 (Wayland).
Tag come in [`README.md`](README.md): **[F]** visto sulla macchina, **[I]** inferenza, **[NV]** non verificato.

## Stato prima del driver (installazione pulita)

- [F] Kernel `7.3.5-2-cachyos` compilato con **clang 23 + ThinLTO**; `6.18.60-3-cachyos-lts` compilato con **gcc 16**.
- [F] T1 `05ac:8600` in **configurazione USB 1** (su 3). Interfacce 0-1 = webcam (`uvcvideo`, già funzionante),
  2 = HID tastiera (`hid-generic`), 3 = HID Touch Bar + sensore di luce, **presa da `hid-sensor-hub`**.
- [F] Il kernel ha `hid-appletb-kbd`, `hid-appletb-bl`, `appletbdrm` come moduli, ma non si legano al T1.
- [F] ACPI crea il platform device `APP7777:00` (quello su cui si aggancia `apple-ibridge`).

## Sorgente scelta

- `nonderbe/macbook-pro-touchbar-driver`, **branch `t1-fixes`**, commit `2677d711` (2026-10-18).
  - [F] Il branch di default di quel fork è identico a F13 (`ecfadc3`) e non compila su ≥ 6.15: va usato `t1-fixes`.
  - [F] Codice letto prima dell'uso: nessuna chiamata a usermode helper, file o rete.
- [F] Su Linux 7.3 **`struct acpi_driver` non esiste più**: anche `t1-fixes` non compila.
  Patch nostre in [`../patches/touchbar/`](../patches/touchbar/):
  1. `apple-ibridge` registrato come `platform_driver` con `acpi_match_table` (APP7777).
  2. `Makefile` che passa `LLVM=1` solo se il kernel di destinazione ha `CONFIG_CC_IS_CLANG=y`.
  3. `dkms.conf` senza `CLEAN` (dkms 3.4.5 lo segnala come deprecato; solo estetica).
- [F] Con le patch compila senza errori né warning su entrambi i kernel installati.

## Test reversibile (insmod, senza installare)

- [F] Dopo `insmod` dei tre moduli e lo spostamento dell'interfaccia 3 da `hid-sensor-hub` ad `apple-ibridge-hid`
  (quello che fa la regola udev del fork `udev/90-apple-ibridge-t1.rules`): **la Touch Bar si accende e funziona**.
- [F] Resta in configurazione USB 1 (`tb_mode=keyboard`, default di `t1-fixes`); la webcam resta su `uvcvideo`.
- [F] Sensore di luce: `iio:device0` "als" da `apple-ib-als`, `in_illuminance_input` restituisce un valore.
- [F] Parametri di `apple_ib_tb` di default: `fnmode=1`, `idle_timeout=300`, `dim_timeout=-2`.
- [F] `sudo` non funziona né dalla shell di Claude né dal pannello Terminale dell'app Claude (opzione
  "no new privileges"): i comandi da root vanno lanciati dall'utente in Konsole.

## Installazione permanente (DKMS) e riavvio

- [F] `sudo ./scripts/install-touchbar.sh` (dkms 3.4.5): compila e installa `appleibridge/0.1` per
  `7.3.5-2-cachyos` e `6.18.60-3-cachyos-lts`. DKMS firma i moduli con una sua chiave MOK autogenerata
  (`/var/lib/dkms/mok.*`); il kernel non la conosce e scrive "module verification failed" (innocuo senza Secure Boot/lockdown).
- [F] Dopo il riavvio: `apple_ibridge` si carica (da `modules-load.d`) **prima** che il T1 venga enumerato,
  quindi entrambe le interfacce HID vanno subito ad `apple-ibridge-hid`; `hid-sensor-hub` resta caricato ma senza
  dispositivi, la regola udev non deve intervenire. Touch Bar e sensore di luce funzionano, webcam su `uvcvideo`.
- [I] Se un giorno `hid-sensor-hub` arrivasse prima (es. nell'initramfs), interviene la regola udev del fork.

## Da verificare [NV]

- Avvio con il kernel LTS (i moduli sono installati, non provato).
- Aggiornamento del kernel: DKMS dovrebbe ricompilare da solo (`AUTOINSTALL=yes`).
- Touch Bar dopo sospensione s2idle (il fork ha un fix, provato solo su 14,2).
- `tb_mode=display` (configurazione 2) sul 14,3.
- Comportamento di `fnmode` (tasti F o tasti speciali di default) e layout dei tasti.
- `usbmuxd` non è installato: se lo diventa, controllare `39-usbmuxd.rules` (può mettere il T1 in configurazione 0).
