//! Configurazione: predefinita (compilata dentro, uguale a /usr/share/omabar/config.toml) più il file
//! dell'utente /etc/omabar/config.toml, le cui sezioni sostituiscono quelle predefinite.

use anyhow::{bail, Context as _, Result};
use input_linux::Key;
use serde::Deserialize;
use std::fs;

pub const DEFAULT_TOML: &str = include_str!("../config.toml");
pub const USER_DIR: &str = "/etc/omabar";
pub const USER_FILE: &str = "config.toml";

#[derive(Deserialize, Clone, Debug)]
#[serde(deny_unknown_fields)]
pub struct Config {
    #[serde(default)]
    pub display: Display,
    #[serde(default)]
    pub theme: ThemeCfg,
    #[serde(rename = "layer", default)]
    pub layers: Vec<LayerCfg>,
    /// Livello a sessione bloccata.
    #[serde(default = "default_lock")]
    pub lock: LayerCfg,
}

fn default_lock() -> LayerCfg {
    LayerCfg { name: "bloccato".into(), buttons: vec![ButtonCfg { clock: Some("%H:%M".into()), ..Default::default() }] }
}

#[derive(Deserialize, Clone, Debug)]
#[serde(deny_unknown_fields, default)]
pub struct Display {
    /// Luminosità massima della barra (1-255).
    pub brightness: u8,
    /// Minima, quando lo schermo è al minimo (con follow_screen).
    pub min_brightness: u8,
    /// La barra segue la luminosità dello schermo.
    pub follow_screen: bool,
    pub pixel_shift: bool,
    pub font: String,
    pub font_size: f64,
    pub fade_ms: u32,
}

impl Default for Display {
    fn default() -> Display {
        Display {
            brightness: 255,
            min_brightness: 40,
            follow_screen: true,
            pixel_shift: true,
            font: "sans-serif".into(),
            font_size: 26.0,
            fade_ms: 300,
        }
    }
}

#[derive(Deserialize, Clone, Copy, Debug, PartialEq)]
#[serde(rename_all = "lowercase")]
pub enum BarBackground {
    Theme,
    Black,
}

#[derive(Deserialize, Clone, Debug)]
#[serde(deny_unknown_fields, default)]
pub struct ThemeCfg {
    pub path: String,
    pub bar: BarBackground,
    pub outlines: bool,
}

impl Default for ThemeCfg {
    fn default() -> ThemeCfg {
        ThemeCfg {
            path: "/run/omabar/theme.toml".into(),
            bar: BarBackground::Theme,
            outlines: true,
        }
    }
}

#[derive(Deserialize, Clone, Debug)]
#[serde(deny_unknown_fields)]
pub struct LayerCfg {
    #[serde(default)]
    pub name: String,
    pub buttons: Vec<ButtonCfg>,
}

#[derive(Deserialize, Clone, Debug, Default)]
#[serde(deny_unknown_fields)]
pub struct ButtonCfg {
    pub label: Option<String>,
    pub icon: Option<String>,
    pub icon_size: Option<f64>,
    pub clock: Option<String>,
    #[serde(default)]
    pub battery: bool,
    #[serde(default)]
    pub media: bool,
    /// Icona da mostrare al posto di `icon` mentre un lettore suona.
    pub icon_playing: Option<String>,
    #[serde(default)]
    pub keys: Vec<Key>,
    /// Larghezza in posti (anche frazionaria, per esempio 1.5).
    pub width: Option<f64>,
    /// Separatore stretto tra gruppi di tasti (al posto di un posto vuoto).
    #[serde(default)]
    pub gap: bool,
}

/// Forma grezza del file dell'utente: solo le sezioni presenti.
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct UserFile {
    display: Option<Display>,
    theme: Option<ThemeCfg>,
    #[serde(rename = "layer")]
    layers: Option<Vec<LayerCfg>>,
    lock: Option<LayerCfg>,
}

impl Config {
    pub fn defaults() -> Config {
        toml::from_str(DEFAULT_TOML).expect("config.toml predefinito non valido")
    }

    /// Predefinita + file dell'utente. Un file dell'utente non valido viene segnalato e ignorato.
    pub fn load() -> Config {
        let mut cfg = Config::defaults();
        let path = format!("{USER_DIR}/{USER_FILE}");
        match fs::read_to_string(&path) {
            Ok(text) => match Config::merge(&mut cfg, &text) {
                Ok(()) => {}
                Err(e) => eprintln!("omabar: {path} ignorato: {e:#}"),
            },
            Err(e) if e.kind() == std::io::ErrorKind::NotFound => {}
            Err(e) => eprintln!("omabar: {path} non leggibile: {e}"),
        }
        cfg
    }

    /// Predefinita + il file indicato, con gli errori restituiti invece che ignorati (anteprima e controllo di
    /// MacBook Manager prima di salvare).
    pub fn load_file(path: &str) -> Result<Config> {
        let mut cfg = Config::defaults();
        let text = fs::read_to_string(path).with_context(|| format!("lettura di {path}"))?;
        Config::merge(&mut cfg, &text)?;
        Ok(cfg)
    }

    fn merge(cfg: &mut Config, text: &str) -> Result<()> {
        let user: UserFile = toml::from_str(text).context("TOML")?;
        let mut merged = cfg.clone();
        if let Some(d) = user.display {
            merged.display = d;
        }
        if let Some(t) = user.theme {
            merged.theme = t;
        }
        if let Some(l) = user.layers {
            merged.layers = l;
        }
        if let Some(l) = user.lock {
            merged.lock = l;
        }
        merged.validate()?;
        *cfg = merged;
        Ok(())
    }

    pub fn validate(&self) -> Result<()> {
        if self.layers.is_empty() {
            bail!("serve almeno un [[layer]]");
        }
        for (i, layer) in self.layers.iter().chain(std::iter::once(&self.lock)).enumerate() {
            if layer.buttons.is_empty() {
                bail!("il livello {} non ha tasti", i + 1);
            }
            for (j, b) in layer.buttons.iter().enumerate() {
                let faces = [b.label.is_some(), b.icon.is_some(), b.clock.is_some(), b.battery, b.media]
                    .iter()
                    .filter(|x| **x)
                    .count();
                if faces > 1 {
                    bail!("livello {}, tasto {}: una sola tra label, icon, clock, battery, media", i + 1, j + 1);
                }
                if b.icon_playing.is_some() && b.icon.is_none() {
                    bail!("livello {}, tasto {}: icon_playing vuole anche icon", i + 1, j + 1);
                }
                if b.width.is_some_and(|w| !(0.25..=20.0).contains(&w)) {
                    bail!("livello {}, tasto {}: width deve essere tra 0.25 e 20", i + 1, j + 1);
                }
                if b.gap && (faces > 0 || !b.keys.is_empty() || b.width.is_some()) {
                    bail!("livello {}, tasto {}: gap è solo un separatore (niente faccia, keys o width)", i + 1, j + 1);
                }
            }
        }
        if self.display.brightness == 0 || self.display.min_brightness == 0 {
            bail!("display.brightness e display.min_brightness devono essere 1-255");
        }
        if self.display.min_brightness > self.display.brightness {
            bail!("display.min_brightness non può superare display.brightness");
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn default_config_is_valid() {
        let cfg = Config::defaults();
        cfg.validate().unwrap();
        assert_eq!(cfg.layers.len(), 2);
        assert_eq!(cfg.layers[0].buttons[0].keys, vec![Key::Esc]);
        let keys: Vec<_> = cfg.layers[0].buttons.iter().flat_map(|b| b.keys.clone()).collect();
        assert!(keys.contains(&Key::IllumDown) && keys.contains(&Key::IllumUp));
    }

    #[test]
    fn user_sections_replace_defaults() {
        let mut cfg = Config::defaults();
        Config::merge(&mut cfg, "[theme]\nbar = \"black\"\n").unwrap();
        assert_eq!(cfg.theme.bar, BarBackground::Black);
        assert_eq!(cfg.layers.len(), 2);
    }

    #[test]
    fn bad_user_file_is_rejected() {
        let mut cfg = Config::defaults();
        assert!(Config::merge(&mut cfg, "[[layer]]\nbuttons = []\n").is_err());
        assert!(Config::merge(&mut cfg, "[display]\nbrightnes = 3\n").is_err());
        assert_eq!(cfg.layers.len(), 2);
    }
}
