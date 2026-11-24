# Stack di protocollo Touch ID sul T1 (MacBookPro14,3) e implementazione di T1Bridge

Note di ricerca, 24/11/2026. Legenda: **[F]** fatto con fonte, **[I]** inferenza, **[NV]** non verificato.
Fonte primaria per l'implementazione: checkout locale e pinnato di T1Bridge `v0.1.12`
(`81cbdf81026a16e02f0bea74735c6b029a8ffae2`) in `/home/drift/src/t1bridge`. Nulla è stato compilato o eseguito
da quel repo. Permalink usato sotto: `TB = https://github.com/standardagents/t1bridge/blob/81cbdf81026a16e02f0bea74735c6b029a8ffae2`.
Fonte secondaria: repo di ricerca dell'utente `DriftDeV/apple_biometrics_linuix` (commit `ff6bf44`, 28/04/2026), clonato
in sola lettura nello scratchpad. Ho analizzato **in sola lettura** i suoi pcapng macOS con uno script mio (stdlib Python,
`-I`, nessun codice del repo eseguito) che cerca la magic BridgeXPC e decodifica i bplist (blob opachi ridotti alla lunghezza).
Quell'analisi è indicata come "analisi pcap locale".

Schema riassuntivo (dal basso verso l'alto) **[F salvo dove indicato]**:

```
Sensore Mesa ──(AES-CCM, chiave condivisa di fabbrica; interno al T1)──> SEP del T1        [F Apple, generico]
                                                                          │
bridgeOS (14Y910 sul Mac dell'utente)  ── processi: biometrickit bridge, xartstoraged, keystore/ACM SEP
                                                                          │ USB 05ac:8600, CONFIGURAZIONE 2
  ┌───────────────────────────────┬───────────────────────────────────────┴───────────────┐
  if 4/5: CDC-NCM privato (IPv6 link-local)                        if 7: vendor bulk 0x05 OUT / 0x88 IN
  ├─ TCP host→T1 :52032  BridgeXPC → RPC bplist → performBiometricCommand("BM" 0x4d42, Mesa)
  └─ TCP T1→host :61500  BridgeXPC → dizionari xart-msg.* (xART fetch/save)        "relay" SEP: AppleKeyStore
                                                                                       (keybag) + ACM, richieste
                                                                                       "sigillate" SHA-256 non a chiave
```

## 1. Quale trasporto usa l'host per parlare con bridgeOS sul T1, ed è cifrato/autenticato?

### Takeaway
Non usbmux né RemoteXPC/HTTP2: il Touch ID del T1 passa per **due canali distinti nella configurazione USB 2**:
(a) un link **CDC-NCM privato** con IPv6 link-local su cui gira **BridgeXPC** (framing proprietario da 16 byte, HELLO JSON,
RPC in bplist) — biometria su **TCP 52032** (host→T1) e storage xART su **TCP 61500** (T1→host); (b) l'**interfaccia
vendor 7** (bulk 0x05/0x88) per il "relay" SEP con **AppleKeyStore (keybag) e ACM**. Sul lato host **non c'è TLS, pairing
né chiavi**: il traffico BridgeXPC è in chiaro (confermato sia dal codice T1Bridge sia dalle catture macOS dell'utente).
La sicurezza sta dentro il SEP (template cifrati, keybag/ACM, catacomb, anti-replay xART), non nel trasporto.

### Cited Findings
- **Configurazione USB 2 obbligatoria** [F]: `t1-cfgsel` sceglie la configurazione solo se un set di descrittori contiene in
  modo univoco display T1, CDC-NCM e SEP con i loro endpoint bulk; altrimenti `-ENODEV`. Display e NCM non esistono prima di
  questo passo — [t1-cfgsel README](https://github.com/standardagents/t1bridge/blob/81cbdf81026a16e02f0bea74735c6b029a8ffae2/kernel/t1-cfgsel/README.md); [architecture.md](https://github.com/standardagents/t1bridge/blob/81cbdf81026a16e02f0bea74735c6b029a8ffae2/docs/architecture.md#boot-and-ordering-contract).
  Il Linux di default si ferma alla configurazione 1 (HID/UVC) — osservato anche dall'utente il 16/04/2026
  ([journal.md](https://github.com/DriftDeV/apple_biometrics_linuix/blob/de211f335d68ec571adda389d04461f02e9747bc/persistent_memory/journal.md)).
- **NCM privato** [F]: la configurazione 2 espone CDC-NCM sulle interfacce 4 e 5 **senza endpoint interrupt/status**, quindi
  il `cdc_ncm` generico non si lega; T1Bridge aggiunge lo shim `apple_t1_ncm` — [apple-t1-ncm README](https://github.com/standardagents/t1bridge/blob/81cbdf81026a16e02f0bea74735c6b029a8ffae2/kernel/apple-t1-ncm/README.md).
  `xart_service.rs` fissa `APPLE_T1_NCM_CONTROL_INTERFACE = 4`, driver `apple_t1_ncm` — [xart_service.rs](https://github.com/standardagents/t1bridge/blob/81cbdf81026a16e02f0bea74735c6b029a8ffae2/crates/t1-daemons/src/xart_service.rs).
- **Indirizzi IPv6 link-local** [F]: peer bridgeOS fisso `fe80::aede:48ff:fe33:4455` (costante `BRIDGEOS_PEER` /
  `BRIDGEOS_XART_PEER`) — [live_operation.rs](https://github.com/standardagents/t1bridge/blob/81cbdf81026a16e02f0bea74735c6b029a8ffae2/crates/t1-bridge/src/live_operation.rs), [xart_service.rs](https://github.com/standardagents/t1bridge/blob/81cbdf81026a16e02f0bea74735c6b029a8ffae2/crates/t1-daemons/src/xart_service.rs).
  Nelle catture macOS dell'utente l'host è `fe80::aede:48ff:fe00:1122` e il T1 `fe80::aede:48ff:fe33:4455` (≈420 pacchetti
  per verso in `s2-enroll-register-r01.pcapng`) [F, analisi pcap locale]. `t1-ncm-ready` porta su l'interfaccia via
  rtnetlink e attende l'indirizzo link-local; nessun profilo NetworkManager, nome fisso, rotta o DNS — [architecture.md](https://github.com/standardagents/t1bridge/blob/81cbdf81026a16e02f0bea74735c6b029a8ffae2/docs/architecture.md).
- **Porta biometrica 52032** [F]: `BIOMETRIC_SERVICE_PORT: u16 = 52_032`, connessione TCP host→T1 con timeout 2 s, I/O 30 s,
  nome processo nel HELLO `t1-touchid` — [live_operation.rs](https://github.com/standardagents/t1bridge/blob/81cbdf81026a16e02f0bea74735c6b029a8ffae2/crates/t1-bridge/src/live_operation.rs). Nelle catture macOS:
  403 frame BridgeXPC per verso tra host:49156 e T1:**52032** durante l'enrollment [F, analisi pcap locale].
- **Porta xART 61500** [F]: `#define T1_XART_PORT 0xf03cu` (= 61500); l'**host ascolta**, il T1 si connette. Il listener è
  solo IPv6, legato all'indice dell'interfaccia NCM T1 scoperta dinamicamente, e rifiuta peer diversi dal T1 —
  [t1_xart_listener.h](https://github.com/standardagents/t1bridge/blob/81cbdf81026a16e02f0bea74735c6b029a8ffae2/crates/t1-daemons/c/t1_xart_listener.h); [architecture.md](https://github.com/standardagents/t1bridge/blob/81cbdf81026a16e02f0bea74735c6b029a8ffae2/docs/architecture.md). Il README
  avverte che un firewall default-deny deve permettere **in ingresso** TCP 61500 solo sul link T1 — [README.md](https://github.com/standardagents/t1bridge/blob/81cbdf81026a16e02f0bea74735c6b029a8ffae2/README.md);
  [setup.md](https://github.com/standardagents/t1bridge/blob/81cbdf81026a16e02f0bea74735c6b029a8ffae2/docs/setup.md#firewall-recovery-and-removal). Il tester del 14,3 ha confermato l'enrollment solo dopo aver
  aperto xART sul link privato — [README.md, tabella hardware](https://github.com/standardagents/t1bridge/blob/81cbdf81026a16e02f0bea74735c6b029a8ffae2/README.md#supported-hardware).
- **Framing BridgeXPC** [F]: header di 16 byte little-endian: magic `u16 0xb892`, versione `u16 1`, tipo `u32`
  (1 = HELLO, 2 = binary plist), lunghezza corpo `u64`; limite difensivo 16 MiB — [framing.rs](https://github.com/standardagents/t1bridge/blob/81cbdf81026a16e02f0bea74735c6b029a8ffae2/crates/t1-bridge/src/framing.rs).
  Nelle catture compaiono anche frame di tipo 0 con corpo vuoto dopo richiesta e risposta xART [F, analisi pcap locale]; T1Bridge
  non definisce un tipo 0 (gap, vedi sotto).
- **HELLO** [F]: corpo JSON; Linux invia `{"OSBuild":"Linux","BridgeXPCVersion":1.35,"ProcessName":"…","MaxSupportedProtocolVersion":1}`
  e richiede dal peer `MaxSupportedProtocolVersion >= 1` — [hello.rs](https://github.com/standardagents/t1bridge/blob/81cbdf81026a16e02f0bea74735c6b029a8ffae2/crates/t1-bridge/src/hello.rs). Nelle catture macOS:
  `xartstorageremoted` (macOS 24G624, `BridgeXPCVersion` 39) ↔ `xartstoraged` (bridgeOS **14Y910**, `BridgeXPCVersion` 1.35) [F, analisi pcap locale].
- **RPC** [F]: ogni frame tipo 2 è un bplist `[1 (versione), is_reply (bool), request_id (UUID maiuscolo), payload (array)]`;
  `nil` Objective-C serializzato come stringa `d4161201-daf5-4bbd-ae4f-9bf319fabbe0`; interi a 64 bit e UUID avvolti in
  `__com.apple.BridgeXPC.uint64` / `__com.apple.BridgeXPC.UUID` — [rpc.rs](https://github.com/standardagents/t1bridge/blob/81cbdf81026a16e02f0bea74735c6b029a8ffae2/crates/t1-bridge/src/rpc.rs), [xart_protocol.rs](https://github.com/standardagents/t1bridge/blob/81cbdf81026a16e02f0bea74735c6b029a8ffae2/crates/t1-daemons/src/xart_protocol.rs).
  Ordinali usati: 1 = set client version (T1Bridge seleziona la **versione 2**), 3 = performBiometricCommand
  `[3, 0, Data(pacchetto), capacità risposta]`, 9/10 = callback di stato servizio dal T1 `[ordinale, servizio, data, timestamp, delta]`,
  5/11 = calibrazione da EEPROM/FDR; risposta 22 = metodo non supportato — [rpc.rs](https://github.com/standardagents/t1bridge/blob/81cbdf81026a16e02f0bea74735c6b029a8ffae2/crates/t1-bridge/src/rpc.rs), [control.rs](https://github.com/standardagents/t1bridge/blob/81cbdf81026a16e02f0bea74735c6b029a8ffae2/crates/t1-bridge/src/control.rs).
- **Nessun TLS/pairing sul canale BridgeXPC** [F]: `live_operation.rs` apre un semplice `std::net::TcpStream` e negozia subito
  `BridgeXpcSession::connect` (HELLO); in `session.rs`, `rpc.rs`, `transport.rs` non c'è alcun riferimento a TLS, cifratura
  o chiavi — [live_operation.rs](https://github.com/standardagents/t1bridge/blob/81cbdf81026a16e02f0bea74735c6b029a8ffae2/crates/t1-bridge/src/live_operation.rs). Le catture macOS mostrano HELLO JSON, chiavi
  `xart-msg.*` e comandi BiometricKit in chiaro [F, analisi pcap locale].
- **Canale SEP su interfaccia 7** [F]: `SEP_USBFS_CONFIGURATION 2`, `SEP_USBFS_INTERFACE 7`, bulk OUT `0x05`, IN `0x88`,
  trasferimenti da 0x4400 byte via usbfs — [sep_usbfs.h](https://github.com/standardagents/t1bridge/blob/81cbdf81026a16e02f0bea74735c6b029a8ffae2/sep-probe/sep_usbfs.h), [sep_urb.h](https://github.com/standardagents/t1bridge/blob/81cbdf81026a16e02f0bea74735c6b029a8ffae2/sep-probe/sep_urb.h).
  Il "relay" ha header v2 da 0xb4 byte e endpoint logici: controllo (`UINT32_MAX`), **ACM = 1**, **keystore = 3** —
  [sep_relay.h](https://github.com/standardagents/t1bridge/blob/81cbdf81026a16e02f0bea74735c6b029a8ffae2/sep-probe/sep_relay.h). È la stessa interfaccia 7 (classe 255, bulk 0x88/0x05) che l'utente aveva
  individuato e reclamato con PyUSB ad aprile — [journal.md](https://github.com/DriftDeV/apple_biometrics_linuix/blob/de211f335d68ec571adda389d04461f02e9747bc/persistent_memory/journal.md).
- **"Sigillo" delle richieste keystore = integrità, non autenticazione** [F dal codice]: `sep_keystore_seal` scrive
  dimensione header 0x50, versione 1, timestamp in µs e un **SHA-256 senza chiave** su header e argomenti; in più contatore
  di transazione a 8 bit e timestamp strettamente crescente — [sep_keystore.c](https://github.com/standardagents/t1bridge/blob/81cbdf81026a16e02f0bea74735c6b029a8ffae2/sep-probe/sep_keystore.c).
- **Link sensore↔SEP** [F, Apple, generico non specifico del T1]: chiave condivisa fornita in fabbrica per ogni coppia
  sensore/Secure Enclave; chiave di sessione negoziata con AES key wrapping; canale "encrypted and authenticated" con AES-CCM;
  il processore inoltra i dati ma non li legge — [Apple Platform Security, Biometric security](https://support.apple.com/guide/security/touch-id-and-face-id-security-sec067eb0c9e/web).
- **Contrasto con RemoteXPC** [F]: su iOS 17+ RemoteXPC porta dizionari XPC su **HTTP/2**, scoperta via RSD (porta 58783)
  e accesso "trusted" solo dopo pairing SRP e tunnel QUIC/TLS — [pymobiledevice3 RemoteXPC.md](https://github.com/doronz88/pymobiledevice3/blob/master/misc/RemoteXPC.md).
  Duo Labs descrive RemoteXPC come il meccanismo con cui il **T2** parla con macOS, esposto tramite un'interfaccia di rete USB —
  [Duo Labs, Apple T2 XPC](https://duo.com/labs/research/apple-t2-xpc), [Duo Decipher](https://duo.com/decipher/apples-t2-chip-good-for-secure-boot-could-be-better)
  (citati da snippet di ricerca; la pagina Duo non si è caricata).

### Inferences
- [I] Il T1 (bridgeOS 14Y9xx, BridgeXPCVersion 1.35) usa il protocollo precedente **BridgeXPC**, non RemoteXPC/HTTP2 del T2:
  stessi concetti (XPC remoto su NCM), wire format diverso. Strumenti RemoteXPC (pymobiledevice3, `remotectl`) non sono
  applicabili direttamente al T1.
- [I] Il modello di fiducia è "chi sta sul link privato è l'host": qualunque processo root su Linux può parlare con 52032 e
  con l'interfaccia 7. Per questo T1Bridge mette tutti i controlli lato Linux (peer check, lock SEP, socket root-only).
- [I] Il "sigillo" SHA-256 senza chiave serve a far accettare la richiesta al keystore del SEP (formato atteso da `keybagd`),
  non a provare l'identità dell'host. La protezione vera è il segreto della keybag e i credenziali ACM, verificati nel SEP.
- [I] I frame di tipo 0 a corpo vuoto visti nelle catture sembrano un marcatore di fine/ack; T1Bridge funziona senza
  generarli/trattarli esplicitamente (o li gestisce a livello di chiusura connessione) — da verificare.

### Gaps
- La HELLO del T1 sulla porta 52032 non c'è nelle catture (connessione già aperta prima della cattura): nome processo e
  versione lato bridgeOS del servizio biometrico non sono confermati.
- I nomi di servizio `com.apple.BiometricKitBridge.executive` / `.transport` **non compaiono** né nel sorgente T1Bridge né
  nelle catture: T1Bridge si connette per porta fissa, non per nome. Il nome viene solo da stringhe di `biometrickitd` lette
  dall'utente in Ghidra (`com.apple.BiometricKitBridge`, varianti ipotizzate) [NV].
- Non ho trovato documentazione Apple su BridgeXPC, porta 52032 o 61500: tutto il wire format è reverse engineering.
- Come il keystore del SEP valida/lega il `client_context` a 64 bit e se esista un'autenticazione nascosta del relay: non chiaro.

## 2. Cosa sono xART, FDR, keybag, catacomb e Mesa, e cosa protegge ciascuno?

### Takeaway
**Mesa** è il sottosistema del sensore/matcher nel SEP; **FDR** fornisce la **calibrazione di fabbrica** del sensore
(firmata, legata al numero di serie del modulo), senza la quale Mesa non lavora; la **keybag** (AppleKeyStore) e l'**ACM**
forniscono il contesto crittografico e di autorizzazione che il SEP richiede per enroll/match; i **catacomb** sono gli
export cifrati e opachi dello stato biometrico (master + utente), che l'host deve conservare e ricaricare a ogni avvio;
**xART** è un piccolo record opaco anti-replay che bridgeOS chiede all'host di conservare, per impedire che si ricarichi
uno stato vecchio. Apple documenta solo il concetto generale; i dettagli T1 vengono dal reverse engineering.

### Cited Findings
- **Mesa** [F]: i messaggi di stato hanno servizio `MESA_SERVICE_MESSAGE = 0xe3ff8000`, tipi `0xe3ff8001` stato enrollment,
  `0xe3ff8002` risultato match (0x0c70 byte), `0xe3ff8003` enrollment completo; identità v1 da 20 byte, limite protocollo
  5 identità — [mesa.rs](https://github.com/standardagents/t1bridge/blob/81cbdf81026a16e02f0bea74735c6b029a8ffae2/crates/t1-bridge/src/mesa.rs), [commands.rs](https://github.com/standardagents/t1bridge/blob/81cbdf81026a16e02f0bea74735c6b029a8ffae2/crates/t1-bridge/src/commands.rs).
  Nelle catture macOS: 274 callback ordinale 9 con servizio `0xe3ff8000` durante un enrollment, 25 durante un match riuscito
  [F, analisi pcap locale].
- **Comandi BiometricKit** [F]: header 8 byte `magic 0x4d42 ("BM"), comando u16, versione u16 = 1, valore u16`, dentro
  l'ordinale RPC 3 — [biometric.rs](https://github.com/standardagents/t1bridge/blob/81cbdf81026a16e02f0bea74735c6b029a8ffae2/crates/t1-bridge/src/biometric.rs). Codici in T1Bridge: 0x02 reset, 0x03 start
  enrollment, 0x04 start match, 0x0c cancel, 0x0d remove identity, 0x0e continue enrollment, 0x1d stato calibrazione,
  0x20 load calibration, 0x22 serial modulo, 0x27 SKS lock state, 0x28 daemon info, 0x2e/0x2f config protetta utente,
  0x31 utente attivo, 0x38 catacomb ID, 0x3a hash catacomb, 0x3c stato catacomb, 0x3d/0x3e/0x3f dimensione/salva/fine
  salvataggio catacomb sicuro, 0x40 load catacomb, 0x42 identità, 0x43/0x44 config protetta di sistema, 0x47 CRC lista
  template, 0x48 remove user, 0x49 force biolockout, 0x4c xART disponibile —
  [commands.rs](https://github.com/standardagents/t1bridge/blob/81cbdf81026a16e02f0bea74735c6b029a8ffae2/crates/t1-bridge/src/commands.rs), [biometric.rs](https://github.com/standardagents/t1bridge/blob/81cbdf81026a16e02f0bea74735c6b029a8ffae2/crates/t1-bridge/src/biometric.rs).
- **FDR / calibrazione** [F]: T1Bridge valida un record DER **IMG4 "Combined"** con sequenza annidata `fdrd` → IM4P **`FSCl`** →
  blob con marcatore `CALB` all'offset 16, dimensione coerente, e che **contiene il numero di serie a 18 byte del modulo
  sensore** letto dal vivo con il comando 0x22; solo allora invia `LOAD_CALIBRATION` (0x20, sorgente FDR = 3; EEPROM = 2) e
  verifica con una seconda lettura daemon-info che il flag "calibrazione caricata" sia attivo —
  [calibration.rs](https://github.com/standardagents/t1bridge/blob/81cbdf81026a16e02f0bea74735c6b029a8ffae2/crates/t1-bridge/src/calibration.rs), [control.rs](https://github.com/standardagents/t1bridge/blob/81cbdf81026a16e02f0bea74735c6b029a8ffae2/crates/t1-bridge/src/control.rs).
- **Perché serve `EFI/APPLE/EMBEDDEDOS/FDRData`** [F]: il README di T1Bridge dice che Touch ID richiede l'`FDRData` originale di
  *questo* Mac; né il re-enrollment, né la reinstallazione, né il backup di un altro Mac possono sostituirlo; se cancellato, si
  rigenera solo reinstallando macOS e completando il primo avvio — [README.md](https://github.com/standardagents/t1bridge/blob/81cbdf81026a16e02f0bea74735c6b029a8ffae2/README.md). L'importer seleziona dalla ESP
  Apple solo il record associato al sensore vivo e lo salva root-only in `/var/lib/t1bridge/` — [security-review/v1.md](https://github.com/standardagents/t1bridge/blob/81cbdf81026a16e02f0bea74735c6b029a8ffae2/docs/security-review/v1.md),
  [touch-id.md](https://github.com/standardagents/t1bridge/blob/81cbdf81026a16e02f0bea74735c6b029a8ffae2/docs/touch-id.md). `t1-revive` scrive `combined.memboot`, `FDRData` e `version.plist` in `EFI/APPLE/EMBEDDEDOS`
  dopo una rigenerazione con i server Apple (provisioning `FDRMemoryCommit`, seconda restore che rigioca lo store) —
  [linux-recovery.md](https://github.com/standardagents/t1bridge/blob/81cbdf81026a16e02f0bea74735c6b029a8ffae2/docs/linux-recovery.md).
- **Keybag / AppleKeyStore** [F]: selettori keystore 0x01 create, 0x02 serialize, 0x03 load, 0x04 lock state, 0x06 copy UUID,
  0x0d make system, 0x18 unlock, 0x19 device state, 0x21 verify secret, 0x23/0x24 get/set config, 0x2a set environment,
  0x4d capabilities — [sep_keystore.h](https://github.com/standardagents/t1bridge/blob/81cbdf81026a16e02f0bea74735c6b029a8ffae2/sep-probe/sep_keystore.h). Al primo avvio l'host genera **32 byte casuali** come
  segreto, crea una keybag di sessione e la promuove a bag di sistema all'handle **-501** (utente biometrico); lo stato è in
  `/var/lib/t1bridge/touch-id/keybag.state` (max 0x8000 byte serializzati) — [sep_keybag.c](https://github.com/standardagents/t1bridge/blob/81cbdf81026a16e02f0bea74735c6b029a8ffae2/sep-probe/sep_keybag.c),
  [sep_keybag.h](https://github.com/standardagents/t1bridge/blob/81cbdf81026a16e02f0bea74735c6b029a8ffae2/sep-probe/sep_keybag.h). Ai riavvii la sequenza imita l'ordine di restore di `keybagd`: osserva la bag
  promossa, risolve la config protetta, poi il selettore 0x18 pubblica lo stato "first-unlock" a Mesa — commento in
  [sep_keybag.c](https://github.com/standardagents/t1bridge/blob/81cbdf81026a16e02f0bea74735c6b029a8ffae2/sep-probe/sep_keybag.c).
- **ACM** [F]: per ogni operazione un contesto ACM autorizzato (init, externalize, verify secret, UUID, readback dello stato
  finale della keybag) viene "prestato" a Mesa; enrollment e cancellazione aggiungono l'iniezione del credenziale
  `TouchIdEnrollment` e la verifica della policy, il match no — [architecture.md](https://github.com/standardagents/t1bridge/blob/81cbdf81026a16e02f0bea74735c6b029a8ffae2/docs/architecture.md#acm-policy-registration-and-retry).
- **Catacomb** [F]: ID 16 byte, hash 32 byte, export sicuro fino a 16 MiB; la persistenza è una transazione a coppia:
  export utente scritto in modo durevole, poi export master; solo la conferma del master committa la generazione e fa avanzare
  il record xART; al boot si carica e valida prima il master poi l'utente abbinato — [catacomb.rs](https://github.com/standardagents/t1bridge/blob/81cbdf81026a16e02f0bea74735c6b029a8ffae2/crates/t1-bridge/src/catacomb.rs),
  [architecture.md](https://github.com/standardagents/t1bridge/blob/81cbdf81026a16e02f0bea74735c6b029a8ffae2/docs/architecture.md#biometric-persistence).
- **xART** [F]: protocollo versione 1, comandi **100 fetch**, **150 save**, **200 lettura directory** (recovery, 48 voci da
  17 byte: UUID volume + flag esterno); chiavi `xart-msg.version/command/success/error/xart/volume-uuid/volume-external?`;
  record opaco max 0x3fef byte in `/var/lib/t1bridge/touch-id/xart/record.xart`, scritto in modo atomico e mai loggato —
  [xart_protocol.rs](https://github.com/standardagents/t1bridge/blob/81cbdf81026a16e02f0bea74735c6b029a8ffae2/crates/t1-daemons/src/xart_protocol.rs), [xart.rs](https://github.com/standardagents/t1bridge/blob/81cbdf81026a16e02f0bea74735c6b029a8ffae2/crates/t1-bridge/src/xart.rs),
  [xart_store.rs](https://github.com/standardagents/t1bridge/blob/81cbdf81026a16e02f0bea74735c6b029a8ffae2/crates/t1-daemons/src/xart_store.rs), [xart_daemon.rs](https://github.com/standardagents/t1bridge/blob/81cbdf81026a16e02f0bea74735c6b029a8ffae2/crates/t1-daemons/src/xart_daemon.rs).
  Nelle catture macOS ogni connessione 61500 è un **save (150) con blob da 192 byte**; la risposta di macOS ha `success: true`
  e anche `error: "encountered an unknown error"` [F, analisi pcap locale].
- **xART secondo terzi e Apple** [F]: xART = "eXtended Anti-Replay Technology", servizi del Secure Enclave di Mac con T1, T2 e M1 —
  [Eclectic Light, Explainer: xART and nonces](https://eclecticlight.co/2021/07/03/explainer-xart-and-nonces/) (fonte secondaria).
  La man page di `xartstorageremoted` (Mojave) lo descrive come demone che ascolta richieste di save/fetch dal CoProcessor,
  necessario per multi-partizione/multi-utente — [man page unix.com](https://www.unix.com/man_page/mojave/8/xartstorageremoted/).
  La pagina Apple sulla Secure Enclave cita il T1 tra i Mac con Secure Enclave ma **non** dice nulla di xART, Secure Storage
  Component o contatori anti-replay per il T1 — [Apple, The Secure Enclave](https://support.apple.com/guide/security/the-secure-enclave-sec59b0b31ff/web).

### Inferences
- [I] Il T1 non ha storage sicuro persistente proprio per lo stato biometrico: lo esporta cifrato (catacomb) e lo affida
  all'host, e usa il record xART custodito dall'host come "contatore" anti-replay per rifiutare catacomb o stati vecchi.
  Questo spiega perché il T1 si **connette lui** all'host (61500): è bridgeOS che chiede "salva/dammi il mio record".
- [I] Nelle catture **anche un match riuscito o fallito produce save xART** (2 in s4-success, 4 in s3-fail): probabilmente
  contatori di tentativi/biolockout. La documentazione T1Bridge parla di avanzamento xART solo al commit del master; il quadro
  completo di quando bridgeOS salva è più ampio.
- [I] FDR serve perché la calibrazione del sensore (FSCl) non è (o non è solo) nel T1: su macOS `biometrickitd` la legge
  dalla ESP (`libFDR`, `EmbeddedOSInstall.framework`) e la spinge a Mesa. Il legame col serial del modulo impedisce di usare
  la calibrazione di un altro Mac.
- [I] La keybag su Linux è "sintetica" (segreto casuale dell'host, nessuna password utente), quindi non dà la protezione
  "password richiesta dopo l'avvio" di macOS: il segreto sta in un file root-only.

### Gaps
- Il formato interno di xART (192 byte nelle catture), dei catacomb e del record FSCl resta opaco; nessuna fonte pubblica.
- Ruolo esatto dei metodi RPC 5 (EEPROM) e 11 (FDR): T1Bridge li implementa come codec ma i daemon non li usano.
- Significato di `success: true` + `error` nelle risposte xART di macOS 15 (con patch OCLP): bug di macOS 15 o normale.

## 3. Come T1Bridge implementa la catena (flusso dei messaggi reale)

### Takeaway
T1Bridge riscrive in C/Rust tutti i ruoli che su macOS hanno `biometrickitd`, `keybagd` e `xartstorageremoted`: selettore
di configurazione e shim NCM nel kernel, un listener xART su 61500, un "relay" della keybag su interfaccia 7, un broker che
per ogni operazione ferma il relay, prende un lock esclusivo sul SEP, apre BridgeXPC su 52032 e lancia i comandi Mesa;
fprintd/libfprint (patchati) e `pam_fprintd` stanno sopra. Funziona su hardware reale, ma sul **14,3** restano problemi aperti.

### Cited Findings
- **Ordine di avvio** [F]: 1) `t1-cfgsel` (config 2); 2) link NCM (`apple_t1_ncm` + `t1-ncm-ready`, unico processo con
  `CAP_NET_ADMIN`); 3) `t1-xart-storage` (listener IPv6 su 61500, solo dal peer T1); 4) relay keybag `sep-probe` (restore
  keybag, first-unlock, ACM, tiene aperta la sessione di notifica, lock condiviso `/run/lock/t1-touchid-sep.lock`);
  5) broker di autenticazione socket-activated — [architecture.md](https://github.com/standardagents/t1bridge/blob/81cbdf81026a16e02f0bea74735c6b029a8ffae2/docs/architecture.md#boot-and-ordering-contract), [touch-id.md](https://github.com/standardagents/t1bridge/blob/81cbdf81026a16e02f0bea74735c6b029a8ffae2/docs/touch-id.md).
- **Arbitraggio SEP** [F]: per enroll/match: verifica relay sano → ferma relay → lock esclusivo → una transazione biometrica →
  rilascia lock e riavvia relay in ogni caso — [architecture.md](https://github.com/standardagents/t1bridge/blob/81cbdf81026a16e02f0bea74735c6b029a8ffae2/docs/architecture.md#sep-arbitration).
- **Sessione BridgeXPC** [F]: TCP verso `[fe80::aede:48ff:fe33:4455%if]:52032` → HELLO (`ProcessName "t1-touchid"`) →
  ordinale 1 con versione client **2** (deve rispondere `[0, true]`) → comandi con ordinale 3; il T1 manda callback
  ordinale 9/10 a cui l'host risponde `[0]` — [live_operation.rs](https://github.com/standardagents/t1bridge/blob/81cbdf81026a16e02f0bea74735c6b029a8ffae2/crates/t1-bridge/src/live_operation.rs), [control.rs](https://github.com/standardagents/t1bridge/blob/81cbdf81026a16e02f0bea74735c6b029a8ffae2/crates/t1-bridge/src/control.rs), [rpc.rs](https://github.com/standardagents/t1bridge/blob/81cbdf81026a16e02f0bea74735c6b029a8ffae2/crates/t1-bridge/src/rpc.rs).
- **Priming e calibrazione** [F]: `prime_biometric_service` legge solo calibrazione e SKS lock state; `ensure_fdr_calibration_loaded`
  = serial modulo (0x22) → validazione FDR → daemon info (0x28) → eventuale `LOAD_CALIBRATION` (0x20) → daemon info di
  conferma — [prime_workflow.rs](https://github.com/standardagents/t1bridge/blob/81cbdf81026a16e02f0bea74735c6b029a8ffae2/crates/t1-bridge/src/prime_workflow.rs), [control.rs](https://github.com/standardagents/t1bridge/blob/81cbdf81026a16e02f0bea74735c6b029a8ffae2/crates/t1-bridge/src/control.rs).
- **Enrollment** [F]: controllo proprietario e capacità (il backend limita a **3** nuove identità per utente Linux, il protocollo
  ne ammette 5), controllo duplicati, `START_ENROLLMENT` (0x03, con descrittore che include l'autorizzazione ACM) e
  `CONTINUE_ENROLLMENT` (0x0e) a ogni stato Mesa nell'intervallo 0x64–0x163, poi export utente e master (0x3d/0x3e/0x3f),
  rilettura identità (0x42), rilascio SEP e relay — [touch-id.md](https://github.com/standardagents/t1bridge/blob/81cbdf81026a16e02f0bea74735c6b029a8ffae2/docs/touch-id.md), [enroll_workflow.rs](https://github.com/standardagents/t1bridge/blob/81cbdf81026a16e02f0bea74735c6b029a8ffae2/crates/t1-bridge/src/enroll_workflow.rs), [mesa.rs](https://github.com/standardagents/t1bridge/blob/81cbdf81026a16e02f0bea74735c6b029a8ffae2/crates/t1-bridge/src/mesa.rs).
- **Match** [F]: calibrazione, ACM, ri-applicazione della policy utente (0x2e/0x2f; solo `EBUSY` viene ritentato); se non c'è
  un'identità viva si fa il **restore a freddo** (load master poi utente via 0x40), si chiude il lease, si riavvia il relay e
  si riparte con un nuovo lease; poi `START_MATCH` (0x04), attesa del risultato `0xe3ff8002`, `CANCEL` (0x0c) in caso di
  annullamento — [touch-id.md](https://github.com/standardagents/t1bridge/blob/81cbdf81026a16e02f0bea74735c6b029a8ffae2/docs/touch-id.md), [architecture.md](https://github.com/standardagents/t1bridge/blob/81cbdf81026a16e02f0bea74735c6b029a8ffae2/docs/architecture.md), [match_workflow.rs](https://github.com/standardagents/t1bridge/blob/81cbdf81026a16e02f0bea74735c6b029a8ffae2/crates/t1-bridge/src/match_workflow.rs).
- **Perdita del dispositivo** [F]: ogni operazione sorveglia l'interfaccia NCM ammessa; se sparisce, chiude subito il socket
  BridgeXPC e restituisce `DeviceLost` — [architecture.md](https://github.com/standardagents/t1bridge/blob/81cbdf81026a16e02f0bea74735c6b029a8ffae2/docs/architecture.md#guarded-device-lifecycle).
- **Stato sul 14,3** [F]: enrollment confermato da un tester dopo aver aperto il firewall xART; una cattura 0.1.1 mostra
  `START_ENROLLMENT` che torna `-536870186` (`kIOReturnTimeout`) dopo 10 s, non diagnosticato — [release-gate/v1.md](https://github.com/standardagents/t1bridge/blob/81cbdf81026a16e02f0bea74735c6b029a8ffae2/docs/release-gate/v1.md).
  Loop di riavvio del relay keybag (issue #14): restore ok, poi promozione rifiutata (`0x0d`) dopo load riuscito (`0x03`);
  si risolve con spegnimento completo, causa ignota — [relay-recovery.md](https://github.com/standardagents/t1bridge/blob/81cbdf81026a16e02f0bea74735c6b029a8ffae2/docs/relay-recovery.md). Sospensione non
  supportata dal progetto — [security-review/v1.md](https://github.com/standardagents/t1bridge/blob/81cbdf81026a16e02f0bea74735c6b029a8ffae2/docs/security-review/v1.md).
- **Servizi chiave generici del SEP** [F]: non implementati; il progetto sconsiglia di distribuire un firmatore Linux finché
  non ci sono contratti T1 per create/sign/release — [secure-enclave-key-services.md](https://github.com/standardagents/t1bridge/blob/81cbdf81026a16e02f0bea74735c6b029a8ffae2/docs/secure-enclave-key-services.md).

### Inferences
- [I] La porta 52032 è fissa e "nascosta": su macOS `biometrickitd` (via `BridgeXPC.framework`) ci si connette senza RSD/Bonjour.
- [I] Le dipendenze reali per il Touch ID su questa macchina sono: config 2 (in conflitto con lo stack attuale della repo,
  vedi `docs/t1bridge.md`), firewall 61500, FDRData della ESP Apple `nvme0n1p1` (intatta su questa macchina), relay e niente sospensione.

### Gaps
- Non è pubblico quale sia la "behavioral reference" citata nel codice (`rpc.rs`, `commands.rs`, `policy.rs`); le regole del
  repo vietano di committare binari Apple, catture e output di decompilazione, il che suggerisce studio di binari macOS [I/NV].

## 4. Cosa è documentato da Apple, cosa è reverse engineering e di chi

### Takeaway
Apple documenta solo i principi (Secure Enclave anche nei T1, chiave di fabbrica sensore↔SEP, AES-CCM, template mai fuori dal
SEP). Tutto il resto (porte, BridgeXPC, comandi BiometricKit, keystore/ACM su interfaccia 7, xART, formato FDR) è reverse
engineering, oggi raccolto soprattutto in T1Bridge (Andrew Boyd / standardagents) e, per la rigenerazione FDR, in t1-revive.

### Cited Findings
- Apple: Secure Enclave presente nei MacBook Pro con Touch Bar 2016–2017 con chip T1 — [Apple, The Secure Enclave](https://support.apple.com/guide/security/the-secure-enclave-sec59b0b31ff/web);
  chiave condivisa di fabbrica, AES-CCM, template cifrati leggibili solo dal SEP — [Apple, Biometric security](https://support.apple.com/guide/security/touch-id-and-face-id-security-sec067eb0c9e/web);
  API Security framework per chiavi P-256 nell'enclave su Mac con Touch Bar/Touch ID, senza protocollo USB — citato in
  [secure-enclave-key-services.md](https://github.com/standardagents/t1bridge/blob/81cbdf81026a16e02f0bea74735c6b029a8ffae2/docs/secure-enclave-key-services.md).
- T1Bridge: mantenuto da Andrew Boyd — [README.md](https://github.com/standardagents/t1bridge/blob/81cbdf81026a16e02f0bea74735c6b029a8ffae2/README.md). Implementazione indipendente; il recovery è scritto in
  C/Rust usando come riferimento libirecovery, usbmuxd, libimobiledevice, libtatsu, idevicerestore e t1-revive, senza
  vendorizzarli — [linux-recovery.md](https://github.com/standardagents/t1bridge/blob/81cbdf81026a16e02f0bea74735c6b029a8ffae2/docs/linux-recovery.md).
- t1-revive (`niconistal/t1-revive`, commit `a861170`): rigenera FDR senza file FDRData originale tramite servizi Apple
  (patch a idevicerestore che pubblicizza `FDRMemoryCommit`), firmware generico pinnato bundle 901 / build 14Y901, reset ACPI
  `FRST` del T1 — [linux-recovery.md](https://github.com/standardagents/t1bridge/blob/81cbdf81026a16e02f0bea74735c6b029a8ffae2/docs/linux-recovery.md).
- OCLP: per Sonoma+ reinstalla da macOS 13.6 `/usr/libexec/biometrickitd` ("Required for Touch ID") ed
  `EmbeddedOSInstall.framework` ("Required for biometrickitd"), più `SharedUtils.framework`/`MechanismPlugins` di
  LocalAuthentication e le librerie NFC per Apple Pay — [OCLP t1_security.py](https://raw.githubusercontent.com/dortania/OpenCore-Legacy-Patcher/main/opencore_legacy_patcher/sys_patch/patchsets/hardware/misc/t1_security.py).
  Il supporto T1 per Sonoma è arrivato con OCLP 1.1.0 — [OCLP repo](https://github.com/dortania/Opencore-Legacy-Patcher), [MacRumors](https://forums.macrumors.com/threads/opencore-legacy-patcher-1-1-0-now-okay-on-2017-macbook-pro.2410006).
- T2/RemoteXPC: Duo Labs (Black Hat USA 2019, "Inside the Apple T2") — [slide](https://i.blackhat.com/USA-19/Thursday/us-19-Davidov-Inside-The-Apple-T2.pdf);
  RemoteXPC iOS 17 — [pymobiledevice3](https://github.com/doronz88/pymobiledevice3/blob/master/misc/RemoteXPC.md). t2linux non si
  applica al 14,3 (niente T2).
- Altri progetti 2026 (T1Bridge li cita): il modulo DKMS di `DriftDeV/apple_biometrics_linuix` registra solo il probe USB con
  TODO; `ELI3GANT/open-touchid-linux` e `apstrand/m2-air-touchid` riguardano Apple Silicon senza Touch ID funzionante —
  [secure-enclave-key-services.md](https://github.com/standardagents/t1bridge/blob/81cbdf81026a16e02f0bea74735c6b029a8ffae2/docs/secure-enclave-key-services.md).

### Inferences
- [I] OCLP conferma indirettamente lo stack: per il Touch ID su T1 bastano `biometrickitd` + `EmbeddedOSInstall` (FDR) da 13.6,
  cioè i due ruoli "comandi Mesa via BridgeXPC" e "calibrazione FDR"; il resto è autorizzazione LocalAuthentication.

### Gaps
- Nessuna pubblicazione accademica o talk specifico su BridgeXPC/T1 trovata in questa sessione (ricerca limitata).

## 5. Come si mappano i risultati di apple_biometrics_linuix su T1Bridge (confermato / mancato)

### Takeaway
La ricerca dell'utente aveva le **catture giuste** ma ha guardato il **flusso sbagliato**: la TCP 61500 è il canale **xART**
(bridgeOS `xartstoraged` → macOS `xartstorageremoted`), non i comandi biometrici. I comandi biometrici completi sono **in chiaro
nella stessa cattura** sulla TCP **52032**, e combaciano con la tabella dei comandi di T1Bridge. Le "firme" per dimensione
pacchetto sono in parte un artefatto della segmentazione TCP.

### Cited Findings
- **Confermato** [F]: interfaccia 7 config 2 (bulk 0x88/0x05) come canale SEP; uso di `BridgeXPC.framework` da parte di
  `biometrickitd`; trasporto NCM/IPv6; necessità di escludere usbmuxd; binari di riferimento macOS 13.6 come in OCLP —
  [journal.md](https://github.com/DriftDeV/apple_biometrics_linuix/blob/de211f335d68ec571adda389d04461f02e9747bc/persistent_memory/journal.md),
  coerente con [sep_usbfs.h](https://github.com/standardagents/t1bridge/blob/81cbdf81026a16e02f0bea74735c6b029a8ffae2/sep-probe/sep_usbfs.h) e [OCLP](https://raw.githubusercontent.com/dortania/OpenCore-Legacy-Patcher/main/opencore_legacy_patcher/sys_patch/patchsets/hardware/misc/t1_security.py).
- **61500 = xART** [F, analisi pcap locale su `s2-enroll-register-r01.tcp61500.pcapng` e `s4-auth-success-r01.tcp61500.pcapng`]:
  ogni stream è: HELLO macOS 16+109 = **125** byte; HELLO T1 16+105 = **121**; richiesta save 16+355 = **371** (blob xART 192 byte);
  frame vuoto **16**; risposta 16+206 = **222**; frame vuoto **16**. Corrisponde esattamente alla firma
  `125,121,371,16,222,16` di [tcp61500_signature_command_hypotheses.json](https://github.com/DriftDeV/apple_biometrics_linuix/blob/de211f335d68ec571adda389d04461f02e9747bc/analysis/tcp61500_signature_command_hypotheses.json).
- **"Variante 387" = segmentazione** [F, analisi pcap locale]: 387 = 371 + 16, cioè gli stessi due frame uniti in un segmento;
  non indica un comando diverso ("register/remove") come ipotizzato nel file di ipotesi.
- **Il canale biometrico c'è già nelle catture** [F, analisi pcap locale su `s2-enroll-register-r01.pcapng` e `s4-auth-success-r01.pcapng`]:
  frame BridgeXPC su host:49156 ↔ T1:52032 con RPC ordinale 3 e header `0x4d42`. Enrollment: 0x03 start enrollment, 0x0e
  continue (×7), 0x0c cancel, 0x27, 0x28, 0x2e, 0x38, 0x3a, 0x3c, 0x3d, 0x3e, 0x3f, 0x4c, più codici **non presenti in T1Bridge**:
  0x08 e 0x11 (capacità 3060), 0x0f, 0x26, 0x41, 0x4a (capacità 4096), 0x54 (capacità 83, il più frequente). Match riuscito:
  0x27, 0x04 start match, 0x54, 0x0c, 0x28, 0x4a. Callback ordinale 9 con servizio `0xe3ff8000` (Mesa) a centinaia.
- **Pairing/handshake crittografico** [F]: il piano dell'utente prevedeva un "pairing handshake" con chiavi in NVRAM come sfida
  principale — [implementation_plan.md](https://github.com/DriftDeV/apple_biometrics_linuix/blob/de211f335d68ec571adda389d04461f02e9747bc/persistent_memory/implementation_plan.md);
  non esiste sul link host (vedi sezione 1). Il vero prerequisito "segreto" è l'**FDRData** sulla ESP, non citato nel piano.
- **Architettura sbagliata nel piano** [F]: il piano punta a un modulo kernel con URB interrupt e `/dev/t1-touchid` e a un
  token successo/fallimento sull'interfaccia USB; T1Bridge mostra invece che la biometria è TCP su NCM (userspace) e
  l'interfaccia 7 serve per keybag/ACM — [implementation_plan.md](https://github.com/DriftDeV/apple_biometrics_linuix/blob/de211f335d68ec571adda389d04461f02e9747bc/persistent_memory/implementation_plan.md),
  [architecture.md](https://github.com/standardagents/t1bridge/blob/81cbdf81026a16e02f0bea74735c6b029a8ffae2/docs/architecture.md).
- La build bridgeOS del Mac dell'utente è **14Y910**; t1-revive pinna il firmware generico **14Y901** [F, analisi pcap locale;
  [linux-recovery.md](https://github.com/standardagents/t1bridge/blob/81cbdf81026a16e02f0bea74735c6b029a8ffae2/docs/linux-recovery.md)].

### Inferences
- [I] Il classificatore di stati (accuratezza 4/4) funziona solo perché il numero di save xART per scenario è diverso
  (6 enroll, 4 fail, 2 success, 2 remove): misura quante volte bridgeOS aggiorna il record anti-replay, non quale comando gira.
- [I] Le catture dell'utente sono una fonte preziosa per **verificare T1Bridge sul 14,3**: confrontare la sequenza macOS
  dell'enrollment (con 0x54/0x4a/0x08/0x11/0x41 prima di 0x03) con quella di T1Bridge potrebbe aiutare con il
  `kIOReturnTimeout` di `START_ENROLLMENT` ancora aperto sul 14,3. Non condividere i blob (calibrazione/catacomb/xART).
- [I] I comandi 0x54/0x4a ripetuti durante il match potrebbero essere letture di stato/immagine per la UI di macOS; T1Bridge
  dimostra che non sono necessari al match base.

### Gaps
- Significato dei comandi 0x08, 0x0f, 0x11, 0x26, 0x41, 0x4a, 0x54: non in T1Bridge, nessuna fonte pubblica.
- Ho analizzato solo s2 e s4 (più i file tcp61500); s0/s1/s3/s5 non sono stati decodificati completamente.
- Le catture sono state fatte su macOS 15.7.5 con le patch OCLP: la sequenza potrebbe differire da macOS 13.6 nativo.
