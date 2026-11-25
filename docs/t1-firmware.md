# Firmware del T1, guardia e disco tutto per Linux

## Dove sta il firmware [F]

Il T1 non ha firmware in ROM. A ogni accensione il firmware EFI del Mac carica dalla partizione EFI di Apple:

- `EFI/APPLE/EMBEDDEDOS/combined.memboot` (~30 MB);
- `FDRData`;
- `version.plist` (su questo Mac la versione è `910`).

Senza questi file il T1 compare come `05ac:1281` (recovery) invece di `05ac:8600`, e Touch Bar, webcam, Touch ID e
sensore di luce non funzionano. macOS li riscrive quando si avvia; senza macOS solo Internet Recovery può rimetterli.

L'utente racconta di aver perso più volte la Touch Bar dopo aver tolto macOS (anche con Boot Camp e tutto il disco a
Windows) [NV: causa sconosciuta]. Per questo c'è la guardia.

## Guardia (`config/t1-guard.sh`, servizio `macbookpro14-3-t1-guard`) [F]

Installata da `install.sh` nel passo `kernel` come `/usr/local/lib/macbookpro14-3/t1-guard.sh`. Lo stato sta in
`/var/lib/macbookpro14-3/t1-guard/`.

- `init`: prende come riferimento i file attuali, solo se il T1 funziona (`8600`). Il riferimento va in
  `EMBEDDEDOS/` e `ref.sha256`.
- `check`: il servizio lo esegue a ogni avvio.
  - Confronta i checksum e scrive una riga in `history.log`.
  - Salva un elenco di tutti i file della ESP (`manifest-*.txt`, al massimo 30), per vedere chi ci scrive.
  - Se i file mancano o sono rovinati li rimette: scrive in un `.tmp`, poi `mv`, poi verifica. A quel punto serve uno
    spegnimento completo.
  - Se sono cambiati ma il T1 funziona (aggiornamento legittimo), i nuovi diventano il riferimento.
- `restore` rimette subito i file; `status` mostra lo stato.
- MacBook Manager legge `last.json` (Touch ID → *Firmware del T1*).
- Se la ESP è già montata in scrittura (per esempio `/boot/efi`), un montaggio in sola lettura viene rifiutato con
  l'avviso "would change RO state", che esce su stdout. Guardia e `backup-esp.sh` usano allora il modo già in uso.

**Ripristino a mano.** Serve se la partizione EFI di Apple è sparita del tutto: la guardia allora segnala
`missing-esp`.

1. Ricrea una partizione EFI FAT32 con settori da 4 KiB.
2. Estrai `esp-files-*.tar` dal backup (`/var/backups/macbookpro14-3/`), oppure riscrivi `esp-*.img` con `dd`.
3. Controlla con `sha256sum -c esp-files-*.sha256`.
4. Spegni completamente il Mac.

## Disco tutto per Linux (25/11/2026, su questo Mac) [F]

Come partiva il Mac prima:

- Il firmware Apple avvia OpenCore (OCLP 3.0.0) dalla ESP di Apple. OpenCore ha `LauncherOption Full`: tiene una sua voce
  di avvio nel firmware. Con `RequestBootVarRouting` Linux vede le variabili `Boot*` di OpenCore, non quelle vere.
- `efi-boot-device` puntava ancora a macOS, ma non era la strada usata.
- Da OpenCore si sceglieva il GRUB su un'altra ESP.

Passi fatti, ognuno verificato prima del successivo:

1. Guardia installata e `init`.
2. GRUB installato nella ESP di Apple come `\EFI\GRUB\grubx64.efi` (con `--no-nvram`), più `.contentDetails` per il nome
   nel menu. In `config.plist` di OpenCore, `BlessOverride` si è aggiunto `\EFI\GRUB\grubx64.efi`.
3. `/boot/efi` spostato sulla ESP di Apple, con `noauto,x-systemd.automount` e passo fsck `0`: niente fsck che "ripara"
   da solo i file del T1.
4. Riavvio di prova: `LoaderDevicePartUUID` è quello della ESP di Apple.
5. Riserva: il bootstrap di OpenCore (`System/Library/CoreServices/boot.efi`, 24 KB, carica `EFI\OC\OpenCore.efi`) copiato
   anche in `EFI/BOOT/BOOTX64.EFI`. Riavvio con ⌥ → EFI Boot → OpenCore.
6. Cancellate p2 (macOS), p3 e p6 (vecchie ESP di Linux); COSLIVE tenuta. La ESP di Apple è passata da 300 a 512 MiB così:
   - copia di tutti i file (665) con checksum;
   - partizione ricreata con lo stesso inizio, PARTUUID e nome;
   - `mkfs.fat -F 32 -S 4096 -s 1 -n EFI -i 5F6617ED`;
   - file rimessi e riverificati.
7. Nuova partizione da 354 GiB al posto di macOS, aggiunta a btrfs con `btrfs device add`: Linux è passato da 104 a
   458 GiB. L'initramfs con systemd contiene `64-btrfs.rules`, e btrfs è compilato dentro il kernel.

Gli script usati sono in `/var/backups/macbookpro14-3/disco-intero/` (`fase0.sh`, `fase1-cancella.sh`, con il registro).
Contengono i settori di questo disco: non sono da riusare così come sono.

[NV] La voce di avvio di OpenCore nel firmware contiene la dimensione vecchia della ESP. Al primo avvio dopo
l'ingrandimento ci si aspetta che il Mac usi la riserva `EFI/BOOT/BOOTX64.EFI` e che OpenCore ricrei la voce. Da
confermare dopo il riavvio. GRUB legge `/boot` da un btrfs su due dispositivi: da confermare dopo il prossimo
aggiornamento del kernel.
