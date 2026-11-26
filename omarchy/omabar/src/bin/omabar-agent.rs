//! omabar-agent: gira nella sessione dell'utente e racconta a OmaBar (renderer di sistema) cosa succede.
//!   - Hyprland, eventi (socket2): finestra attiva, apertura/chiusura dello screensaver di Omarchy
//!   - Hyprland, richieste (ogni secondo): sessione bloccata (LOCK in solitaryBlockedBy, come
//!     omarchy-hyprland-session-locked) e schermi spenti (dpmsStatus)
//!   - D-Bus di sessione: lettori MPRIS (quello che suona, altrimenti l'ultimo che ha suonato) e la copertina del
//!     brano (mpris:artUrl: file, http(s) via curl o data:), ritagliata e ridotta a protocol::ART pixel
//! Manda lo stato completo sul socket del renderer a ogni cambiamento e si ricollega da solo se il renderer riparte.
//!
//!   - durante lo screensaver: la finestra dello screensaver catturata (wlr-screencopy) e adattata alla barra
//!
//!   omabar-agent                  normale (servizio utente omabar-agent.service)
//!   omabar-agent --print          stampa gli stati invece di mandarli (prova senza renderer)
//!   omabar-agent --screenshot F   salva in F (PNG) quello che la barra mostra adesso
//!   omabar-agent --mirror-test F  specchia lo schermo attuale in F (PPM) e misura i tempi

#[path = "../capture.rs"]
mod capture;
#[path = "../mirror.rs"]
mod mirror;
#[path = "../protocol.rs"]
mod protocol;

use base64::Engine as _;
use protocol::ToAgent;

use protocol::{App, Media, SessionState, ToRenderer, VERSION};
use std::{
    collections::{HashMap, HashSet},
    env, fs,
    io::{BufRead, BufReader, ErrorKind, Read, Write},
    os::unix::net::UnixStream,
    path::{Path, PathBuf},
    sync::mpsc::{self, Receiver, RecvTimeoutError, Sender},
    thread,
    time::{Duration, Instant, SystemTime},
};
use zbus::zvariant::OwnedValue;

const SCREENSAVER_CLASS: &str = "org.omarchy.screensaver";
const MONITOR_POLL: Duration = Duration::from_secs(1);
const RECONNECT: Duration = Duration::from_secs(2);
/// I titoli delle finestre cambiano anche più volte al secondo (indicatori nei terminali): se cambia solo quello,
/// al massimo un messaggio ogni TITLE_EVERY.
const TITLE_EVERY: Duration = Duration::from_secs(1);

enum Update {
    /// Fotogramma dello screensaver già adattato (RGB mirror::W × mirror::H).
    Frame(Vec<u8>),
    App(Option<App>),
    Screensaver(bool),
    Monitors { locked: bool, off: bool },
    Media(Option<Media>),
    /// Copertina caricata (RGB in base64, vuota se non riuscita) per mpris:artUrl `url`.
    Art { url: String, rgb: String },
}

fn main() {
    let args: Vec<String> = env::args().collect();
    if let Some(i) = args.iter().position(|a| a == "--screenshot") {
        let out = args.get(i + 1).map(String::as_str).unwrap_or("omabar.png");
        match screenshot(out) {
            Ok(()) => println!("{out}"),
            Err(e) => {
                eprintln!("omabar-agent: istantanea non riuscita: {e}");
                std::process::exit(1);
            }
        }
        return;
    }
    if let Some(i) = args.iter().position(|a| a == "--mirror-test") {
        let out = args.get(i + 1).map(String::as_str).unwrap_or("mirror.ppm");
        if let Err(e) = mirror_test(out) {
            eprintln!("omabar-agent: {e:#}");
            std::process::exit(1);
        }
        return;
    }
    let print_only = args.iter().any(|a| a == "--print");
    let (tx, rx) = mpsc::channel();

    {
        let tx = tx.clone();
        thread::spawn(move || hypr_events(tx));
    }
    {
        let tx = tx.clone();
        thread::spawn(move || hypr_monitors(tx));
    }
    {
        let tx = tx.clone();
        thread::spawn(move || mpris(tx));
    }
    let (art_tx, art_rx) = mpsc::channel::<String>();
    {
        let tx = tx.clone();
        thread::spawn(move || art_loader(art_rx, tx));
    }
    if !print_only {
        let tx = tx.clone();
        thread::spawn(move || mirror_screensaver(tx));
    }
    drop(tx);

    let mut state = SessionState::default();
    let mut sent: Option<SessionState> = None;
    let mut conn: Option<UnixStream> = None;
    let mut last_try = Instant::now() - RECONNECT;
    let mut last_send = Instant::now() - TITLE_EVERY;

    loop {
        if !print_only && conn.is_none() && last_try.elapsed() >= RECONNECT {
            last_try = Instant::now();
            conn = connect();
            sent = None;
        }
        let mut frame = None;
        match rx.recv_timeout(Duration::from_millis(500)) {
            Ok(u) => {
                apply(&mut state, u, &mut frame, &art_tx);
                // Più aggiornamenti insieme (per esempio all'avvio): un solo messaggio; dei fotogrammi l'ultimo.
                while let Ok(u) = rx.try_recv() {
                    apply(&mut state, u, &mut frame, &art_tx);
                }
            }
            Err(RecvTimeoutError::Timeout) => {}
            Err(RecvTimeoutError::Disconnected) => break,
        }
        if let (Some(f), Some(c)) = (frame, &mut conn) {
            let rgb = base64::engine::general_purpose::STANDARD.encode(f);
            let msg = ToRenderer::Frame { w: mirror::W as u32, h: mirror::H as u32, rgb };
            let line = serde_json::to_string(&msg).unwrap() + "\n";
            if let Err(e) = c.write_all(line.as_bytes()) {
                eprintln!("omabar-agent: invio del fotogramma non riuscito ({e}), mi ricollego");
                conn = None;
                continue;
            }
        }
        if sent.as_ref() == Some(&state) {
            if let Some(c) = &mut conn {
                if renderer_closed(c) {
                    eprintln!("omabar-agent: renderer scollegato");
                    conn = None;
                }
            }
            continue;
        }
        if only_title_changed(sent.as_ref(), &state) && last_send.elapsed() < TITLE_EVERY {
            continue; // lo manderà un giro successivo (recv_timeout di 500 ms)
        }
        last_send = Instant::now();
        let line = serde_json::to_string(&ToRenderer::State(state.clone())).unwrap() + "\n";
        if print_only {
            // La copertina in base64 riempirebbe il terminale: solo la sua lunghezza.
            let mut shown = state.clone();
            if let Some(m) = &mut shown.media {
                if !m.art.is_empty() {
                    m.art = format!("<{} caratteri>", m.art.len());
                }
            }
            let line = serde_json::to_string(&ToRenderer::State(shown)).unwrap() + "\n";
            print!("{line}");
            let _ = std::io::stdout().flush();
            sent = Some(state.clone());
        } else if let Some(c) = &mut conn {
            match c.write_all(line.as_bytes()) {
                Ok(()) => {
                    describe(sent.as_ref(), &state);
                    sent = Some(state.clone());
                }
                Err(e) => {
                    eprintln!("omabar-agent: invio non riuscito ({e}), mi ricollego");
                    conn = None;
                }
            }
        }
    }
}

fn only_title_changed(sent: Option<&SessionState>, now: &SessionState) -> bool {
    let Some(sent) = sent else { return false };
    let mut same = sent.clone();
    if let (Some(a), Some(b)) = (&mut same.app, &now.app) {
        if a.class == b.class {
            a.title = b.title.clone();
        }
    }
    &same == now
}

fn apply(s: &mut SessionState, u: Update, frame: &mut Option<Vec<u8>>, art_tx: &Sender<String>) {
    match u {
        Update::Frame(f) => *frame = Some(f),
        Update::App(a) => s.app = a,
        Update::Screensaver(v) => s.screensaver = v,
        Update::Monitors { locked, off } => {
            s.locked = locked;
            s.display_off = off;
        }
        Update::Media(mut m) => {
            if let Some(new) = &mut m {
                match &s.media {
                    // Stessa copertina e stesso brano: si tiene quella già caricata.
                    Some(old) if old.art_url == new.art_url && old.title == new.title => new.art = old.art.clone(),
                    // Alcuni lettori (Chromium) riusano lo stesso file per brani diversi: si ricarica anche se
                    // cambia solo il titolo (il caricatore ha una cache per URL e data di modifica).
                    _ if !new.art_url.is_empty() => {
                        let _ = art_tx.send(new.art_url.clone());
                    }
                    _ => {}
                }
            }
            s.media = m;
        }
        Update::Art { url, rgb } => {
            if let Some(m) = &mut s.media {
                if m.art_url == url {
                    m.art = rgb;
                }
            }
        }
    }
}

/// Nel journal solo i cambi di modalità e di brano, non ogni cambio di finestra.
fn describe(old: Option<&SessionState>, new: &SessionState) {
    let d = SessionState::default();
    let old = old.unwrap_or(&d);
    if (old.locked, old.screensaver, old.display_off) != (new.locked, new.screensaver, new.display_off) {
        eprintln!(
            "omabar-agent: bloccata={} screensaver={} schermi spenti={}",
            new.locked, new.screensaver, new.display_off
        );
    }
    if old.media.as_ref().map(|m| (&m.player, &m.title, m.playing)) != new.media.as_ref().map(|m| (&m.player, &m.title, m.playing)) {
        match &new.media {
            Some(m) => eprintln!("omabar-agent: {} {} \"{}\"", m.player, if m.playing { "suona" } else { "in pausa" }, m.title),
            None => eprintln!("omabar-agent: nessun lettore"),
        }
    }
}

fn connect() -> Option<UnixStream> {
    let mut c = UnixStream::connect(protocol::SOCKET).ok()?;
    let hello = serde_json::to_string(&ToRenderer::Hello { version: VERSION }).unwrap() + "\n";
    c.write_all(hello.as_bytes()).ok()?;
    // Scritture bloccanti (un fotogramma è ~520 KB) ma mai più di 2 s; letture quasi istantanee (renderer_closed).
    c.set_write_timeout(Some(Duration::from_secs(2))).ok()?;
    c.set_read_timeout(Some(Duration::from_millis(1))).ok()?;
    eprintln!("omabar-agent: collegato a {}", protocol::SOCKET);
    Some(c)
}

/// Il renderer non manda niente dopo il saluto: una lettura che dà 0 byte vuol dire che ha chiuso.
fn renderer_closed(c: &mut UnixStream) -> bool {
    let mut buf = [0u8; 512];
    loop {
        match c.read(&mut buf) {
            Ok(0) => return true,
            Ok(_) => continue,
            Err(e) if matches!(e.kind(), ErrorKind::WouldBlock | ErrorKind::TimedOut) => return false,
            Err(e) if e.kind() == ErrorKind::Interrupted => continue,
            Err(_) => return true,
        }
    }
}

// ---------------------------------------------------------------------------------------------------------------
// Hyprland

/// Cartella dei socket di Hyprland: quella della variabile d'ambiente se esiste ancora, altrimenti la più recente
/// (Hyprland riavviato dopo l'agente cambia firma).
fn hypr_dir() -> Option<PathBuf> {
    let runtime = PathBuf::from(env::var_os("XDG_RUNTIME_DIR")?).join("hypr");
    if let Some(sig) = env::var_os("HYPRLAND_INSTANCE_SIGNATURE") {
        let d = runtime.join(sig);
        if d.join(".socket2.sock").exists() {
            return Some(d);
        }
    }
    fs::read_dir(&runtime)
        .ok()?
        .flatten()
        .map(|e| e.path())
        .filter(|p| p.join(".socket2.sock").exists())
        .max_by_key(|p| fs::metadata(p).and_then(|m| m.modified()).ok())
}

fn hypr_request(dir: &Path, cmd: &str) -> Option<serde_json::Value> {
    let mut s = UnixStream::connect(dir.join(".socket.sock")).ok()?;
    s.set_read_timeout(Some(Duration::from_secs(2))).ok()?;
    s.write_all(cmd.as_bytes()).ok()?;
    let mut out = String::new();
    s.read_to_string(&mut out).ok()?;
    serde_json::from_str(&out).ok()
}

fn norm_addr(a: &str) -> String {
    a.trim().trim_start_matches("0x").to_string()
}

fn app_from(class: &str, title: &str) -> Option<App> {
    (!class.is_empty()).then(|| App { class: class.to_string(), title: title.to_string() })
}

fn hypr_events(tx: Sender<Update>) {
    loop {
        let Some(dir) = hypr_dir() else {
            thread::sleep(Duration::from_secs(5));
            continue;
        };
        let Ok(stream) = UnixStream::connect(dir.join(".socket2.sock")) else {
            thread::sleep(RECONNECT);
            continue;
        };
        // Stato di partenza: finestra attiva e screensaver già aperto.
        if let Some(w) = hypr_request(&dir, "j/activewindow") {
            let s = |k: &str| w.get(k).and_then(|v| v.as_str()).unwrap_or("").to_string();
            let _ = tx.send(Update::App(app_from(&s("class"), &s("title"))));
        }
        let mut savers: HashSet<String> = HashSet::new();
        if let Some(serde_json::Value::Array(clients)) = hypr_request(&dir, "j/clients") {
            for c in clients {
                if c.get("class").and_then(|v| v.as_str()) == Some(SCREENSAVER_CLASS) {
                    if let Some(a) = c.get("address").and_then(|v| v.as_str()) {
                        savers.insert(norm_addr(a));
                    }
                }
            }
        }
        if tx.send(Update::Screensaver(!savers.is_empty())).is_err() {
            return;
        }

        for line in BufReader::new(stream).lines() {
            let Ok(line) = line else { break };
            let Some((ev, data)) = line.split_once(">>") else { continue };
            let update = match ev {
                "activewindow" => {
                    let (class, title) = data.split_once(',').unwrap_or((data, ""));
                    Some(Update::App(app_from(class, title)))
                }
                "openwindow" => {
                    let parts: Vec<&str> = data.splitn(4, ',').collect();
                    if parts.len() >= 3 && parts[2] == SCREENSAVER_CLASS {
                        savers.insert(norm_addr(parts[0]));
                        Some(Update::Screensaver(true))
                    } else {
                        None
                    }
                }
                "closewindow" => {
                    if savers.remove(&norm_addr(data)) && savers.is_empty() {
                        Some(Update::Screensaver(false))
                    } else {
                        None
                    }
                }
                _ => None,
            };
            if let Some(u) = update {
                if tx.send(u).is_err() {
                    return;
                }
            }
        }
        // Hyprland chiuso o riavviato: si riparte da capo.
        let _ = tx.send(Update::Screensaver(false));
        thread::sleep(Duration::from_secs(1));
    }
}

fn hypr_monitors(tx: Sender<Update>) {
    let mut last = None;
    loop {
        let state = hypr_dir()
            .and_then(|d| hypr_request(&d, "j/monitors"))
            .and_then(|v| v.as_array().cloned())
            .map(|mons| {
                let locked = mons.iter().any(|m| {
                    m.get("solitaryBlockedBy")
                        .and_then(|b| b.as_array())
                        .is_some_and(|b| b.iter().any(|x| x.as_str() == Some("LOCK")))
                });
                let active: Vec<_> = mons
                    .iter()
                    .filter(|m| !m.get("disabled").and_then(|v| v.as_bool()).unwrap_or(false))
                    .collect();
                let off = !active.is_empty()
                    && active.iter().all(|m| m.get("dpmsStatus").and_then(|v| v.as_bool()) == Some(false));
                (locked, off)
            });
        if let Some((locked, off)) = state {
            if last != Some((locked, off)) {
                last = Some((locked, off));
                if tx.send(Update::Monitors { locked, off }).is_err() {
                    return;
                }
            }
        }
        thread::sleep(MONITOR_POLL);
    }
}

// ---------------------------------------------------------------------------------------------------------------
// MPRIS

const MPRIS_PREFIX: &str = "org.mpris.MediaPlayer2.";

fn mpris(tx: Sender<Update>) {
    loop {
        if let Err(e) = mpris_loop(&tx) {
            eprintln!("omabar-agent: D-Bus: {e}");
        }
        if tx.send(Update::Media(None)).is_err() {
            return;
        }
        thread::sleep(Duration::from_secs(5));
    }
}

fn mpris_loop(tx: &Sender<Update>) -> zbus::Result<()> {
    let conn = zbus::blocking::Connection::session()?;
    for rule in [
        "type='signal',interface='org.freedesktop.DBus.Properties',member='PropertiesChanged',path='/org/mpris/MediaPlayer2'",
        "type='signal',sender='org.freedesktop.DBus',interface='org.freedesktop.DBus',member='NameOwnerChanged',arg0namespace='org.mpris.MediaPlayer2'",
    ] {
        conn.call_method(
            Some("org.freedesktop.DBus"),
            "/org/freedesktop/DBus",
            Some("org.freedesktop.DBus"),
            "AddMatch",
            &(rule,),
        )?;
    }
    let mut last_playing: Option<String> = None;
    let mut last: Option<Option<Media>> = None;
    let mut refresh = |conn: &zbus::blocking::Connection, last_playing: &mut Option<String>| -> bool {
        let m = pick_player(conn, last_playing);
        if last.as_ref() != Some(&m) {
            last = Some(m.clone());
            return tx.send(Update::Media(m)).is_ok();
        }
        true
    };
    if !refresh(&conn, &mut last_playing) {
        return Ok(());
    }
    for msg in zbus::blocking::MessageIterator::from(&conn) {
        let msg = msg?;
        let h = msg.header();
        let member = h.member().map(|m| m.as_str().to_string()).unwrap_or_default();
        if member == "PropertiesChanged" || member == "NameOwnerChanged" {
            if !refresh(&conn, &mut last_playing) {
                return Ok(());
            }
        }
    }
    Ok(())
}

fn pick_player(conn: &zbus::blocking::Connection, last_playing: &mut Option<String>) -> Option<Media> {
    let names: Vec<String> = conn
        .call_method(
            Some("org.freedesktop.DBus"),
            "/org/freedesktop/DBus",
            Some("org.freedesktop.DBus"),
            "ListNames",
            &(),
        )
        .ok()?
        .body()
        .deserialize()
        .ok()?;
    let mut paused = Vec::new();
    for name in names.iter().filter(|n| n.starts_with(MPRIS_PREFIX)) {
        let Some(m) = player_state(conn, name) else { continue };
        if m.playing {
            *last_playing = Some(name.clone());
            return Some(m);
        }
        paused.push((name.clone(), m));
    }
    // Nessuno suona: quello che suonava per ultimo, se è ancora in pausa, altrimenti il primo in pausa.
    let pos = paused.iter().position(|(n, _)| Some(n) == last_playing.as_ref()).unwrap_or(0);
    (!paused.is_empty()).then(|| paused.swap_remove(pos).1)
}

fn player_state(conn: &zbus::blocking::Connection, name: &str) -> Option<Media> {
    let props: HashMap<String, OwnedValue> = conn
        .call_method(
            Some(name),
            "/org/mpris/MediaPlayer2",
            Some("org.freedesktop.DBus.Properties"),
            "GetAll",
            &("org.mpris.MediaPlayer2.Player",),
        )
        .ok()?
        .body()
        .deserialize()
        .ok()?;
    let status = props.get("PlaybackStatus").and_then(|v| String::try_from(v.try_clone().ok()?).ok())?;
    if status != "Playing" && status != "Paused" {
        return None;
    }
    let meta: HashMap<String, OwnedValue> = props
        .get("Metadata")
        .and_then(|v| HashMap::<String, OwnedValue>::try_from(v.try_clone().ok()?).ok())
        .unwrap_or_default();
    let title = meta
        .get("xesam:title")
        .and_then(|v| String::try_from(v.try_clone().ok()?).ok())
        .unwrap_or_default();
    let artist = meta
        .get("xesam:artist")
        .and_then(|v| Vec::<String>::try_from(v.try_clone().ok()?).ok())
        .map(|a| a.join(", "))
        .unwrap_or_default();
    let art_url = meta
        .get("mpris:artUrl")
        .and_then(|v| String::try_from(v.try_clone().ok()?).ok())
        .unwrap_or_default();
    // "org.mpris.MediaPlayer2.firefox.instance_1_42" → "firefox"
    let player = name.trim_start_matches(MPRIS_PREFIX).split('.').next().unwrap_or("").to_string();
    Some(Media { player, playing: status == "Playing", title, artist, art: String::new(), art_url })
}

// ---------------------------------------------------------------------------------------------------------------
// Copertina del brano

const ART_MAX_BYTES: u64 = 16 << 20;
const ART_CACHE: usize = 24;
/// Un file locale può non esserci ancora o essere scritto a metà quando arriva il segnale (Chromium): si riprova.
const ART_RETRIES: u32 = 5;
const ART_RETRY: Duration = Duration::from_millis(400);

/// Carica le copertine una alla volta, in un thread suo (un download lento non ferma lo stato della sessione).
/// Delle richieste accumulate conta solo l'ultima.
fn art_loader(rx: Receiver<String>, tx: Sender<Update>) {
    let mut cache: Vec<(String, Option<SystemTime>, String)> = Vec::new();
    let mut pending: Option<String> = None;
    loop {
        let mut url = match pending.take() {
            Some(u) => u,
            None => match rx.recv() {
                Ok(u) => u,
                Err(_) => return,
            },
        };
        while let Ok(u) = rx.try_recv() {
            url = u;
        }
        let local = art_file(&url);
        let mut rgb = String::new();
        for attempt in 1..=ART_RETRIES {
            let mtime = local.as_ref().and_then(|p| fs::metadata(p).ok()?.modified().ok());
            if let Some(hit) = cache.iter().find(|c| c.0 == url && c.1 == mtime) {
                rgb = hit.2.clone();
                break;
            }
            match load_art(&url, local.as_deref()) {
                Ok(data) => {
                    if cache.len() >= ART_CACHE {
                        cache.remove(0);
                    }
                    cache.push((url.clone(), mtime, data.clone()));
                    rgb = data;
                    break;
                }
                Err(e) if local.is_none() || attempt == ART_RETRIES => {
                    eprintln!("omabar-agent: copertina {}: {e:#}", short(&url));
                    break;
                }
                Err(_) => {
                    thread::sleep(ART_RETRY);
                    if let Ok(u) = rx.try_recv() {
                        pending = Some(u); // brano già cambiato: inutile insistere su questo
                        break;
                    }
                }
            }
        }
        if pending.is_some() && rgb.is_empty() {
            continue;
        }
        if tx.send(Update::Art { url, rgb }).is_err() {
            return;
        }
    }
}

fn short(url: &str) -> String {
    if url.chars().count() > 80 {
        url.chars().take(80).collect::<String>() + "…"
    } else {
        url.to_string()
    }
}

/// file:///percorso%20con%20spazi → /percorso con spazi
fn art_file(url: &str) -> Option<PathBuf> {
    let rest = url.strip_prefix("file://")?;
    let rest = rest.strip_prefix("localhost").unwrap_or(rest);
    let b = rest.as_bytes();
    let mut out = Vec::with_capacity(b.len());
    let mut i = 0;
    while i < b.len() {
        if b[i] == b'%' && i + 2 < b.len() {
            if let Ok(v) = u8::from_str_radix(std::str::from_utf8(&b[i + 1..i + 3]).unwrap_or("zz"), 16) {
                out.push(v);
                i += 3;
                continue;
            }
        }
        out.push(b[i]);
        i += 1;
    }
    use std::os::unix::ffi::OsStringExt;
    Some(PathBuf::from(std::ffi::OsString::from_vec(out)))
}

/// Legge l'immagine, la ritaglia al centro in un quadrato di protocol::ART pixel e la restituisce in base64 (RGB).
fn load_art(url: &str, local: Option<&Path>) -> anyhow::Result<String> {
    use anyhow::{bail, Context as _};
    let bytes = if let Some(p) = local {
        let len = fs::metadata(p).with_context(|| format!("{}", p.display()))?.len();
        if len > ART_MAX_BYTES {
            bail!("file troppo grande ({len} byte)");
        }
        fs::read(p)?
    } else if url.starts_with("https://") || url.starts_with("http://") {
        let out = std::process::Command::new("curl")
            .args(["-sfL", "--max-time", "8", "--max-filesize", &ART_MAX_BYTES.to_string(), "-o", "-", "--", url])
            .stdin(std::process::Stdio::null())
            .output()
            .context("curl")?;
        if !out.status.success() {
            bail!("curl è uscito con {}", out.status);
        }
        out.stdout
    } else if let Some(rest) = url.strip_prefix("data:") {
        let (head, data) = rest.split_once(',').context("URL data: senza virgola")?;
        if !head.ends_with(";base64") {
            bail!("URL data: non in base64");
        }
        base64::engine::general_purpose::STANDARD.decode(data.trim())?
    } else {
        bail!("schema non gestito");
    };
    let img = image::load_from_memory(&bytes).context("immagine non riconosciuta")?;
    let side = protocol::ART;
    let thumb = img.resize_to_fill(side, side, image::imageops::FilterType::Lanczos3);
    // Trasparenza su nero (il fondo della barra è scuro): meglio di un alone bianco.
    let rgba = thumb.to_rgba8();
    let mut rgb = Vec::with_capacity((side * side * 3) as usize);
    for px in rgba.pixels() {
        let a = px[3] as u32;
        rgb.extend(px.0[..3].iter().map(|&c| (c as u32 * a / 255) as u8));
    }
    Ok(base64::engine::general_purpose::STANDARD.encode(rgb))
}

// ---------------------------------------------------------------------------------------------------------------
// Screensaver specchiato

/// Finestra dello screensaver: uscita, posizione e dimensioni rispetto all'uscita (coordinate logiche).
fn saver_window(dir: &Path) -> Option<(String, i32, i32, i32, i32)> {
    let clients = hypr_request(dir, "j/clients")?;
    let c = clients
        .as_array()?
        .iter()
        .find(|c| c.get("class").and_then(|v| v.as_str()) == Some(SCREENSAVER_CLASS))?;
    let pair = |k: &str| -> Option<(i64, i64)> {
        let a = c.get(k)?.as_array()?;
        Some((a.first()?.as_i64()?, a.get(1)?.as_i64()?))
    };
    let (x, y) = pair("at")?;
    let (w, h) = pair("size")?;
    let mon_id = c.get("monitor")?.as_i64()?;
    let mons = hypr_request(dir, "j/monitors")?;
    let m = mons.as_array()?.iter().find(|m| m.get("id").and_then(|v| v.as_i64()) == Some(mon_id))?;
    let (mx, my) = (m.get("x")?.as_i64()?, m.get("y")?.as_i64()?);
    Some((m.get("name")?.as_str()?.to_string(), (x - mx) as i32, (y - my) as i32, w as i32, h as i32))
}

const MIRROR_FRAME: Duration = Duration::from_millis(50); // fino a 20 fps

fn mirror_screensaver(tx: Sender<Update>) {
    let mut cap: Option<capture::Capturer> = None;
    let mut m = mirror::Mirror::default();
    let mut window: Option<(String, i32, i32, i32, i32)> = None;
    let mut last_check = Instant::now() - Duration::from_secs(1);
    let mut frames = 0u32;
    let mut since = Instant::now();
    loop {
        let start = Instant::now();
        // La posizione della finestra si ricontrolla ogni mezzo secondo, non a ogni fotogramma.
        if last_check.elapsed() >= Duration::from_millis(500) {
            last_check = Instant::now();
            let w = hypr_dir().and_then(|d| saver_window(&d));
            if w.is_none() && window.is_some() {
                m.reset();
                cap = None; // si richiude la connessione Wayland finché non serve
                if frames > 0 {
                    eprintln!(
                        "omabar-agent: screensaver specchiato, {:.1} fps",
                        frames as f64 / since.elapsed().as_secs_f64()
                    );
                }
            }
            if w.is_some() && window.is_none() {
                frames = 0;
                since = Instant::now();
            }
            window = w;
        }
        let Some((out, x, y, w, h)) = window.clone() else {
            thread::sleep(Duration::from_millis(500));
            continue;
        };
        if cap.is_none() {
            match capture::Capturer::new() {
                Ok(c) => cap = Some(c),
                Err(e) => {
                    eprintln!("omabar-agent: cattura dello schermo non disponibile: {e:#}");
                    thread::sleep(Duration::from_secs(5));
                    continue;
                }
            }
        }
        match cap.as_mut().unwrap().capture(&out, x, y, w, h) {
            Ok(c) => {
                let f = mirror::Frame {
                    data: c.data,
                    width: c.width,
                    height: c.height,
                    stride: c.stride,
                    order: c.order,
                    y_invert: c.y_invert,
                };
                if tx.send(Update::Frame(m.compose(&f))).is_err() {
                    return;
                }
                frames += 1;
            }
            Err(e) => {
                eprintln!("omabar-agent: cattura: {e:#}");
                cap = None;
                thread::sleep(Duration::from_millis(500));
            }
        }
        if let Some(rest) = MIRROR_FRAME.checked_sub(start.elapsed()) {
            thread::sleep(rest);
        }
    }
}

// ---------------------------------------------------------------------------------------------------------------
// Istantanea della barra

/// Chiede al renderer cosa mostra. La connessione prende per un attimo il posto dell'agente, che si ricollega da solo.
fn screenshot(out: &str) -> Result<(), String> {
    let mut c = UnixStream::connect(protocol::SOCKET).map_err(|e| format!("{}: {e}", protocol::SOCKET))?;
    c.set_read_timeout(Some(Duration::from_secs(5))).map_err(|e| e.to_string())?;
    let req = serde_json::to_string(&ToRenderer::Screenshot).unwrap() + "\n";
    c.write_all(req.as_bytes()).map_err(|e| e.to_string())?;
    for line in BufReader::new(c).lines() {
        let line = line.map_err(|e| e.to_string())?;
        if let Ok(ToAgent::Screenshot { png }) = serde_json::from_str::<ToAgent>(&line) {
            let png = base64::engine::general_purpose::STANDARD.decode(png).map_err(|e| e.to_string())?;
            fs::write(out, png).map_err(|e| e.to_string())?;
            return Ok(());
        }
    }
    Err("il renderer ha chiuso senza rispondere".into())
}

/// Prova del mirroring senza screensaver: 10 catture dell'intero schermo principale, l'ultima salvata in PPM.
fn mirror_test(out: &str) -> anyhow::Result<()> {
    let dir = hypr_dir().ok_or_else(|| anyhow::anyhow!("Hyprland non trovato"))?;
    let mons = hypr_request(&dir, "j/monitors").ok_or_else(|| anyhow::anyhow!("j/monitors"))?;
    let m = &mons.as_array().ok_or_else(|| anyhow::anyhow!("monitor"))?[0];
    let name = m["name"].as_str().unwrap_or("").to_string();
    let scale = m["scale"].as_f64().unwrap_or(1.0);
    let (w, h) = ((m["width"].as_f64().unwrap_or(0.0) / scale) as i32, (m["height"].as_f64().unwrap_or(0.0) / scale) as i32);
    let mut cap = capture::Capturer::new()?;
    let mut mir = mirror::Mirror::default();
    let mut frame = Vec::new();
    let (mut t_cap, mut t_comp) = (Duration::ZERO, Duration::ZERO);
    for _ in 0..10 {
        let t = Instant::now();
        let c = cap.capture(&name, 0, 0, w, h)?;
        t_cap += t.elapsed();
        let t = Instant::now();
        let f = mirror::Frame { data: c.data, width: c.width, height: c.height, stride: c.stride, order: c.order, y_invert: c.y_invert };
        frame = mir.compose(&f);
        t_comp += t.elapsed();
    }
    println!("{name} {w}×{h} logici: cattura {:.1} ms, adattamento {:.1} ms a fotogramma",
        t_cap.as_secs_f64() * 100.0, t_comp.as_secs_f64() * 100.0);
    let mut ppm = format!("P6\n{} {}\n255\n", mirror::W, mirror::H).into_bytes();
    ppm.extend_from_slice(&frame);
    fs::write(out, ppm)?;
    Ok(())
}
