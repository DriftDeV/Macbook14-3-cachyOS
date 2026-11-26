//! Testo con Pango invece dell'API "giocattolo" di cairo: Pango cerca da solo, glifo per glifo, un carattere che
//! li abbia (giapponese, cinese, coreano, emoji…), mentre select_font_face usa un solo carattere e mostra
//! quadratini vuoti per quello che non contiene.

use cairo::Context;
use pango::{EllipsizeMode, FontDescription, Layout, Weight, SCALE};

#[derive(Clone, Copy, Debug)]
pub struct Font<'a> {
    pub family: &'a str,
    /// Dimensione in pixel (come set_font_size di cairo).
    pub size: f64,
    pub bold: bool,
}

impl<'a> Font<'a> {
    pub fn sized(self, size: f64) -> Font<'a> {
        Font { size, ..self }
    }
    pub fn regular(self) -> Font<'a> {
        Font { bold: false, ..self }
    }
}

pub fn layout(c: &Context, text: &str, f: Font) -> Layout {
    let l = pangocairo::functions::create_layout(c);
    let mut d = FontDescription::new();
    d.set_family(f.family);
    d.set_absolute_size(f.size * SCALE as f64);
    d.set_weight(if f.bold { Weight::Bold } else { Weight::Normal });
    l.set_font_description(Some(&d));
    l.set_single_paragraph_mode(true);
    l.set_text(text);
    l
}

/// Come layout, ma tagliato con "…" alla fine se supera `max` pixel.
pub fn fitted(c: &Context, text: &str, f: Font, max: f64) -> Layout {
    let l = layout(c, text, f);
    l.set_width((max.max(0.0) * SCALE as f64) as i32);
    l.set_ellipsize(EllipsizeMode::End);
    l
}

/// Larghezza logica (avanzamento) in pixel.
pub fn width(l: &Layout) -> f64 {
    l.pixel_extents().1.width() as f64
}

/// Disegna con la linea di base in `baseline`.
pub fn show_at_baseline(c: &Context, l: &Layout, x: f64, baseline: f64) {
    c.move_to(x, baseline - l.baseline() as f64 / SCALE as f64);
    pangocairo::functions::show_layout(c, l);
}

/// Centra sulla scatola dell'inchiostro, così le minuscole non sembrano basse.
pub fn centered(c: &Context, l: &Layout, x: f64, y: f64, w: f64, h: f64) {
    let (ink, _) = l.pixel_extents();
    c.move_to(
        (x + (w - ink.width() as f64) / 2.0 - ink.x() as f64).round(),
        (y + (h - ink.height() as f64) / 2.0 - ink.y() as f64).round(),
    );
    pangocairo::functions::show_layout(c, l);
}
