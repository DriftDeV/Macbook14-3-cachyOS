# OmaBar

Renderer della Touch Bar T1 del MacBookPro14,3 in modalità display, scritto da zero (Rust: drm, cairo, librsvg,
libinput, uinput; nessun codice di tiny-dfr). Terzo renderer accanto a T1Bridge/fnstrip e tiny-dfr.

Fase 1 (26/11/2026): motore dei temi.
- La sessione copia il `colors.toml` del tema attivo di Omarchy in `/run/omabar/theme.toml`
  (`omabar-theme-sync`, servizio + path unit utente su `theme.name`). Il renderer, di sistema e senza accesso alla
  home, guarda il file con inotify e passa ai nuovi colori con una dissolvenza (`display.fade_ms`).
- Colori: fondo = `darker_background`, tasti = `lighter_background`, tasto premuto = `accent`, testo = `foreground`
  (sul premuto il colore che contrasta di più), batteria `green`/`red`. Icone simboliche ricolorate col tema.
- Configurazione: `config.toml` (predefinita) e `/etc/omabar/config.toml` (sezioni che sostituiscono), ricaricata
  da sola.

Fase 2 (26/11/2026): agente di sessione e socket.
- `omabar-agent` (servizio utente, `graphical-session.target`) legge da Hyprland la finestra attiva, lo screensaver
  di Omarchy (finestra `org.omarchy.screensaver`), il blocco (`LOCK` in `solitaryBlockedBy`, come
  `omarchy-hyprland-session-locked`) e gli schermi spenti (`dpmsStatus`); da D-Bus i lettori MPRIS (quello che suona,
  altrimenti l'ultimo che ha suonato). Manda lo stato completo come riga JSON (`src/protocol.rs`).
- Socket `/run/omabar/renderer.sock`: lo crea il renderer da root, 0660 con il gruppo della cartella, e controlla
  SO_PEERCRED. Un agente alla volta (l'ultimo collegato vince); senza agente la barra torna normale.
- Reazioni: schermi spenti e screensaver → barra nera, tocco ignorato (animazione nella fase 4); sessione bloccata →
  livello `[lock]` (lucchetto, brano, ora, batteria) che non invia tasti; tasto `media = true` con titolo e artista;
  `icon_playing` (pausa al posto di play mentre un lettore suona).
- Testo con Pango (`src/text.rs`, 26/11/2026) invece dell'API "giocattolo" di cairo: ripiego automatico glifo per
  glifo (giapponese e altri alfabeti nei titoli, prima quadratini vuoti) e "…" di Pango. [F] sulla barra vera.
- Separatori (`gap = true`) tolti dalla configurazione predefinita su richiesta dell'utente (l'opzione resta).
- Batteria (26/11/2026): "in carica" (livello verde + fulmine) viene da `online` dell'alimentatore (`ADP1`), non da
  `status` di `BAT0`, che con il cavo collegato salta tra Charging e Discharging ogni secondo [F]. Lettura ogni 2 s,
  ridisegno solo quando cambia.
- Copertina del brano (26/11/2026) nel tasto `media`, a sinistra del titolo: l'agente legge `mpris:artUrl` (file
  locale con nuovi tentativi se il lettore lo sta ancora scrivendo, `http(s)` via `curl`, `data:`), la ritaglia al
  centro e la riduce a 44×44 (`protocol::ART`), e la manda in base64 dentro lo stato. Il renderer, senza accesso alla
  home né alla rete, la disegna con gli angoli arrotondati; senza copertina il testo resta centrato come prima.
- Tasti della retroilluminazione della tastiera (`IllumDown`/`IllumUp`, che Omarchy lega a
  `omarchy-brightness-keyboard`).

Dopo la fase 2 (26/11/2026):
- Screensaver specchiato: durante lo screensaver l'agente cattura la sua finestra con wlr-screencopy (connessione
  Wayland aperta, memoria condivisa mappata, `src/capture.rs`) e la adatta alla barra (`src/mirror.rs`): riflesso
  attenuato di tutto lo schermo più il riquadro dei pixel accesi, adattato all'altezza della barra (al massimo 2× in
  larghezza) e mosso con una media mobile. Generico: funziona con qualunque screensaver. Cattura ~45 ms (la impone il
  compositore), adattamento ~8 ms su 4 thread: ~20 fps.
- Luminosità che segue lo schermo (`display.follow_screen`, da `min_brightness` a `brightness`, `gmux_backlight`).
- Tasti fino ai bordi (nessun margine; il pixel shift muove solo icone e testo); separatori `gap = true` tra i gruppi
  e larghezze frazionarie al posto dei posti vuoti.
- Bordi del pannello [F]: il T1 dichiara 2170×60 e la colonna 0 è visibile (`omabar ruler`); la striscia nera oltre
  è il bordo non emissivo del vetro. T1Bridge usa la stessa area da x=0 (`stock_slice.rs`, `escape_bounds().x == 0`).

Comandi:
```
sudo scripts/install-omabar.sh            # compila e installa (--undo per togliere)
sudo touchbar-mode renderer omabar        # usa OmaBar (t1bridge per tornare indietro)
omabar preview out.png [--theme FILE] [--layer N] [--press I] [--locked] [--media "Titolo|Artista"] [--art COPERTINA.png]
omabar-agent --print                       # stati della sessione su stdout, senza renderer
sudo omabar bench                          # FPS reali (con il servizio fermo)
sudo omabar ruler                          # righello sui bordi (con il servizio fermo)
omabar-agent --screenshot out.png          # quello che la barra mostra adesso
omabar-agent --mirror-test out.ppm         # specchia lo schermo attuale e misura i tempi
```

Stato (marcature di AGENTS.md):
- [F] Disegno, temi e dissolvenza sulla barra vera; cambio di tema dal vivo (scrittura di `/run/omabar/theme.toml`).
- [F] FPS misurati il 26/11/2026: barra intera 81,5 fps (12,3 ms), zona di un tasto 438 fps (2,3 ms). Misurati al
  ritorno di DIRTYFB: [NV] se il trasferimento USB del T1 finisca davvero entro quel tempo.
- [F] Tasti al tocco, livello Fn, cambio con `omarchy theme set` (confermati dall'utente il 26/11/2026).
- [F] Fase 2: agente collegato, finestra attiva e lettore MPRIS (cliamp) letti dalla sessione vera; modalità
  Normale → Bloccata → Screensaver → Spenta → Normale provate sulla barra con stati inviati a mano sul socket;
  riconnessione automatica dell'agente.
- [F] Screensaver di Omarchy reale (`omarchy-launch-screensaver force`, 26/11/2026): barra nera in ~2 ms
  dall'apertura della finestra, di nuovo normale alla chiusura.
- [F] Screensaver specchiato sulla barra vera (istantanee con la scritta e gli effetti; 12 fps con le istantanee che
  interrompevano l'agente, ~50 ms a fotogramma misurati senza).
- [F] Copertina dal lettore vero (Chromium, PNG in /tmp) disegnata sulla barra vera (istantanea, 26/11/2026);
  [NV] con lettori che danno URL http(s) (Spotify). [F] Batteria in carica dall'alimentatore, sulla barra vera.
- [NV] Rilevamento reale di hyprlock e del DPMS (stessa logica di Omarchy, non ancora visto scattare); tasti della retroilluminazione della tastiera; sospensione/risveglio.
- Scheda in MacBook Manager (26/11/2026, `manager/macbook_manager/omabar.py` + `gui_omabar.py`): editor di
  `/etc/omabar/config.toml` (luminosità dal vivo, aspetto, livelli e tasti, livello di blocco) con anteprima disegnata
  da `omabar preview --config` e controllo con `omabar check` prima di salvare. [F] provata fuori schermo
  (offscreen) con il binario vero; [NV] nella sessione reale.
- Nome: fino al 26/11/2026 si chiamava CachyBar (nome fuorviante: è fatto per Omarchy, non per CachyOS).
  `install-omabar.sh` migra l'installazione vecchia (servizi, binari, `/etc/cachybar/config.toml`, renderer salvato);
  `touchbar-mode` accetta ancora `cachybar` come sinonimo.
- Da fare: fase 3 (livelli per contesto dalla finestra attiva, tasti personalizzati).
- Nota: il contesto libinput di seat0 (serve solo per Fn) apre anche il trackpad e ne riporta nel journal gli
  avvisi "Touch jump detected", innocui.
