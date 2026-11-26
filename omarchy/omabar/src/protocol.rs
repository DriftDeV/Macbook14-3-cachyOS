//! Protocollo tra omabar-agent (sessione dell'utente) e omabar (renderer di sistema): righe JSON su un socket
//! Unix stream che il renderer crea in /run/omabar. L'agente manda lo stato completo della sessione a ogni
//! cambiamento (idempotente: un messaggio perso non lascia stati a metà).

use serde::{Deserialize, Serialize};

pub const SOCKET: &str = "/run/omabar/renderer.sock";
pub const VERSION: u32 = 1;
/// Lato in pixel della copertina del brano (Media::art), già ritagliata e ridotta dall'agente.
pub const ART: u32 = 44;

#[derive(Serialize, Deserialize, Clone, Debug, Default, PartialEq)]
#[serde(default)]
pub struct SessionState {
    /// Finestra attiva (classe e titolo di Hyprland).
    pub app: Option<App>,
    /// Sessione bloccata (hyprlock / ext-session-lock).
    pub locked: bool,
    /// Screensaver di Omarchy aperto.
    pub screensaver: bool,
    /// Tutti gli schermi spenti (DPMS).
    pub display_off: bool,
    /// Lettore MPRIS scelto: quello che suona, altrimenti l'ultimo in pausa.
    pub media: Option<Media>,
}

#[derive(Serialize, Deserialize, Clone, Debug, Default, PartialEq)]
#[serde(default)]
pub struct App {
    pub class: String,
    pub title: String,
}

#[derive(Serialize, Deserialize, Clone, Debug, Default, PartialEq)]
#[serde(default)]
pub struct Media {
    pub player: String,
    pub playing: bool,
    pub title: String,
    pub artist: String,
    /// Copertina: RGB ART×ART in base64 (vuota se il lettore non ne ha o non si è potuta leggere).
    pub art: String,
    /// mpris:artUrl, solo dentro l'agente (il renderer non può leggere la home né la rete).
    #[serde(skip)]
    pub art_url: String,
}

#[derive(Serialize, Deserialize, Clone, Debug, PartialEq)]
#[serde(tag = "type", rename_all = "snake_case")]
pub enum ToRenderer {
    Hello { version: u32 },
    State(SessionState),
    /// Fotogramma già adattato alla barra (RGB, w×h, in base64): lo screensaver dello schermo, specchiato.
    Frame { w: u32, h: u32, rgb: String },
    /// Chiede un'istantanea della barra (risposta: ToAgent::Screenshot).
    Screenshot,
}

#[derive(Serialize, Deserialize, Clone, Debug, PartialEq)]
#[serde(tag = "type", rename_all = "snake_case")]
pub enum ToAgent {
    Hello { version: u32 },
    /// PNG della barra (prima della luminosità in software), in base64.
    Screenshot { png: String },
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn round_trip() {
        let msg = ToRenderer::State(SessionState {
            app: Some(App { class: "firefox".into(), title: "x".into() }),
            locked: true,
            media: Some(Media { player: "spotify".into(), playing: true, ..Default::default() }),
            ..Default::default()
        });
        let line = serde_json::to_string(&msg).unwrap();
        assert!(line.starts_with("{\"type\":\"state\""));
        assert_eq!(serde_json::from_str::<ToRenderer>(&line).unwrap(), msg);
    }

    #[test]
    fn missing_fields_default() {
        let m: ToRenderer = serde_json::from_str("{\"type\":\"state\",\"locked\":true}").unwrap();
        assert_eq!(m, ToRenderer::State(SessionState { locked: true, ..Default::default() }));
    }
}
