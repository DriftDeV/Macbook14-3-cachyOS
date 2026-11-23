# MacBookPro14,3 + CachyOS

Obiettivo: riunire in un'unica repo tutto ciò che serve (pacchetti, moduli DKMS, patch,
configurazioni, script di installazione) per usare **CachyOS** sul **MacBook Pro 14,3**
(15" 2017, Touch Bar T1, Kaby Lake, Radeon Pro 555/560, **senza chip T2**).

> ⚠️ **Stato: sperimentale e mai provato su hardware reale.** Tutto ciò che c'è qui deriva
> da una ricerca su fonti secondarie (vedi [`docs/research-report.md`](docs/research-report.md)).
> Molti repo sorgente sono piccoli, recenti, e testati su 14,2 o 13,x, non sul 14,3.
> "100% senza compromessi" **non è raggiungibile oggi**: vedi la tabella sotto.

## Stato per dispositivo

| Dispositivo | Come | Stato |
|---|---|---|
| Tastiera, trackpad | `applespi` (kernel) + quirk libinput + initramfs | funziona (fonti) |
| Touch Bar (tasti) | DKMS da fork (`config/sources.conf`) | parziale, fragile ad ogni kernel |
| ALS / luminosità auto | `apple-ib-als` + `iio-sensor-proxy` | da verificare |
| Audio | driver CS8409 (fork dnlbtz) | funziona con un bug noto al boot; microfono debole |
| Wi-Fi | `brcmfmac` + file NVRAM (**da fornire tu**) | 5 GHz solo con NVRAM |
| Bluetooth | kernel | funziona (fonti), chip non verificato |
| Webcam | `uvcvideo` (**non** `facetimehd`) | dipende dal firmware T1 nell'ESP |
| Thunderbolt/USB-C | kernel | funziona, niente power management |
| Sospensione | s2idle + hook (`config/sleep`) | parziale |
| Ibernazione | richiede patch `amdgpu` non upstream | **rotta** |
| dGPU Radeon | non entra in runtime suspend (~7 W a riposo) | **compromesso** |
| Touch ID, grafica Touch Bar | nessun driver Linux | **non risolvibile ora** |

Il codec audio è probabilmente **CS8409**, non CS4208; non è confermato sulla macchina.
`install-audio.sh` rifiuta di procedere se non lo rileva.

## Struttura

```
install.sh                  installazione su CachyOS già installato (--dry-run!)
macos/prepare.sh            da macOS: ridimensiona APFS, prepara il live dal disco interno
scripts/                    backup ESP, Touch Bar, audio, Wi-Fi NVRAM, d3cold, T1
config/                     mkinitcpio, libinput, sleep, systemd, modprobe, sources.conf
dkms/apple-ibridge/         dkms.conf di riserva per la Touch Bar
pkgs/                       PKGBUILD: macbookpro14-3-meta, apple-ibridge-dkms
patches/                    patch kernel/moduli (per ora vuota, vedi README)
docs/                       report di ricerca e note
```

## 1. Installare CachyOS da macOS (senza USB) — sperimentale

```bash
./macos/prepare.sh prepare --linux-gb 120          # DRY-RUN: mostra il piano
./macos/prepare.sh prepare --linux-gb 120 --execute
```

Fa: controlli (modello, alimentatore, FileVault), backup della mappa partizioni e dell'ESP
(contiene il firmware T1), download e verifica sha256 dell'ISO più recente, ridimensiona
il container APFS creando una FAT32 `COSLIVE` da 8 GB **e una partizione Linux non formattata**
con tutto il resto dello spazio (`--no-target` per lasciarlo libero), copia l'ISO e adatta
`grub.cfg`. Poi riavvii con **Option (⌥)** e scegli "EFI Boot". L'installazione vera la fai
dal live con Calamares (partizionamento manuale): formatta la partizione Linux e montala su `/`.

Limiti noti: non esiste un esempio documentato di questa procedura su Mac Intel; il
bootloader dell'ISO potrebbe richiedere l'estrazione di `efiboot.img`; la tastiera interna
nel live non è garantita (tieni una tastiera USB-C a portata). **Fai un backup Time Machine.**
Annullare: `./macos/prepare.sh rollback --execute`.

## 2. Dopo l'installazione di CachyOS

```bash
git clone https://github.com/DriftDeV/Macbook14-3-cachyOS && cd Macbook14-3-cachyOS
sudo ./install.sh --dry-run
sudo ./install.sh --wifi-nvram /percorso/nvram.txt
```

Il file NVRAM del BCM43602 non è incluso (licenza poco chiara): estrailo da macOS/Boot Camp.
Bootloader consigliati su EFI Apple: **rEFInd o GRUB con `--removable`**.

## Cose ancora da fare

- Pinnare `TOUCHBAR_REF` / `AUDIO_REF` a commit verificati su un 14,3.
- Integrare il filter-chain PipeWire di `dnlbtz/mbp143-audio` (struttura del repo non verificata).
- Gestire la rimozione/rescan delle porte Thunderbolt attorno alla sospensione.
- Override di `39-usbmuxd.rules` per il T1 senza rompere gli iPhone.
- PKGBUILD per il driver audio e repo pacman firmata con CI.
- Capire cosa puntava il vecchio submodule `macbook-pro-touchbar-driver` (commit `42034ae`,
  senza `.gitmodules`; rimosso perché inutilizzabile).
