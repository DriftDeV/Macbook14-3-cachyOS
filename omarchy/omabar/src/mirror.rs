//! Adatta un fotogramma dello schermo (16:10) alla Touch Bar (36:1), qualunque cosa mostri.
//! - Riflesso: tutto lo schermo schiacciato nella barra e attenuato, così particelle e scie restano visibili.
//! - Contenuto: il riquadro dei pixel accesi (scartando i punti isolati ai margini), adattato all'altezza della barra
//!   con al massimo MAX_STRETCH di allargamento, nella stessa posizione orizzontale che ha sullo schermo.
//! Il riquadro si muove con una media mobile, per non saltare tra un fotogramma e l'altro.

pub const W: usize = 2170;
pub const H: usize = 60;
const MAX_STRETCH: f64 = 2.0;
const LIT: u32 = 40;
const AMBIENT: u32 = 115; // su 256: ~45 %
const TRIM: f64 = 0.015;
const SMOOTH: f64 = 0.35;

/// Ordine dei byte di un pixel a 32 bit nel buffer catturato.
#[derive(Clone, Copy)]
pub enum Order {
    /// XRGB8888 / ARGB8888 little endian: B, G, R, X
    Bgrx,
    /// XBGR8888 / ABGR8888 little endian: R, G, B, X
    Rgbx,
}

/// Fasce di righe disegnate in parallelo (una per thread).
const BANDS: usize = 4;

pub struct Frame<'a> {
    pub data: &'a [u8],
    pub width: usize,
    pub height: usize,
    pub stride: usize,
    pub order: Order,
    /// Righe dal basso verso l'alto.
    pub y_invert: bool,
}

impl Frame<'_> {
    #[inline]
    fn px(&self, x: usize, y: usize) -> [u32; 3] {
        let y = if self.y_invert { self.height - 1 - y } else { y };
        let i = y * self.stride + x * 4;
        let d = &self.data[i..i + 3];
        match self.order {
            Order::Bgrx => [d[2] as u32, d[1] as u32, d[0] as u32],
            Order::Rgbx => [d[0] as u32, d[1] as u32, d[2] as u32],
        }
    }

    /// Media dei pixel nel rettangolo [x0,x1)×[y0,y1) (almeno un pixel), in coordinate del fotogramma.
    fn area(&self, x0: f64, y0: f64, x1: f64, y1: f64) -> [u32; 3] {
        let ix0 = (x0.floor().max(0.0) as usize).min(self.width - 1);
        let iy0 = (y0.floor().max(0.0) as usize).min(self.height - 1);
        let ix1 = (x1.ceil() as usize).clamp(ix0 + 1, self.width);
        let iy1 = (y1.ceil() as usize).clamp(iy0 + 1, self.height);
        // Su zone grandi basta un campione ogni tanto: il risultato è una media comunque.
        let step_x = ((ix1 - ix0) / 3).max(1);
        let step_y = ((iy1 - iy0) / 3).max(1);
        let (mut acc, mut n) = ([0u32; 3], 0u32);
        for y in (iy0..iy1).step_by(step_y) {
            for x in (ix0..ix1).step_by(step_x) {
                let p = self.px(x, y);
                acc[0] += p[0];
                acc[1] += p[1];
                acc[2] += p[2];
                n += 1;
            }
        }
        [acc[0] / n, acc[1] / n, acc[2] / n]
    }
}

#[derive(Default)]
pub struct Mirror {
    bbox: Option<[f64; 4]>,
}

impl Mirror {
    pub fn reset(&mut self) {
        self.bbox = None;
    }

    /// Riquadro dei pixel accesi, su una griglia rada (1 pixel ogni 4), scartando TRIM dei pixel accesi per lato.
    fn lit_box(f: &Frame) -> Option<[f64; 4]> {
        const S: usize = 4;
        let (gw, gh) = (f.width / S, f.height / S);
        let mut cols = vec![0u32; gw];
        let mut rows = vec![0u32; gh];
        let mut total = 0u32;
        for gy in 0..gh {
            for gx in 0..gw {
                let p = f.px(gx * S, gy * S);
                if (p[0] * 77 + p[1] * 150 + p[2] * 29) >> 8 > LIT {
                    cols[gx] += 1;
                    rows[gy] += 1;
                    total += 1;
                }
            }
        }
        if total < 4 {
            return None;
        }
        let cut = (total as f64 * TRIM) as u32;
        let span = |v: &[u32]| {
            let (mut acc, mut lo) = (0, 0);
            for (i, c) in v.iter().enumerate() {
                acc += c;
                if acc > cut {
                    lo = i;
                    break;
                }
            }
            let (mut acc, mut hi) = (0, v.len() - 1);
            for (i, c) in v.iter().enumerate().rev() {
                acc += c;
                if acc > cut {
                    hi = i;
                    break;
                }
            }
            (lo as f64 * S as f64, (hi + 1) as f64 * S as f64)
        };
        let (x0, x1) = span(&cols);
        let (y0, y1) = span(&rows);
        Some([x0, y0, x1, y1])
    }

    /// Fotogramma RGB W×H per la barra.
    pub fn compose(&mut self, f: &Frame) -> Vec<u8> {
        let mut out = vec![0u8; W * H * 3];
        let (sw, sh) = (f.width as f64, f.height as f64);
        if f.width == 0 || f.height == 0 {
            return out;
        }

        // Contenuto: riquadro dei pixel accesi, con la media mobile.
        if let Some(b) = Self::lit_box(f) {
            self.bbox = Some(match self.bbox {
                None => b,
                Some(o) => [0, 1, 2, 3].map(|i| o[i] + (b[i] - o[i]) * SMOOTH),
            });
        }
        // Dove va il contenuto nella barra: (x0, y0, sx, sy, left, dw) oppure niente.
        let place = self.bbox.and_then(|[x0, y0, x1, y1]| {
            let pad = ((y1 - y0) * 0.1).max(4.0);
            let (x0, y0, x1, y1) = ((x0 - pad).max(0.0), (y0 - pad).max(0.0), (x1 + pad).min(sw), (y1 + pad).min(sh));
            let (cw, ch) = (x1 - x0, y1 - y0);
            if cw < 1.0 || ch < 1.0 {
                return None;
            }
            let sy = H as f64 / ch;
            let sx = (sy * MAX_STRETCH).min(W as f64 / cw);
            let dw = (cw * sx).round().min(W as f64) as usize;
            let center = (x0 + x1) / 2.0 / sw * W as f64;
            let left = (center - dw as f64 / 2.0).clamp(0.0, (W - dw) as f64).round() as usize;
            Some((x0, y0, sx, sy, left, dw))
        });

        let (fx, fy) = (sw / W as f64, sh / H as f64);
        let rows_per_band = H.div_ceil(BANDS);
        std::thread::scope(|scope| {
            for (band, chunk) in out.chunks_mut(rows_per_band * W * 3).enumerate() {
                scope.spawn(move || {
                    for (r, row) in chunk.chunks_mut(W * 3).enumerate() {
                        let y = band * rows_per_band + r;
                        // Riflesso di tutto lo schermo, attenuato.
                        for x in 0..W {
                            let p = f.area(x as f64 * fx, y as f64 * fy, (x + 1) as f64 * fx, (y + 1) as f64 * fy);
                            row[x * 3] = (p[0] * AMBIENT >> 8) as u8;
                            row[x * 3 + 1] = (p[1] * AMBIENT >> 8) as u8;
                            row[x * 3 + 2] = (p[2] * AMBIENT >> 8) as u8;
                        }
                        // Contenuto a piena luminosità sopra il riflesso.
                        if let Some((x0, y0, sx, sy, left, dw)) = place {
                            let (ya, yb) = (y0 + y as f64 / sy, y0 + (y + 1) as f64 / sy);
                            for dx in 0..dw {
                                let p = f.area(x0 + dx as f64 / sx, ya, x0 + (dx + 1) as f64 / sx, yb);
                                let o = (left + dx) * 3;
                                row[o] = p[0] as u8;
                                row[o + 1] = p[1] as u8;
                                row[o + 2] = p[2] as u8;
                            }
                        }
                    }
                });
            }
        });
        out
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Schermo 400×250 nero con un rettangolo bianco al centro (200×50) e un punto isolato in un angolo.
    fn screen() -> Vec<u8> {
        let (w, h) = (400usize, 250usize);
        let mut d = vec![0u8; w * h * 4];
        for y in 100..150 {
            for x in 100..300 {
                d[(y * w + x) * 4..(y * w + x) * 4 + 3].copy_from_slice(&[255, 255, 255]);
            }
        }
        d[(4 * w + 4) * 4..(4 * w + 4) * 4 + 3].copy_from_slice(&[255, 255, 255]);
        d
    }

    #[test]
    fn content_fills_bar_height_and_ignores_outliers() {
        let d = screen();
        let f = Frame { data: &d, width: 400, height: 250, stride: 1600, order: Order::Bgrx, y_invert: false };
        let mut m = Mirror::default();
        let b = Mirror::lit_box(&f).unwrap();
        assert!(b[0] >= 96.0 && b[1] >= 96.0, "il punto isolato non deve allargare il riquadro: {b:?}");
        let out = m.compose(&f);
        assert_eq!(out.len(), W * H * 3);
        // Centro della barra: contenuto a piena luminosità.
        let mid = (30 * W + W / 2) * 3;
        assert_eq!(&out[mid..mid + 3], &[255, 255, 255]);
        // Bordo sinistro: solo riflesso scuro.
        assert!(out[(30 * W + 5) * 3] < 130);
    }

    #[test]
    fn black_screen_is_black_bar() {
        let d = vec![0u8; 400 * 250 * 4];
        let f = Frame { data: &d, width: 400, height: 250, stride: 1600, order: Order::Rgbx, y_invert: true };
        assert!(Mirror::default().compose(&f).iter().all(|&v| v == 0));
    }
}
