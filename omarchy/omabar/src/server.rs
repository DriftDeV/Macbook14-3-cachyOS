//! Lato renderer del socket dell'agente. Il socket nasce da root (prima di passare a nobody) con permessi 0660 e il
//! gruppo della cartella /run/omabar, cioè quello dell'utente della Touch Bar; in più si controlla SO_PEERCRED.
//! Un solo agente alla volta: una nuova connessione sostituisce la precedente.

use crate::protocol::{SessionState, ToAgent, ToRenderer, VERSION};
use base64::Engine as _;
use anyhow::{Context as _, Result};
use nix::sys::socket::{getsockopt, sockopt::PeerCredentials};
use std::{
    fs,
    io::{ErrorKind, Read, Write},
    os::{
        fd::{AsFd, BorrowedFd},
        unix::{
            fs::{MetadataExt, PermissionsExt},
            net::{UnixListener, UnixStream},
        },
    },
    path::Path,
};

pub struct Server {
    listener: UnixListener,
    allowed_gid: u32,
    client: Option<Client>,
}

struct Client {
    stream: UnixStream,
    buf: Vec<u8>,
    /// Ha mandato uno stato: è l'agente (non, per esempio, `omabar-agent --screenshot`).
    sent_state: bool,
}

pub enum Incoming {
    State(SessionState),
    Frame { w: u32, h: u32, rgb: Vec<u8> },
    ScreenshotRequest,
    /// L'agente se n'è andato (non arriva per i client che non hanno mai mandato uno stato).
    Disconnected,
}

impl Server {
    pub fn bind(path: &Path) -> Result<Server> {
        let dir = path.parent().context("percorso del socket")?;
        let gid = fs::metadata(dir).with_context(|| format!("{} assente", dir.display()))?.gid();
        match fs::remove_file(path) {
            Ok(()) => {}
            Err(e) if e.kind() == ErrorKind::NotFound => {}
            Err(e) => return Err(e).context("socket vecchio non rimovibile"),
        }
        let listener = UnixListener::bind(path).with_context(|| format!("bind di {}", path.display()))?;
        listener.set_nonblocking(true)?;
        nix::unistd::chown(path, None, Some(nix::unistd::Gid::from_raw(gid)))?;
        fs::set_permissions(path, fs::Permissions::from_mode(0o660))?;
        Ok(Server { listener, allowed_gid: gid, client: None })
    }

    pub fn listener_fd(&self) -> BorrowedFd<'_> {
        self.listener.as_fd()
    }

    pub fn client_fd(&self) -> Option<BorrowedFd<'_>> {
        self.client.as_ref().map(|c| c.stream.as_fd())
    }

    /// Accetta le connessioni in attesa. true se è cambiato il client (va ri-registrato in epoll).
    pub fn accept(&mut self) -> bool {
        let mut changed = false;
        loop {
            let stream = match self.listener.accept() {
                Ok((s, _)) => s,
                Err(e) if e.kind() == ErrorKind::WouldBlock => break,
                Err(e) => {
                    eprintln!("omabar: accept: {e}");
                    break;
                }
            };
            let cred = match getsockopt(&stream, PeerCredentials) {
                Ok(c) => c,
                Err(e) => {
                    eprintln!("omabar: credenziali del client: {e}");
                    continue;
                }
            };
            if cred.uid() != 0 && cred.gid() != self.allowed_gid {
                eprintln!("omabar: connessione rifiutata (uid {}, gid {})", cred.uid(), cred.gid());
                continue;
            }
            if stream.set_nonblocking(true).is_err() {
                continue;
            }
            let mut client = Client { stream, buf: Vec::new(), sent_state: false };
            let hello = serde_json::to_string(&ToAgent::Hello { version: VERSION }).unwrap() + "\n";
            let _ = client.stream.write_all(hello.as_bytes());
            eprintln!("omabar: agente collegato (pid {})", cred.pid());
            self.client = Some(client);
            changed = true;
        }
        changed
    }

    /// Legge i messaggi completi arrivati dall'agente.
    pub fn read(&mut self) -> Vec<Incoming> {
        let mut out = Vec::new();
        let Some(client) = &mut self.client else { return out };
        let mut chunk = [0u8; 4096];
        let mut closed = false;
        loop {
            match client.stream.read(&mut chunk) {
                Ok(0) => {
                    closed = true;
                    break;
                }
                Ok(n) => client.buf.extend_from_slice(&chunk[..n]),
                Err(e) if e.kind() == ErrorKind::WouldBlock => break,
                Err(e) if e.kind() == ErrorKind::Interrupted => continue,
                Err(_) => {
                    closed = true;
                    break;
                }
            }
            // Un agente che non manda mai un a capo non deve far crescere la memoria all'infinito
            // (un fotogramma 2170×60 in base64 è ~520 KB).
            if client.buf.len() > 4 * 1024 * 1024 {
                eprintln!("omabar: messaggio dell'agente troppo lungo, chiudo");
                closed = true;
                break;
            }
        }
        while let Some(pos) = client.buf.iter().position(|&b| b == b'\n') {
            let line: Vec<u8> = client.buf.drain(..=pos).collect();
            match serde_json::from_slice::<ToRenderer>(&line[..line.len() - 1]) {
                Ok(ToRenderer::State(s)) => {
                    client.sent_state = true;
                    out.push(Incoming::State(s))
                }
                Ok(ToRenderer::Frame { w, h, rgb }) => match base64::engine::general_purpose::STANDARD.decode(rgb) {
                    Ok(rgb) if rgb.len() == (w * h * 3) as usize && w > 0 && h > 0 && w <= 4096 && h <= 512 => {
                        out.push(Incoming::Frame { w, h, rgb })
                    }
                    _ => eprintln!("omabar: fotogramma non valido"),
                },
                Ok(ToRenderer::Screenshot) => out.push(Incoming::ScreenshotRequest),
                Ok(ToRenderer::Hello { version }) if version != VERSION => {
                    eprintln!("omabar: agente con protocollo {version}, il renderer usa {VERSION}")
                }
                Ok(ToRenderer::Hello { .. }) => {}
                Err(e) => eprintln!("omabar: messaggio dell'agente non valido: {e}"),
            }
        }
        if closed {
            let was_agent = client.sent_state;
            self.client = None;
            if was_agent {
                eprintln!("omabar: agente scollegato");
                out.push(Incoming::Disconnected);
            }
        }
        out
    }

    /// Manda un messaggio al client (bloccante, al massimo 2 s: un'istantanea è qualche decina di KB).
    pub fn send(&mut self, msg: &ToAgent) {
        let Some(client) = &mut self.client else { return };
        let line = serde_json::to_string(msg).unwrap() + "\n";
        let s = &mut client.stream;
        let ok = s.set_nonblocking(false).is_ok()
            && s.set_write_timeout(Some(std::time::Duration::from_secs(2))).is_ok()
            && s.write_all(line.as_bytes()).is_ok();
        let _ = s.set_nonblocking(true);
        if !ok {
            eprintln!("omabar: risposta al client non riuscita");
        }
    }
}
