//! Luminosità della barra che segue quella dello schermo. In modalità display il T1 non espone una retroilluminazione:
//! la barra si scurisce in software (display.rs scala i pixel), qui si sceglie solo il livello.

use crate::config::Display as DisplayCfg;
use std::{fs, path::PathBuf};

pub struct ScreenBacklight {
    actual: PathBuf,
    max: f64,
}

impl ScreenBacklight {
    /// Retroilluminazione dello schermo principale: sul 14,3 gmux_backlight. Si preferiscono i tipi "raw" e
    /// "firmware" (quelli del pannello) a "platform".
    pub fn find() -> Option<ScreenBacklight> {
        let mut found: Vec<(u8, ScreenBacklight)> = fs::read_dir("/sys/class/backlight")
            .ok()?
            .flatten()
            .filter_map(|e| {
                let p = e.path();
                let max: f64 = fs::read_to_string(p.join("max_brightness")).ok()?.trim().parse().ok()?;
                if max <= 0.0 {
                    return None;
                }
                let rank = match fs::read_to_string(p.join("type")).unwrap_or_default().trim() {
                    "raw" => 0,
                    "firmware" => 1,
                    _ => 2,
                };
                Some((rank, ScreenBacklight { actual: p.join("actual_brightness"), max }))
            })
            .collect();
        found.sort_by_key(|(r, _)| *r);
        found.into_iter().next().map(|(_, b)| b)
    }

    /// Luminosità dello schermo, 0-1.
    pub fn fraction(&self) -> Option<f64> {
        let v: f64 = fs::read_to_string(&self.actual).ok()?.trim().parse().ok()?;
        Some((v / self.max).clamp(0.0, 1.0))
    }
}

/// Livello della barra (1-255) per una luminosità dello schermo `screen` (0-1): da min_brightness a brightness.
/// L'esponente < 1 tiene la barra leggibile quando lo schermo è basso (la barra è più piccola e più vicina agli occhi).
pub fn bar_level(cfg: &DisplayCfg, screen: Option<f64>) -> u8 {
    match (cfg.follow_screen, screen) {
        (true, Some(f)) => {
            let (lo, hi) = (cfg.min_brightness as f64, cfg.brightness as f64);
            (lo + (hi - lo) * f.powf(0.7)).round().clamp(1.0, 255.0) as u8
        }
        _ => cfg.brightness,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn follows_screen_within_bounds() {
        let cfg = DisplayCfg { brightness: 200, min_brightness: 40, follow_screen: true, ..Default::default() };
        assert_eq!(bar_level(&cfg, Some(0.0)), 40);
        assert_eq!(bar_level(&cfg, Some(1.0)), 200);
        // Predefiniti: schermo al massimo = barra al massimo reale.
        let def = DisplayCfg::default();
        assert_eq!(bar_level(&def, Some(1.0)), 255);
        let mid = bar_level(&cfg, Some(0.5));
        assert!(mid > 120 && mid < 200, "{mid}");
        assert_eq!(bar_level(&cfg, None), 200);
        let fixed = DisplayCfg { follow_screen: false, ..cfg };
        assert_eq!(bar_level(&fixed, Some(0.1)), 200);
    }
}
