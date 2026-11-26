//! Avviso quando un file cambia, guardando la sua cartella con inotify: così funziona anche se il file viene
//! sostituito (scrittura su un temporaneo + rename) o se la cartella nasce dopo l'avvio.

use nix::{
    errno::Errno,
    sys::inotify::{AddWatchFlags, InitFlags, Inotify, WatchDescriptor},
};
use std::{
    ffi::OsString,
    os::fd::{AsFd, BorrowedFd},
    path::{Path, PathBuf},
};

pub struct FileWatch {
    inotify: Inotify,
    dir: PathBuf,
    name: OsString,
    wd: Option<WatchDescriptor>,
}

impl FileWatch {
    pub fn new(path: &Path) -> nix::Result<FileWatch> {
        let mut w = FileWatch {
            inotify: Inotify::init(InitFlags::IN_NONBLOCK | InitFlags::IN_CLOEXEC)?,
            dir: path.parent().unwrap_or(Path::new("/")).to_path_buf(),
            name: path.file_name().unwrap_or_default().to_os_string(),
            wd: None,
        };
        w.arm();
        Ok(w)
    }

    fn arm(&mut self) -> bool {
        if self.wd.is_some() {
            return false;
        }
        let flags = AddWatchFlags::IN_CLOSE_WRITE
            | AddWatchFlags::IN_MOVED_TO
            | AddWatchFlags::IN_MOVED_FROM
            | AddWatchFlags::IN_DELETE
            | AddWatchFlags::IN_CREATE;
        self.wd = self.inotify.add_watch(&self.dir, flags).ok();
        self.wd.is_some()
    }

    /// true se il file potrebbe essere cambiato dall'ultima chiamata (va riletto).
    pub fn changed(&mut self) -> bool {
        // Cartella comparsa ora: il file può esserci già.
        if self.arm() {
            return true;
        }
        let events = match self.inotify.read_events() {
            Ok(ev) => ev,
            Err(Errno::EAGAIN) => return false,
            Err(e) => {
                eprintln!("omabar: inotify su {}: {e}", self.dir.display());
                return false;
            }
        };
        let mut changed = false;
        for ev in events {
            if ev.mask.contains(AddWatchFlags::IN_IGNORED) {
                // Cartella tolta: si riprova ad agganciarla al prossimo giro.
                self.wd = None;
                changed = true;
            } else if ev.name.as_deref() == Some(self.name.as_os_str()) {
                changed = true;
            }
        }
        changed
    }

    /// Da chiamare a ogni giro del ciclo: se la cartella non c'era, prova ad agganciarla.
    pub fn is_armed(&self) -> bool {
        self.wd.is_some()
    }
}

impl AsFd for FileWatch {
    fn as_fd(&self) -> BorrowedFd<'_> {
        self.inotify.as_fd()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;

    #[test]
    fn sees_atomic_replace_and_late_directory() {
        let base = std::env::temp_dir().join(format!("omabar-watch-{}", std::process::id()));
        let _ = fs::remove_dir_all(&base);
        let file = base.join("theme.toml");
        let mut w = FileWatch::new(&file).unwrap();
        assert!(!w.is_armed());
        assert!(!w.changed());

        fs::create_dir_all(&base).unwrap();
        assert!(w.changed(), "cartella comparsa: va riletto");
        assert!(!w.changed());

        fs::write(base.join(".tmp"), "a").unwrap();
        assert!(!w.changed(), "altri file non contano");
        fs::rename(base.join(".tmp"), &file).unwrap();
        assert!(w.changed(), "rename sul file guardato");

        fs::remove_dir_all(&base).unwrap();
        assert!(w.changed());
        assert!(!w.is_armed());
    }
}
