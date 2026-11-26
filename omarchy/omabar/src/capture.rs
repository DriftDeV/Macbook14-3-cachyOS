//! Cattura di una zona dello schermo con wlr-screencopy (Hyprland), su una connessione Wayland che resta aperta:
//! niente processi e niente PNG a ogni fotogramma come con grim.

use anyhow::{anyhow, bail, Context as _, Result};
use std::{fs::File, os::fd::AsFd};
use wayland_client::{
    protocol::{wl_buffer, wl_output, wl_registry, wl_shm, wl_shm_pool},
    Connection, Dispatch, EventQueue, QueueHandle, WEnum,
};
use wayland_protocols_wlr::screencopy::v1::client::{
    zwlr_screencopy_frame_v1::{self, ZwlrScreencopyFrameV1},
    zwlr_screencopy_manager_v1::ZwlrScreencopyManagerV1,
};

use crate::mirror::Order;

#[derive(Default)]
struct State {
    shm: Option<wl_shm::WlShm>,
    manager: Option<ZwlrScreencopyManagerV1>,
    outputs: Vec<(wl_output::WlOutput, String)>,
    frame: FrameInfo,
}

#[derive(Default, Clone)]
struct FrameInfo {
    format: Option<wl_shm::Format>,
    width: u32,
    height: u32,
    stride: u32,
    y_invert: bool,
    buffer_done: bool,
    ready: bool,
    failed: bool,
}

/// Fotogramma catturato: punta alla memoria condivisa del Capturer, valido fino alla cattura successiva.
pub struct Captured<'a> {
    pub data: &'a [u8],
    pub width: usize,
    pub height: usize,
    pub stride: usize,
    pub order: Order,
    pub y_invert: bool,
}

pub struct Capturer {
    _conn: Connection,
    queue: EventQueue<State>,
    qh: QueueHandle<State>,
    state: State,
    /// memfd riusato tra un fotogramma e l'altro, mappato in memoria (niente copie del fotogramma).
    shm: Option<Shm>,
}

struct Shm {
    file: File,
    size: usize,
    ptr: std::ptr::NonNull<std::ffi::c_void>,
}

impl Drop for Shm {
    fn drop(&mut self) {
        unsafe {
            let _ = nix::sys::mman::munmap(self.ptr, self.size);
        }
    }
}

impl Capturer {
    pub fn new() -> Result<Capturer> {
        let conn = Connection::connect_to_env().context("connessione a Wayland")?;
        let mut queue = conn.new_event_queue();
        let qh = queue.handle();
        conn.display().get_registry(&qh, ());
        let mut state = State::default();
        // Due giri: globali, poi i nomi delle uscite.
        queue.roundtrip(&mut state)?;
        queue.roundtrip(&mut state)?;
        if state.manager.is_none() {
            bail!("il compositore non offre wlr-screencopy");
        }
        if state.shm.is_none() {
            bail!("wl_shm assente");
        }
        Ok(Capturer { _conn: conn, queue, qh, state, shm: None })
    }

    /// Cattura la zona (x, y, w, h) in coordinate logiche dell'uscita `output` (per esempio "eDP-1").
    pub fn capture(&mut self, output: &str, x: i32, y: i32, w: i32, h: i32) -> Result<Captured<'_>> {
        let out = self
            .state
            .outputs
            .iter()
            .find(|(_, n)| n == output)
            .map(|(o, _)| o.clone())
            .ok_or_else(|| anyhow!("uscita {output} non trovata"))?;
        let manager = self.state.manager.clone().unwrap();
        self.state.frame = FrameInfo::default();
        let frame = manager.capture_output_region(0, &out, x, y, w, h, &self.qh, ());
        while !self.state.frame.buffer_done && !self.state.frame.failed {
            self.queue.blocking_dispatch(&mut self.state)?;
        }
        let info = self.state.frame.clone();
        if info.failed {
            frame.destroy();
            bail!("cattura rifiutata");
        }
        let format = info.format.ok_or_else(|| anyhow!("nessun formato shm offerto"))?;
        let order = match format {
            wl_shm::Format::Xrgb8888 | wl_shm::Format::Argb8888 => Order::Bgrx,
            wl_shm::Format::Xbgr8888 | wl_shm::Format::Abgr8888 => Order::Rgbx,
            f => {
                frame.destroy();
                bail!("formato {f:?} non gestito");
            }
        };
        let size = info.stride as usize * info.height as usize;
        if self.shm.as_ref().map(|s| s.size) != Some(size) {
            self.shm = None;
            let fd = nix::sys::memfd::memfd_create(c"omabar-mirror", nix::sys::memfd::MemFdCreateFlag::MFD_CLOEXEC)?;
            let file = File::from(fd);
            file.set_len(size as u64)?;
            let ptr = unsafe {
                nix::sys::mman::mmap(
                    None,
                    std::num::NonZeroUsize::new(size).ok_or_else(|| anyhow!("fotogramma vuoto"))?,
                    nix::sys::mman::ProtFlags::PROT_READ,
                    nix::sys::mman::MapFlags::MAP_SHARED,
                    &file,
                    0,
                )?
            };
            self.shm = Some(Shm { file, size, ptr });
        }
        let shm_mem = self.shm.as_ref().unwrap();
        let shm = self.state.shm.as_ref().unwrap();
        let pool = shm.create_pool(shm_mem.file.as_fd(), size as i32, &self.qh, ());
        let buffer = pool.create_buffer(
            0,
            info.width as i32,
            info.height as i32,
            info.stride as i32,
            format,
            &self.qh,
            (),
        );
        frame.copy(&buffer);
        while !self.state.frame.ready && !self.state.frame.failed {
            self.queue.blocking_dispatch(&mut self.state)?;
        }
        let ok = self.state.frame.ready;
        let y_invert = self.state.frame.y_invert;
        frame.destroy();
        buffer.destroy();
        pool.destroy();
        if !ok {
            bail!("copia del fotogramma non riuscita");
        }
        // SAFETY: mappatura di `size` byte, viva finché vive self.shm (il prestito di &mut self lo garantisce).
        let data = unsafe { std::slice::from_raw_parts(shm_mem.ptr.as_ptr() as *const u8, size) };
        Ok(Captured {
            data,
            width: info.width as usize,
            height: info.height as usize,
            stride: info.stride as usize,
            order,
            y_invert,
        })
    }
}

impl Dispatch<wl_registry::WlRegistry, ()> for State {
    fn event(
        state: &mut State,
        registry: &wl_registry::WlRegistry,
        event: wl_registry::Event,
        _: &(),
        _: &Connection,
        qh: &QueueHandle<State>,
    ) {
        if let wl_registry::Event::Global { name, interface, version } = event {
            match interface.as_str() {
                "wl_shm" => state.shm = Some(registry.bind(name, 1, qh, ())),
                "zwlr_screencopy_manager_v1" => state.manager = Some(registry.bind(name, version.min(3), qh, ())),
                // Versione 4 per l'evento name ("eDP-1").
                "wl_output" if version >= 4 => {
                    let o = registry.bind(name, 4, qh, ());
                    state.outputs.push((o, String::new()));
                }
                _ => {}
            }
        }
    }
}

impl Dispatch<wl_output::WlOutput, ()> for State {
    fn event(state: &mut State, o: &wl_output::WlOutput, event: wl_output::Event, _: &(), _: &Connection, _: &QueueHandle<State>) {
        if let wl_output::Event::Name { name } = event {
            if let Some(e) = state.outputs.iter_mut().find(|(x, _)| x == o) {
                e.1 = name;
            }
        }
    }
}

impl Dispatch<ZwlrScreencopyFrameV1, ()> for State {
    fn event(
        state: &mut State,
        _: &ZwlrScreencopyFrameV1,
        event: zwlr_screencopy_frame_v1::Event,
        _: &(),
        _: &Connection,
        _: &QueueHandle<State>,
    ) {
        let f = &mut state.frame;
        match event {
            zwlr_screencopy_frame_v1::Event::Buffer { format, width, height, stride } => {
                // Il primo formato shm offerto (di solito XRGB8888).
                if f.format.is_none() {
                    if let WEnum::Value(fmt) = format {
                        f.format = Some(fmt);
                        f.width = width;
                        f.height = height;
                        f.stride = stride;
                    }
                }
            }
            zwlr_screencopy_frame_v1::Event::Flags { flags } => {
                if let WEnum::Value(fl) = flags {
                    f.y_invert = fl.contains(zwlr_screencopy_frame_v1::Flags::YInvert);
                }
            }
            zwlr_screencopy_frame_v1::Event::BufferDone => f.buffer_done = true,
            zwlr_screencopy_frame_v1::Event::Ready { .. } => f.ready = true,
            zwlr_screencopy_frame_v1::Event::Failed => f.failed = true,
            _ => {}
        }
    }
}

wayland_client::delegate_noop!(State: ignore wl_shm::WlShm);
wayland_client::delegate_noop!(State: ignore wl_shm_pool::WlShmPool);
wayland_client::delegate_noop!(State: ignore wl_buffer::WlBuffer);
wayland_client::delegate_noop!(State: ignore ZwlrScreencopyManagerV1);
