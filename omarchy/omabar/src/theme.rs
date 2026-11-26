//! Colori della barra. Arrivano dal tema del sistema: la sessione utente copia il colors.toml del tema attivo
//! (schema di Omarchy: accent, background, foreground, ...) in /run/omabar/theme.toml. Senza file: colori neutri.

use anyhow::{anyhow, Result};
use cairo::Context;
use std::collections::HashMap;

#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Rgb {
    pub r: f64,
    pub g: f64,
    pub b: f64,
}

impl Rgb {
    pub const fn gray(v: f64) -> Rgb {
        Rgb { r: v, g: v, b: v }
    }

    /// "#rrggbb" oppure "rrggbb".
    pub fn hex(s: &str) -> Option<Rgb> {
        let s = s.trim();
        let h = s.strip_prefix('#').unwrap_or(s);
        if h.len() != 6 || !h.chars().all(|c| c.is_ascii_hexdigit()) {
            return None;
        }
        let v = u32::from_str_radix(h, 16).ok()?;
        let ch = |shift: u32| ((v >> shift) & 0xff) as f64 / 255.0;
        Some(Rgb { r: ch(16), g: ch(8), b: ch(0) })
    }

    pub fn mix(self, other: Rgb, t: f64) -> Rgb {
        let l = |a: f64, b: f64| a + (b - a) * t;
        Rgb { r: l(self.r, other.r), g: l(self.g, other.g), b: l(self.b, other.b) }
    }

    /// Luminanza relativa (WCAG 2).
    pub fn luminance(self) -> f64 {
        let lin = |c: f64| if c <= 0.04045 { c / 12.92 } else { ((c + 0.055) / 1.055).powf(2.4) };
        0.2126 * lin(self.r) + 0.7152 * lin(self.g) + 0.0722 * lin(self.b)
    }

    pub fn contrast(self, other: Rgb) -> f64 {
        let (a, b) = (self.luminance(), other.luminance());
        (a.max(b) + 0.05) / (a.min(b) + 0.05)
    }

    pub fn set(self, c: &Context) {
        c.set_source_rgb(self.r, self.g, self.b);
    }
}

#[derive(Clone, Debug, PartialEq)]
pub struct Theme {
    pub name: String,
    /// Fondo della barra.
    pub bar: Rgb,
    /// Tasto a riposo.
    pub button: Rgb,
    /// Tasto premuto.
    pub pressed: Rgb,
    /// Etichette e icone, a riposo e sul tasto premuto.
    pub text: Rgb,
    pub text_pressed: Rgb,
    pub accent: Rgb,
    /// Batteria in carica / quasi scarica.
    pub good: Rgb,
    pub warn: Rgb,
}

impl Default for Theme {
    fn default() -> Theme {
        Theme {
            name: "neutro".into(),
            bar: Rgb::gray(0.0),
            button: Rgb::gray(0.2),
            pressed: Rgb::gray(0.45),
            text: Rgb::gray(1.0),
            text_pressed: Rgb::gray(1.0),
            accent: Rgb::gray(0.85),
            good: Rgb { r: 0.30, g: 0.78, b: 0.40 },
            warn: Rgb { r: 0.92, g: 0.27, b: 0.27 },
        }
    }
}

impl Theme {
    /// Legge un colors.toml nello schema di Omarchy. Serve almeno background e foreground; il resto ha ripieghi.
    /// Una chiave `name` facoltativa (aggiunta da omabar-theme-sync) dà il nome del tema.
    pub fn from_colors_toml(text: &str) -> Result<Theme> {
        let table: HashMap<String, toml::Value> = toml::from_str(text)?;
        let get = |k: &str| table.get(k).and_then(|v| v.as_str()).and_then(Rgb::hex);
        let background = get("background").ok_or_else(|| anyhow!("manca background"))?;
        let foreground = get("foreground").ok_or_else(|| anyhow!("manca foreground"))?;
        let bar = get("darker_background").or_else(|| get("dark_background")).unwrap_or(background);
        let accent = get("accent").or_else(|| get("blue")).unwrap_or(foreground);

        let mut button = get("lighter_background")
            .or_else(|| get("selection"))
            .unwrap_or_else(|| background.mix(foreground, 0.15));
        // Alcuni temi hanno lighter_background quasi uguale al fondo: il tasto sparirebbe.
        if button.contrast(bar) < 1.15 {
            button = bar.mix(foreground, 0.14);
        }
        // Sul tasto premuto (accent) il testo prende il colore che contrasta di più.
        let text_pressed = if accent.contrast(bar) >= accent.contrast(foreground) { bar } else { foreground };

        let defaults = Theme::default();
        Ok(Theme {
            name: table
                .get("name")
                .and_then(|v| v.as_str())
                .unwrap_or("senza nome")
                .to_string(),
            bar,
            button,
            pressed: accent,
            text: foreground,
            text_pressed,
            accent,
            good: get("green").unwrap_or(defaults.good),
            warn: get("red").unwrap_or(defaults.warn),
        })
    }

    /// Fondo nero al posto di quello del tema (opzione theme.bar = "black").
    pub fn with_black_bar(mut self) -> Theme {
        self.bar = Rgb::gray(0.0);
        self
    }

    /// Tema intermedio per la dissolvenza: t = 0 → self, t = 1 → other.
    pub fn mix(&self, other: &Theme, t: f64) -> Theme {
        Theme {
            name: other.name.clone(),
            bar: self.bar.mix(other.bar, t),
            button: self.button.mix(other.button, t),
            pressed: self.pressed.mix(other.pressed, t),
            text: self.text.mix(other.text, t),
            text_pressed: self.text_pressed.mix(other.text_pressed, t),
            accent: self.accent.mix(other.accent, t),
            good: self.good.mix(other.good, t),
            warn: self.warn.mix(other.warn, t),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_omarchy_colors() {
        let t = Theme::from_colors_toml(
            "name = \"Prova\"\nmode = \"dark\"\naccent = \"#4fc3f7\"\nbackground = \"#0d1220\"\n\
             darker_background = \"#060912\"\nlighter_background = \"#172238\"\nforeground = \"#dce6f5\"\n\
             green = \"#7fdba0\"\nred = \"#ff5370\"",
        )
        .unwrap();
        assert_eq!(t.name, "Prova");
        assert_eq!(t.bar, Rgb::hex("#060912").unwrap());
        assert_eq!(t.pressed, Rgb::hex("#4fc3f7").unwrap());
        // accent chiaro: testo scuro sopra
        assert_eq!(t.text_pressed, t.bar);
    }

    #[test]
    fn rejects_incomplete() {
        assert!(Theme::from_colors_toml("accent = \"#ffffff\"").is_err());
    }

    #[test]
    fn invisible_buttons_get_contrast() {
        let t = Theme::from_colors_toml(
            "background = \"#000000\"\nlighter_background = \"#010101\"\nforeground = \"#ffffff\"",
        )
        .unwrap();
        assert!(t.button.contrast(t.bar) >= 1.15);
    }
}
