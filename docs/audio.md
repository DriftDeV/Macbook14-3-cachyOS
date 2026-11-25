# Audio su MacBookPro14,3: risultati verificati

Data: 23 novembre 2026. Macchina: MacBookPro14,3, CachyOS, kernel `7.3.5-2-cachyos` (clang + ThinLTO),
PipeWire 1.6.11, WirePlumber 0.5.19, KDE Plasma 6.8. Tag come in [`README.md`](README.md).

## Hardware [F]

- Scheda `HDA Intel PCH` (`00:1f.3`), codec **Cirrus Logic CS8409** (`0x10138409`), subsystem `0x106b3900`.
  Confermato sulla macchina: **non** è un CS4208.
- Col driver giusto il codec si presenta come `CS8409/CS42L83` (il CS42L83 gestisce il jack cuffie/microfono).
- Seconda scheda `HDA ATI HDMI` (Radeon, `01:00.1`): audio HDMI/DP, gestito dal kernel.

## Senza driver [F]

Il modulo del kernel `snd-hda-codec-cs8409` riconosce il codec ma lo configura in modo generico
(non conosce gli amplificatori Apple): PipeWire mostra "Audio interno" ma gli speaker restano muti.

## Driver scelto

- `davidjo/snd_hda_macbookpro` (CS8409 + amplificatori Apple) nel fork **`dnlbtz/snd_hda_macbookpro`, branch
  `offlineDkmsDeb`, commit `11febcf`** (2026-11-09) = master davidjo + 5 correzioni scritte su un 14,3:
  ripresa dopo S3/ibernazione (ripete il setup se il codec ha perso i GPIO), microfono cuffie a 4 poli,
  "Capture Source" che sceglie fra microfono interno e cuffie, interrupt, build DKMS senza rete.
- [F] I file del kernel inclusi nel fork (`kernel/7.3/sound/hda/...`, 8 file) sono **identici** a Linux v7.3
  (confronto byte per byte con `torvalds/linux` tag `v7.3`). Nei commit dnlbtz nessuna chiamata a file, rete o programmi esterni.
- [F] Patch nostra [`../patches/audio/`](../patches/audio/): `LLVM=1` automatico nel `Makefile` (gcc rifiuta le opzioni
  del kernel clang: `-fms-anonymous-structs`, `-mstack-alignment`). Due warning innocui (fall-through in pin sense, label C23).
- [F] Il fork compila solo per le serie di kernel che contiene (oggi `7.3`): `scripts/install-audio.sh` salta le altre
  (l'LTS `6.18` resta senza driver: speaker muti su quel kernel). Per aggiungere una serie: `./vendorKernel 6.18` nel fork.

## Prove [F]

| Prova | Risultato |
|---|---|
| Modulo sostituito al volo (unbind `00:1f.3`, rmmod, insmod, bind) | `GPIO mask 0x27 direction 0x22` dopo il boot setup; ingressi Mic Jack e Headphone Jack creati |
| Speaker (`speaker-test -c 2 -t wav`) | **funzionano**, sinistra e destra |
| Microfono interno | **funziona** (livello in Impostazioni → Audio) |
| Cuffie (inserimento/rimozione) | **funzionano**, l'audio passa alle cuffie e torna agli speaker; il driver registra plug/unplug/tasto |
| Microfono delle cuffie | **funziona** |
| Installazione DKMS (`scripts/install-audio.sh`) | `snd_hda_macbookpro/0.1` installato in `updates/dkms` per 7.3.5; modulo originale archiviato da DKMS |

## Da verificare [NV]

- Avvio a freddo con il modulo DKMS (le prove sopra sono con il modulo caricato a mano, stesso codice).
- Bug noto 14,3 (davidjo #80, #134): dopo alcuni avvii il codec ha subsystem id `0x10138409` invece di `0x106b3900`
  e non esce audio. Rimedi riportati: reset NVRAM, avvio da Option, reinstallare il bootloader. Controllo:
  `grep Subsystem /proc/asound/card*/codec#0`.
- Audio dopo la sospensione s2idle (il fork ha la correzione per S3/ibernazione; in s2idle il codec dovrebbe restare alimentato).
- Filter-chain PipeWire `dnlbtz/mbp143-audio`: valutato e installato il 25/11/2026, vedi sotto.
- Volume del microfono basso (segnalato nel README davidjo).

## Altoparlanti: tweeter, woofer e DSP (25/11/2026)

**Hardware**
- 4 altoparlanti, ognuno con il suo amplificatore: tweeter e woofer a sinistra e a destra [F dal README davidjo, che cita
  i nomi nei layout di `AppleHDA.kext`; un utente iFixit conferma tweeter e woofer in ogni gruppo altoparlante].
- Il CS8409 non elabora niente: converte lo stream in TDM a 4 canali verso gli amplificatori (pin 0x24 = canali 1-2,
  0x25 = canali 3-4), che fanno la conversione D/A. Programmazione degli amplificatori fissa, niente volume né filtri in
  hardware (`NOTES.md` di davidjo). Per `106b3900` il driver usa la sequenza `real_config` [I: MAX98706].
- La DSP di macOS è software, in CoreAudio: il layout del 14,3 ha una catena (`Mozart`, `DualBand`, `Loudness`,
  `BuzzKill`, `ControlFreak`, protezione termica) solo sul percorso degli altoparlanti.

**Senza DSP [F]**: profilo "Stereo analogico" (2 canali, 44,1 kHz); il driver copia lo stereo su tutte e due le coppie,
quindi tweeter e woofer ricevono lo stesso segnale a banda piena, senza crossover né EQ: suono sottile. [I] I tweeter
ricevono anche i bassi, senza protezione termica. La scheda offre già il profilo "Surround analogico 4.0".

**`dnlbtz/mbp143-audio` [F]**, commit `aa4d8c1` (v1.0.0), pacchetto da [`../pkgs/mbp143-audio/`](../pkgs/mbp143-audio/)
(PKGBUILD originale con sorgente fissata al commit e `pkgver` fisso):
- Codice letto: Makefile/PKGBUILD copiano solo file; regole WirePlumber legate a `HDA:10138409,106b3900`; script Lua solo
  con l'API di WirePlumber (profilo che segue il jack, volume grezzo a 0 dB, +35 dB al microfono cuffie); plugin Rust
  senza file/rete/processi (unico `unsafe`: flush-to-zero di MXCSR, ripristinato); dipendenze `lv2` 0.6.0 da crates.io con
  `Cargo.lock`. Grafo: volume iniziale 12,5 %, un guadagno fisso +1,5 dB, 66 biquad dai coefficienti del layout Apple,
  crossover ~1 kHz, FL/FR = tweeter, RL/RR = woofer (stesso ordine del driver). 13/13 test superati.
- Installato con `sudo pacman -U`, poi `systemctl --user restart pipewire pipewire-pulse wireplumber`. Profilo 4.0,
  "MacBook Pro 14,3 Speakers" predefinito, uscita grezza nascosta. Verificato con `pw-link`/`pw-top`: app →
  `audio_effect.mbp143-speakers` → `effect_output` (4 canali, ~1 ms per blocco da 512) → scheda.
- **Suono migliore**, confermato dall'utente. Attenzione: dopo il riavvio di PipeWire le app Chromium/Electron (Sidra) si
  mettono in pausa; al primo tentativo la musica non passava dal filtro e "non cambiava nulla".
- **Costo**: il grafo ha `session.suspend-timeout-seconds = 0` (non si sospende mai) e gira nel thread audio di
  WirePlumber: ~19 % di un core anche in silenzio (86 risvegli/s = 44100/512), di più con un flusso aperto (Sidra in pausa
  lo tiene aperto). Batteria a riposo: mediana 17,9 W contro 16,3 W (circa +1,5 W; misura disturbata da Sidra aperto e
  messaggi). Possibile correzione non applicata per scelta dell'utente: timeout a 5 s nel PKGBUILD (rischi [NV]: clic alla
  ripresa, modello termico che riparte freddo).
- L'ingresso predefinito era rimasto "Audio interno" (predefinito salvato prima dell'installazione), non
  `effect_output.mbp143-mic`: il microfono delle cuffie esce basso se l'app registra dalla sorgente grezza. Corretto il
  25/11 con `wpctl set-default <id di effect_output.mbp143-mic>` (WirePlumber lo salva). I due ingressi visibili sono lo
  stesso microfono: la sorgente grezza resta visibile di proposito perché porta la scelta interno/cuffie.
- Togliere: `sudo pacman -R mbp143-audio`, poi riavviare i tre servizi utente.

**bankstown, bassi psicoacustici di Asahi Linux [F] (25/11/2026)**: `chadmed/bankstown` commit `8e6f96f` (1.1.0 + fix
del sample rate zero), letto: 257 righe di Rust, solo DSP (passa-banda 20-200 Hz, saturazione con tanh per 2ª e 3ª
armonica, passa-alto, somma al segnale), dipendenze `biquad` e `lv2` da `Cargo.lock`. Pacchetto
[`../pkgs/bankstown-lv2/`](../pkgs/bankstown-lv2/) in `/usr/lib/lv2`; `pkgs/mbp143-audio` (pkgrel 2) lo inserisce con
`add-bankstown.py` all'inizio del grafo degli altoparlanti (headroom → `bassex` → passa-alto 88 Hz → resto invariato), così
vale solo per gli altoparlanti e passa da crossover, limitatori e protezione termica. Valori di Asahi per il MacBook Pro
14" M1 (`firs/j314/graph.json`: amt 1,45, sat_second 1,35, sat_third 2,25, blend 0,67, ceil/final_hp 200 Hz); il 16" usa
amt 1,65 e 125 Hz. Prova A/B dal vivo (filtro separato davanti, bypass acceso/spento): l'utente preferisce acceso; dopo
l'installazione fissa "suona bene". Regolabile dal vivo con `pw-cli s <id> Props '{ params = [ "bassex:amt" 1.65 ] }'`.

**Scheda Audio di MacBook Manager [F] (25/11/2026)**: preset (fabbrica, + bassi, + bassi intensi, notte) e regolazioni
limitate (bankstown, livello massimo e bilanciamento sul guadagno `f6` solo verso il basso, Loudness e compressori
accesi/spenti); limitatori, protezione termica, BuzzKill, crossover ed EQ non raggiungibili. Applicazione dal vivo con
`pw-cli`, salvataggio nel file di stato di WirePlumber, script Lua che riapplica alla nascita del filtro (provato con un
riavvio di WirePlumber; il caso cuffie scollegate usa lo stesso evento [I]). Dettagli in `manager/README.md`.

**Altoparlanti difettosi di questo Mac [F] (25/11/2026)**: a volume alto si interrompono il woofer sinistro e i due tweeter.
Abbassando dal vivo il guadagno `f6c0gain`/`f6c1gain` (uguale sui 4 canali, `pw-cli s <id> Props`) fino a -6 dB si
interrompono ancora; registrando l'uscita del filtro a -6 dB e volume 100 %: picchi woofer -7,5/-8,3 dBFS, tweeter
-14 dBFS, limitatori fermi. Quindi non è il segnale al massimo [I: protezione degli amplificatori sui bassi forti, o
difetto meccanico; i tweeter si interrompono insieme al woofer]. ControlFreak ha il tetto fisso a 0 dBFS nel codice
(`ceiling_db`), regolabile solo ricompilando o aggiungendo guadagni nel grafo.

**Non "riavviare gli amplificatori" con unbind/bind di `0000:00:1f.3` [F] (25/11/2026)**: il reset del collegamento HDA
riporta il subsystem del codec al valore di fabbrica `0x10138409`; il driver davidjo non attiva il percorso Apple
(`!(driver->ops && driver->ops->probe)`, probe -22, WARN del kernel), il codec passa a `snd_hda_codec_generic` (zero
uscite) e non torna indietro nemmeno scrivendo `0x106b3900` in `/sys/class/sound/hwC1D0/subsystem_id` (il kernel ricorda
`probe_id` generico: bind → ENODEV). Si ripristina solo riavviando (il firmware riscrive il subsystem). Il 23/11 la stessa
procedura con rmmod/insmod aveva funzionato [C].

**Dopo il riavvio (25/11/2026, 13:05) [F]**: codec `0x106b3900` legato al driver Apple, nessun errore I2C, profilo 4.0,
filtro attivo. Toni di prova attraverso il filtro (150 Hz → woofer, 5 kHz → tweeter, un lato per volta): l'utente sente
**solo woofer e tweeter destri**; i sinistri sono muti. Registrando `effect_output` durante i toni di sinistra il segnale
c'è (woofer sx -15,5 dBFS, tweeter sx -33,8 dBFS), quindi il software lo manda. [I] Guasto hardware del lato sinistro:
woofer e tweeter sinistri stanno nello stesso gruppo altoparlante (ricambio unico "Left Speaker" su iFixit), quindi il
sospetto è il gruppo o il suo connettore/cavo. L'utente lo considera un guasto hardware anche per macOS (non provato
in macOS). Finché il lato sinistro è muto, i contenuti solo sul canale sinistro non si sentono [I: rimedio possibile un
downmix mono davanti al filtro, non fatto]. Poco dopo, stessa prova: sentiti woofer destro e **tutti e due i tweeter**;
woofer sinistro ancora muto. Il guasto è intermittente [I: woofer sinistro, o contatto del gruppo sinistro].

## Bluetooth audio [F]

- Prova del 23/11/2026 con cuffie Nothing Ear: riproduzione OK in **A2DP con codec AAC** (PipeWire, 48 kHz).
  Profili offerti: SBC, SBC-XQ, AAC; per le chiamate HSP/HFP con mSBC (banda larga) o CVSD.
- `libldac` e `libfreeaptx` sono installati ma LDAC/aptX non compaiono: li decide il dispositivo (per LDAC di solito
  va attivato nell'app del produttore) [I].
- Il Wi-Fi era a 5 GHz: nessuna contesa con il Bluetooth, che condivide l'antenna con il Wi-Fi a 2,4 GHz.
- Profilo headset (HSP/HFP): **muto** in partenza. Il Bluetooth è un Broadcom su UART (ACPI `BCM2E7C`, `hci_uart` +
  `btbcm`, firmware della ROM: `brcm/BCM.hcd` non trovato) che manda l'audio SCO alla sua interfaccia PCM invece che
  all'host [I].
- **Correzione [F]**: comando del produttore `Write_SCO_PCM_Int_Param` (OGF 0x3F, OCF 0x001C, parametri
  `01 02 00 01 01`, routing via HCI) inviato da `scripts/bt-sco-route.py` (socket HCI grezzo, Python, niente
  `hcitool`). Il chip risponde `0x00`; da lì il profilo headset con **codec CVSD funziona** (audio e microfono),
  **mSBC resta muto** (servirebbe la modalità wideband speech del chip, non provata).
- `scripts/install-bt.sh`: servizio `macbookpro14-3-bt-sco` legato a `bluetooth.service` (aspetta che il controller sia
  acceso, poi invia il comando) + riapplicazione nell'hook di sleep. Il comando si perde a ogni reset del controller.
- WirePlumber: `config/wireplumber/51-macbookpro14-3-bluetooth.conf` (`bluez5.enable-msbc = false`, installato da
  `install-bt.sh` in `/etc/wireplumber/wireplumber.conf.d/`). Senza, il profilo `headset-head-unit` predefinito è
  mSBC, che le app (es. Discord) attivano da sole e resta muto (`link failed` di WirePlumber). Con l'opzione resta un
  solo profilo headset, con CVSD [F] (verificato su `pactl list cards`). Audio e microfono delle cuffie nel profilo
  headset confermati dall'utente il 23/11/2026.
- [NV] Se il comando sopravvive allo spegnimento/riaccensione del Bluetooth da KDE (spegnere il Bluetooth non riavvia
  `bluetooth.service`).
