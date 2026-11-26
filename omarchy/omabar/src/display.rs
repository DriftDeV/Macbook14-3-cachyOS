//! Schermo della Touch Bar via DRM (appletbdrm): un dumb buffer XRGB8888 fisso, aggiornato a zone con DIRTYFB.
//! Sul 14,3 il pannello è verticale (60×2170): il disegno orizzontale viene ruotato qui durante la copia.

use crate::bar::Rect;
use anyhow::{anyhow, Context as _, Result};
use drm::{
    buffer::DrmFourcc,
    control::{connector, crtc, dumbbuffer::DumbBuffer, framebuffer, ClipRect, Device as ControlDevice},
    Device,
};
use std::{
    fs::{File, OpenOptions},
    os::fd::{AsFd, BorrowedFd},
    path::Path,
};

struct Card(File);
impl AsFd for Card {
    fn as_fd(&self) -> BorrowedFd<'_> {
        self.0.as_fd()
    }
}
impl Device for Card {}
impl ControlDevice for Card {}

pub struct Display {
    card: Card,
    db: Option<DumbBuffer>,
    fb: framebuffer::Handle,
    _crtc: crtc::Handle,
    fb_w: u32,
    fb_h: u32,
    pitch: u32,
    /// Pannello verticale: (x, y) orizzontale → colonna fb_w-1-y, riga x.
    rotated: bool,
    pub dirty_supported: bool,
}

impl Display {
    pub fn open(path: &Path) -> Result<Display> {
        let file = OpenOptions::new()
            .read(true)
            .write(true)
            .open(path)
            .with_context(|| format!("apertura di {}", path.display()))?;
        let card = Card(file);
        // Nessun altro deve avere lo schermo: se un altro renderer è attivo, meglio fermarsi subito.
        card.acquire_master_lock()
            .context("DRM master non disponibile: c'è già un renderer della Touch Bar attivo?")?;

        let res = card.resource_handles().context("risorse DRM")?;
        let (conn, mode) = res
            .connectors()
            .iter()
            .filter_map(|&h| card.get_connector(h, true).ok().map(|i| (h, i)))
            .find(|(_, i)| i.state() == connector::State::Connected && !i.modes().is_empty())
            .map(|(h, i)| (h, i.modes()[0]))
            .ok_or_else(|| anyhow!("nessun connettore collegato su {}", path.display()))?;
        let info = card.get_connector(conn, false)?;
        let crtc = info
            .current_encoder()
            .and_then(|e| card.get_encoder(e).ok())
            .and_then(|e| e.crtc())
            .or_else(|| {
                info.encoders().iter().find_map(|&e| {
                    let enc = card.get_encoder(e).ok()?;
                    res.filter_crtcs(enc.possible_crtcs()).first().copied()
                })
            })
            .ok_or_else(|| anyhow!("nessun CRTC per il connettore"))?;

        let (w, h) = mode.size();
        let (fb_w, fb_h) = (w as u32, h as u32);
        let db = card
            .create_dumb_buffer((fb_w, fb_h), DrmFourcc::Xrgb8888, 32)
            .context("dumb buffer")?;
        let fb = card.add_framebuffer(&db, 24, 32).context("framebuffer")?;
        card.set_crtc(crtc, Some(fb), (0, 0), &[conn], Some(mode)).context("set_crtc")?;
        let pitch = drm::buffer::Buffer::pitch(&db);
        Ok(Display {
            card,
            db: Some(db),
            fb,
            _crtc: crtc,
            fb_w,
            fb_h,
            pitch,
            rotated: fb_h > fb_w,
            dirty_supported: true,
        })
    }

    /// Dimensioni del disegno orizzontale (larghezza, altezza).
    pub fn logical_size(&self) -> (u32, u32) {
        if self.rotated {
            (self.fb_h, self.fb_w)
        } else {
            (self.fb_w, self.fb_h)
        }
    }

    /// Copia le zone `rects` del disegno (ARGB32, `stride`) nel framebuffer, ruotando e scalando la luminosità
    /// (`level` 1-255), poi segnala le zone al driver.
    pub fn present(&mut self, src: &[u8], stride: usize, rects: &[Rect], level: u8) -> Result<()> {
        let (lw, lh) = self.logical_size();
        let (fb_w, pitch, rotated) = (self.fb_w as usize, self.pitch as usize, self.rotated);
        let scale = level as u32;
        let mut clips = Vec::with_capacity(rects.len());
        {
            let db = self.db.as_mut().expect("dumb buffer");
            let mut map = self.card.map_dumb_buffer(db).context("map del dumb buffer")?;
            let dst = map.as_mut();
            for r in rects {
                let x0 = r.x.floor().max(0.0) as usize;
                let y0 = r.y.floor().max(0.0) as usize;
                let x1 = ((r.x + r.w).ceil() as usize).min(lw as usize);
                let y1 = ((r.y + r.h).ceil() as usize).min(lh as usize);
                if x0 >= x1 || y0 >= y1 {
                    continue;
                }
                for y in y0..y1 {
                    for x in x0..x1 {
                        let s = y * stride + x * 4;
                        let d = if rotated {
                            x * pitch + (fb_w - 1 - y) * 4
                        } else {
                            y * pitch + x * 4
                        };
                        for k in 0..3 {
                            dst[d + k] = if scale == 255 { src[s + k] } else { (src[s + k] as u32 * scale / 255) as u8 };
                        }
                        dst[d + 3] = 0;
                    }
                }
                clips.push(if rotated {
                    ClipRect::new((fb_w - y1) as u16, x0 as u16, (fb_w - y0) as u16, x1 as u16)
                } else {
                    ClipRect::new(x0 as u16, y0 as u16, x1 as u16, y1 as u16)
                });
            }
        }
        if self.dirty_supported && !clips.is_empty() {
            if let Err(e) = self.card.dirty_framebuffer(self.fb, &clips) {
                // ENOSYS: il driver aggiorna da solo, non serve segnalarlo.
                if e.raw_os_error() == Some(libc_enosys()) {
                    self.dirty_supported = false;
                } else {
                    return Err(anyhow!(e).context("DIRTYFB"));
                }
            }
        }
        Ok(())
    }
}

fn libc_enosys() -> i32 {
    nix::errno::Errno::ENOSYS as i32
}

impl Drop for Display {
    fn drop(&mut self) {
        let _ = self.card.destroy_framebuffer(self.fb);
        if let Some(db) = self.db.take() {
            let _ = self.card.destroy_dumb_buffer(db);
        }
    }
}
