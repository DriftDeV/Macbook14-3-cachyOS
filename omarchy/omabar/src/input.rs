//! Ingressi e uscite: sensore della Touch Bar (libinput, posto "seat-touchbar" assegnato dalla regola udev),
//! tastiera principale per il tasto Fn (seat0) e una tastiera virtuale uinput che invia i tasti premuti.

use anyhow::{Context as _, Result};
use input::{Libinput, LibinputInterface};
use input_linux::{uinput::UInputHandle, EventKind, Key, SynchronizeKind};
use input_linux_sys::{input_event, input_id, timeval, uinput_setup};
use std::{
    fs::{File, OpenOptions},
    os::{
        fd::OwnedFd,
        unix::fs::OpenOptionsExt,
    },
    path::Path,
};

struct Opener;

impl LibinputInterface for Opener {
    fn open_restricted(&mut self, path: &Path, flags: i32) -> Result<OwnedFd, i32> {
        let acc = flags & nix::fcntl::OFlag::O_ACCMODE.bits();
        OpenOptions::new()
            .custom_flags(flags & !nix::fcntl::OFlag::O_ACCMODE.bits())
            .read(acc == nix::fcntl::OFlag::O_RDONLY.bits() || acc == nix::fcntl::OFlag::O_RDWR.bits())
            .write(acc == nix::fcntl::OFlag::O_WRONLY.bits() || acc == nix::fcntl::OFlag::O_RDWR.bits())
            .open(path)
            .map(OwnedFd::from)
            .map_err(|e| e.raw_os_error().unwrap_or(1))
    }
    fn close_restricted(&mut self, fd: OwnedFd) {
        drop(File::from(fd));
    }
}

pub fn libinput_seat(seat: &str) -> Result<Libinput> {
    let mut li = Libinput::new_with_udev(Opener);
    li.udev_assign_seat(seat)
        .map_err(|_| anyhow::anyhow!("libinput: posto {seat} non assegnabile"))?;
    Ok(li)
}

pub struct VirtualKeys {
    dev: UInputHandle<File>,
}

impl VirtualKeys {
    pub fn new() -> Result<VirtualKeys> {
        let f = OpenOptions::new()
            .write(true)
            .open("/dev/uinput")
            .context("apertura di /dev/uinput")?;
        let dev = UInputHandle::new(f);
        dev.set_evbit(EventKind::Key)?;
        for k in Key::iter() {
            dev.set_keybit(k)?;
        }
        let mut name = [0 as std::os::raw::c_char; 80];
        for (d, s) in name.iter_mut().zip(b"OmaBar Touch Bar Keys") {
            *d = *s as std::os::raw::c_char;
        }
        dev.dev_setup(&uinput_setup {
            id: input_id { bustype: 0x06 /* BUS_VIRTUAL */, vendor: 0x05ac, product: 0x8600, version: 1 },
            name,
            ff_effects_max: 0,
        })?;
        dev.dev_create()?;
        Ok(VirtualKeys { dev })
    }

    fn emit(&self, kind: EventKind, code: u16, value: i32) {
        let ev = input_event { time: timeval { tv_sec: 0, tv_usec: 0 }, type_: kind as u16, code, value };
        if let Err(e) = self.dev.write(&[ev]) {
            eprintln!("omabar: uinput: {e}");
        }
    }

    /// Preme (true) o rilascia (false) tutti i tasti indicati insieme, poi sincronizza.
    pub fn set(&self, keys: &[Key], down: bool) {
        if keys.is_empty() {
            return;
        }
        if down {
            for k in keys {
                self.emit(EventKind::Key, *k as u16, 1);
            }
        } else {
            for k in keys.iter().rev() {
                self.emit(EventKind::Key, *k as u16, 0);
            }
        }
        self.emit(EventKind::Synchronize, SynchronizeKind::Report as u16, 0);
    }
}
