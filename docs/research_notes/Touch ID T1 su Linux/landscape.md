# Touch ID sui MacBook Pro con T1 sotto Linux: chi altro ci lavora (2024 - novembre 2026)

Note di ricerca del 24/11/2026. Etichette: **[F]** fatto con link alla fonte, **[I]** inferenza mia,
**[NV]** non verificato. Le fonti GitHub sono state lette via API (`gh`) il 24/11/2026: stelle, date e
stato delle issue possono cambiare. T1Bridge (standardagents/t1bridge) compare solo dove altri ne parlano o
dove serve per capire un vicolo cieco.

Contesto della repo dell'utente (letta solo come dati): `DriftDeV/apple_biometrics_linuix` ha uno scheletro
di modulo DKMS (`apple_t1_touchid.c`), uno script PyUSB che passa il T1 alla configurazione 2 e reclama
l'interfaccia 7 (vendor `ff/f9/11`, bulk `0x05` OUT / `0x88` IN), un'analisi Ghidra di `biometrickitd`
di macOS 13.6 (BridgeXPC, `com.apple.BiometricKitBridge`) e catture macOS della porta TCP 61500 sul
collegamento NCM del T1.

## 1. Progetti GitHub indipendenti su Touch ID T1, bridgeOS, NCM/XPC, libfprint

### Takeaway
Nel 2026 è nato un piccolo ecosistema attorno a T1Bridge: quasi tutto il lavoro "Touch ID T1" indipendente
è **satellite** (recovery del firmware, packaging per altre distro, port, segnalazioni) e non un'implementazione
alternativa. L'unico altro tentativo autonomo trovato (gavinmclelland) si è fermato su un vicolo cieco;
la repo dell'utente è citata da T1Bridge come progetto "scheletro" senza operazioni funzionanti.

### Cited Findings
- **niconistal/t1-revive** (MIT, 10 stelle, aggiornata il 23/11/2026): rigenera da Linux, senza macOS, i dati
  firmware del T1 (`EFI/APPLE/EMBEDDEDOS`) quando l'installer Linux ha cancellato la ESP; usa il protocollo di
  restore EmbeddedOS di Apple con libimobiledevice patchato, il chip scarica dai server Apple i propri dati di
  fabbrica (FDR) firmati e un'immagine di boot personalizzata; dopo, "t1bridge provides the Touch Bar, the camera
  and Touch ID" — [README t1-revive](https://github.com/niconistal/t1-revive) [F]
  - Fork di supporto pubblicati il 15/09/2026: `usbmuxd-t1`, `libirecovery-t1`, `idevicerestore-t1`
    ("with Apple T1 (iBridge1,1) support") — [usbmuxd-t1](https://github.com/niconistal/usbmuxd-t1),
    [libirecovery-t1](https://github.com/niconistal/libirecovery-t1),
    [idevicerestore-t1](https://github.com/niconistal/idevicerestore-t1) [F]
  - Tabella "Tested": MacBookPro14,3 del maintainer, restore 03/09/2026, Touch ID 06/09/2026, "persists across
    reboot; existing enrolment survives regeneration"; poi 14,2, 13,3 e due 13,2 di tester (sei macchine). Una
    14,3 (issue #7) ha un set ricostruito che il firmware non carica a freddo, problema precedente al tool —
    [README t1-revive](https://github.com/niconistal/t1-revive) [F]
  - Avvertenze: scrive nuovi dati di fabbrica nel chip, nessun "undo" senza una copia di `EFI/APPLE`; dipende dai
    server di firma Apple; non chiama mai il metodo ACPI `SOCW`, l'unico reset usato è `FRST` —
    [README t1-revive](https://github.com/niconistal/t1-revive) [F]
- **nonderbe/t1bridge-ubuntu**: packaging di T1Bridge per Ubuntu 26.04, provato su MacBookPro14,2 (Touch Bar anche
  sulla schermata di login GNOME, impronta per `sudo` e Polkit); login e blocco schermo tenuti volutamente fuori dal
  lettore "because of a reported Secure Enclave hang"; sospensione ancora in prova — post di nonderbe del 07/11/2026
  su [Ubuntu Discourse](https://discourse.ubuntu.com/t/touch-id-fingerprint-on-2016-2017-macbook-pros-with-touch-bar-apple-t1-under-ubuntu-26-04/91232)
  e note di port in [t1bridge #62](https://github.com/standardagents/t1bridge/issues/62) [F]
  (nonderbe è lo stesso autore del branch `t1-fixes` di apple-ibridge usato da questa repo, vedi `AGENTS.md`.)
- **gavinmclelland/omarchy-macbookpro14-3, issue #20** (01/09/2026): tentativo autonomo di Touch ID sul 14,3 tramite
  "BridgeXPC + KernelRelay"; ha trovato che `KernelRelayHost.kext` di OCLP si aggancia a `05ac` classe `0xff`
  sottoclasse `0xf9` protocollo `0x11` = **configurazione 2, interfaccia 7** (bulk OUT `0x05`, IN `0x88`); la config 1
  non la espone. Un `SET_CONFIGURATION(2)` a caldo ha bloccato il processo in stato D; conclusione dell'autore:
  "That path is closed. Do not retry." Le richieste vendor su EP0 in config 1 rispondono PIPE (-9) —
  [issue #20](https://github.com/gavinmclelland/omarchy-macbookpro14-3/issues/20) [F]
- **heymaaz/mbp-t1-touchbar** (il README clona `Seborider/mbp-t1-touchbar`): Touch Bar illuminata con `appletbdrm` +
  `tiny-dfr` + `hid-multitouch`, "four lines" di patch; tabella delle tre configurazioni USB del T1 con config 2
  interfaccia 7 = "vendor ff/f9/11 (Secure Enclave)"; afferma che le catture smentiscono l'ipotesi che l'input della
  Touch Bar passi su NCM: "The NCM link carries Apple Pay and MobileGestalt, not input". Non fa Touch ID —
  [README heymaaz/mbp-t1-touchbar](https://github.com/heymaaz/mbp-t1-touchbar) [F]. heymaaz ha anche proposto un
  pacchetto DKMS NCM separato a T1Bridge — [t1bridge #56](https://github.com/standardagents/t1bridge/issues/56) [F]
- **seatrips/macbook-pro-t1-touchbar-linux** (guida Omarchy, 14,3): confronta T1Bridge (Touch ID via fprintd: sì) con
  **creolben/macbook-t1-touchbar** (apple-ibridge di Ronald Tschalär patchato via DKMS: Touch ID no) e consiglia
  T1Bridge "Want Touch ID? Use t1bridge" —
  [README seatrips](https://github.com/seatrips/macbook-pro-t1-touchbar-linux) [F]
- **mihneadevries**: repo pubbliche solo per sospensione e Wi-Fi del 14,3 (`mbp14-3-linux-sleep-fix`,
  `mbp14-3-linux-wifi-fix`, aggiornate il 22/11/2026); nessuna repo Touch ID trovata —
  [mbp14-3-linux-sleep-fix](https://github.com/mihneadevries/mbp14-3-linux-sleep-fix) [F]. Secondo
  `docs/t1bridge.md` di questa repo, le sue note hanno valutato T1Bridge senza installarlo [F, fonte interna].
- **T1Bridge cita la repo dell'utente** fra i "newer Linux projects": "targets T1. Its inspected kernel driver
  registers/probes USB and leaves interface selection and cleanup as TODOs. It provides no signing operation" —
  [secure-enclave-key-services.md](https://github.com/standardagents/t1bridge/blob/main/docs/secure-enclave-key-services.md) [F]
- Altri progetti Touch ID Linux citati lì, **non T1**: `ELI3GANT/open-touchid-linux` (M1: vede gli endpoint SEP,
  autenticazione non disponibile), `apstrand/m2-air-touchid` (M2: driver si aggancia, nessuna risposta SEP) —
  [secure-enclave-key-services.md](https://github.com/standardagents/t1bridge/blob/main/docs/secure-enclave-key-services.md) [F]
- **T2, per contrasto**: `macintog/t2touch` (Touch ID via fprintd su T2, riferimento MacBookPro16,1, "early proof of
  concept"); avverte di non installarlo su Mac con macOS: dopo l'uso, macOS ha rimosso le impronte e sostituito keybag
  e portachiavi di login — [README t2touch](https://github.com/macintog/t2touch),
  [issue #16](https://github.com/macintog/t2touch/issues/16) [F]. Fork `nichols2124/TouchID-linux` (14/11/2026) con
  correzioni per niri e kernel 7.3 — [README](https://github.com/nichols2124/TouchID-linux) [F]
- **t2linux wiki**: Touch ID T2 solo su Ubuntu/Debian con il pacchetto `t2-touchid` (André Eikmeyer, progetto
  KaiT2en); usabili solo le dita registrate in macOS; smette dopo spegnimento forzato, kernel panic o a volte
  sospensione finché non si riavvia macOS. Il T1 non è menzionato — [t2linux wiki: Touch ID](https://wiki.t2linux.org/guides/touchid/) [F]
- **Asahi Linux** (Apple Silicon): nella tabella M1 SEP è "WIP" e TouchID "TBA" —
  [Asahi docs, m1.md](https://github.com/AsahiLinux/docs/blob/main/docs/platform/feature-support/m1.md) [F]; il driver
  SEP del kernel Asahi "identifies itself as a stub and implements no key service" secondo la revisione di T1Bridge —
  [secure-enclave-key-services.md](https://github.com/standardagents/t1bridge/blob/main/docs/secure-enclave-key-services.md) [F]
- **roadrunner2/macbook12-spi-driver**: nessuna issue su Touch ID/impronta (la ricerca restituisce solo issue su
  tastiera, Touch Bar e kernel) — [ricerca issue](https://github.com/roadrunner2/macbook12-spi-driver/issues?q=touch+id) [F]
- Lavoro storico (pre-2024): la tabella di Dunedan/mbp-2016-linux segna Touch ID "not working" su 13,2/13,3/14,2/14,3
  e descrive l'iBridge `05ac:8600` come interfaccia al T1 "running iOS" che dà accesso a ALS, camera, Touch Bar e
  Touch ID, con firmware sulla ESP (`05ac:1281` = recovery se manca) —
  [README mbp-2016-linux](https://github.com/Dunedan/mbp-2016-linux) [F]

### Inferences
- [I] Non esiste un secondo progetto che implementi Touch ID T1 indipendentemente da T1Bridge. Il "mercato" è:
  T1Bridge (implementazione), t1-revive (prerequisito firmware), packaging (Ubuntu, Fedora via issue), guide Omarchy.
- [I] La repo dell'utente è allo stadio a cui gavinmclelland si è fermato (interfaccia 7 individuata, nessun protocollo).
  T1Bridge ha già superato quello stadio con un'implementazione completa (keybag, relay, broker, xART, libfprint/fprintd).
- [I] La porta **TCP 61500** catturata dall'utente è, secondo T1Bridge, il servizio **xART** che *l'host* espone al T1
  (il T1 si connette in ingresso, IPv6, sul link NCM) per conservare "one opaque anti-replay record for BridgeOS" —
  [architecture.md](https://github.com/standardagents/t1bridge/blob/main/docs/architecture.md),
  [README T1Bridge, passo 4](https://github.com/standardagents/t1bridge) [F per la funzione della porta]. Quindi le
  catture dell'utente riguardano l'archiviazione anti-replay, non il canale dei comandi biometrici; quel canale in
  T1Bridge è il SEP via `usbfs` sull'interfaccia 7 (BridgeXPC) — [architecture.md](https://github.com/standardagents/t1bridge/blob/main/docs/architecture.md) [F/I].

### Gaps
- Libfprint GitLab: non ho consultato il tracker; non risulta un driver Apple upstream, ma non l'ho verificato [NV].
  T1Bridge distribuisce libfprint/fprintd propri (`libfprint-t1bridge`, `fprintd-t1bridge`) —
  [t1bridge #2](https://github.com/standardagents/t1bridge/issues/2) [F].
- Non ho trovato repo di mihneadevries dedicate al Touch ID né note pubbliche oltre a sospensione/Wi-Fi.
- La ricerca GitHub per "T1 touch id", "bridgeos touchid", "remotexpc t1" non restituisce altro: possibile che esistano
  repo con nomi diversi o private.

## 2. Community: Reddit, Hacker News, Phoronix, forum, segnalazioni

### Takeaway
La discussione pubblica vive quasi tutta nelle **issue di T1Bridge** (72 al 23/11/2026) e in un post su Ubuntu
Discourse. Non ho trovato articoli Phoronix né thread Reddit/HN su Touch ID T1 nel 2024-2026. I risultati
pratici: enrollment e verifica confermati su tutti e quattro i modelli da più tester, con problemi ricorrenti
(firewall xART, bootstrap del keybag, sospensione, calibrazione dopo recovery online).

### Cited Findings
- Conferme di funzionamento: 13,2 su Omarchy ([#5](https://github.com/standardagents/t1bridge/issues/5)), 13,3 su
  Fedora 45 ([#59](https://github.com/standardagents/t1bridge/issues/59), [#66](https://github.com/standardagents/t1bridge/issues/66)),
  14,2 su Ubuntu 26.04 ([#62](https://github.com/standardagents/t1bridge/issues/62)) [F]
- **MacBookPro14,3, issue #2** (06/09/2026, due macchine): stack "ready" ma `START_ENROLLMENT` rifiutato dal SEP con
  status 1; il segnalante ha misurato `sks_lock_state=0x15`; il maintainer: "SKS=0x15 is not yet a confirmed cause".
  Chiusa; il README di T1Bridge oggi dice per il 14,3 "Enrollment confirmed after scoped xART firewall setup" —
  [#2](https://github.com/standardagents/t1bridge/issues/2), [README](https://github.com/standardagents/t1bridge) [F]
- 14,3 con dati rigenerati da t1-revive: primo enrollment fallito per "prepare device keybag failed", riuscito dopo
  `systemctl restart t1-touchid-auth.service` (6 tocchi) — commento di lecstor in
  [#29](https://github.com/standardagents/t1bridge/issues/29) [F]; il caso originale 13,3 (errore dopo ~23 ms) resta aperto [F]
- 14,2 su Arch, #57 (28/10/2026): dopo due sospensioni Touch ID fallisce sempre (`LoadMaster` 726, poi
  `Policy status 1`), anche dopo avvio a freddo; causa trovata dall'utente: `ufw` bloccava la porta 61500 sul link T1;
  dopo la regola resta un'identità "orfana" (`enroll-duplicate`) — [#57](https://github.com/standardagents/t1bridge/issues/57) [F]
- 13,3 su Ubuntu, #46: dopo `machine-data recover --online` l'enrollment fallisce a `LOAD_CALIBRATION (0x20)` con
  codici 302/28 — [#46](https://github.com/standardagents/t1bridge/issues/46) [F]
- 14,3 su CachyOS (`7.3.4-1-cachyos`), #69 (19/11/2026): recovery nativa completata dopo due correzioni (CA radice
  Apple assente nel bundle di Arch per `gs.apple.com`; race sullo StatusMsg finale) — [#69](https://github.com/standardagents/t1bridge/issues/69) [F]
- 14,3, #68 (12/11/2026): sospensione dell'host funziona dopo correzioni di piattaforma; il pannello della Touch Bar
  richiede la coppia ACPI `ASOC.SOCW` sleep/wake — [#68](https://github.com/standardagents/t1bridge/issues/68) [F, solo titolo letto]
- Ubuntu Discourse, nonderbe 07/11/2026: nessuna risposta visibile al momento della lettura —
  [thread](https://discourse.ubuntu.com/t/touch-id-fingerprint-on-2016-2017-macbook-pros-with-touch-bar-apple-t1-under-ubuntu-26-04/91232) [F]
- Ricerca web "t1bridge Touch ID Linux Hacker News OR Phoronix OR reddit": nessun risultato pertinente [F, esito di ricerca]

### Inferences
- [I] I problemi aperti sono di **robustezza e stato** (keybag, relay, xART, sospensione, dati da recovery), non di
  protocollo: sono il tipo di contributo dove un tester con un 14,3 e competenze di analisi del traffico ha più valore.
- [I] Su questa macchina CachyOS + kernel 7.3 + clang esiste già un precedente (#69) di T1Bridge compilato da sorgente.

### Gaps
- Reddit (r/linux, r/archlinux, r/MacOS, r/linuxhardware), HN e Phoronix: nessun risultato trovato con la ricerca web;
  non ho cercato direttamente nei siti (possibile copertura mancata) [NV].
- Il video del 26/08/2026 di @0xBOYD (Touch ID su Omarchy) è citato solo da un riassunto di ricerca, non verificato [NV].

## 3. Windows / Boot Camp: Apple fornisce Touch ID su T1?

### Takeaway
No, secondo tutte le fonti trovate (solo forum, nessuna pagina Apple ufficiale): i driver Boot Camp non portano
Touch ID su Windows nei Mac T1. Nessun driver Windows Hello di terze parti esiste; la richiesta è arrivata a
T1Bridge il 23/11/2026 senza risposta.

### Cited Findings
- Apple Community (2018): "there are no Bootcamp drivers that support TouchID functionality on Windows" (risposta
  segnata come migliore) — [discussions.apple.com 8615076](https://discussions.apple.com/thread/8615076) [F, fonte forum]
- MacRumors (2017-2018), MBP 15" 2017: Touch ID non funziona in Windows via Boot Camp —
  [MacRumors](https://forums.macrumors.com/threads/touch-id-on-macbook-pro-15in-2017-model-and-touch-bar-in-windows.2122614) [F, fonte forum]
- In Boot Camp la Touch Bar mostra tasti funzione/media; segnalazioni frequenti di barra spenta risolte reinstallando
  il software di supporto Boot Camp — [Apple Community 7959957](https://discussions.apple.com/thread/7959957),
  [Apple Community 8332052](https://discussions.apple.com/thread/8332052) [F, fonti forum]
- Richiesta "Windows Hello driver for Apple T1 Touch ID" aperta su T1Bridge il 23/11/2026, nessuna risposta —
  [t1bridge #72](https://github.com/standardagents/t1bridge/issues/72) [F]
- Parallels porta Touch ID nelle VM Windows (ma tramite macOS host, non un driver per il sensore) —
  [Parallels KB 129870](https://kb.parallels.com/en/129870) [F]; non pertinente per il T1 in Boot Camp [I]

### Inferences
- [I] Poiché Apple non ha mai scritto il lato host Windows del protocollo biometrico T1, un ramo "implementazione
  Windows" non può partire da driver Apple da analizzare: dovrebbe portare l'intera pila T1Bridge (config 2, NCM,
  xART, keybag, SEP) su Windows + WinBio. È un progetto più grande di quello Linux.
- [I] Il file `.inf`/driver Boot Camp della Touch Bar potrebbe comunque documentare quale configurazione USB del T1
  usa Windows [NV, non verificato].

### Gaps
- Nessuna documentazione Apple ufficiale trovata; non ho estratto né letto i pacchetti Boot Camp 6.x per elencare i
  driver T1 esposti.

## 4. OpenCore Legacy Patcher (OCLP): come ripristina Touch ID T1 e cosa serve a Linux

### Takeaway
OCLP non reimplementa nulla: **trapianta binari Apple di macOS 13.6** (`biometrickitd`, `EmbeddedOSInstall.framework`,
parti di LocalAuthentication) nei macOS più recenti, e ha avuto bisogno di correzioni a ogni versione (14.2, 14.4,
15.2, 15.4, 15.5, 26). È utile a Linux come indicazione di **quali binari analizzare**, non come protocollo pronto.

### Cited Findings
- Patch set `T1 Security Chip` (attivo da macOS 14 Sonoma): sovrascrive `/usr/libexec/biometrickitd` da 13.6
  ("Required for Touch ID"), `nfcd`/`nfrestore_service` e librerie NFC (Apple Pay); unisce
  `EmbeddedOSInstall.framework` 13.6 ("Required for biometrickitd"), `LocalAuthentication.framework/Support/SharedUtils.framework`
  (13.6 o 13.7.1), `MechanismPlugins` 15.0 Beta 4 ("Required to add a TouchID fingerprint"), `ModulePlugins` 15.1,
  `ModuleBase.framework` 15.2; su Tahoe aggiunge `seld` e `LocalAuthenticationCore.framework` 26.0 e disattiva
  `KyberInTheSEPRegisteredKeys` —
  [t1_security.py](https://github.com/dortania/OpenCore-Legacy-Patcher/blob/main/opencore_legacy_patcher/sys_patch/patchsets/hardware/misc/t1_security.py) [F]
- Changelog: 1.0.0 "T1 chip currently unsupported in Sonoma"; 1.1.0 supporto T1 su macOS 14; 1.2.0 crash di
  `coreauthd` su 14.2 e rilevamento T1 in DFU; 1.4.0 T1 su 14.4+; 2.2.0 "Resolved T1 TouchID support on macOS Sequoia
  15.2"; 2.3.0/2.3.2 errori su 15.4 e Passwords/Autofill; 2.4.0 crash `coreautha` e Apple Pay 15.5; 3.0.0 "T1 coprocessor
  patches for macOS 26" — [CHANGELOG OCLP](https://github.com/dortania/OpenCore-Legacy-Patcher/blob/main/CHANGELOG.md) [F]
- OCLP fornisce anche `KernelRelayHost.kext`, che si aggancia all'interfaccia vendor `ff/f9/11` (config 2, interfaccia 7)
  — osservazione di gavinmclelland in [issue #20](https://github.com/gavinmclelland/omarchy-macbookpro14-3/issues/20) [F, fonte secondaria]
- La repo dell'utente ha estratto proprio `biometrickitd`, `EmbeddedOSInstall.framework` e `SharedUtils.framework` da
  13.6 e ha visto in Ghidra BridgeXPC e `com.apple.BiometricKitBridge` (journal locale, 16/04/2026) [F, fonte interna]

### Inferences
- [I] Il fatto che Apple abbia tolto il T1 da Sonoma e OCLP debba rattoppare a ogni release conferma che il lato host è
  tutto in user space macOS (daemon + framework) sopra un trasporto USB/XPC; coerente con l'approccio di T1Bridge
  (daemon Linux che parla BridgeXPC sull'interfaccia 7).
- [I] Per chi vuole contribuire a T1Bridge, l'analisi di `biometrickitd`/`EmbeddedOSInstall` 13.6 è utile soprattutto
  sui punti ancora aperti: semantica dei codici di stato Mesa (302/28 in #46), contratti di chiave SEP (#23), ripristino
  dopo sospensione (#18, #57).

### Gaps
- Nessuna documentazione OCLP che descriva il protocollo; solo l'elenco dei file. Non ho letto le discussioni OCLP sui
  singoli bug T1.

## 5. Vicoli ciechi documentati e cosa ha smentito T1Bridge

### Takeaway
Il vecchio consenso "Touch ID impossibile su Linux senza pairing col SEP / senza macOS" è **smentito nella pratica**
per il T1: T1Bridge registra e verifica impronte da Linux usando i dati FDR della macchina, e t1-revive li rigenera
anche senza macOS. Restano vicoli ciechi reali: cambio di configurazione USB a caldo, dati presi da un altro Mac,
servizi di chiave SEP generici, coesistenza con lo stack in config 1, sospensione.

### Cited Findings
- **Smentito**: "Touch ID not working" (stato storico, Dunedan) → T1Bridge: "Touch ID enrollment, matching and deletion
  | 🟢 Available | Standard fprintd tools; up to three enrolled fingers for one Linux owner" —
  [README mbp-2016-linux](https://github.com/Dunedan/mbp-2016-linux), [README T1Bridge](https://github.com/standardagents/t1bridge) [F]
- **Smentito in parte**: "serve macOS / il pairing di fabbrica". Serve l'`EFI/APPLE/EMBEDDEDOS/FDRData` *di questo Mac*
  (non di un altro), ma può essere rigenerato dai server Apple con t1-revive — [Ubuntu Discourse](https://discourse.ubuntu.com/t/touch-id-fingerprint-on-2016-2017-macbook-pros-with-touch-bar-apple-t1-under-ubuntu-26-04/91232),
  [README t1-revive](https://github.com/niconistal/t1-revive) [F]. Il keybag è nuovo e di proprietà di Linux
  ("fresh Linux-owned keybag (handle -501) with a SEP-hardware-generated secret") — [#2](https://github.com/standardagents/t1bridge/issues/2) [F]
- **Smentito**: "config 1 e config 2 si escludono, niente display". Config 2 contiene display, digitizer, NCM e SEP —
  [heymaaz/mbp-t1-touchbar](https://github.com/heymaaz/mbp-t1-touchbar) [F]
- **Vicolo cieco confermato**: cambiare a caldo da config 1 a config 2 → processo bloccato nel kernel USB (14,3) —
  [gavinmclelland #20](https://github.com/gavinmclelland/omarchy-macbookpro14-3/issues/20) [F]. T1Bridge seleziona la
  configurazione all'enumerazione e avverte di non scambiare a caldo driver T1 concorrenti —
  [architecture.md](https://github.com/standardagents/t1bridge/blob/main/docs/architecture.md); `docs/t1bridge.md` locale [F].
  Nota: lo script PyUSB dell'utente passa a config 2 a caldo e dichiara successo (journal 16/04/2026) [F, fonte interna]:
  i due esiti divergono [C].
- **Vicolo cieco confermato**: config 1 non espone alcun canale SEP (EP0 vendor → PIPE) —
  [gavinmclelland #20](https://github.com/gavinmclelland/omarchy-macbookpro14-3/issues/20) [F]; quindi Touch ID e lo
  stack `apple-ibridge` (config 1) usato da questa repo non coesistono [I].
- **Aperto, nessuno l'ha risolto**: chiavi SEP generiche (P-256, passkey) — "T1/Linux key-service contracts remain
  unresolved"; il codice pubblico Apple (AKS) contiene solo test double —
  [t1bridge #23](https://github.com/standardagents/t1bridge/issues/23), [README](https://github.com/standardagents/t1bridge) [F]
- **Aperto**: sospensione/ripristino di tutte le funzioni T1 — [#18](https://github.com/standardagents/t1bridge/issues/18),
  [#57](https://github.com/standardagents/t1bridge/issues/57), [#68](https://github.com/standardagents/t1bridge/issues/68) [F]
- **Rischio documentato per dual boot** (su T2, non T1): l'enrollment Linux ha rimosso le impronte macOS e rotto il
  portachiavi — [t2touch #16](https://github.com/macintog/t2touch/issues/16) [F]. Per il T1 non ho trovato una
  segnalazione equivalente; T1Bridge usa un keybag Linux separato [F, #2], ma l'effetto su macOS installato accanto
  non è dimostrato [NV].

### Inferences
- [I] Continuare `apple_biometrics_linuix` come implementazione indipendente significherebbe rifare da zero ciò che
  T1Bridge ha già (config 2 all'enumerazione, NCM, xART su 61500, relay keybag, Mesa/SEP, libfprint). Il valore unico
  della repo (catture macOS di 61500, analisi di `biometrickitd` 13.6) è più utile come **contributo a T1Bridge** sui
  punti aperti: codici Mesa, sospensione, recovery, coesistenza con macOS, chiavi SEP (#23).
- [I] Un'alternativa con spazio libero: il ramo Windows (nessuno l'ha fatto; richiesta #72), ma richiede di portare
  l'intera pila, non un driver.
- [I] Per questa repo (Macbook14-3-cachyOS) la scelta resta quella di `docs/t1bridge.md`: Touch ID passa per T1Bridge
  in config 2, che oggi sostituisce lo stack Touch Bar in config 1 e mette a rischio la sospensione.

### Gaps
- Non ho trovato una dichiarazione pubblica esplicita "impossibile senza pairing SEP" datata 2024-2026 da citare; il
  consenso storico è ricostruito dalla tabella Dunedan e dai README.
- Non verificato se T1Bridge tocca lo stato biometrico di un macOS presente sulla stessa macchina.
