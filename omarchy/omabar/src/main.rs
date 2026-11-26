//! OmaBar: renderer della Touch Bar T1 del MacBookPro14,3 (modalità display) che segue il tema del sistema.
//!
//!   omabar                                avvia il renderer (root; poi passa a nobody con i gruppi input e video)
//!   omabar preview OUT.png [opzioni]      disegna la barra in un PNG, senza toccare lo schermo
//!        --theme FILE   colors.toml da usare (predefinito: quello in theme.path della configurazione)
//!        --layer N      livello da mostrare (0 = normale, 1 = con Fn)
//!        --press I      mostra premuto il tasto I
//!        --locked       mostra il livello della sessione bloccata
//!        --media "Titolo|Artista"   finge un brano in riproduzione
//!        --art COPERTINA.png        con questa copertina
//!        --size WxH     dimensioni (predefinito 2170x60)
//!        --config FILE  usa FILE al posto di /etc/omabar/config.toml (un errore ferma l'anteprima)
//!   omabar check FILE                     controlla un file di configurazione personale (come lo legge il renderer)
//!   omabar bench [--seconds N]            misura i fotogrammi al secondo reali (root, nessun altro renderer)
//!   omabar ruler [--seconds N]            righello sui bordi della barra, per vedere quali pixel sono visibili

mod backlight;
mod bar;
mod config;
mod display;
mod input;
mod protocol;
mod server;
mod text;
mod theme;
mod watch;

use anyhow::{anyhow, bail, Context as _, Result};
use bar::{rgb_surface, Bar, ClockTick, DrawOpts, Rect};
use cairo::{Context, Format, ImageSurface};
use chrono::{Local, Timelike};
use config::{BarBackground, Config};
use display::Display;
use input::VirtualKeys;
use ::input::event::{
    keyboard::{KeyState, KeyboardEvent, KeyboardEventTrait},
    touch::{TouchEvent, TouchEventPosition, TouchEventSlot},
    DeviceEvent, Event, EventTrait,
};
use input_linux::Key;
use protocol::{Media, SessionState};
use server::{Incoming, Server};
use nix::sys::epoll::{Epoll, EpollCreateFlags, EpollEvent, EpollFlags, EpollTimeout};
use std::{
    collections::HashMap,
    fs,
    path::{Path, PathBuf},
    time::{Duration, Instant},
};
use theme::Theme;
use watch::FileWatch;

const DRM_PATH: &str = "/dev/dri/touchbar";
/// Ogni quanto si rileggono batteria e alimentatore; si ridisegna solo se cambiano (cavo collegato: subito visibile).
const BATTERY_REFRESH: Duration = Duration::from_secs(2);
const PIXEL_SHIFT_EVERY: Duration = Duration::from_secs(120);
/// Spostamenti del disegno contro il burn-in (x, y), percorsi a giro.
const PIXEL_SHIFTS: [(f64, f64); 8] =
    [(0.0, 0.0), (2.0, 1.0), (4.0, 0.0), (2.0, -1.0), (0.0, 0.0), (-2.0, 1.0), (-4.0, 0.0), (-2.0, -1.0)];
const FRAME: Duration = Duration::from_millis(16);
/// Ogni quanto si rilegge la luminosità dello schermo.
const BACKLIGHT_POLL: Duration = Duration::from_millis(500);

fn main() {
    let args: Vec<String> = std::env::args().skip(1).collect();
    let result = match args.first().map(String::as_str) {
        None | Some("run") => run(),
        Some("preview") => preview(&args[1..]),
        Some("check") => check(&args[1..]),
        Some("bench") => bench(&args[1..]),
        Some("ruler") => ruler(&args[1..]),
        Some("-h" | "--help" | "help") => {
            println!("Uso: omabar [run] | preview OUT.png [--theme FILE] [--layer N] [--press I] [--locked] [--media \"Titolo|Artista\" [--art COPERTINA.png]] [--size WxH] [--config FILE] | check FILE | bench [--seconds N]");
            Ok(())
        }
        Some(other) => Err(anyhow!("comando sconosciuto: {other} (omabar --help)")),
    };
    if let Err(e) = result {
        eprintln!("omabar: {e:#}");
        std::process::exit(1);
    }
}

fn load_theme(cfg: &Config, path: &Path) -> Theme {
    let t = match fs::read_to_string(path) {
        Ok(text) => Theme::from_colors_toml(&text).unwrap_or_else(|e| {
            eprintln!("omabar: tema {} non valido ({e:#}): colori neutri", path.display());
            Theme::default()
        }),
        Err(_) => Theme::default(),
    };
    if cfg.theme.bar == BarBackground::Black {
        t.with_black_bar()
    } else {
        t
    }
}

fn opt<'a>(args: &'a [String], name: &str) -> Option<&'a str> {
    args.iter().position(|a| a == name).and_then(|i| args.get(i + 1)).map(String::as_str)
}

fn preview(args: &[String]) -> Result<()> {
    let out = args.first().filter(|a| !a.starts_with("--")).ok_or_else(|| anyhow!("manca il file PNG"))?;
    let cfg = match opt(args, "--config") {
        Some(p) => Config::load_file(p)?,
        None => Config::load(),
    };
    let theme_path = PathBuf::from(opt(args, "--theme").unwrap_or(&cfg.theme.path));
    let theme = load_theme(&cfg, &theme_path);
    let (w, h) = match opt(args, "--size") {
        Some(s) => {
            let (a, b) = s.split_once('x').ok_or_else(|| anyhow!("--size vuole LxA"))?;
            (a.parse()?, b.parse()?)
        }
        None => (2170, 60),
    };
    let mut bar = Bar::new(&cfg, w as f64, h as f64);
    bar.active = opt(args, "--layer").map(str::parse).transpose()?.unwrap_or(0);
    if bar.active >= bar.layers.len() {
        bail!("livello {} inesistente (ce ne sono {})", bar.active, bar.layers.len());
    }
    bar.locked = args.iter().any(|a| a == "--locked");
    let media = opt(args, "--media").map(|m| {
        let (title, artist) = m.split_once('|').unwrap_or((m, ""));
        Media { player: "anteprima".into(), playing: true, title: title.into(), artist: artist.into(), ..Default::default() }
    });
    let mut media = media;
    if let (Some(m), Some(p)) = (&mut media, opt(args, "--art")) {
        m.art = preview_art(p)?;
    }
    if let Some(i) = opt(args, "--press").map(str::parse::<usize>).transpose()? {
        let b = bar.layer_mut().buttons.get_mut(i).ok_or_else(|| anyhow!("tasto {i} inesistente"))?;
        b.pressed = true;
    }
    let surface = ImageSurface::create(Format::Rgb24, w, h)?;
    {
        let c = Context::new(&surface)?;
        bar.draw(&c, &draw_opts(&cfg, &theme, (0.0, 0.0), media.as_ref()), true);
    }
    let mut f = fs::File::create(out).with_context(|| format!("creazione di {out}"))?;
    surface.write_to_png(&mut f)?;
    let layer_name = if bar.locked { &cfg.lock.name } else { &cfg.layers[bar.active].name };
    println!("{out}: tema \"{}\", livello \"{layer_name}\"", theme.name);
    Ok(())
}

/// Copertina finta per l'anteprima: un PNG ritagliato al centro e ridotto come fa l'agente.
fn preview_art(path: &str) -> Result<String> {
    use base64::Engine as _;
    let mut f = fs::File::open(path).with_context(|| format!("apertura di {path}"))?;
    let src = ImageSurface::create_from_png(&mut f).with_context(|| format!("{path}: non è un PNG"))?;
    let side = protocol::ART as i32;
    let dst = ImageSurface::create(Format::Rgb24, side, side)?;
    {
        let c = Context::new(&dst)?;
        let (sw, sh) = (src.width() as f64, src.height() as f64);
        let scale = side as f64 / sw.min(sh);
        c.scale(scale, scale);
        c.set_source_surface(&src, -(sw - sw.min(sh)) / 2.0, -(sh - sw.min(sh)) / 2.0)?;
        c.paint()?;
    }
    let stride = dst.stride() as usize;
    let mut dst = dst;
    let data = dst.data()?;
    let mut rgb = Vec::with_capacity((side * side * 3) as usize);
    for y in 0..side as usize {
        for x in 0..side as usize {
            let px = u32::from_ne_bytes(data[y * stride + x * 4..y * stride + x * 4 + 4].try_into().unwrap());
            rgb.extend([(px >> 16) as u8, (px >> 8) as u8, px as u8]);
        }
    }
    Ok(base64::engine::general_purpose::STANDARD.encode(rgb))
}

fn check(args: &[String]) -> Result<()> {
    let path = args.first().ok_or_else(|| anyhow!("manca il file da controllare"))?;
    let cfg = Config::load_file(path)?;
    println!("{path}: valido ({} livelli, {} tasti nel primo)", cfg.layers.len(), cfg.layers[0].buttons.len());
    Ok(())
}

fn draw_opts<'a>(cfg: &'a Config, theme: &'a Theme, shift: (f64, f64), media: Option<&'a Media>) -> DrawOpts<'a> {
    DrawOpts {
        theme,
        outlines: cfg.theme.outlines,
        font: &cfg.display.font,
        font_size: cfg.display.font_size,
        shift,
        media,
    }
}

/// Cosa mostra la barra, dallo stato della sessione (più forte prima).
#[derive(Clone, Copy, Debug, PartialEq)]
enum Mode {
    /// Schermi spenti (DPMS): barra nera, tocco ignorato.
    Off,
    /// Screensaver: lo schermo specchiato dall'agente (fotogrammi), nero se non ne arrivano.
    Screensaver,
    /// Sessione bloccata: livello [lock], nessun tasto inviato.
    Locked,
    Normal,
}

impl Mode {
    fn of(s: &SessionState) -> Mode {
        if s.display_off {
            Mode::Off
        } else if s.screensaver {
            Mode::Screensaver
        } else if s.locked {
            Mode::Locked
        } else {
            Mode::Normal
        }
    }
    fn blank(self) -> bool {
        matches!(self, Mode::Off | Mode::Screensaver)
    }
}

/// Misura quanti fotogrammi al secondo arrivano davvero sulla barra: barra intera e zona di un tasto.
fn bench(args: &[String]) -> Result<()> {
    let secs: f64 = opt(args, "--seconds").map(str::parse).transpose()?.unwrap_or(5.0);
    let mut disp = Display::open(Path::new(DRM_PATH))?;
    let (w, h) = disp.logical_size();
    let surface = ImageSurface::create(Format::Rgb24, w as i32, h as i32)?;
    let stride = surface.stride() as usize;
    let full = [Rect { x: 0.0, y: 0.0, w: w as f64, h: h as f64 }];
    let button = [Rect { x: 200.0, y: 0.0, w: 160.0, h: h as f64 }];
    println!("Touch Bar {w}×{h}, {secs} s per prova");
    let mut surface = surface;
    for (label, rects) in [("barra intera", &full[..]), ("un tasto (160 px)", &button[..])] {
        let start = Instant::now();
        let mut frames = 0u32;
        while start.elapsed().as_secs_f64() < secs {
            {
                let c = Context::new(&surface)?;
                let t = frames as f64 / 30.0;
                c.set_source_rgb(0.5 + 0.5 * (t).sin(), 0.5 + 0.5 * (t + 2.1).sin(), 0.5 + 0.5 * (t + 4.2).sin());
                c.paint()?;
            }
            surface.flush();
            let data = surface.data().map_err(|e| anyhow!("{e}"))?;
            disp.present(&data, stride, rects, 255)?;
            drop(data);
            frames += 1;
        }
        let fps = frames as f64 / start.elapsed().as_secs_f64();
        println!("{label}: {fps:.1} fps ({:.1} ms a fotogramma)", 1000.0 / fps);
    }
    if !disp.dirty_supported {
        println!("nota: il driver non usa DIRTYFB (ENOSYS)");
    }
    Ok(())
}

/// Righello: bande di 10 px colorate ai due bordi (rosso, verde, blu, giallo, bianco dall'esterno verso l'interno),
/// tacche ogni 10 px e numeri ogni 50 px. Serve a capire se il pannello mostra tutti i pixel del framebuffer.
fn ruler(args: &[String]) -> Result<()> {
    let secs: u64 = opt(args, "--seconds").map(str::parse).transpose()?.unwrap_or(30);
    let mut disp = Display::open(Path::new(DRM_PATH))?;
    let (w, h) = disp.logical_size();
    let (wf, hf) = (w as f64, h as f64);
    let mut surface = ImageSurface::create(Format::Rgb24, w as i32, h as i32)?;
    {
        let c = Context::new(&surface)?;
        c.set_source_rgb(0.0, 0.0, 0.0);
        c.paint()?;
        let colors = [(1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.2, 0.4, 1.0), (1.0, 1.0, 0.0), (1.0, 1.0, 1.0)];
        for (i, (r, g, b)) in colors.iter().enumerate() {
            c.set_source_rgb(*r, *g, *b);
            c.rectangle(i as f64 * 10.0, 0.0, 10.0, hf);
            c.rectangle(wf - (i as f64 + 1.0) * 10.0, 0.0, 10.0, hf);
            c.fill()?;
        }
        c.set_source_rgb(0.8, 0.8, 0.8);
        c.select_font_face("sans-serif", cairo::FontSlant::Normal, cairo::FontWeight::Bold);
        c.set_font_size(18.0);
        let mut x = 50.0;
        while x < wf - 50.0 {
            c.rectangle(x, 0.0, 2.0, 16.0);
            c.rectangle(x, hf - 16.0, 2.0, 16.0);
            c.fill()?;
            c.move_to(x + 4.0, hf / 2.0 + 6.0);
            c.show_text(&format!("{}", x as u32))?;
            x += 50.0;
        }
        let mut x = 50.0;
        while x < wf - 50.0 {
            c.rectangle(x, 0.0, 1.0, 6.0);
            c.fill()?;
            x += 10.0;
        }
    }
    let stride = surface.stride() as usize;
    let data = surface.data().map_err(|e| anyhow!("{e}"))?;
    disp.present(&data, stride, &[Rect { x: 0.0, y: 0.0, w: wf, h: hf }], 255)?;
    println!("righello {w}×{h} per {secs} s: bande di 10 px rosso, verde, blu, giallo, bianco dai bordi verso l'interno");
    std::thread::sleep(Duration::from_secs(secs));
    Ok(())
}

/// Passa da root a nobody tenendo i gruppi input e video (schermo, uinput e sensore sono già aperti).
fn drop_privileges() -> Result<()> {
    use nix::unistd::{setgid, setgroups, setuid, Group, User};
    let user = User::from_name("nobody")?.ok_or_else(|| anyhow!("utente nobody assente"))?;
    let groups: Vec<_> = ["input", "video"]
        .iter()
        .filter_map(|g| Group::from_name(g).ok().flatten().map(|g| g.gid))
        .collect();
    setgroups(&groups).context("setgroups")?;
    setgid(user.gid).context("setgid")?;
    setuid(user.uid).context("setuid")?;
    Ok(())
}

struct Fade {
    from: Theme,
    start: Instant,
    duration: Duration,
}

fn run() -> Result<()> {
    let mut disp = Display::open(Path::new(DRM_PATH))?;
    let keys = VirtualKeys::new()?;
    // Il socket dell'agente nasce da root: la cartella /run/omabar è root:<gruppo dell'utente>.
    let mut server = match Server::bind(Path::new(protocol::SOCKET)) {
        Ok(s) => Some(s),
        Err(e) => {
            eprintln!("omabar: niente socket per l'agente ({e:#}): solo tema e tasti");
            None
        }
    };
    if nix::unistd::geteuid().is_root() {
        drop_privileges()?;
    }
    let mut touch = input::libinput_seat("seat-touchbar")?;
    let mut keyboard = input::libinput_seat("seat0")?;

    let (w, h) = disp.logical_size();
    let mut surface = ImageSurface::create(Format::Rgb24, w as i32, h as i32)?;
    let stride = surface.stride() as usize;

    let mut cfg = Config::load();
    let mut cfg_watch = FileWatch::new(&Path::new(config::USER_DIR).join(config::USER_FILE))?;
    let mut theme_path = PathBuf::from(&cfg.theme.path);
    let mut theme_watch = FileWatch::new(&theme_path)?;
    let mut target = load_theme(&cfg, &theme_path);
    let mut theme = target.clone();
    let mut fade: Option<Fade> = None;
    let mut bar = Bar::new(&cfg, w as f64, h as f64);
    eprintln!("omabar: {w}×{h}, tema \"{}\"", theme.name);

    let epoll = Epoll::new(EpollCreateFlags::EPOLL_CLOEXEC)?;
    epoll.add(&touch, EpollEvent::new(EpollFlags::EPOLLIN, 0))?;
    epoll.add(&keyboard, EpollEvent::new(EpollFlags::EPOLLIN, 1))?;
    epoll.add(&cfg_watch, EpollEvent::new(EpollFlags::EPOLLIN, 2))?;
    epoll.add(&theme_watch, EpollEvent::new(EpollFlags::EPOLLIN, 3))?;
    if let Some(srv) = &server {
        epoll.add(srv.listener_fd(), EpollEvent::new(EpollFlags::EPOLLIN, 4))?;
    }
    let mut session = SessionState::default();
    let mut mode = Mode::Normal;
    let screen_bl = backlight::ScreenBacklight::find();
    if screen_bl.is_none() {
        eprintln!("omabar: retroilluminazione dello schermo non trovata: luminosità fissa");
    }
    let mut level = backlight::bar_level(&cfg.display, screen_bl.as_ref().and_then(|b| b.fraction()));
    let mut last_bl = Instant::now();
    // Ultimo fotogramma dello screensaver specchiato e quando è arrivato.
    let mut mirror: Option<(Instant, ImageSurface)> = None;
    let mut mirror_new = false;
    let mut want_screenshot = false;

    let mut digitizer = None;
    // slot del dito → (livello, tasto)
    let mut touches: HashMap<u32, (usize, usize)> = HashMap::new();
    let mut full_redraw = true;
    let mut last_clock = (Local::now().minute(), Local::now().second());
    let mut last_battery = Instant::now();
    let mut battery_shown = bar::battery_state();
    let mut shift_idx = 0usize;
    let mut last_shift = Instant::now();

    loop {
        // --- configurazione e tema ---
        if cfg_watch.changed() {
            cfg = Config::load();
            release_all(&mut bar, &keys, &mut touches);
            bar = Bar::new(&cfg, w as f64, h as f64);
            if cfg.theme.path != theme_path.to_string_lossy() {
                theme_path = PathBuf::from(&cfg.theme.path);
                let _ = epoll.delete(&theme_watch);
                theme_watch = FileWatch::new(&theme_path)?;
                epoll.add(&theme_watch, EpollEvent::new(EpollFlags::EPOLLIN, 3))?;
            }
            target = load_theme(&cfg, &theme_path);
            theme = target.clone();
            full_redraw = true;
            eprintln!("omabar: configurazione ricaricata");
        }
        if theme_watch.changed() {
            let new = load_theme(&cfg, &theme_path);
            if new != target {
                eprintln!("omabar: tema \"{}\"", new.name);
                if cfg.display.fade_ms > 0 {
                    fade = Some(Fade {
                        from: theme.clone(),
                        start: Instant::now(),
                        duration: Duration::from_millis(cfg.display.fade_ms as u64),
                    });
                } else {
                    theme = new.clone();
                    full_redraw = true;
                }
                target = new;
            }
        }
        if let Some(f) = &fade {
            let t = (f.start.elapsed().as_secs_f64() / f.duration.as_secs_f64()).min(1.0);
            // ease-in-out
            let e = t * t * (3.0 - 2.0 * t);
            theme = f.from.mix(&target, e);
            full_redraw = true;
            if t >= 1.0 {
                theme = target.clone();
                fade = None;
            }
        }

        // --- luminosità che segue lo schermo (anche dopo una configurazione nuova) ---
        if last_bl.elapsed() >= BACKLIGHT_POLL || full_redraw {
            last_bl = Instant::now();
            let new = backlight::bar_level(&cfg.display, screen_bl.as_ref().and_then(|b| b.fraction()));
            if new != level {
                level = new;
                // I pixel vanno riscritti con il nuovo livello (la luminosità si applica nella copia).
                full_redraw = true;
            }
        }

        // --- tempo: orologio, batteria, spostamento dei pixel ---
        let now = Local::now();
        if let Some(tick) = bar.layer().clock {
            let cur = (now.minute(), now.second());
            if (tick == ClockTick::Second && cur != last_clock) || cur.0 != last_clock.0 {
                bar.layer_mut().mark_all_dirty();
            }
            last_clock = cur;
        }
        if last_battery.elapsed() >= BATTERY_REFRESH {
            last_battery = Instant::now();
            let now_battery = bar::battery_state();
            if now_battery != battery_shown {
                battery_shown = now_battery;
                for b in bar.layer_mut().buttons.iter_mut().filter(|b| b.is_battery()) {
                    b.dirty = true;
                }
            }
        }
        if cfg.display.pixel_shift && last_shift.elapsed() >= PIXEL_SHIFT_EVERY {
            last_shift = Instant::now();
            shift_idx = (shift_idx + 1) % PIXEL_SHIFTS.len();
            full_redraw = true;
        }
        let shift = if cfg.display.pixel_shift { PIXEL_SHIFTS[shift_idx] } else { (0.0, 0.0) };

        // --- disegno ---
        let fresh = mirror.as_ref().filter(|(t, _)| t.elapsed() < Duration::from_secs(2)).map(|(_, s)| s);
        let damage = if mode == Mode::Screensaver && fresh.is_some() {
            if mirror_new || full_redraw {
                let src = fresh.unwrap();
                let c = Context::new(&surface)?;
                c.scale(w as f64 / src.width() as f64, h as f64 / src.height() as f64);
                c.set_source_surface(src, 0.0, 0.0)?;
                c.paint()?;
                vec![Rect { x: 0.0, y: 0.0, w: w as f64, h: h as f64 }]
            } else {
                Vec::new()
            }
        } else if mode.blank() {
            if full_redraw {
                let c = Context::new(&surface)?;
                c.set_source_rgb(0.0, 0.0, 0.0);
                c.paint()?;
                vec![Rect { x: 0.0, y: 0.0, w: w as f64, h: h as f64 }]
            } else {
                Vec::new()
            }
        } else {
            let c = Context::new(&surface)?;
            bar.draw(&c, &draw_opts(&cfg, &theme, shift, session.media.as_ref()), full_redraw)
        };
        full_redraw = false;
        mirror_new = false;
        if want_screenshot {
            want_screenshot = false;
            surface.flush();
            let mut png = Vec::new();
            if surface.write_to_png(&mut png).is_ok() {
                if let Some(srv) = &mut server {
                    use base64::Engine as _;
                    let png = base64::engine::general_purpose::STANDARD.encode(png);
                    srv.send(&protocol::ToAgent::Screenshot { png });
                }
            }
        }
        if !damage.is_empty() {
            surface.flush();
            let data = surface.data().map_err(|e| anyhow!("{e}"))?;
            disp.present(&data, stride, &damage, level)?;
        }

        // --- attesa ---
        let timeout = if fade.is_some() || want_screenshot {
            FRAME
        } else {
            let mut t = BATTERY_REFRESH.saturating_sub(last_battery.elapsed());
            if let Some(tick) = bar.layer().clock {
                let ms = now.timestamp_subsec_millis() as u64;
                let to_next = match tick {
                    ClockTick::Second => 1000 - ms,
                    ClockTick::Minute => (60 - now.second() as u64) * 1000 - ms,
                };
                t = t.min(Duration::from_millis(to_next + 5));
            }
            if cfg.display.pixel_shift {
                t = t.min(PIXEL_SHIFT_EVERY.saturating_sub(last_shift.elapsed()));
            }
            if cfg.display.follow_screen && screen_bl.is_some() {
                t = t.min(BACKLIGHT_POLL);
            }
            // Cartella del tema ancora assente (sessione non avviata): si ricontrolla ogni tanto.
            if !theme_watch.is_armed() || !cfg_watch.is_armed() {
                t = t.min(Duration::from_secs(5));
            }
            t
        };
        let mut events = [EpollEvent::empty(); 8];
        let ms = timeout.as_millis().clamp(1, u16::MAX as u128) as u16;
        match epoll.wait(&mut events, EpollTimeout::from(ms)) {
            Ok(_) | Err(nix::errno::Errno::EINTR) => {}
            Err(e) => return Err(anyhow!(e).context("epoll")),
        }

        // --- agente della sessione ---
        if let Some(srv) = &mut server {
            if srv.accept() {
                if let Some(fd) = srv.client_fd() {
                    // Il client precedente (se c'era) è già chiuso: epoll lo ha tolto da solo.
                    let _ = epoll.add(fd, EpollEvent::new(EpollFlags::EPOLLIN, 5));
                }
            }
            for msg in srv.read() {
                let new = match msg {
                    Incoming::State(s) => s,
                    Incoming::Frame { w: fw, h: fh, rgb } => {
                        if let Some(surf) = rgb_surface(fw, fh, &rgb) {
                            mirror = Some((Instant::now(), surf));
                            mirror_new = true;
                        }
                        continue;
                    }
                    Incoming::ScreenshotRequest => {
                        want_screenshot = true;
                        continue;
                    }
                    // Senza agente la barra torna normale: meglio che restare nera o bloccata per sempre.
                    Incoming::Disconnected => SessionState::default(),
                };
                if new.media != session.media {
                    bar.mark_media_dirty();
                }
                let new_mode = Mode::of(&new);
                if new_mode != mode {
                    eprintln!("omabar: {:?} → {:?}", mode, new_mode);
                    release_all(&mut bar, &keys, &mut touches);
                    bar.locked = new_mode == Mode::Locked;
                    bar.layer_mut().mark_all_dirty();
                    mode = new_mode;
                    full_redraw = true;
                }
                session = new;
            }
        }

        // --- ingressi ---
        touch.dispatch()?;
        keyboard.dispatch()?;
        for ev in keyboard.by_ref() {
            if let Event::Keyboard(KeyboardEvent::Key(k)) = &ev {
                if k.key() == Key::Fn as u32 && bar.layers.len() > 1 && mode == Mode::Normal {
                    let want = if k.key_state() == KeyState::Pressed { 1 } else { 0 };
                    if bar.active != want {
                        release_all(&mut bar, &keys, &mut touches);
                        bar.active = want;
                        bar.layer_mut().mark_all_dirty();
                        full_redraw = true;
                    }
                }
            }
        }
        for ev in touch.by_ref() {
            match ev {
                Event::Device(DeviceEvent::Added(a)) => {
                    let dev = a.device();
                    if dev.name().contains("iBridge Touchpad") || dev.name().contains("Touch Bar") {
                        eprintln!("omabar: sensore {}", dev.name());
                        digitizer = Some(dev);
                    }
                }
                Event::Touch(te) => {
                    // A barra spenta il tocco non fa niente; a sessione bloccata non si inviano tasti.
                    if Some(te.device()) != digitizer || mode != Mode::Normal {
                        continue;
                    }
                    let (bw, bh) = (bar.width, bar.height);
                    match te {
                        TouchEvent::Down(d) => {
                            let (x, y) = (d.x_transformed(w), d.y_transformed(h));
                            if let Some(i) = bar.layer().hit(x, y, bw, bh) {
                                let layer = bar.active;
                                let b = &mut bar.layers[layer].buttons[i];
                                b.pressed = true;
                                b.dirty = true;
                                keys.set(&b.keys, true);
                                touches.insert(d.seat_slot(), (layer, i));
                            }
                        }
                        TouchEvent::Motion(m) => {
                            let Some(&(layer, i)) = touches.get(&m.seat_slot()) else { continue };
                            let (x, y) = (m.x_transformed(w), m.y_transformed(h));
                            let inside = layer == bar.active && bar.layers[layer].hit(x, y, bw, bh) == Some(i);
                            let b = &mut bar.layers[layer].buttons[i];
                            if b.pressed != inside {
                                b.pressed = inside;
                                b.dirty = true;
                                keys.set(&b.keys, inside);
                            }
                        }
                        TouchEvent::Up(u) => {
                            if let Some((layer, i)) = touches.remove(&u.seat_slot()) {
                                let b = &mut bar.layers[layer].buttons[i];
                                if b.pressed {
                                    b.pressed = false;
                                    b.dirty = true;
                                    keys.set(&b.keys, false);
                                }
                            }
                        }
                        TouchEvent::Cancel(_) => release_all(&mut bar, &keys, &mut touches),
                        _ => {}
                    }
                }
                _ => {}
            }
        }
    }
}

/// RGB compatto → superficie cairo (RGB24 = 0x00RRGGBB per pixel, in ordine nativo).
fn release_all(bar: &mut Bar, keys: &VirtualKeys, touches: &mut HashMap<u32, (usize, usize)>) {
    for (_, (layer, i)) in touches.drain() {
        if let Some(b) = bar.layers.get_mut(layer).and_then(|l| l.buttons.get_mut(i)) {
            if b.pressed {
                b.pressed = false;
                b.dirty = true;
                keys.set(&b.keys, false);
            }
        }
    }
}
