# Rischi e rollback di Touch ID via T1Bridge sul MacBookPro14,3 (dual boot con macOS 15)

Ambito: T1Bridge v0.1.12, commit `81cbdf8` (sorgenti locali in `/home/drift/src/t1bridge`, letti senza compilare né
eseguire nulla). Stato a novembre 2026. Legenda: **[F]** fatto verificato (codice, documento o comando in sola
lettura su questa macchina), **[I]** inferenza, **[NV]** non verificato, **[C]** conflitto tra fonti.
I link `blob/81cbdf8/...` corrispondono ai file locali con lo stesso percorso sotto `/home/drift/src/t1bridge/`.

Fatti sulla macchina raccolti in questa sessione (sola lettura):
- [F] Lo stack attuale per la Touch Bar in modalità display installa solo i DKMS `t1bridge-appletbdrm` e `t1bridge-uvc`
  (`scripts/install-touchbar-display.sh`, `DKMS_PKGS`). **Non** installa `t1-cfgsel` né `apple-t1-ncm`: `/dev/t1bridge-recovery`
  non esiste. Il passaggio di configurazione USB lo fa `touchbar-mode` scrivendo `bConfigurationValue` (1↔2).
- [F] `fprintd` e `libfprint` non sono installati (`pacman -Q` non li trova); `usbmuxd` non è installato.
- [F] `ufw` è attivo, `DEFAULT_INPUT_POLICY="DROP"`, `IPV6=yes` (`/etc/default/ufw`).
- [F] `/usr/lib/pam.d/kde-fingerprint` esiste già (fornito da Plasma) con `-auth required pam_fprintd.so` e
  `pam_faillock.so preauth`; `/etc/pam.d/system-auth` usa `pam_faillock`. Il trattino davanti a `auth` fa ignorare la riga
  finché il modulo manca: **appena si installa fprintd, la schermata di blocco KDE inizia a offrire l'impronta** [I].

---

## 1. L'enrollment su Linux può toccare il Touch ID di macOS?

### Takeaway
T1Bridge non dice nulla della coesistenza con macOS, e nessun tester l'ha documentata (né in un senso né nell'altro).
Il codice usa **lo stesso utente biometrico 501** del primo account macOS e accetta un "utente vivo" già caricato nel SEP
senza ricaricare i propri blob. Perciò un riavvio a caldo tra i due sistemi può mescolare gli stati. Nell'ipotesi
peggiore realistica si perdono le impronte di uno dei due sistemi (da registrare di nuovo), non si danneggia l'hardware [I].
Regola pratica: **spegnere del tutto il Mac (non riavviare) ogni volta che si cambia sistema**.

### Cited Findings
- [F] L'enrollment di T1Bridge limita le nuove impronte a **3 identità per un solo proprietario Linux**. Può elencare e
  ridurre insiemi più vecchi fino al limite di protocollo di **5**. Prima della cattura controlla capacità e duplicati; dopo
  la cattura esporta "user, poi master" e rilegge le identità, pretendendo esattamente l'insieme atteso. —
  [docs/touch-id.md](https://github.com/standardagents/t1bridge/blob/81cbdf8/docs/touch-id.md);
  [docs/interfaces.md](https://github.com/standardagents/t1bridge/blob/81cbdf8/docs/interfaces.md) ("so an existing larger set can still be listed, verified, and reduced")
- [F] L'utente biometrico usato dal broker è la costante `BIOMETRIC_USER_ID: u32 = 501`, sia per root sia per il
  proprietario dell'enrollment. 501 è anche l'UID predefinito del primo account macOS [I per la parte macOS]. —
  [crates/t1-daemons/src/auth_protocol.rs:17,251-259](https://github.com/standardagents/t1bridge/blob/81cbdf8/crates/t1-daemons/src/auth_protocol.rs)
- [F] Il ripristino "accetta prima un'identità viva valida per l'utente richiesto senza caricare nessuno dei due blob".
  Solo se non c'è un'identità viva carica il master durevole e poi lo user. Il commit della coppia (user, poi master)
  "fa avanzare il record anti-replay xART". —
  [docs/architecture.md, "Biometric persistence"](https://github.com/standardagents/t1bridge/blob/81cbdf8/docs/architecture.md)
- [F] Durante Identify, una corrispondenza con un'identità "legacy" senza etichetta o sconosciuta diventa `NoMatch`.
  Un'impronta di macOS eventualmente presente nel SEP **non** autentica quindi su Linux. —
  [crates/t1-daemons/src/standard_query_policy.rs:70-90](https://github.com/standardagents/t1bridge/blob/81cbdf8/crates/t1-daemons/src/standard_query_policy.rs)
- [F] Precedente di identità "orfana": su un 14,2 il SEP aveva ancora un'impronta che fprintd non vedeva e non poteva
  cancellare. Ogni nuovo enrollment di quel dito dava `enroll-duplicate` e lo stato persisteva al riavvio a freddo
  (perché viene dal blob ripristinato). Nessun comando supportato per rimuoverla. —
  [issue #57](https://github.com/standardagents/t1bridge/issues/57)
- [F] Due tester del 14,3 avevano macOS intatto: uno sullo stesso NVMe, uno con Linux su SSD esterno. Il secondo ha
  completato l'enrollment dopo la regola firewall per xART e uno spegnimento completo. Nessuno dei due riporta lo stato
  del Touch ID di macOS **dopo** l'enrollment su Linux. —
  [#2, commento josesalazar2025](https://github.com/standardagents/t1bridge/issues/2#issuecomment-5560762922);
  [#2, commento CG-8663](https://github.com/standardagents/t1bridge/issues/2#issuecomment-5560846273);
  [#2, successo](https://github.com/standardagents/t1bridge/issues/2#issuecomment-5569089212)
- [F] Su macOS lo stesso 14,3 di josesalazar2025 aveva Touch ID funzionante con le stesse dita, mentre l'enrollment
  Linux falliva con `START_ENROLLMENT` → `kIOReturnTimeout`. La causa resta non diagnosticata
  (stato SKS `0x15` solo come ipotesi). — [issue #2](https://github.com/standardagents/t1bridge/issues/2)
- [F] Apple: il modello dell'impronta è conservato cifrato, leggibile solo dal Secure Enclave, e "non lascia mai il
  dispositivo". La guida non parla del T1 nello specifico. —
  [Apple Platform Security, Touch ID e Face ID](https://support.apple.com/guide/security/touch-id-and-face-id-security-sec067eb0c9e/web)
- [F] Sul T1, reinstallare macOS non cancella i dati di Touch ID; serve `xartutil --erase-all` da Recovery (fonte
  secondaria del 2017). — [How-To Geek](https://www.howtogeek.com/337755/how-to-clear-your-macbooks-touch-bar-and-secure-enclave-data/amp/)
- [F] Su questa macchina il T1 si resetta solo con lo spegnimento completo: un riavvio non lo resetta (contesto di
  progetto, `AGENTS.md`; anche `touchbar-mode` richiede uno spegnimento completo per tornare in modalità keyboard).

### Inferences
- [I] Cosa ognuno dei due sistemi tiene da sé: T1Bridge conserva su Linux la sua coppia catacomb (master + user 501) e il
  suo record xART (`/var/lib/t1bridge`). macOS conserva i suoi tramite `biometrickitd`/`xartstorageremoted` sul proprio
  volume (le catture dell'utente mostrano `xartstorageremoted` in macOS 15 che parla con `xartstoraged` del T1, build 14Y910).
  Ogni sistema ripristina i propri blob quando il T1 parte a freddo. Così le due catene **dovrebbero** restare indipendenti.
- [I] Il rischio concreto è il **riavvio a caldo** macOS → Linux (o l'inverso). Il T1 resta acceso con l'utente 501 di
  macOS già caricato; T1Bridge lo prende come "identità viva valida" e salta il caricamento dei propri blob. In quella
  sessione:
  1. le dita di macOS occupano posti nel limite di 5 o 3;
  2. un enrollment Linux esporterebbe una coppia catacomb che **contiene anche le identità macOS** senza etichetta,
     cioè orfane come nella #57;
  3. una cancellazione potrebbe agire sullo stato vivo condiviso.

  Al contrario, dopo un riavvio a caldo Linux → macOS, `biometrickitd` troverebbe identità Linux caricate. La reazione
  di macOS è sconosciuta [NV]: potrebbe ignorarle, salvarle nel proprio catacomb o chiedere una nuova registrazione.
- [I] Il blob catacomb del sistema opposto sul suo disco **non** dovrebbe essere riscritto. Se però il T1 tiene un
  contatore anti-replay non volatile proprio, legato ai commit del master, ogni enrollment su un sistema potrebbe
  invalidare il master dell'altro. L'esito sarebbe un errore di caricamento del master (come `LoadMaster` 726 nella #57)
  su Linux, oppure la richiesta di registrare di nuovo le impronte su macOS. Non si sa se il T1 abbia questo contatore
  [NV]. La documentazione di recovery ammette che il T1 ha uno "stato persistente proprio"
  ([linux-recovery.md](https://github.com/standardagents/t1bridge/blob/81cbdf8/docs/linux-recovery.md)).
- [I] Mitigazioni:
  - spegnere del tutto (e aspettare qualche secondo) ogni volta che si cambia sistema;
  - prima della prova annotare in macOS quante e quali dita sono registrate (Impostazioni → Touch ID);
  - su Linux registrare **un solo dito, diverso** da quelli usati in macOS;
  - mettere in conto di dover registrare di nuovo le dita in macOS, che è l'esito peggiore plausibile;
  - non lasciare mai 5 identità complessive.

### Gaps
- Nessuna fonte, né T1Bridge né issue né Apple, documenta il comportamento dual boot: cosa vede macOS dopo un
  enrollment Linux, e se esiste un contatore anti-replay persistente nel T1.
- Non è verificato se l'account macOS di questa macchina abbia UID 501 (`id -u` in macOS lo direbbe).
- Non si sa con certezza se il SEP del T1 conservi le identità tra cicli a freddo o se dipenda solo dai blob dell'host.

---

## 2. Può bloccare il T1 o mandarlo in recovery (05ac:1281)? Quali componenti toccano il firmware?

### Takeaway
La configurazione normale di Touch ID (import, enrollment, verifica) **non** tocca il firmware e non scarica nulla da
Apple. Le parti pericolose sono separate e attivabili solo a mano:
- `t1bridge machine-data recover --online`, che contatta Apple, riprogramma il T1 e scrive sulla ESP;
- l'interfaccia kernel `/dev/t1bridge-recovery` di `t1_cfgsel`, che invoca l'ACPI `FRST`.

Il rischio di recovery accidentale sta soprattutto nell'**usare `FRST` per errore**, oggi possibile solo a mano con
`acpi_call`.

### Cited Findings
- [F] La recovery nativa è "sperimentale", "mai da installazione o aggiornamenti". Richiede un T1 **già** in recovery, un
  terminale presidiato e la conferma scritta `RECOVER`. Si blocca se esiste già una cartella `EMBEDDEDOS` o dati parziali.
  Contatta endpoint HTTPS di Apple (firma TSS, FDR) e scarica un pacchetto firmware Apple pinnato con checksum. —
  [docs/linux-recovery.md](https://github.com/standardagents/t1bridge/blob/81cbdf8/docs/linux-recovery.md);
  [docs/release-0.1.12.md](https://github.com/standardagents/t1bridge/blob/81cbdf8/docs/release-0.1.12.md)
- [F] `/dev/t1bridge-recovery` è 0600 e richiede `CAP_SYS_RAWIO`. Il kernel accetta solo i modelli supportati e rifiuta un
  T1 che espone ancora la personalità HID funzionante; cerca un unico `FRST` sotto il controller USB del T1. —
  [docs/linux-recovery.md](https://github.com/standardagents/t1bridge/blob/81cbdf8/docs/linux-recovery.md);
  definizione in `kernel/t1-cfgsel/t1_recovery_reset.h:159` (`.name = "t1bridge-recovery"`) [F, file locale]
- [F] `\_SB.PCI0.XHC1.RHUB.ASOC.FRST` è un reset hardware del T1 che lo lascia in recovery iBoot (05ac:1281) "fino a un
  riavvio dell'host: non valutarlo". — [issue #18, commento bjhinkle](https://github.com/standardagents/t1bridge/issues/18)
- [F] L'import "legge le fonti ed estrae la calibrazione di Touch ID; non ripristina l'albero di boot EFI, non scarica
  firmware, non avvia la rigenerazione"; un errore di import "non avvia mai automaticamente la recovery online". —
  [docs/setup.md](https://github.com/standardagents/t1bridge/blob/81cbdf8/docs/setup.md)
- [F] Casi reali di recovery online su un 14,3 (CachyOS 7.3.4) e su un 13,3: hanno richiesto correzioni locali (CA Apple
  mancante, race sullo stato finale, varianti di protocollo). Sul 13,3, dopo la recovery, `LOAD_CALIBRATION` viene
  rifiutato e Touch ID non funziona. — [issue #69](https://github.com/standardagents/t1bridge/issues/69);
  [issue #46](https://github.com/standardagents/t1bridge/issues/46)
- [F] Il wedge del relay keybag (#14) si è risolto con uno **spegnimento completo**; i manutentori chiedono di non fare
  reset del T1, non cancellare keybag e non registrare di nuovo le dita. —
  [docs/relay-recovery.md](https://github.com/standardagents/t1bridge/blob/81cbdf8/docs/relay-recovery.md);
  [issue #14](https://github.com/standardagents/t1bridge/issues/14)
- [F] Il pacchetto `t1bridge-dkms` porta `t1_cfgsel` nell'initramfs (`MODULES+=(t1_cfgsel)`) e **neutralizza
  `apple_ibridge`, `apple_touchbar`, `apple_ib_tb`, `apple_ib_als`** con `install ... /usr/bin/true`. —
  `packaging/arch/t1bridge-dkms/t1bridge.conf`, `t1bridge.modprobe.conf` [F, file locali]

### Inferences
- [I] Con lo stack attuale (`t1_cfgsel` non installato) `/dev/t1bridge-recovery` non esiste: il percorso `FRST` di T1Bridge
  non è raggiungibile. Per la prova di Touch ID **non serve** installare `t1_cfgsel` né il pacchetto `t1bridge-dkms`.
  Installarlo romperebbe tra l'altro la sospensione, perché neutralizza `apple_ibridge` usato in configurazione 1
  durante lo sleep.
- [I] Il binario `t1bridge` (userspace) contiene comunque il sottocomando `machine-data recover`. Per escluderlo basta
  non eseguirlo mai: senza un T1 già in 05ac:1281 e senza la conferma `RECOVER` si ferma da solo. Una volta su una
  macchina funzionante, la recovery comporterebbe invece **scritture sulla ESP Apple** e **traffico verso Apple con
  l'identità del T1**.
- [I] Nella procedura normale non c'è nessun download dalla CDN Apple; le uniche connessioni sono locali (link NCM).

### Gaps
- Nessuna fonte dice se il T1 possa finire in recovery per un enrollment interrotto (per esempio spegnimento a metà del
  commit). La documentazione parla solo di "stato di recovery protetto" sul lato host.

---

## 3. Import FDR / dati EFI della macchina: legge soltanto o può scrivere?

### Takeaway
L'import automatico monta le ESP **in sola lettura**, in un namespace privato e con accesso ai block device solo in
lettura. L'import esplicito `--from` legge un percorso e non monta nulla. Scrive solo in `/var/lib/t1bridge/machine-data/`.
Se i dati mancano o sono corrotti l'import fallisce con codici 20-30, senza toccare né la ESP né la calibrazione
esistente. **Scrive sulla ESP solo la recovery online.**

### Cited Findings
- [F] L'unità `t1bridge-import.service` ha `DeviceAllow=block-* r`, `PrivateMounts=yes`, `ProtectSystem=strict`, e come unico
  percorso scrivibile `ReadWritePaths=/var/lib/t1bridge/machine-data` (più il lock SEP). —
  [systemd/t1bridge-import.service](https://github.com/standardagents/t1bridge/blob/81cbdf8/systemd/t1bridge-import.service)
- [F] L'importer "monta i candidati in sola lettura con flag restrittivi, rifiuta i conflitti, salva atomicamente solo il
  record selezionato". Il `--from` esplicito non è nella sandbox ma "non monta nulla e non esegue sottoprocessi", rifiuta
  symlink e file speciali e non sovrascrive una calibrazione diversa già presente. —
  [docs/security-review/v1.md](https://github.com/standardagents/t1bridge/blob/81cbdf8/docs/security-review/v1.md)
- [F] Gli exit code: 20 sensore non disponibile; 21 nessuna fonte; 22 illeggibile; 23-25 dati non validi, non
  corrispondenti o in conflitto; 26-30 errore di archiviazione protetta. In nessun caso si devono usare dati di un altro
  Mac o cancellare la calibrazione. — [docs/setup.md](https://github.com/standardagents/t1bridge/blob/81cbdf8/docs/setup.md)
- [F] Senza `EFI/APPLE/EMBEDDEDOS/FDRData` di **questo** Mac non si configura Touch ID. Il backup di un altro Mac viene
  rifiutato dal confronto con il sensore. Se i dati sono persi, si ripristina macOS con un primo avvio completo. —
  [README.md](https://github.com/standardagents/t1bridge/blob/81cbdf8/README.md)
- [F] La versione 0.1.9 aveva un bug della sandbox (exit 30), corretto in 0.1.10 (#36). Su un 14,3 l'import esplicito
  `--from` funzionava. — [issue #36](https://github.com/standardagents/t1bridge/issues/36)

### Inferences
- [I] Con macOS installato, `EMBEDDEDOS/FDRData` c'è sulla ESP Apple (`nvme0n1p1`). Conviene comunque usare
  l'**import esplicito da una copia** (`t1bridge machine-data import --from <copia>/EFI/APPLE/EMBEDDEDOS/FDRData`)
  invece della scansione automatica: la ESP Apple non viene montata da T1Bridge.
- [I] Backup consigliati prima della prova:
  1. il backup della ESP Apple già previsto da `scripts/backup-esp.sh`, verificando che contenga `EFI/APPLE/EMBEDDEDOS/FDRData`,
     più una copia **fuori dalla macchina** come chiede il README;
  2. dopo l'import e dopo ogni enrollment riuscito, un archivio root-only (0600) di `/var/lib/t1bridge/`. Serve per
     tornare a "nessuno stato" o allo stato precedente su Linux, non da cancellare per "riprovare".

  Questi file sono segreti della macchina: non vanno nella repo né in un'issue
  ([README.md](https://github.com/standardagents/t1bridge/blob/81cbdf8/README.md): niente seriali né dati EFI nelle segnalazioni).
- [I] Un aggiornamento di macOS/bridgeOS può riscrivere `EMBEDDEDOS` (memboot), ma i dati FDR di fabbrica dovrebbero
  restare uguali; se cambiassero, l'import rifiuterebbe di sovrascrivere la calibrazione (exit 25) [NV].

### Gaps
- La prova dal vivo dell'import automatico (permessi, conflitti, pulizia dei mount) è ancora "aperta" nel release gate. —
  [docs/release-gate/v1.md](https://github.com/standardagents/t1bridge/blob/81cbdf8/docs/release-gate/v1.md)

---

## 4. Interazione con la nostra sospensione (configurazione 2 → 1 → 2 attorno a S3)

### Takeaway
T1Bridge dichiara la sospensione **non supportata** e sconsiglia di cambiare configurazione USB a mano. Il nostro hook
smonta il link NCM a ogni sospensione: xART si ferma (è legato al dispositivo di rete), il relay keybag va in errore e
riparte. Dopo il risveglio il primo uso di Touch ID dovrebbe fare un warm match (il T1 non viene resettato) oppure un cold
restore. Il rischio principale non è la sospensione in sé ma **sospendere durante un enrollment o mentre xART non è
raggiungibile**: possono restare stati di recovery o identità orfane.

### Cited Findings
- [F] README: "T1 sleep/wake: 🔴 non funziona sulla macchina provata; non supportato al momento". —
  [README.md](https://github.com/standardagents/t1bridge/blob/81cbdf8/README.md)
- [F] "Do not hot-swap competing T1 stacks or reset the USB device"; il passaggio senza riavvio da configurazione 1 a 2
  non è un comando supportato. — [docs/setup.md](https://github.com/standardagents/t1bridge/blob/81cbdf8/docs/setup.md)
- [F] `t1-xart-storage@.service` ha `BindsTo=sys-subsystem-net-devices-%i.device` e `Requires=t1-ncm-ready@%i`: si ferma
  quando sparisce l'interfaccia NCM. Il relay keybag ha `Restart=on-failure` con backoff da 2 a 60 s. —
  [systemd/t1-xart-storage@.service](https://github.com/standardagents/t1bridge/blob/81cbdf8/systemd/t1-xart-storage@.service);
  [systemd/t1bridge-keybag.service](https://github.com/standardagents/t1bridge/blob/81cbdf8/systemd/t1bridge-keybag.service)
- [F] Ogni operazione controlla l'interfaccia NCM ammessa all'inizio. Se sparisce o viene sostituita, l'operazione si
  annulla con `DeviceLost`; dopo il punto di non ritorno il worker finisce il cleanup prima di rilasciare il lease. —
  [docs/architecture.md](https://github.com/standardagents/t1bridge/blob/81cbdf8/docs/architecture.md);
  [docs/security-review/v1.md](https://github.com/standardagents/t1bridge/blob/81cbdf8/docs/security-review/v1.md)
- [F] Un errore dopo una modifica sul dispositivo "può lasciare stato di recovery protetto". "Non cancellare i file di
  stato per riprovare". — [docs/touch-id.md](https://github.com/standardagents/t1bridge/blob/81cbdf8/docs/touch-id.md)
- [F] Su un 14,2, S3 restando in configurazione 2: il relay va in `sep-lease -107` a ogni risveglio e si riprende con un
  solo restart (7 su 7). — [issue #18, commento bjhinkle](https://github.com/standardagents/t1bridge/issues/18)
- [F] Su un 13,3 con S3 profondo e la coppia `SOCW`, Touch ID funziona dopo il risveglio. L'unico guasto era causato da un
  hook che mascherava `fprintd` durante lo sleep. Su un 13,2 invece un utente non riusciva ad accedere con Touch ID dopo
  il risveglio. — [issue #68](https://github.com/standardagents/t1bridge/issues/68)
- [F] Su un 14,2, dopo due sospensioni tutte le operazioni fallivano con `LoadMaster` 726 e poi `Policy status 1`, anche
  dopo uno spegnimento completo. La causa trovata era `ufw` che bloccava TCP 61500 sul link NCM. Dopo la regola e uno
  spegnimento completo funzionava di nuovo, ma restava un'identità orfana. — [issue #57](https://github.com/standardagents/t1bridge/issues/57)

### Inferences
- [I] Il nostro approccio (passaggio in configurazione 1 con `apple-ibridge` durante S3) è diverso da tutti i casi
  riportati: nessuno ha provato Touch ID di T1Bridge con un passaggio di configurazione a ogni sospensione. Il T1 non
  viene resettato, quindi lo stato vivo del SEP dovrebbe sopravvivere e il primo match dopo il risveglio dovrebbe essere
  "warm". Se lo stato si perde, il broker esegue un solo cold restore ed è progettato per farlo [I dal diagramma di
  touch-id.md].
- [I] Accorgimenti da aggiungere all'hook di sospensione se si adotta Touch ID:
  1. non sospendere durante un enrollment: fare gli enrollment a coperchio aperto e alimentatore collegato, magari con
     `systemd-inhibit --what=sleep:handle-lid-switch fprintd-enroll ...`;
  2. prima di passare in configurazione 1, fermare in modo pulito il relay (`systemctl stop t1bridge-keybag.service`), così
     il SEP viene rilasciato prima che l'interfaccia sparisca; al risveglio lasciare che udev e systemd riavviino xART e
     relay, senza mascherare né fermare `fprintd` o `t1-touchid-auth` (#68);
  3. dopo il risveglio aspettare `t1bridge status` con `xart: ready` e `keybag: ready` prima di affidarsi all'impronta;
     la password resta comunque disponibile.
- [I] Il link NCM al risveglio potrebbe cambiare nome. La regola firewall deve seguire l'interfaccia del driver
  `apple_t1_ncm` e non un nome fisso (vedi §5).
- [I] Restano utili i backup di `/var/lib/t1bridge` fatti a operazioni concluse (§3). Se dopo una sospensione compare
  `LoadMaster`/`Policy status 1`, prima si controlla il firewall, poi si spegne del tutto. Non si cancellano file.

### Gaps
- Nessun dato su Touch ID di T1Bridge con un passaggio di configurazione 2→1→2 a ogni S3; va provato in modo
  controllato (§7).
- Non si sa se il cambio di configurazione USB faccia perdere al T1 lo stato vivo del SEP.

---

## 5. Esposizione di rete: xART su IPv6 TCP 61500 e firewall

### Takeaway
xART ascolta sulla porta TCP 61500 legata all'interfaccia NCM privata e verifica il peer, il cui indirizzo è una costante
nel codice. Con `ufw` in DROP (la situazione di questa macchina) l'enrollment **fallisce** senza una regola limitata a
quell'interfaccia e a quel peer. Non bisogna mai aprire la porta su Wi-Fi o su tutte le interfacce.

### Cited Findings
- [F] Il peer xART atteso è `fe80::aede:48ff:fe33:4455` (costante `BRIDGEOS_XART_PEER`). L'ammissione accetta solo quel
  link-local, con scope zero o uguale all'interfaccia. —
  [crates/t1-daemons/src/xart_service.rs:11](https://github.com/standardagents/t1bridge/blob/81cbdf8/crates/t1-daemons/src/xart_service.rs)
- [F] Il servizio parte da udev per l'interfaccia 04 di `05ac:8600`, che viene marcata `NM_UNMANAGED=1`. Il file `.link`
  mantiene il nome assegnato dal kernel (`NamePolicy=keep`). —
  [systemd/90-t1bridge-xart.rules](https://github.com/standardagents/t1bridge/blob/81cbdf8/systemd/90-t1bridge-xart.rules);
  [systemd/50-t1bridge-ncm.link](https://github.com/standardagents/t1bridge/blob/81cbdf8/systemd/50-t1bridge-ncm.link)
- [F] Dalla documentazione: aprire IPv6 TCP 61500 solo su quell'interfaccia e da quel peer; mai su Wi-Fi, Ethernet o tutte
  le interfacce; non salvare un nome di interfaccia come regola portabile; la validazione del peer tra macchine diverse
  è ancora aperta. — [docs/setup.md](https://github.com/standardagents/t1bridge/blob/81cbdf8/docs/setup.md)
- [F] Il successo sul 14,3 è arrivato con la regola `61500/tcp on eth0 ALLOW IN fe80::aede:48ff:fe33:4455` (ufw, default
  deny mantenuto) e uno spegnimento completo. Lo schema del guasto: primo enrollment in timeout dopo 10 s, poi errori
  immediati. — [issue #2](https://github.com/standardagents/t1bridge/issues/2#issuecomment-5569089212)
- [F] `xart: ready` vuol dire solo che il servizio è attivo, non che il traffico arriva; la riga `xart-admission` ha dato
  un falso negativo su una configurazione funzionante. — [docs/setup.md](https://github.com/standardagents/t1bridge/blob/81cbdf8/docs/setup.md);
  [issue #2](https://github.com/standardagents/t1bridge/issues/2#issuecomment-5569089212)
- [F] Il record xART è tra gli "asset protetti" del modello di minaccia. —
  [docs/security-review/v1.md](https://github.com/standardagents/t1bridge/blob/81cbdf8/docs/security-review/v1.md)

### Inferences
- [I] Con `ufw` su questa macchina la regola sarebbe:
  `ufw allow in on <iface-apple_t1_ncm> from fe80::aede:48ff:fe33:4455 to any port 61500 proto tcp`.
  Va ricavata al momento con `ip -d link` / `udevadm info` (driver `apple_t1_ncm`) e va rimossa nel rollback
  (`ufw status numbered` → `ufw delete N`).
- [I] Il nome dell'interfaccia può cambiare dopo un passaggio di configurazione al risveglio o dopo un riavvio. Una regola
  legata a un nome è fragile: se il nome cambia, xART smette di essere raggiungibile e l'enrollment o il commit
  falliscono (rischio di identità orfane come nella #57). Alternativa più robusta [I]: una regola nftables in
  `/etc/ufw/before6.rules` che usi `iifname` più l'indirizzo sorgente link-local, oppure un nome stabile assegnato con un
  `.link` che corrisponda a `Driver=apple_t1_ncm`.
- [I] L'esposizione aggiunta è minima: link-local, interfaccia USB interna, peer fisso, ammissione nel servizio. Un
  attaccante dovrebbe già controllare il T1 o il bus USB interno.

### Gaps
- Non verificato se oggi, in configurazione 2, l'interfaccia NCM esca con il driver stock `cdc_ncm` o serva
  `apple_t1_ncm` (`ip -br link` adesso mostra solo `lo` e `wlan0`). I servizi di T1Bridge si aspettano il driver
  `apple_t1_ncm`.

---

## 6. Modifiche al sistema (fprintd/libfprint, PAM) e rollback pulito

### Takeaway
I pacchetti `libfprint-t1bridge` e `fprintd-t1bridge` sostituiscono libfprint e fprintd per tutto il sistema. Qui non sono
installati, quindi il rollback consiste nel rimuoverli. T1Bridge non modifica i file PAM. Plasma però ha già
`kde-fingerprint`, che si attiva da solo quando c'è fprintd. Il rischio PAM più concreto è il **blocco dell'account da
`pam_faillock`** se l'impronta conta come tentativo fallito.

### Cited Findings
- [F] `libfprint-t1bridge`: `provides=libfprint, libfprint-2.so`, `conflicts=libfprint`; `fprintd-t1bridge`:
  `provides=fprintd`, `conflicts=fprintd`. Devono restare una coppia abbinata. — `packaging/arch/*/PKGBUILD` [F, file locali];
  [README.md](https://github.com/standardagents/t1bridge/blob/81cbdf8/README.md)
- [F] "T1Bridge non sostituisce file PAM né distribuisce un modulo PAM proprio". Prima di modificare PAM: tenere aperta una
  shell root di recupero, provare per ogni consumer sia l'impronta sia la password con il servizio fermo, usare timeout e
  tentativi limitati (default 30 s). — [docs/setup.md](https://github.com/standardagents/t1bridge/blob/81cbdf8/docs/setup.md)
- [F] La password con il broker fermo è provata per sudo, non per Polkit né per la schermata di blocco: "remaining live
  security checks". — [docs/release-gate/v1.md](https://github.com/standardagents/t1bridge/blob/81cbdf8/docs/release-gate/v1.md)
- [F] Con `pam_fprintd` in testa allo stack, i fallimenti immediati hanno prodotto tre errori `pam_faillock` e un blocco
  dell'account di 10 minuti. — [issue #57](https://github.com/standardagents/t1bridge/issues/57)
- [F] Rimozione documentata: ripristinare e provare l'autenticazione solo con password; fermare servizi, socket e istanze
  xART; rimuovere i pacchetti; ripristinare la coppia libfprint/fprintd della distribuzione se serve; rigenerare
  l'initramfs. "La rimozione del pacchetto non autorizza a cancellare lo stato protetto né la ESP Apple". —
  [docs/setup.md](https://github.com/standardagents/t1bridge/blob/81cbdf8/docs/setup.md)
- [F] Su questa macchina `/usr/lib/pam.d/kde-fingerprint` contiene `-auth required pam_fprintd.so` dopo
  `pam_faillock.so preauth`; non esistono file PAM personalizzati per l'impronta. [F, lettura locale]

### Inferences
- [I] Conviene **non** toccare `system-auth`/`sudo` all'inizio. Prima fase: solo `fprintd-verify` da terminale. Seconda
  fase: la schermata di blocco KDE, dove `kde-fingerprint` è un servizio separato in parallelo alla password, quindi
  nessun percorso di blocco. Solo dopo, eventualmente, `sudo` con
  `auth sufficient pam_fprintd.so max-tries=1 timeout=10` **prima** di `include system-auth`, così la password resta il
  percorso normale.
- [I] Niente impronta per il login di plasmalogin: il portachiavi KWallet richiede comunque la password.
- [I] Per evitare il blocco da faillock: non mettere `pam_fprintd` in `system-auth`; in caso di blocco
  `faillock --user <utente> --reset` da root.
- [I] Va detto all'utente che **appena si installa fprintd, la schermata di blocco KDE cambia comportamento** (offre il
  dito), anche senza modificare PAM.

### Gaps
- Non provato il comportamento di `kde-fingerprint` con T1Bridge su Plasma 6.8 (i tester usano Omarchy/Hyprland).

---

## 7. Procedura di prova sicura e reversibile per questa macchina

### Takeaway
La prova ha senso **solo** in una forma minima e reversibile:
- nessun pacchetto `t1bridge-dkms` né `t1_cfgsel` né recovery;
- import da una copia dell'FDR;
- un dito diverso da quelli di macOS;
- regola firewall limitata;
- PAM non modificato;
- spegnimento completo a ogni cambio di sistema.

Il rollback lascia intatti ESP Apple e macOS. Le identità create nel SEP potrebbero però restare orfane: è il rischio
residuo non eliminabile [I].

### Cited Findings
- [F] Ordine e precondizioni documentati:
  1. `systemd-sysusers` e `systemd-tmpfiles` per T1Bridge;
  2. gruppo `t1bridge`;
  3. abilitare `t1-touchid-auth.socket` e `t1bridge-fingerprint.socket`;
  4. riavviare;
  5. controllare `t1bridge status`;
  6. firewall per xART prima dell'enrollment;
  7. import;
  8. `fprintd-enroll -f <dito>` da un terminale grafico con agente Polkit;
  9. `fprintd-verify`.

  Non usare `sudo fprintd-enroll`; cancellare un dito solo con `-f` (senza `-f` cancella tutte le impronte). —
  [README.md](https://github.com/standardagents/t1bridge/blob/81cbdf8/README.md);
  [docs/setup.md](https://github.com/standardagents/t1bridge/blob/81cbdf8/docs/setup.md)
- [F] Non abilitare il relay keybag come servizio di avvio incondizionato; non usare `t1bridge enroll` (percorso di
  sviluppo). — [docs/setup.md](https://github.com/standardagents/t1bridge/blob/81cbdf8/docs/setup.md)
- [F] `/var/lib/t1bridge`: non cancellarla, non azzerare gli enrollment, non usare i comandi di validazione USB come
  riparazione generica. — [docs/setup.md](https://github.com/standardagents/t1bridge/blob/81cbdf8/docs/setup.md)

### Inferences
Procedura proposta [I]; tutto il lavoro da root lo fa l'utente nel pannello Terminale:

0. **Prerequisiti**
   - Backup della ESP Apple con `scripts/backup-esp.sh`, verificando `EFI/APPLE/EMBEDDEDOS/FDRData`, più una copia fuori
     dalla macchina.
   - Backup dei dati Linux.
   - In macOS: annotare le dita registrate, verificare che Touch ID funzioni e controllare `id -u`.
   - Alimentatore collegato; una shell root aperta durante le prove PAM.
1. **Installazione minima.** Compilare dal sorgente già verificato (`81cbdf8`) solo `t1bridge` (userspace), la coppia
   `libfprint-t1bridge` + `fprintd-t1bridge` e il modulo `apple-t1-ncm` se `cdc_ncm` non basta. **Non** installare
   `t1-cfgsel`, la recovery o il pacchetto `t1bridge-dkms`, che neutralizza `apple_ibridge` e romperebbe lo sleep. Tenere
   un elenco dei file installati, come fa già `install-touchbar-display.sh` con `--undo`, per poterli rimuovere.
2. **Firewall.** Regola `ufw` limitata all'interfaccia `apple_t1_ncm` e al peer `fe80::aede:48ff:fe33:4455`, porta 61500.
3. **Spegnimento completo e avvio diretto in CachyOS** (mai un riavvio a caldo da macOS). Touch Bar in modalità display.
   `t1bridge status`: `xart: ready`, `keybag: not-enrolled`.
4. **Import esplicito** dalla copia di backup:
   `t1bridge machine-data import --from <backup>/EFI/APPLE/EMBEDDEDOS/FDRData`. Se fallisce, fermarsi: nessuna recovery.
5. **Un solo enrollment** di un dito diverso da quelli di macOS, a coperchio aperto, con inibizione dello sleep, da
   Konsole nella sessione grafica. Poi `fprintd-verify` con il dito giusto e con uno sbagliato.
6. **Archivio root-only** di `/var/lib/t1bridge` (0600, fuori dalla repo).
7. **Prove di persistenza**, una cosa per volta:
   1. riavvio di Linux;
   2. sospensione con l'hook attuale (più lo stop pulito del relay), poi `fprintd-verify`;
   3. spegnimento completo, avvio di **macOS**: Touch ID di macOS funziona ancora? quante dita elenca?;
   4. spegnimento completo, ritorno a Linux: `fprintd-verify`.
8. **PAM**, solo se il punto 7 passa: prima la schermata di blocco KDE (già automatica), poi forse `sudo`. Ogni volta
   provare la password con `t1-touchid-auth` fermo.

**Rollback** [I]:
1. In Linux, con macOS ancora funzionante: `fprintd-delete "$USER" -f <dito>` (cancella l'identità dal SEP tramite il
   broker) e `fprintd-list` vuoto.
2. Ripristinare i file PAM eventualmente modificati e provare la password.
3. Disabilitare e fermare `t1-touchid-auth.socket`, `t1bridge-fingerprint.socket`, il relay e le istanze xART.
4. Rimuovere le unità, il binario e la coppia fprintd/libfprint (non c'era una coppia di sistema da ripristinare), più il
   modulo `apple-t1-ncm` se installato.
5. Rimuovere la regola `ufw`.
6. Archiviare `/var/lib/t1bridge` invece di cancellarla, poi toglierla dal sistema.
7. Spegnimento completo.
8. Verificare in macOS che Touch ID sia invariato. Se macOS chiede di registrare di nuovo le dita, farlo da Impostazioni.
   `xartutil --erase-all` **non** va usato: cancella tutto lo stato del SEP.

### Gaps
- Gli effetti dei punti 7.3 e 7.4 (dual boot) non sono documentati da nessuno: sono la vera incognita della prova.
- Non verificato che `fprintd-delete` rimuova davvero l'identità dal SEP e non solo dal catalogo (la #57 mostra un caso
  in cui il catalogo e il SEP non coincidevano più).

---

## 8. Repo pubblica DriftDeV/apple_biometrics_linuix: licenze e privacy

### Takeaway
La repo è **pubblica e senza licenza** (`gh repo view`: `visibility: PUBLIC`, `licenseInfo: null`). Contiene:
- binari Apple proprietari (`biometrickitd`, `SharedUtils.framework`, `EmbeddedOSInstall.framework`, 23 MB);
- un listato Ghidra di `biometrickitd` di circa 295.000 righe;
- 37 catture pcapng (134 MB) di sessioni Touch ID macOS↔T1, con il traffico xART.

Le eccezioni UE e italiane per il reverse engineering coprono **lo studio e la decompilazione da parte del licenziatario**,
non la **ridistribuzione** dei binari né del listato. Questi vanno tolti **da tutta la storia**. Nelle catture non sono
emersi seriali, ECID o UDID. Ci sono però record xART (asset protetto) e circa 1.000 UUID: le catture vanno tolte anche
loro.

### Cited Findings
- [F] Licenza di macOS Sequoia, §2J: "you may not rent, lease, lend, sell, **redistribute** or sublicense the Apple Software".
  §2K: firmware e Boot ROM Apple "may not [be] copy, modify or redistribute[d]". §2N: niente decompilazione o reverse
  engineering "except as and only to the extent any foregoing restriction is prohibited by applicable law". —
  [Apple, macOS Sequoia SLA (PDF)](https://www.apple.com/legal/sla/docs/macOSSequoia.pdf)
- [F] Direttiva 2009/24/CE: l'art. 5(3) consente di osservare, studiare e provare un programma; l'art. 6 consente la
  decompilazione "indispensabile" per l'interoperabilità, da parte del licenziatario, limitata alle parti necessarie. Le
  informazioni ottenute non possono essere comunicate a terzi salvo che serva all'interoperabilità né usate per un
  programma sostanzialmente simile. L'art. 8 rende nulle le clausole contrattuali contrarie. —
  [EUR-Lex, Direttiva 2009/24/CE](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32009L0024)
- [F] L. 633/1941, art. 64-quater: stesse condizioni. Le informazioni non possono essere "comunicate a terzi, fatta salva la
  necessità di consentire l'interoperabilità"; il comma 3 rende nulle le clausole contrarie; il comma 4 vieta il
  "pregiudizio indebito" al titolare. — [Brocardi, art. 64-quater](https://www.brocardi.it/legge-diritto-autore/titolo-i/capo-iv/sezione-vi/art64quater.html)
- [F] Gli stessi manutentori di T1Bridge chiedono "No raw captures, UUIDs, credentials or biometric bytes" e niente dati
  EFI, keybag o biometrici nelle issue. — [issue #2](https://github.com/standardagents/t1bridge/issues/2);
  [README.md](https://github.com/standardagents/t1bridge/blob/81cbdf8/README.md)
- [F] T1Bridge pubblica senza asset Apple ("No Apple assets are committed or included in packages") e ha fatto una
  scansione degli identificativi con squash della storia. —
  [docs/linux-recovery.md](https://github.com/standardagents/t1bridge/blob/81cbdf8/docs/linux-recovery.md);
  [docs/release-gate/v1.md](https://github.com/standardagents/t1bridge/blob/81cbdf8/docs/release-gate/v1.md)
- [F, scansione locale; contati solo i file, nessun valore stampato]:
  - `scratch/ioreg_biometrics.txt` è vuoto (0 byte); `scratch/iousb.txt` ha 13 righe e nessuna chiave Serial, ECID o UUID.
  - Nessun pcap contiene le stringhe ECID:, SRNM:, CPID:, SerialNumber, UniqueDeviceID, UniqueChipID, MacBookPro14,
    `/Users/` (né ASCII né UTF-16).
  - Tutti i pcap hanno nell'intestazione pcapng la CPU (i7-7820HQ), la versione di macOS (15.7.5, 24G624) e Dumpcap 4.6.4.
  - 21 su 37 contengono messaggi `xart-msg` (scambi tra `xartstorageremoted` e `xartstoraged`, bridgeOS 14Y910).
  - 14 contengono UUID in forma testuale: 1.047 distinti in totale (fino a 806 per cattura di enrollment), in messaggi
    BridgeXPC; l'unica corrispondenza con lo schema dei seriali Apple era la coda di un UUID.
  - Le catture `*.ep87.pcapng` sono traffico USB del canale SEP.
- [F] I file sono tracciati da git: 65 percorsi tra pcapng e `macOS_binaries`. La storia ha 7 commit, tra il 16 e il
  28/04/2026. `scratch/OCLP_T1_Reference/*.py` sono file di OpenCore Legacy Patcher senza intestazione di licenza.
  [F, `git ls-files`, `git log`]

### Inferences
- [I] **Binari Apple** (`scratch/macOS_binaries/**`) e **listato decompilato** (`biometrickdt_extraction.txt`): ridistribuirli
  è vietato dalla licenza §2J/§2K. Nessuna eccezione degli artt. 5(3) e 6 / 64-ter e 64-quater lo autorizza: quelle norme
  riguardano gli atti del licenziatario, e l'art. 6(2)(b) limita perfino la comunicazione delle *informazioni*.
  L'art. 8 rende nulla la §2N solo per gli atti consentiti, non per la §2J. Anche il listato Ghidra riproduce in larga
  parte il codice (rischio copyright e DMCA §1201/§512 per GitHub) [I, non è consulenza legale]. Vanno **rimossi da tutta
  la storia**.
- [I] **Catture pcapng**: non risultano seriali, ECID o UDID; contengono però:
  1. record xART di questa macchina, opachi e trattati da T1Bridge come asset protetto;
  2. traffico SEP cifrato di enrollment e autenticazione (derivato biometrico cifrato, non leggibile senza il SEP ma
     legato al dispositivo);
  3. molti UUID, probabilmente in parte identificativi di sessione e forse di keybag o identità [NV].

  Per prudenza e per coerenza con le richieste di T1Bridge, vanno rimosse dalla storia pubblica. Al loro posto si possono
  tenere **descrizioni testuali** di selettori, ordine e tempi, senza payload.
- [I] **OCLP_T1_Reference**: codice di terzi senza licenza dichiarata nella repo. La licenza di OCLP non è stata verificata
  [NV]: conviene sostituirlo con un link al commit upstream.
- [I] Riscrittura della storia consigliata:
  1. dichiarare la repo privata subito, se va bene all'utente;
  2. in un clone fresco: `git filter-repo --invert-paths --path scratch/macOS_binaries --path captures --path scratch/XC20.pcapng --path scratch/OCLP_T1_Reference --path-glob '*.pcapng'`;
  3. `git push --force` di tutti i branch e i tag;
  4. chiedere al supporto GitHub di eliminare la cache e le viste dei commit orfani; fork esistenti e cloni altrui
     restano fuori controllo;
  5. aggiungere una licenza per il solo codice originale e un `.gitignore` per `captures/` e `scratch/macOS_binaries/`.

  Push forzato e cambio di visibilità sono azioni dell'utente, da confermare.
- [I] Il caso dell'utente rientra nello studio per interoperabilità (art. 5(3) e 6 della direttiva, artt. 64-ter e
  64-quater): **tenere in locale** binari e catture per lo studio è difendibile, **pubblicarli** no.

### Gaps
- Non si è decodificato il contenuto dei pcap oltre `strings`. Payload binari, descrittori USB senza stringhe e campi
  BridgeXPC codificati potrebbero contenere identificativi non testuali [NV].
- Non verificati i termini di licenza di OCLP né se GitHub abbia già ricevuto segnalazioni.
