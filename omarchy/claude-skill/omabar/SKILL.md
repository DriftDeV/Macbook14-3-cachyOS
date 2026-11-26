---
name: omabar
description: >
  Personalizza OmaBar, il renderer della Touch Bar del MacBookPro14,3 (chip T1) su Omarchy: tasti, livelli, icone,
  etichette, orologio, batteria, brano in riproduzione con copertina, livello della schermata di blocco, luminosità,
  carattere, colori (segue il tema di Omarchy), pixel shift. Usala per qualsiasi richiesta sulla Touch Bar ("touch bar",
  "touchbar", "OmaBar", "barra sopra la tastiera", "tasti funzione", "Fn"), da qualunque cartella e sessione, sia per
  cambiare la configurazione sia per modificare il codice del renderer.
---

# OmaBar: personalizzare la Touch Bar

OmaBar disegna la Touch Bar del MacBookPro14,3 (2170×60 pixel, OLED) quando la barra è in **modalità display**.
Gira come servizio di sistema (`macbookpro14-3-omabar.service`, da root, senza accesso alla home). Un agente di sessione
(`omabar-agent.service`, utente) gli racconta blocco, screensaver, schermi spenti e il brano MPRIS.
Repo sorgente: `@REPO@` (codice in `omarchy/omabar/`, guida in `omarchy/omabar/README.md`). L'utente scrive in
italiano: rispondi in italiano.

## Prima di tutto: capire lo stato

```bash
touchbar-mode status 2>/dev/null || cat /etc/macbookpro14-3/touchbar.conf   # modalità e renderer scelti
systemctl is-active macbookpro14-3-omabar.service; systemctl --user is-active omabar-agent.service
cat /etc/omabar/config.toml                     # configurazione personale (sezioni che sostituiscono le predefinite)
cat /usr/share/omabar/config.toml               # predefinita, commentata: è il riferimento del formato
```

Se il renderer scelto non è `omabar`, chiedi all'utente prima di cambiarlo (`run0 touchbar-mode renderer omabar`).
Non cambiare mai la **modalità** (display/tastiera) senza richiesta esplicita: il passaggio a tastiera vale solo dopo uno
spegnimento completo e toglie Touch ID.

## Cambiare la configurazione (caso normale, niente root)

1. Modifica `/etc/omabar/config.toml`: è del gruppo dell'utente e scrivibile, quindi non serve `sudo`. **Ogni sezione
   scritta qui sostituisce per intero quella predefinita.** Per cambiare un solo tasto copia tutto il blocco
   `[[layer]]` (tutti i livelli: la lista `layer` si sostituisce in blocco) o `[lock]` da `/usr/share/omabar/config.toml`
   e modifica la copia. Le sezioni che non scrivi restano predefinite.
2. Controlla **prima di salvare** il file vero (scrivi su un file temporaneo, poi copia):
   `omabar check FILE`. Un file non valido viene ignorato da OmaBar (resta la configurazione precedente) e lo segnala
   nel journal.
3. Anteprima in PNG, senza toccare la barra:
   `omabar preview /tmp/omabar.png --config FILE [--layer 1] [--locked] [--media "Titolo|Artista"] [--art copertina.png]`
   e guarda l'immagine (Read). Con `--config` l'anteprima usa la predefinita più FILE, come il servizio.
4. Salvato il file, OmaBar lo rilegge da solo (inotify): nessun riavvio. Verifica sulla barra vera con
   `omabar-agent --screenshot /tmp/barra.png` (quello che la barra mostra adesso) e guardalo.
5. Problemi: `journalctl -u macbookpro14-3-omabar.service -n 30`.

`omabar` è `/usr/local/lib/macbookpro14-3/omabar/omabar` se non è nel PATH.
In alternativa l'utente ha un editor grafico: MacBook Manager → scheda Touch Bar (con renderer OmaBar).

## Formato

```toml
[display]
brightness = 255      # 1-255, in software (il T1 non ha retroilluminazione regolabile)
follow_screen = true  # segue la luminosità dello schermo, da min_brightness a brightness
min_brightness = 40
pixel_shift = true    # sposta icone e testo di qualche pixel ogni 2 minuti (burn-in dell'OLED)
font = "sans-serif"   # famiglia fontconfig; il testo passa da Pango (ripiego automatico per giapponese, emoji…)
font_size = 26
fade_ms = 300         # dissolvenza al cambio di tema

[theme]
path = "/run/omabar/theme.toml"   # colors.toml del tema di Omarchy, copiato da omabar-theme-sync: non cambiarlo
bar = "theme"                     # oppure "black" (nero vero: consuma meno)
outlines = true                   # false: tasti senza sfondo, solo icona/testo

[[layer]]             # primo livello = normale; secondo = tenendo premuto Fn
name = "sistema"
buttons = [ { label = "esc", keys = ["Esc"] }, ... ]

[lock]                # mostrato a sessione bloccata (hyprlock); non invia tasti
name = "bloccato"
buttons = [ ... ]
```

Ogni tasto ha **una sola faccia**: `label = "testo"`, `icon = "nome"`, `clock = "formato strftime"` (per esempio
`"%H:%M  %a %-d"`; con i secondi si ridisegna ogni secondo), `battery = true`, `media = true` (copertina, titolo e
artista del lettore MPRIS); senza faccia è uno spazio vuoto. Altri campi:
- `keys = ["VolumeUp"]`: tasti inviati al tocco; più tasti = combinazione premuta insieme (`["LeftCtrl", "C"]`). Nomi
  delle varianti di `input_linux::Key`: `Esc`, `F1`…`F24`, `A`…`Z`, `Num0`…`Num9`, `LeftCtrl`, `LeftShift`, `LeftAlt`,
  `LeftMeta`, `Enter`, `Space`, `Tab`, `Backspace`, `Delete`, `Up`/`Down`/`Left`/`Right`, `VolumeUp`, `VolumeDown`,
  `Mute`, `PlayPause`, `NextSong`, `PreviousSong`, `BrightnessDown`, `BrightnessUp`, `IllumDown`, `IllumUp`, `Print`…
  Se un nome non esiste `omabar check` lo dice.
- `width = 1.5`: posti occupati (frazionari ammessi); lo spazio si divide in proporzione.
- `gap = true`: separatore stretto tra gruppi (l'utente li ha tolti: non rimetterli senza richiesta).
- `icon_size = 30` (predefinito 36); `icon_playing = "nome"`: icona al posto di `icon` mentre un lettore suona.

Icone: nome di un'icona simbolica cercata in `/etc/omabar/icons`, `/usr/share/omabar/icons` e
`/usr/share/icons/Adwaita/symbolic/*/` (per esempio `ls /usr/share/icons/Adwaita/symbolic/*/ | grep -i volume`),
oppure il percorso di un SVG. Le icone si ricolorano con il tema (usate come maschera). Icone proprie: metti gli SVG in
`/etc/omabar/icons` (serve `run0` per creare la cartella).

Colori: vengono dal tema di Omarchy attivo e cambiano da soli con `omarchy theme set` (fondo `darker_background`,
tasti `lighter_background`, premuto `accent`, testo `foreground`, batteria `green`/`red`). Non si scelgono nel file.

## Modificare il codice (nuove funzioni)

1. Codice in `@REPO@/omarchy/omabar/src/` (Rust): `bar.rs` disegno e tasti, `config.rs` formato, `main.rs` ciclo del
   renderer, `text.rs` testo con Pango, `bin/omabar-agent.rs` agente, `protocol.rs` messaggi agente → renderer.
   Rispetta `AGENTS.md` della repo (stato [F]/[NV], niente promesse non provate).
2. `cd @REPO@/omarchy/omabar && cargo build --release --locked && cargo test --release` (con una dipendenza nuova:
   `cargo build --release` aggiorna `Cargo.lock`, poi di nuovo con `--locked`).
3. Anteprima con `./target/release/omabar preview ...` e guardala.
4. Installa e riavvia renderer e agente: `run0 @REPO@/omarchy/install-omabar.sh` (chiede la password). **Usa `run0`,
   non `sudo`**: nel terminale di Claude `sudo` è bloccato da NoNewPrivs.
5. Verifica sulla barra con `omabar-agent --screenshot` e aggiorna `omarchy/omabar/README.md`.
   Commit/push solo se l'utente lo chiede.
