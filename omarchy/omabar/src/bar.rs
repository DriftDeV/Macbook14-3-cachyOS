//! Disposizione e disegno dei tasti, in coordinate "orizzontali" (2170×60 sul 14,3). La rotazione verso il
//! framebuffer verticale la fa display.rs.

use crate::config::{ButtonCfg, Config, LayerCfg};
use crate::protocol::Media;
use crate::theme::Theme;
use base64::Engine as _;
use crate::text::{self, Font};
use cairo::{Context, Format, ImageSurface};
use chrono::{Local, Locale};
use input_linux::Key;
use librsvg_rebind::{prelude::HandleExt, Handle, Rectangle};
use std::{f64::consts::PI, fs, path::Path};

/// Nessun margine: i tasti arrivano ai bordi della barra.
const PAD_X: f64 = 0.0;
const SPACING: f64 = 12.0;
const PAD_Y: f64 = 0.0;
const RADIUS: f64 = 9.0;
/// Separatore tra gruppi (gap = true): spazio fisso al posto della spaziatura normale.
const GAP: f64 = 34.0;
const ICON_SIZE: f64 = 36.0;

#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Rect {
    pub x: f64,
    pub y: f64,
    pub w: f64,
    pub h: f64,
}

enum Face {
    Spacer,
    Label(String),
    Icon(Handle, f64),
    /// Icona non trovata: si mostra il nome, così l'errore si vede sulla barra.
    MissingIcon(String),
    Clock(String, Locale),
    Battery,
    /// Brano del lettore MPRIS scelto dall'agente.
    Media,
}

pub struct Button {
    face: Face,
    /// Icona alternativa mentre un lettore suona (icon_playing, per esempio pausa al posto di play).
    playing_icon: Option<Handle>,
    pub keys: Vec<Key>,
    /// Larghezza in posti; 0 per un separatore.
    width: f64,
    gap: bool,
    pub pressed: bool,
    pub dirty: bool,
}

impl Button {
    fn new(cfg: &ButtonCfg) -> Button {
        let face = if let Some(l) = &cfg.label {
            Face::Label(l.clone())
        } else if let Some(name) = &cfg.icon {
            match load_icon(name) {
                Some(h) => Face::Icon(h, cfg.icon_size.unwrap_or(ICON_SIZE)),
                None => {
                    eprintln!("omabar: icona {name} non trovata");
                    Face::MissingIcon(name.clone())
                }
            }
        } else if let Some(fmt) = &cfg.clock {
            Face::Clock(fmt.clone(), system_locale())
        } else if cfg.battery {
            Face::Battery
        } else if cfg.media {
            Face::Media
        } else {
            Face::Spacer
        };
        let playing_icon = cfg.icon_playing.as_deref().and_then(|n| {
            let h = load_icon(n);
            if h.is_none() {
                eprintln!("omabar: icona {n} non trovata");
            }
            h
        });
        Button {
            face,
            playing_icon,
            keys: cfg.keys.clone(),
            width: if cfg.gap { 0.0 } else { cfg.width.unwrap_or(1.0) },
            gap: cfg.gap,
            pressed: false,
            dirty: true,
        }
    }

    /// Spazio vuoto o separatore: niente sfondo, niente tocco.
    pub fn is_spacer(&self) -> bool {
        matches!(self.face, Face::Spacer)
    }
    pub fn is_battery(&self) -> bool {
        matches!(self.face, Face::Battery)
    }
    /// Il disegno dipende dal lettore multimediale.
    pub fn shows_media(&self) -> bool {
        matches!(self.face, Face::Media) || self.playing_icon.is_some()
    }
}

pub struct Layer {
    pub buttons: Vec<Button>,
    /// Un orologio con i secondi chiede un ridisegno al secondo, altrimenti al minuto.
    pub clock: Option<ClockTick>,
}

#[derive(Clone, Copy, Debug, PartialEq)]
pub enum ClockTick {
    Second,
    Minute,
}

impl Layer {
    fn new(cfg: &LayerCfg) -> Layer {
        let buttons: Vec<Button> = cfg.buttons.iter().map(Button::new).collect();
        let clock = buttons
            .iter()
            .filter_map(|b| match &b.face {
                Face::Clock(f, _) if f.contains("%S") || f.contains("%T") || f.contains("%r") => Some(ClockTick::Second),
                Face::Clock(..) => Some(ClockTick::Minute),
                _ => None,
            })
            .max_by_key(|t| (*t == ClockTick::Second) as u8);
        Layer { buttons, clock }
    }

    /// Posizione e larghezza di ogni elemento su una barra larga `w`. I tasti si dividono lo spazio in proporzione
    /// alla loro larghezza; tra due tasti c'è SPACING, un separatore occupa GAP al posto della spaziatura.
    fn layout(&self, w: f64) -> Vec<(f64, f64)> {
        let n = self.buttons.len();
        let units: f64 = self.buttons.iter().map(|b| b.width).sum();
        // Spaziatura tra elementi vicini: nessuna attorno a un separatore (il separatore è già lo spazio).
        let joints = (1..n).filter(|&i| !self.buttons[i - 1].gap && !self.buttons[i].gap).count() as f64;
        let gaps = self.buttons.iter().filter(|b| b.gap).count() as f64;
        // Un tasto largo k posti ingloba k-1 spaziature, così i bordi restano allineati alla griglia.
        let inner: f64 = self.buttons.iter().map(|b| (b.width - 1.0).max(0.0)).sum();
        let unit = ((w - 2.0 * PAD_X - SPACING * (joints + inner) - GAP * gaps) / units.max(1.0)).max(1.0);
        let mut out = Vec::with_capacity(n);
        let mut x = PAD_X;
        for (i, b) in self.buttons.iter().enumerate() {
            if i > 0 && !b.gap && !self.buttons[i - 1].gap {
                x += SPACING;
            }
            let bw = if b.gap { GAP } else { b.width * unit + (b.width - 1.0).max(0.0) * SPACING };
            out.push((x, bw));
            x += bw;
        }
        out
    }

    pub fn rect(&self, i: usize, w: f64, h: f64, shift: (f64, f64)) -> Rect {
        let (x, bw) = self.layout(w)[i];
        Rect { x: (x + shift.0).round(), y: PAD_Y + shift.1, w: bw.round(), h: h - 2.0 * PAD_Y }
    }

    /// Tasto (non vuoto) sotto il punto, senza spostamento dei pixel: il tocco è sul vetro, non sul disegno.
    pub fn hit(&self, x: f64, y: f64, w: f64, h: f64) -> Option<usize> {
        (0..self.buttons.len()).find(|&i| {
            let r = self.rect(i, w, h, (0.0, 0.0));
            // Fuori dai margini verticali il dito è comunque sul tasto: si allarga il bersaglio.
            !self.buttons[i].is_spacer() && x >= r.x - SPACING / 2.0 && x <= r.x + r.w + SPACING / 2.0 && y >= 0.0 && y <= h
        })
    }

    pub fn mark_all_dirty(&mut self) {
        for b in &mut self.buttons {
            b.dirty = true;
        }
    }
}

pub struct Bar {
    pub layers: Vec<Layer>,
    /// Livello mostrato a sessione bloccata (sezione [lock]): non invia tasti.
    pub lock: Layer,
    pub locked: bool,
    pub active: usize,
    pub width: f64,
    pub height: f64,
}

pub struct DrawOpts<'a> {
    pub theme: &'a Theme,
    pub outlines: bool,
    pub font: &'a str,
    pub font_size: f64,
    pub shift: (f64, f64),
    pub media: Option<&'a Media>,
}

impl Bar {
    pub fn new(cfg: &Config, width: f64, height: f64) -> Bar {
        Bar {
            layers: cfg.layers.iter().map(Layer::new).collect(),
            lock: Layer::new(&cfg.lock),
            locked: false,
            active: 0,
            width,
            height,
        }
    }

    pub fn layer(&self) -> &Layer {
        if self.locked {
            &self.lock
        } else {
            &self.layers[self.active]
        }
    }
    pub fn layer_mut(&mut self) -> &mut Layer {
        if self.locked {
            &mut self.lock
        } else {
            &mut self.layers[self.active]
        }
    }

    pub fn mark_media_dirty(&mut self) {
        for l in self.layers.iter_mut().chain(std::iter::once(&mut self.lock)) {
            for b in l.buttons.iter_mut().filter(|b| b.shows_media()) {
                b.dirty = true;
            }
        }
    }

    /// Disegna la barra. Con `full` ridisegna tutto, altrimenti solo i tasti segnati come cambiati.
    /// Restituisce le zone toccate (vuoto se niente da mostrare).
    pub fn draw(&mut self, c: &Context, o: &DrawOpts, full: bool) -> Vec<Rect> {
        let (w, h) = (self.width, self.height);
        let mut damage = Vec::new();
        if full {
            o.theme.bar.set(c);
            c.paint().ok();
            damage.push(Rect { x: 0.0, y: 0.0, w, h });
        }
        let layer = if self.locked { &mut self.lock } else { &mut self.layers[self.active] };
        for i in 0..layer.buttons.len() {
            if !full && !layer.buttons[i].dirty {
                continue;
            }
            // Sfondi fermi e attaccati ai bordi; lo spostamento contro il burn-in vale per icone e testo.
            let r = layer.rect(i, w, h, (0.0, 0.0));
            let face_r = Rect { x: r.x + o.shift.0, y: r.y + o.shift.1, ..r };
            let b = &mut layer.buttons[i];
            b.dirty = false;
            if !full {
                // Ripulisce la zona del tasto (anche il bordo arrotondato) prima di ridisegnarlo.
                let clear = Rect { x: r.x - 1.0, y: 0.0, w: r.w + 2.0, h };
                o.theme.bar.set(c);
                c.rectangle(clear.x, clear.y, clear.w, clear.h);
                c.fill().ok();
                damage.push(clear);
            }
            if b.is_spacer() {
                continue;
            }
            let fill = if b.pressed {
                Some(o.theme.pressed)
            } else if o.outlines {
                Some(o.theme.button)
            } else {
                None
            };
            if let Some(fill) = fill {
                rounded_rect(c, r, RADIUS);
                fill.set(c);
                c.fill().ok();
            }
            let fg = if b.pressed { o.theme.text_pressed } else { o.theme.text };
            let playing = o.media.is_some_and(|m| m.playing);
            match (&b.playing_icon, &b.face) {
                (Some(alt), Face::Icon(_, size)) if playing => draw_face(c, &Face::Icon(alt.clone(), *size), face_r, o, fg),
                _ => draw_face(c, &b.face, face_r, o, fg),
            }
        }
        damage
    }
}

fn rounded_rect(c: &Context, r: Rect, rad: f64) {
    c.new_sub_path();
    c.arc(r.x + r.w - rad, r.y + rad, rad, -PI / 2.0, 0.0);
    c.arc(r.x + r.w - rad, r.y + r.h - rad, rad, 0.0, PI / 2.0);
    c.arc(r.x + rad, r.y + r.h - rad, rad, PI / 2.0, PI);
    c.arc(r.x + rad, r.y + rad, rad, PI, 1.5 * PI);
    c.close_path();
}

impl DrawOpts<'_> {
    /// Carattere dei tasti: quello della configurazione, in grassetto.
    fn font(&self) -> Font<'_> {
        Font { family: self.font, size: self.font_size, bold: true }
    }
}

fn centered_text(c: &Context, r: Rect, text: &str, f: Font) {
    text::centered(c, &text::layout(c, text, f), r.x, r.y, r.w, r.h);
}

fn draw_face(c: &Context, face: &Face, r: Rect, o: &DrawOpts, fg: crate::theme::Rgb) {
    fg.set(c);
    match face {
        Face::Spacer => {}
        Face::Label(t) => centered_text(c, r, t, o.font()),
        Face::MissingIcon(name) => centered_text(c, r, name, o.font().sized(12.0)),
        Face::Clock(fmt, loc) => centered_text(c, r, &Local::now().format_localized(fmt, *loc).to_string(), o.font()),
        Face::Icon(handle, size) => {
            let x = (r.x + (r.w - size) / 2.0).round();
            let y = (r.y + (r.h - size) / 2.0).round();
            // Le icone simboliche si usano come maschera: prendono il colore del tema.
            c.push_group();
            handle.render_document(c, &Rectangle::new(x, y, *size, *size)).ok();
            if let Ok(pattern) = c.pop_group() {
                fg.set(c);
                c.mask(&pattern).ok();
            }
        }
        Face::Battery => draw_battery(c, r, o.theme, fg, o.font()),
        Face::Media => draw_media(c, r, o, fg),
    }
}

/// Spazio tra la copertina e il titolo.
const ART_GAP: f64 = 12.0;

/// Copertina (quadratino con gli angoli arrotondati, se l'agente l'ha mandata), titolo (grassetto) e artista,
/// ridotti con "…" se non entrano; niente se nessun lettore è attivo.
fn draw_media(c: &Context, r: Rect, o: &DrawOpts, fg: crate::theme::Rgb) {
    let Some(m) = o.media else { return };
    let inner = Rect { x: r.x + 14.0, w: r.w - 28.0, ..r };
    c.save().ok();
    c.rectangle(inner.x, r.y, inner.w, r.h);
    c.clip();
    // La copertina solo se resta spazio per almeno qualche lettera del titolo.
    let side = crate::protocol::ART as f64;
    let art = art_surface(&m.art).filter(|_| inner.w > side + ART_GAP + 80.0 && r.h >= side);
    let art_w = if art.is_some() { side + ART_GAP } else { 0.0 };
    let text_w = inner.w - art_w;
    let title = if m.title.is_empty() { m.player.as_str() } else { m.title.as_str() };
    let size = o.font_size * 0.8;
    let font = o.font().sized(size);
    let title = text::fitted(c, title, font, text_w);
    let title_w = text::width(&title);
    let artist = (!m.artist.is_empty() && text_w - title_w > 60.0)
        .then(|| text::fitted(c, &format!("  ·  {}", m.artist), font.regular(), text_w - title_w));
    let artist_w = artist.as_ref().map(text::width).unwrap_or(0.0);
    // Copertina + riga centrate nel tasto; la linea di base viene dall'altezza del carattere, non dal testo (stabile
    // tra brani).
    let x0 = (inner.x + (inner.w - art_w - title_w - artist_w) / 2.0).round();
    if let Some(surf) = &art {
        let ay = (r.y + (r.h - side) / 2.0).round();
        c.save().ok();
        rounded_rect(c, Rect { x: x0, y: ay, w: side, h: side }, 6.0);
        c.clip();
        c.set_source_surface(surf, x0, ay).ok();
        c.paint().ok();
        c.restore().ok();
    }
    let x = x0 + art_w;
    let y = (r.y + r.h / 2.0 + size * 0.36).round();
    fg.set(c);
    text::show_at_baseline(c, &title, x, y);
    if let Some(artist) = &artist {
        fg.mix(o.theme.button, 0.35).set(c);
        text::show_at_baseline(c, artist, x + title_w, y);
    }
    c.restore().ok();
}

/// Copertina dal base64 dell'agente; None se vuota o della dimensione sbagliata.
fn art_surface(b64: &str) -> Option<ImageSurface> {
    if b64.is_empty() {
        return None;
    }
    let rgb = base64::engine::general_purpose::STANDARD.decode(b64).ok()?;
    let side = crate::protocol::ART;
    (rgb.len() == (side * side * 3) as usize).then(|| rgb_surface(side, side, &rgb)).flatten()
}

/// Superficie cairo da pixel RGB compatti (w×h×3 byte).
pub fn rgb_surface(w: u32, h: u32, rgb: &[u8]) -> Option<ImageSurface> {
    let mut surf = ImageSurface::create(Format::Rgb24, w as i32, h as i32).ok()?;
    let stride = surf.stride() as usize;
    {
        let mut data = surf.data().ok()?;
        for y in 0..h as usize {
            for x in 0..w as usize {
                let s = (y * w as usize + x) * 3;
                let px = u32::from_be_bytes([0, rgb[s], rgb[s + 1], rgb[s + 2]]).to_ne_bytes();
                data[y * stride + x * 4..y * stride + x * 4 + 4].copy_from_slice(&px);
            }
        }
    }
    surf.mark_dirty();
    Some(surf)
}

#[derive(Clone, Copy, Debug, PartialEq)]
pub struct BatteryState {
    pub percent: u32,
    /// Alimentatore collegato (si mostra "in carica" anche a batteria piena o ferma alla soglia).
    pub charging: bool,
}

/// Percentuale della batteria e alimentatore. "In carica" viene da `online` dell'alimentatore (Mains/USB), non da
/// `status` della batteria: sul 14,3 con il cavo collegato `status` salta tra Charging e Discharging ogni secondo
/// (26/11/2026). Solo senza alimentatori in sysfs si usa `status`.
pub fn battery_state() -> Option<BatteryState> {
    let mut battery: Option<(u32, String)> = None;
    let mut adapter: Option<bool> = None;
    for e in fs::read_dir("/sys/class/power_supply").ok()?.flatten() {
        let p = e.path();
        let read = |f: &str| fs::read_to_string(p.join(f)).map(|s| s.trim().to_string()).ok();
        if read("scope").as_deref() == Some("Device") {
            continue; // batterie di mouse, cuffie, ...
        }
        match read("type").as_deref() {
            Some("Battery") if battery.is_none() => {
                if let Some(percent) = read("capacity").and_then(|c| c.parse().ok()) {
                    battery = Some((percent, read("status").unwrap_or_default()));
                }
            }
            Some("Mains") | Some("USB") => {
                let online = read("online").as_deref() == Some("1");
                adapter = Some(adapter.unwrap_or(false) || online);
            }
            _ => {}
        }
    }
    let (percent, status) = battery?;
    let charging = adapter.unwrap_or(status == "Charging" || status == "Full");
    Some(BatteryState { percent, charging })
}

/// Batteria disegnata con cairo: corpo, polo, livello (verde in carica, rosso sotto il 15 %) e percentuale.
fn draw_battery(c: &Context, r: Rect, theme: &Theme, fg: crate::theme::Rgb, font: Font) {
    let Some(st) = battery_state() else {
        centered_text(c, r, "—", font);
        return;
    };
    let text = format!("{}%", st.percent);
    let label = text::layout(c, &text, font);
    let text_w = text::width(&label);
    let (bw, bh, tip, gap) = (46.0, 22.0, 4.0, 10.0);
    let total = bw + tip + gap + text_w;
    let x0 = (r.x + (r.w - total) / 2.0).round();
    let y0 = (r.y + (r.h - bh) / 2.0).round();

    fg.set(c);
    c.set_line_width(2.5);
    rounded_rect(c, Rect { x: x0 + 1.25, y: y0 + 1.25, w: bw - 2.5, h: bh - 2.5 }, 4.0);
    c.stroke().ok();
    c.rectangle(x0 + bw, y0 + bh * 0.3, tip, bh * 0.4);
    c.fill().ok();

    let level = if st.charging {
        theme.good
    } else if st.percent <= 15 {
        theme.warn
    } else {
        fg
    };
    let inner = bw - 9.0;
    let fill_w = (inner * st.percent.min(100) as f64 / 100.0).max(2.0);
    level.set(c);
    rounded_rect(c, Rect { x: x0 + 4.5, y: y0 + 4.5, w: fill_w, h: bh - 9.0 }, 2.0);
    c.fill().ok();

    if st.charging {
        // Fulmine al centro del corpo, con il contorno del colore del fondo per staccarsi dal livello.
        let (cx, cy) = (x0 + bw / 2.0, y0 + bh / 2.0);
        c.new_path();
        for (i, (dx, dy)) in [(2.0, -9.0), (-6.0, 1.5), (-0.5, 1.5), (-2.0, 9.0), (6.0, -1.5), (0.5, -1.5)].iter().enumerate() {
            if i == 0 {
                c.move_to(cx + dx, cy + dy);
            } else {
                c.line_to(cx + dx, cy + dy);
            }
        }
        c.close_path();
        theme.bar.set(c);
        c.set_line_width(2.0);
        c.stroke_preserve().ok();
        fg.set(c);
        c.fill().ok();
    }

    fg.set(c);
    let ink_w = label.pixel_extents().0.width() as f64;
    text::centered(c, &label, x0 + bw + tip + gap, r.y, ink_w, r.h);
}

/// Icona: percorso di un SVG, oppure nome cercato in /etc/omabar/icons, /usr/share/omabar/icons e tra le
/// icone simboliche di Adwaita.
fn load_icon(name: &str) -> Option<Handle> {
    let mut candidates = Vec::new();
    if name.contains('/') {
        candidates.push(Path::new(name).to_path_buf());
    } else {
        for dir in ["/etc/omabar/icons", "/usr/share/omabar/icons"] {
            candidates.push(Path::new(dir).join(format!("{name}.svg")));
        }
        if let Ok(rd) = fs::read_dir("/usr/share/icons/Adwaita/symbolic") {
            for e in rd.flatten() {
                candidates.push(e.path().join(format!("{name}.svg")));
            }
        }
    }
    candidates
        .into_iter()
        .filter(|p| p.is_file())
        .find_map(|p| Handle::from_file(p.to_str()?).ok())
}

/// Lingua per date e giorni: LC_ALL, LC_TIME o LANG dell'ambiente, altrimenti LANG di /etc/locale.conf (il servizio
/// di sistema parte senza ambiente della sessione).
fn system_locale() -> Locale {
    let from_env = ["LC_ALL", "LC_TIME", "LANG"].iter().find_map(|v| std::env::var(v).ok().filter(|s| !s.is_empty()));
    let raw = from_env.or_else(|| {
        fs::read_to_string("/etc/locale.conf").ok().and_then(|t| {
            t.lines()
                .filter_map(|l| l.strip_prefix("LC_TIME=").or_else(|| l.strip_prefix("LANG=")))
                .next()
                .map(|v| v.trim_matches('"').to_string())
        })
    });
    raw.as_deref()
        .map(|s| s.split(['.', '@']).next().unwrap_or(s))
        .and_then(|s| Locale::try_from(s).ok())
        .unwrap_or(Locale::POSIX)
}
