# AGENTS.md — contesto per le sessioni di Claude (e altri agenti)

Leggi questo file prima di toccare la repo. Aggiornalo quando cambia qualcosa di importante.

## Scopo

Riunire in una sola repo tutto ciò che serve (pacchetti, moduli DKMS, patch, configurazioni,
script) per avere **CachyOS (Arch) il più possibile funzionante sul MacBook Pro 14,3**
(15" 2017, Touch Bar con chip **T1**, i7-7820HQ, Radeon Pro 555/560, **senza T2**).
L'utente vuole abbandonare macOS (Mac non più supportato) e punta al "100% senza compromessi".
**Non è raggiungibile oggi**: Touch ID, ibernazione, grafica della Touch Bar e il consumo della dGPU
restano limiti. Non promettere il 100%.

Obiettivo secondario: installare CachyOS **da macOS, senza chiavetta USB** (partizione live sul disco interno).

La macchina su cui lavora l'utente **è proprio un MacBookPro14,3** (macOS 15, Darwin 24.6, SIP in configurazione
personalizzata con kext signing disattivato). L'utente scrive in italiano: rispondi in italiano.

## Mappa della repo

| Percorso | Contenuto |
|---|---|
| `install.sh` | installazione su CachyOS già installato; usa sempre `--dry-run` prima |
| `macos/prepare.sh` | da macOS: backup, download ISO, ridimensiona APFS, crea `COSLIVE` + partizione Linux, estrae ISO |
| `scripts/` | `lib.sh`, `backup-esp.sh`, `install-touchbar.sh`, `install-audio.sh`, `install-wifi-nvram.sh`, `d3cold-nvme.sh`, `t1-reenumerate.sh` |
| `config/` | mkinitcpio, libinput, sleep, systemd, modprobe, `sources.conf` (sorgenti esterne, non pinnate) |
| `pkgs/`, `dkms/` | PKGBUILD (`macbookpro14-3-meta`, `apple-ibridge-dkms`) e `dkms.conf` di riserva |
| `patches/` | patch kernel/moduli: vuota, con README sulle candidate |
| `docs/` | report di ricerca e note per componente; indice in `docs/README.md` |

## Regole per chi lavora qui

1. **Sicurezza dei dischi.** `macos/prepare.sh` modifica le partizioni di questo Mac. Non lanciarlo con
   `--execute` di tua iniziativa: serve una richiesta esplicita dell'utente nella chat, backup fatto e
   alimentatore collegato. Le conferme scritte (`RIDIMENSIONA`, `ROLLBACK`) le scrive l'utente, non tu.
   Non cancellare mai la ESP di macOS (`disk0s1`): contiene il firmware T1 (Touch Bar, webcam, ALS).
2. **Onestà sullo stato.** Nulla di quanto c'è qui è stato provato su Linux o su hardware reale.
   Marca come **[F] fatto / [I] inferenza / [NV] non verificato / [C] conflitto**. Non dichiarare "risolto"
   ciò che deriva solo da fonti secondarie.
3. **Non inventare.** Nomi di moduli, branch, URL, parametri: se non sono in `docs/`, verificali o marcali [NV].
   Non scaricare/ridistribuire il file NVRAM Wi-Fi (licenza poco chiara).
4. **Niente sorgenti non fidate eseguite alla cieca.** I repo 2026 citati sono piccoli, si citano a vicenda e in
   parte sono scritti con IA: leggi il codice prima di integrarlo; pinna a un commit dopo averlo verificato.
5. **Commit/push solo su richiesta dell'utente.** Messaggi di commit con la riga `Co-Authored-By` richiesta dal sistema.
6. Mantieni gli script compatibili: `macos/prepare.sh` con **bash 3.2** (quella di macOS); gli script Linux con bash moderna.
   Controlla con `bash -n` e `shellcheck` (la CI lo fa).

## Fatti da non dimenticare (correzioni emerse dalla ricerca)

- Codec audio: con ogni probabilità **CS8409**, non CS4208. Va confermato con `grep -i cs8409` sulla macchina.
- Webcam: USB dietro l'iBridge → `uvcvideo`. **`facetimehd` non serve.**
- Il 14,3 **non ha il T2**: ignora `t2linux` e le pagine CachyOS sui T2.
- Bootloader su EFI Apple: rEFInd o GRUB `--removable`. systemd-boot e Limine sconsigliati.
- Il kernel `linux-cachyos` non ha una cartella di patch utente: preferire DKMS + header.
- L'ISO desktop più recente trovata sul mirror a fine novembre 2026 è `261122` (3,2 GB, entra in FAT32); lo script
  risolve da solo la cartella più nuova.
- Il vecchio submodule `macbook-pro-touchbar-driver` (commit `42034ae`) è stato rimosso: senza `.gitmodules` e senza commit pubblico.
- Il dry-run su questo Mac ha mostrato: container APFS `disk1` da ~500 GB, **7 snapshot locali di Time Machine**
  (il limite minimo del resize è uguale alla dimensione attuale finché non vengono eliminati).

## Stato della sessione (aggiornato il 23 novembre 2026)

- Repo pubblicata su `DriftDeV/Macbook14-3-cachyOS`, branch `main`. Le modifiche a `macos/prepare.sh` (creazione della
  partizione Linux con `diskutil addPartition ... %noformat% 0`, flag `--no-target`) possono non essere ancora in un commit.
- L'utente ha chiesto di far girare `./macos/prepare.sh prepare --linux-gb 120 --helper-gb 8 --execute` in un terminale
  (partizione live da 8 GB + 112 GB Linux, da eliminare/riusare dopo l'installazione). Al momento della scrittura
  lo script era fermo alla richiesta della password `sudo` per il backup dell'ESP.
- **Backup Time Machine non verificato**: il disco "Sandisk" non era montato. L'utente è stato avvisato.
- **Per sapere cosa è successo davvero**, non fidarti di questo file: controlla `diskutil list` e `ls ~/cachyos-mbp143/`.
- La procedura `prepare.sh` è **mai stata completata né provata**: non è noto se la ISO estratta si avvia dal disco interno
  (possibili problemi: bootloader dentro `efiboot.img`, righe di ricerca diverse in `grub.cfg`, blocco del kernel da FAT32).
  Tieni a portata una tastiera USB-C: `applespi` nel live non è garantito.

## Da fare (priorità)

1. Verificare l'avvio live dal disco interno e correggere `prepare.sh` secondo quanto emerge.
2. Pinnare `TOUCHBAR_REF` e `AUDIO_REF` a commit funzionanti su un 14,3 (provare nonderbe, F13+PR, AJ-dev-i60).
3. Filter-chain PipeWire di `dnlbtz/mbp143-audio`; gestione porte Thunderbolt in sospensione; override `39-usbmuxd.rules`
   senza rompere gli iPhone; PKGBUILD per l'audio; repo pacman firmata con CI.
4. Ricerca kernel: patch `amdgpu` "reset VI ASIC on Apple boards" (ibernazione), runtime PM della dGPU.

## Memoria e contesto

- La ricerca completa è in `docs/` (report + 7 note): **leggila invece di rifare le ricerche**. Aggiornala se scopri qualcosa.
- Questa sessione ha anche salvato una nota di progetto nella memoria persistente di Claude Code (progetto `git`),
  che rimanda a questo file.
