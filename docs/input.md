# Tastiera e trackpad su MacBookPro14,3: stato verificato

Data: 23 novembre 2026. CachyOS, kernel `7.3.5-2-cachyos`, libinput 1.32.0, KDE Plasma 6.8 Wayland.
Tag come in [`README.md`](README.md).

## Dispositivi [F]

| Dispositivo | Driver | Nodo |
|---|---|---|
| `Apple SPI Keyboard` | `applespi` (mainline), SPI `APP000D:00` | `event4` |
| `Apple SPI Touchpad` | `applespi` (si presenta col vendor Synaptics `0x06CB`) | `event5` |
| `Apple Inc. iBridge` (Touch Bar, USB `05ac:8600`) | `apple-ibridge-hid` / `apple-ib-tb` | |

## Quirk libinput

- Già in libinput (`/usr/share/libinput/50-system-apple.quirks`, sezione "applespi driver"): `ModelAppleTouchpad=1`,
  `AttrSizeHint=104x75`, `AttrTouchSizeRange=150:130`, `AttrPalmSizeThreshold=1600`.
- Della repo, [`../config/libinput/local-overrides.quirks`](../config/libinput/local-overrides.quirks) → `/etc/libinput/`:
  tastiera SPI e Touch Bar come tastiere **interne** (`AttrKeyboardIntegration=internal`). Senza, libinput considera
  interne solo le tastiere PS/2 e il "disabilita durante la digitazione" non scatta.
- [F] Installato e provato dall'utente il 23/11/2026: funziona. Verifica: `sudo libinput quirks list /dev/input/event4`
  (serve `libinput-tools`); effetto dal login successivo.

## Tasti funzione e webcam [F]

- Tasti funzione e multimediali dalla Touch Bar: funzionano (provati dall'utente il 23/11/2026).
- Webcam FaceTime HD (USB dietro l'iBridge, `uvcvideo`, `/dev/video0`): funziona, provata in una chiamata Discord.
  Nessun driver aggiuntivo: `facetimehd` non serve sul 14,3.

## Da verificare [NV]

- Luminosità automatica dello schermo: KWin 6.8 la offre (`kscreen-doctor -o`: "Automatic brightness: supported,
  enabled"; retroilluminazione `gmux_backlight`). In una prova di 90 s la luminosità non è cambiata, ma la luce forte è
  durata solo ~4 s. Con luce prolungata nemmeno.
  - [F] KWin legge il sensore (`ClaimLight` su `net.hadess.SensorProxy`, `LightLevel` aggiornato) e salva in
    `~/.config/kwinoutputconfig.json` una curva per lo schermo: era `autoBrightnessCurve = [[3, 0.55]]`, un solo punto.
  - [F] Dal sorgente di KWin v6.8.3 (`src/workspace.cpp`, `src/core/backendoutput.cpp`): a ogni lettura KWin campiona la
    curva (interpolazione lineare tra i punti, piatta oltre gli estremi) e cambia la luminosità solo se differisce più
    del 20 % da quella attuale (`KWIN_AUTO_BRIGHTNESS_DEADZONE`), dopo 2 s di lettura stabile. Una regolazione manuale
    con la funzione attiva aggiunge il punto `[lux attuali, luminosità]` e sostituisce quello con gli stessi lux.
  - [F] Dopo altre regolazioni dell'utente la curva era ancora `[[3, 0.55]]`: con la stanza a 1-4 lux tutte le
    regolazioni cadono sullo stesso punto, e una curva di un solo punto è piatta.
  - [I] Il sensore sotto il vetro della Touch Bar dà valori molto bassi con la luce ambiente (1-4 lux in una stanza
    illuminata, fino a ~2900 solo con luce diretta): probabilmente manca la calibrazione che applica macOS. KWin
    distingue il buio dalla luce diretta, non le condizioni intermedie.
  - **Soluzione [F]**: curva di partenza `config/kde/kwin-brightness-curve.json`
    (`[[0,0.35],[1,0.5],[4,0.55],[20,0.75],[200,1]]`), scritta da `scripts/set-kwin-brightness-curve.sh` con un servizio
    utente che gira **prima di KWin** al login e poi si disattiva. Scriverla con KWin acceso non funziona: KWin salva la
    configurazione che ha in memoria (anche al logout) e la sovrascrive.
  - Prova del 23/11/2026 dopo il login: sensore coperto (0 lux) → schermo dal 55 % al 35 % in ~3 s; torcia (fino a 5000
    lux) → 100 %; di nuovo luce ambiente → ritorno graduale al 55 %; stanza a 2-3 lux → luminosità ferma, niente
    sfarfallio. La curva resta modificabile con le regolazioni manuali.

## Sensore di luce [F]

- `apple-ib-als` → `iio:device0` → `iio-sensor-proxy` (attivo) → KWin. Campo HID illuminance del T1: 0-5000 lux,
  32 bit, senza esponente (`report_descriptor` di `0003:05AC:8600.0002`); il driver lo passa così com'è, ed è corretto.
- Prova del 23/11/2026: stanza ~1-3 lux, coperto 0, torcia del telefono fino a **2906 lux**. Aggiornamento rapido
  durante la torcia (anche con `poll_interval` a 5000 ms).
- [I] Posizione: dai tempi della prova, il sensore sembra sul lato sinistro della Touch Bar, non vicino alla webcam.
- La luminosità della Touch Bar si adatta alla luce (la regola il T1).
- Tastiera nell'initramfs (`config/mkinitcpio/macbookpro14-3.conf`): serve solo con il disco cifrato; qui non c'è LUKS.
