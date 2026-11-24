# Stato reale del Touch ID in T1Bridge (standardagents/t1bridge) sui MacBook Pro T1, con focus sul MacBookPro14,3

Data della ricerca: 24 novembre 2026. Fonti primarie: checkout locale pinnato a `v0.1.12` (`81cbdf8`) in
`/home/drift/src/t1bridge` (letto, niente compilato né eseguito), API GitHub via `gh` (release, tag, commit, issue, PR,
commenti) e il repository pacman `linux.standardagents.ai`. Tag: **[F]** fatto con fonte, **[I]** inferenza, **[NV]** non
verificato. Nessun seriale/dato macchina riportato; gli indirizzi citati compaiono identici in report di macchine diverse.

## 1. Release e changelog dopo v0.1.12: ci sono novità su Touch ID o sospensione?

### Takeaway
No. **v0.1.12 (20/09/2026) è ancora l'ultima release** a fine novembre 2026: nessun tag, commit su `main` o pacchetto più
recente. Il manutentore non risponde su GitHub dal 20/09/2026. Da allora le correzioni (sospensione, SOCW, recovery,
usbmuxd, SELinux) arrivano solo come **PR della comunità ancora aperte** e come script fuori dall'albero.

### Cited Findings
- [F] Release GitHub: v0.1.1 (06/09), v0.1.2 (06/09), v0.1.6–0.1.7 (09/09), v0.1.8–0.1.9 (11/09), v0.1.10, v0.1.11, v0.1.12 (tutte il 20/09/2026, l'ultima alle 22:19 UTC). Tag più recente: `v0.1.12` — [Releases](https://github.com/standardagents/t1bridge/releases)
- [F] L'ultimo commit su `main` è `81cbdf8` "Ship experimental native T1 online recovery in v0.1.12 (#45)", 20/09/2026 22:02 UTC. Da allora non c'è nessun commit — [Commits](https://github.com/standardagents/t1bridge/commits/main)
- [F] Il database pacman `standardagents.db` contiene solo `t1bridge-0.1.12-1`, `t1bridge-dkms-0.1.12-1`, `libfprint-t1bridge-1.94.100-20`, `fprintd-t1bridge-1.94.5-17` e `t1bridge-omarchy-0.2.2-1`. `PRERELEASE.md` dice "Updated September 20, 2026" — [linux.standardagents.ai PRERELEASE.md](https://linux.standardagents.ai/arch/standardagents/x86_64/PRERELEASE.md)
- [F] I commenti del manutentore (`andrew-boyd` e il bot `standard-agents-issues`, "Update from @andrew-boyd's coding agent") si fermano al 20/09/2026. Dal 22/09 al 19/11 i commenti nelle issue sono solo di tester e contributori — [API issue comments](https://github.com/standardagents/t1bridge/issues)
- [F] Changelog v0.1.10: corregge il fallimento dell'import automatico nel sandbox (#36) riaprendo la radice di storage dopo il cambio di mount namespace. Il Touch Bar riprova il probe del display se l'init al resume fallisce. Il loop di riavvio del relay (#14) "remains unresolved". Pacchetti: libfprint 1.94.100-18, fprintd 1.94.5-15 — [docs/release-0.1.10.md](https://github.com/standardagents/t1bridge/blob/v0.1.12/docs/release-0.1.10.md)
- [F] Changelog v0.1.11: corregge una perdita di memoria nelle risposte del display e aggiunge diagnostica. "Relay failures, system suspend, runtime power saving ... the original enrollment failure and the display reports remain open" — [docs/release-0.1.11.md](https://github.com/standardagents/t1bridge/blob/v0.1.12/docs/release-0.1.11.md)
- [F] Changelog v0.1.12: aggiunge solo il comando sperimentale `t1bridge machine-data recover --online` per ricreare i dati EFI persi. "does not establish real-device recovery"; la coppia fingerprint è ricompilata, "its protocol is unchanged" — [docs/release-0.1.12.md](https://github.com/standardagents/t1bridge/blob/v0.1.12/docs/release-0.1.12.md)
- [F] PR aperte e non unite, dopo v0.1.12: #47 (risveglio del display al probe e al riarmo), #49 (sblocco del pannello al resume), #58 (SOCW(0)/SOCW(1) dall'`appletbdrm` intorno alla sospensione), #54 e #48 (correzioni alla recovery), #60 (ordine di link), #65 (policy SELinux per fprintd), #67 (`PACKAGE_VERSION` di dkms.conf ancora a 0.1.11), #70 (stato del Fn con tastiera "grabbata") — [Pull requests](https://github.com/standardagents/t1bridge/pulls)
- [F] Il `dkms.conf` della v0.1.12 dichiara `PACKAGE_VERSION="0.1.11"`. È solo un'incoerenza: DKMS prende la versione dalla cartella — `/home/drift/src/t1bridge/kernel/dkms/dkms.conf`; [PR #67](https://github.com/standardagents/t1bridge/pull/67)

### Inferences
- [I] Il progetto è di fatto fermo lato manutentore da 2 mesi. Le correzioni utili per il 14,3 (sospensione, firewall, usbmuxd) esistono, ma come workaround dei tester, non nei pacchetti firmati.
- [I] Chi installa oggi riceve gli stessi binari del 20/09: tutti i limiti elencati sotto valgono per lo stack "ufficiale".

### Gaps
- Nessuna dichiarazione pubblica di abbandono o pausa: il silenzio del manutentore è osservato, non spiegato.
- GitHub Discussions non controllate; nessuna discussione è citata nelle issue.

## 2. Stato del Touch ID per modello (enrollment, riconoscimento, cancellazione, persistenza, PAM)

### Takeaway
Sul **14,3** enrollment, riconoscimento, sudo, Polkit e persistenza dopo riavvio e spegnimento sono **confermati da più
tester** (Omarchy/Arch, kernel 7.2.x, pacchetti 0.1.1–0.1.12), **a patto** di aprire il firewall per xART. Il README li
segna ancora 🟡. La schermata di blocco funziona, ma causa il blocco del SEP (#14) e molti la disattivano. Sospensione e
riattivazione non sono supportate. La cancellazione è poco provata e ha almeno un caso di identità "orfana" (14,2).

### Cited Findings
- [F] Tabella del README per il 14,3: "🟡 Enrollment confirmed after scoped xART firewall setup; broader coverage unconfirmed". Per il 13,2: 🟢 Touch Bar, Touch ID e persistenza dopo riavvio. Per il 13,3: 🟢 su due macchine. Per il 14,2: 🟡 con problemi di coperchio/resume e del relay — [README.md](https://github.com/standardagents/t1bridge/blob/v0.1.12/README.md#supported-hardware)
- [F] Funzioni dichiarate nel README: enrollment, riconoscimento e cancellazione 🟢 ("up to three enrolled fingers for one Linux owner"); sudo/Polkit/blocco 🟡 "Requires configuration"; impronte dopo riavvio 🟢; "T1 sleep/wake ... 🔴 Not working on the tested machine" — [README.md](https://github.com/standardagents/t1bridge/blob/v0.1.12/README.md#t1-function-support)
- [F] **14,3, primo tester (#2)**: su 0.1.0-63 ogni enrollment falliva (`START_ENROLLMENT` con status SEP 1 o `kIOReturnTimeout`). Causa: **ufw con default-deny che bloccava il TCP 61500 dal T1**. Dopo la regola limitata, uno spegnimento completo e i pacchetti 0.1.1 invariati: `enroll-completed`; il manutentore conferma "fresh enrollment works on your 14,3". Issue chiusa il 06/09 — [Issue #2](https://github.com/standardagents/t1bridge/issues/2)
- [F] **14,3, secondo tester (#2)**: "Confirmed working on MacBookPro14,3 with v0.1.2 and the scoped xART firewall rule". 7 tentativi falliti prima della regola: il primo in timeout dopo ~10 s, gli altri falliti in ~7 ms. Anche il blocco schermo di Omarchy funziona. Nota: la riga `xart-admission` di `t1bridge status` dava un falso negativo con la configurazione funzionante — [Issue #2, commento CG-8663 07/09](https://github.com/standardagents/t1bridge/issues/2)
- [F] **14,3, terzo tester (#50, 0.1.12, Omarchy 4.0.4, kernel 7.2.5)**: "Touch Bar, enrollment, verification, sudo and Polkit by fingerprint work, and enrolled prints survive reboots and full power-offs". Impronta disattivata sulla schermata di blocco per via di #14. Al primo enrollment su installazione pulita ha avuto `prepare device keybag failed` e poi `sep-lease -111`, risolti dopo un ping al T1 sulla rete NCM — [Issue #50](https://github.com/standardagents/t1bridge/issues/50)
- [F] **14,3, quarto tester (#14, 0.1.12)**: il riconoscimento funziona, ma dopo 23–34 minuti di schermata di blocco il keybag si blocca. sudo funziona di nuovo dopo uno spegnimento completo — [Issue #14, commenti makoni 09/10 e 11/11](https://github.com/standardagents/t1bridge/issues/14)
- [F] **14,3 con dati rigenerati da t1-revive** (ESP Apple cancellata): l'import automatico falliva nel sandbox (#36, chiusa come corretta in v0.1.10, conferma sul campo "pending"); `import --from /boot` funziona e poi l'enrollment riesce. Un altro 14,3 rigenerato ha il display che non risponde (-110, #31), ma il Touch ID funziona — [Issue #36](https://github.com/standardagents/t1bridge/issues/36); [Issue #31](https://github.com/standardagents/t1bridge/issues/31)
- [F] **13,2 (#5)**: su v0.1.1 confermati controlli della Touch Bar, enrollment e verifica di due dita, persistenza dopo riavvio e consumatori PAM configurati. Camera e sospensione non provate — [README.md](https://github.com/standardagents/t1bridge/blob/v0.1.12/README.md); [Issue #5](https://github.com/standardagents/t1bridge/issues/5)
- [F] **13,2 con hook SOCW (#68)**: la Touch Bar torna dopo la sospensione, ma "there is still a problem on the TouchID, i couldn't login ... after hibernation/suspend exit". Un tester 13,3 attribuisce il proprio caso a un vecchio hook che mascherava `fprintd` — [Issue #68](https://github.com/standardagents/t1bridge/issues/68)
- [F] **13,3 su Fedora 45 (#66, #59) da sorgente**: enrollment e verifica ok. Servivano la policy SELinux (#65) e l'override di usbmuxd (#64). Il primo enrollment è riuscito solo dopo `systemctl restart t1-touchid-auth.service`. Cancellazione, duplicato e dita piene "not run" — [Issue #66](https://github.com/standardagents/t1bridge/issues/66)
- [F] **14,2 su Ubuntu 26.04 (#62) da sorgente**: Touch ID ok dopo un riavvio del broker al primo tentativo; sudo e Polkit ok; GDM e blocco GNOME tenuti lontani dal lettore per via di #14 — [Issue #62](https://github.com/standardagents/t1bridge/issues/62)
- [F] **14,2 (#57, 0.1.12) cancellazione/persistenza**: dopo l'attivazione di ufw ogni operazione falliva (`Restore ... LoadMaster` 726, poi `Policy(NativeStatus { status: 1 })`), anche dopo un avvio a freddo; anche `fprintd-delete` falliva. Con la regola ufw per il 61500 Touch ID torna, ma l'identità registrata in precedenza resta nel SEP **senza che fprintd la veda**: non si può cancellare, e quel dito dà `enroll-duplicate`. Domanda aperta senza risposta. Effetto collaterale: `pam_faillock` ha bloccato l'account per 10 minuti — [Issue #57](https://github.com/standardagents/t1bridge/issues/57)
- [F] Il release gate segna come **non ancora verificati**: la prova completa di duplicato, dita piene, cancellazione ed enrollment sui pacchetti pubblicati; il ripiego sulla password con broker spento per Polkit e blocco schermo; la validazione del peer xART su macchine diverse — [docs/release-gate/v1.md](https://github.com/standardagents/t1bridge/blob/v0.1.12/docs/release-gate/v1.md)

### Inferences
- [I] Per il 14,3 il README è prudente rispetto ai dati: almeno 3–4 tester indipendenti riportano enrollment, verifica, sudo/Polkit e persistenza. Il punto debole non è il riconoscimento, ma il ciclo di vita (relay e SEP, sospensione).
- [I] Un fallimento del primo enrollment su installazione nuova è ricorrente su più modelli (firewall, broker da riavviare, link NCM silenzioso). Va messo in conto un debug iniziale.

### Gaps
- Nessun report sul 14,3 con **CachyOS** e kernel **7.3.x clang** per il Touch ID. L'unico 14,3 su `7.3.4-1-cachyos` (#69) riguarda la recovery online, non l'enrollment.
- Cancellazione mirata (`fprintd-delete -f`) sul 14,3: nessun report esplicito.

## 3. Le issue richieste e quelle nuove: sintomi, workaround, risposte, stato

### Takeaway
Restano aperti i problemi strutturali: blocco del relay e del keybag dopo circa 68 attivazioni per avvio (#14), Touch Bar
spenta dopo la sospensione (#18/#68), display spenti (#31/#34). Le correzioni chiuse riguardano setup e import (#2, #36,
#21, #15). Le soluzioni alla sospensione esistono solo come hook della comunità (SOCW via `acpi_call` più report HID 3).

### Cited Findings
- [F] **#2 (14,3) — CHIUSA 06/09/2026**: causa xART bloccato dal firewall; risolta con una regola ufw limitata. Ne è nata la PR #4 (diagnostica `xart-admission` in `t1bridge status`, distinzione tra chiusura pulita e troncamento in xART), unita e rilasciata in v0.1.2 — [Issue #2](https://github.com/standardagents/t1bridge/issues/2)
- [F] **#5 (13,2) — CHIUSA**: report positivo del tester (vedi sezione 2) — [Issue #5](https://github.com/standardagents/t1bridge/issues/5)
- [F] **#14 loop di riavvio del relay — APERTA (31 commenti)**. Sintomo: dopo un certo numero di cicli, la promozione del keybag (`selector=0x0d`) viene rifiutata con "activate biometric keybag failed"; da lì ogni caricamento fallisce (`load biometric keybag failed`) e systemd riavvia in loop (backoff 2→60 s da v0.1.6). Tutto il Touch ID resta fermo fino a uno **spegnimento completo** (il riavvio non basta). Due tester (un 14,2 e un 14,3) contano **68 attivazioni del relay per avvio** prima del blocco, con totale costante. Ogni giro della schermata di blocco (~31 s, legato a `MAX_MATCH_TIMEOUT` di 30 s) e **ogni sospensione** consumano un'attivazione. `pam_fprintd timeout=-1` non aiuta. Workaround dei tester: disattivare l'impronta sulla schermata di blocco, tenere sudo/Polkit. L'ultima risposta del manutentore (20/09) dice che il blocco non è riprodotto né corretto — [Issue #14](https://github.com/standardagents/t1bridge/issues/14)
- [F] **#18 sospensione/riattivazione — APERTA (16 commenti)**. Su 14,3 (S3) Touch Bar e Touch ID muoiono dopo il resume. Correzione dei tester: chiamare `\_SB.PCI0.XHC1.RHUB.ASOC.SOCW 1` via `acpi_call` dopo il resume, poi scrivere il feature report 3 `03 02 f4 01` sull'interfaccia HID 6 del T1 per la luminosità. Con s2idle basta il report 3. Un tester 14,3 riporta 31/31 resume S3 riusciti con entrambi gli hook. Avvertenza ripetuta: **mai chiamare `ASOC.FRST`**, lascia il T1 in recovery (`05ac:1281`) — [Issue #18](https://github.com/standardagents/t1bridge/issues/18)
- [F] **#68 (14,3, s2idle) — APERTA**: con le correzioni di piattaforma l'host sospende, ma il pannello resta spento finché non si manda la coppia `SOCW(0)` prima e `SOCW(1)` dopo, da un hook `system-sleep`. Un tester 13,3 con S3: Touch ID funziona dopo il resume con la coppia SOCW — [Issue #68](https://github.com/standardagents/t1bridge/issues/68)
- [F] Un tester 14,2 osserva che **a ogni S3 il relay esce** ("receive keybag notifications failed") e systemd lo riavvia dopo circa 2 s. Questo consuma il budget di #14 — [Issue #14, commento dreinecke 11/11](https://github.com/standardagents/t1bridge/issues/14)
- [F] **#31 (14,3, dati rigenerati) — APERTA**: il probe del display di `appletbdrm` va in timeout (-110), Touch Bar spenta. Su un altro 14,3, dopo l'ibernazione: errori -75/-110, "Touch ID kept working", recupero solo con reset del T1 tramite t1-revive (che usa FRST) — [Issue #31](https://github.com/standardagents/t1bridge/issues/31)
- [F] **#34 (13,3) — APERTA**: Touch Bar spenta con `drm: ready`; la v0.1.11 aggiunge solo diagnostica; il manutentore attende dati — [Issue #34](https://github.com/standardagents/t1bridge/issues/34)
- [F] **#36 (14,3) — CHIUSA 20/09**: `t1bridge-import.service` esce con 30 ("private import temporary file could not be created"). Corretto in v0.1.10; conferma sulla macchina del tester "pending". Workaround: `sudo t1bridge machine-data import --from /boot` (o il percorso della ESP Apple) — [Issue #36](https://github.com/standardagents/t1bridge/issues/36)
- [F] **#15 — CHIUSA**: un enrollment lanciato fuori dalla sessione grafica va in timeout per l'autorizzazione Polkit e sembra un problema di firewall — [Issue #15](https://github.com/standardagents/t1bridge/issues/15); [docs/setup.md](https://github.com/standardagents/t1bridge/blob/v0.1.12/docs/setup.md#enrollment-timeouts)
- [F] **#21 — CHIUSA**: l'enrollment falliva subito con `t1bridge-keybag.service` in stato failed; corretto (commit `ed83989`, v0.1.9) — [Issue #21](https://github.com/standardagents/t1bridge/issues/21)
- [F] **#57 (14,2) — APERTA, senza risposta**: identità orfana nel SEP dopo un periodo di firewall bloccato (vedi sezione 2) — [Issue #57](https://github.com/standardagents/t1bridge/issues/57)
- [F] **#64 — APERTA**: la regola udev upstream di usbmuxd (`39-usbmuxd.rules`) forza `bConfigurationValue=1` su `05ac:8600` e annulla `t1_cfgsel`: `usb-configuration: unexpected`, tutto lo stack T1 è giù. Workaround: copia della regola in `/etc/udev/rules.d/` senza le righe `5ac/8600`. Aperta anche la issue upstream libimobiledevice/usbmuxd#291 — [Issue #64](https://github.com/standardagents/t1bridge/issues/64)
- [F] **#51 (14,3) — APERTA**: abilitare `t1-touchbar-hw.service` blocca l'avvio per 90 s se il T1 enumera tardi; udev lo avvia comunque — [Issue #51](https://github.com/standardagents/t1bridge/issues/51)
- [F] **#55 (14,3) — APERTA**: il Fn non cambia la Touch Bar se `keyd` si prende la tastiera SPI; correzione proposta nella PR #70 — [Issue #55](https://github.com/standardagents/t1bridge/issues/55)
- [F] **#29, #46 (13,3, dati rigenerati o recuperati online)**: #29 risolta con import esplicito; #46 ha `LOAD_CALIBRATION` (0x20) rifiutato (codici 302/28) dopo la recovery online. Calibrazione da dati recuperati non garantita — [Issue #29](https://github.com/standardagents/t1bridge/issues/29); [Issue #46](https://github.com/standardagents/t1bridge/issues/46)
- [F] **#69 (14,3, CachyOS 7.3.4) — APERTA**: la recovery online richiede la CA Apple, assente nel bundle Mozilla di Arch (curl code 60), più una correzione della race sullo status finale. Riguarda solo chi ha perso la ESP Apple — [Issue #69](https://github.com/standardagents/t1bridge/issues/69)
- [F] **#72** (richiesta di driver per Windows Hello) e **#71** (Esc tenuto premuto) aperte, non pertinenti al Touch ID su Linux — [Issues](https://github.com/standardagents/t1bridge/issues)

### Inferences
- [I] Per un uso quotidiano senza sorprese sul 14,3 servono oggi tre cose fuori dai pacchetti: (a) la regola firewall; (b) impronta disattivata sulla schermata di blocco, oppure accettare il blocco con spegnimento completo per recuperare; (c) hook SOCW e report 3 per la sospensione, che consumano comunque un'attivazione del relay a ogni ciclo.
- [I] Con sospensione frequente (S3 è [F] attiva su questa macchina, vedi `docs/sleep.md`) il budget di ~68 attivazioni per avvio può esaurirsi in una giornata se si somma l'uso della schermata di blocco. Non c'è un dato diretto per il 14,3 con S3.

### Gaps
- Causa del limite di 68 attivazioni non nota: un tester segnala nel binario stringhe come `request identity exhausted` / `TooManyIdentities` [NV].
- Hook SOCW e PR #58 non provati su CachyOS né combinati con il nostro `macbookpro14-3-sleep-mode.service`.

## 4. Che cosa comporta il "firewall xART" sul 14,3

### Takeaway
Il T1 apre **una connessione TCP in entrata verso l'host, IPv6, porta 61500**, sull'interfaccia di rete privata
`apple_t1_ncm`, che ha nome effimero, spesso `eth0`. Con un firewall che scarta il traffico in entrata la connessione si
perde in silenzio: `t1bridge status` mostra comunque `xart: ready`. Il progetto chiede un'eccezione limitata a
interfaccia e peer, mai globale. Gli esempi ufficiali sono **solo per ufw**. **Su questa macchina ufw è attivo con
`DEFAULT_INPUT_POLICY="DROP"`**: il problema si presenterebbe identico.

### Cited Findings
- [F] "xART needs inbound IPv6 TCP port 61500 on the dynamically discovered private T1 network interface. Keep IPv6 enabled there ... never open the port on Wi-Fi, Ethernet, or all interfaces. Do not save a machine-specific interface name as a portable rule ... Cross-machine peer validation remains an open release gate." — [docs/setup.md](https://github.com/standardagents/t1bridge/blob/v0.1.12/docs/setup.md#firewall-recovery-and-removal)
- [F] Sintomo documentato: "a first enrollment timeout followed by immediate failures until the private link was permitted. `xart: ready` means the service is active, not that inbound traffic reaches it." — [docs/setup.md](https://github.com/standardagents/t1bridge/blob/v0.1.12/docs/setup.md#firewall-recovery-and-removal)
- [F] Forma di regola indicata dal manutentore in #2: `sudo ufw allow in on "${t1_if:?}" proto tcp from "${t1_peer:?}" to any port 61500 comment 'T1Bridge xART'`. "Don't open the port globally, disable UFW, or change its default policy. Verify the installed rule is IPv6-only and T1-scoped." Poi uno spegnimento completo e un solo enrollment — [Issue #2](https://github.com/standardagents/t1bridge/issues/2)
- [F] Regole effettivamente usate dai tester 14,3: `61500/tcp on eth0 ALLOW IN fe80::aede:48ff:fe33:4455` (#2) e `ufw allow in on eth0 proto tcp from fe80::aede:48ff:fe33:4455 to any port 61500` (#50). Lo stesso peer link-local compare su due 14,3 diversi — [Issue #2](https://github.com/standardagents/t1bridge/issues/2); [Issue #50](https://github.com/standardagents/t1bridge/issues/50)
- [F] Sul 14,2 di #57 il log ufw mostrava 44 `UFW BLOCK IN=eth0 ... DPT=61500` dall'interfaccia NCM. Il tester ha sbloccato con `ufw allow in on eth0 to any port 61500 proto tcp` (senza peer) — [Issue #57](https://github.com/standardagents/t1bridge/issues/57)
- [F] Il link systemd del pacchetto tiene il nome assegnato dal driver (`NamePolicy=keep`) e marca l'interfaccia `ID_NET_MANAGED_BY=org.t1bridge`, `NM_UNMANAGED=1`. Una regola udev avvia `t1-xart-storage@<nome>.service` per l'interfaccia 4 di `05ac:8600` — `/home/drift/src/t1bridge/systemd/50-t1bridge-ncm.link`, `/home/drift/src/t1bridge/systemd/90-t1bridge-xart.rules`
- [F] Il listener xART controlla anche lui dispositivo e peer: accetta solo il peer link-local atteso e l'indice di interfaccia corretto. Manca però la prova su hardware di altre macchine e del rifiuto di peer estranei — [docs/security-review/v1.md](https://github.com/standardagents/t1bridge/blob/v0.1.12/docs/security-review/v1.md)
- [F] Su un 14,3 appena installato la rete NCM non riceveva pacchetti dal T1 finché il tester non ha fatto ping a `fe80::aede:48ff:fe33:4455%eth0`. Dopo, il T1 si è collegato a xART da solo — [Issue #50](https://github.com/standardagents/t1bridge/issues/50)
- [F] **Questa macchina**: `ufw` abilitato e attivo, `/etc/ufw/ufw.conf ENABLED=yes`, `/etc/default/ufw` con `IPV6=yes` e `DEFAULT_INPUT_POLICY="DROP"`. Nessuna regola per 61500 in `user6.rules`. `firewalld` non installato, `nftables.service` disabilitato (verificato in sola lettura il 24/11/2026).
- [F] Il progetto non dà ricette per nftables o firewalld: `docs/setup.md` è generico, gli esempi concreti sono solo ufw — `/home/drift/src/t1bridge/docs/setup.md` (grep: nessuna occorrenza di nft/firewalld)

### Inferences
- [I] Su CachyOS con ufw basterebbe la stessa regola dei tester, con interfaccia e peer verificati al momento (`ip -6 addr`/`ip -6 neigh` sull'interfaccia `apple_t1_ncm`). Essendo legata al nome `eth0`, smette di valere se il nome cambia (per esempio con un adattatore USB-Ethernet collegato prima).
- [I] Equivalente nftables non ufficiale: in una catena input con `iifname <t1_if> ip6 saddr fe80::aede:48ff:fe33:4455 tcp dport 61500 accept`. Con firewalld servirebbe una zona dedicata all'interfaccia T1 con una rich rule per la sorgente IPv6. Nessuna di queste forme è documentata o provata dal progetto [NV].
- [I] Una regola udev o un dispatcher che crei la regola al volo sull'interfaccia `apple_t1_ncm` (chiesto in #50) eviterebbe il nome fisso. Non esiste nei pacchetti.

### Gaps
- Non è confermato dal progetto che il peer `fe80::aede:48ff:fe33:4455` sia costante su tutti i T1: "cross-machine peer validation" è ancora aperta.

## 5. Design di sicurezza dichiarato dal progetto

### Takeaway
Il riconoscimento avviene nel Secure Enclave del T1. Un broker root unico, attivato via socket, fa da tramite verso una
coppia libfprint/fprintd patchata che **sostituisce quella della distribuzione in tutto il sistema**. Lo stato protetto è
root-only in `/var/lib/t1bridge`. Il PAM resta `pam_fprintd` standard, che l'utente configura da sé mantenendo la
password. I pacchetti sono firmati GPG con la sottochiave di release. Il "release gate" ammette apertamente prove ancora
mancanti.

### Cited Findings
- [F] "Linux applications use fprintd. Its libfprint driver asks T1Bridge to perform the operation; T1Bridge coordinates the T1 Secure Enclave, where finger capture and matching happen. The Touch Bar displays progress and results but cannot authorize anything." — [docs/touch-id.md](https://github.com/standardagents/t1bridge/blob/v0.1.12/docs/touch-id.md)
- [F] Dati macchina Apple (`FDRData`) importati in locale da una ESP Apple della stessa macchina, mai distribuiti nei pacchetti. "Protected state remains root-owned on the machine; other users and the renderer do not receive it." — [docs/touch-id.md](https://github.com/standardagents/t1bridge/blob/v0.1.12/docs/touch-id.md)
- [F] tmpfiles: `/var/lib/t1bridge`, `machine-data`, `touch-id`, `touch-id/catacombs`, `touch-id/xart` tutte `0700 root root`; `/run/t1bridge` `0750 root t1bridge`; lock SEP `/run/lock/t1-touchid-sep.lock` `0600 root` (evita che un utente lo crei prima e blocchi il servizio) — `/home/drift/src/t1bridge/systemd/t1bridge.conf`; [security review](https://github.com/standardagents/t1bridge/blob/v0.1.12/docs/security-review/v1.md)
- [F] Controllo dei peer: "the standard path admits only UID 0, resolves its asserted account, rejects unprivileged cross-user requests before mutation". Il driver libfprint è solo per root; l'autorizzazione all'enrollment resta quella Polkit di fprintd (`net.reactivated.fprint.device.enroll`) — [docs/security-review/v1.md](https://github.com/standardagents/t1bridge/blob/v0.1.12/docs/security-review/v1.md); [docs/setup.md](https://github.com/standardagents/t1bridge/blob/v0.1.12/docs/setup.md#enrollment-timeouts)
- [F] Ripiego PAM: "Fingerprint failure must never lock out the password path. This depends on the consumer's PAM configuration: T1Bridge does not edit it". `setup.md`: "T1Bridge does not replace PAM files or ship a custom PAM module"; timeout predefinito 30 s; la conversazione PAM seriale può ritardare il prompt della password — [docs/touch-id.md](https://github.com/standardagents/t1bridge/blob/v0.1.12/docs/touch-id.md); [docs/setup.md](https://github.com/standardagents/t1bridge/blob/v0.1.12/docs/setup.md#enable-fingerprint-sign-in-safely)
- [F] Nel repository c'è `pam/pam_t1_touchid.c`, ma la security review lo definisce "source-only rollback tooling", non distribuito; il release gate: "No ... direct PAM module is shipped in core" — `/home/drift/src/t1bridge/pam/`; [release-gate](https://github.com/standardagents/t1bridge/blob/v0.1.12/docs/release-gate/v1.md)
- [F] Sostituzione in tutto il sistema: `libfprint-t1bridge` ha `provides=libfprint=1.94.100, libfprint-2.so` e `conflicts=libfprint`; `fprintd-t1bridge` ha `provides=fprintd=1.94.5`, `conflicts=fprintd` e dipende dalla versione esatta di `libfprint-t1bridge`. Patch: driver T1Bridge per libfprint; per fprintd "Honor driver-native duplicate detection" — `/home/drift/src/t1bridge/packaging/arch/*/PKGBUILD`; [docs/dependencies.md](https://github.com/standardagents/t1bridge/blob/v0.1.12/docs/dependencies.md)
- [F] Firma: repository con `SigLevel = Required DatabaseRequired`; chiave primaria `35B166F78B063B04DE1E3D913E6C4216EB03D371`. La firma in CI usa solo la sottochiave di release, nell'ambiente GitHub `release` limitato a `main` e senza bypass amministratore; la chiave primaria resta fuori da GitHub. Corretti difetti del flusso di firma (file extra, checksum incompleti, tag firmati da chiavi estranee) — [README.md](https://github.com/standardagents/t1bridge/blob/v0.1.12/README.md#1-trust-the-signing-key); [release-gate](https://github.com/standardagents/t1bridge/blob/v0.1.12/docs/release-gate/v1.md); [security review](https://github.com/standardagents/t1bridge/blob/v0.1.12/docs/security-review/v1.md)
- [F] Prove del release gate ancora mancanti: runbook completo su due macchine; diagnosi originale dell'enrollment sul 14,3; accettazione dal vivo dell'import; prova completa delle operazioni sui pacchetti pubblicati; ripiego con broker spento per Polkit e blocco schermo; revoca del seat dal vivo; validazione del peer xART tra macchine e rifiuto di peer estranei; revisione della provenienza di sorgenti e storia. Sospensione/riattivazione: "not supported currently" — [docs/release-gate/v1.md](https://github.com/standardagents/t1bridge/blob/v0.1.12/docs/release-gate/v1.md)
- [F] Test sintetici: libfprint patchato 132/132, fprintd 560/560 su bus mock con `pam_wrapper`; "These are synthetic results, not live password-fallback evidence." — [docs/security-review/v1.md](https://github.com/standardagents/t1bridge/blob/v0.1.12/docs/security-review/v1.md)
- [F] Sandbox systemd: `t1bridge-import.service` con `ProtectSystem=strict`, `PrivateMounts`, `DevicePolicy=closed`, solo `CAP_SYS_ADMIN`; `t1bridge-keybag.service` senza capability, `PrivateNetwork=yes`, `Restart=on-failure` con `RestartSteps=5`/`RestartMaxDelaySec=60` — `/home/drift/src/t1bridge/systemd/t1bridge-import.service`, `/home/drift/src/t1bridge/systemd/t1bridge-keybag.service`
- [F] Il progetto è sviluppato in gran parte da un "coding agent" del manutentore: commenti firmati "Update from @andrew-boyd's coding agent" — [Issue #2](https://github.com/standardagents/t1bridge/issues/2)

### Inferences
- [I] Il disegno è prudente (fallisce chiuso, password sempre disponibile se il PAM è configurato bene). Restano però critici, e senza prova su hardware, il ripiego per Polkit e blocco schermo e l'admission xART. #57 mostra che un `pam_fprintd` messo in testa allo stack con `pam_faillock` può bloccare l'account se il broker fallisce subito.
- [I] Coerente con la regola 4 di AGENTS.md: codice in gran parte scritto da IA, un solo manutentore oggi silente. Va letto e pinnato prima di fidarsi.

### Gaps
- Nessun audit di sicurezza esterno indipendente trovato; la security review è del progetto stesso.

## 6. Footprint di installazione e disinstallazione

### Takeaway
Quattro pacchetti (più uno opzionale per Omarchy): servizi e socket systemd, utente/gruppo `t1bridge`, regole udev, link
di rete, 4 moduli DKMS in `updates/dkms` (incluso un **`uvcvideo` e un `appletbdrm` che prendono il posto di quelli del
kernel**), un drop-in mkinitcpio, e il blocco esplicito dei driver `apple_ibridge`/`apple_ib_tb`/`apple_ib_als`. **Questo
lo rende incompatibile con lo stack Touch Bar attuale di questa repo.** La disinstallazione documentata è manuale e lascia
stato su disco. Un ritorno pulito allo stato originale non è garantito né automatico.

### Cited Findings
- [F] Comando di installazione: `pacman -Syu --needed linux-headers t1bridge t1bridge-dkms libfprint-t1bridge fprintd-t1bridge`. Per Touch Bar e camera senza Touch ID si omettono i due pacchetti fingerprint — [README.md](https://github.com/standardagents/t1bridge/blob/v0.1.12/README.md#2-add-the-repository-and-install)
- [F] `t1bridge` (0.1.12-1) dipende da `curl gcc-libs glibc iio-sensor-proxy libarchive openssl systemd>=256 xz`. Installa: binari in `/usr/lib/t1bridge/` (`t1-touchbar-hw`, `t1-touchbar`, `t1-xart-storage`, `t1-ncm-ready`, `t1-keybag-relay`, `t1-touchid-auth`, `t1-legacy-recovery`), `/usr/bin/t1bridge`, `/usr/bin/t1-touchid`. Unità di sistema: `t1-touchbar-hw.service/.socket`, `t1-xart-storage@.service`, `t1-ncm-ready@.service`, `t1bridge-keybag.service`, `t1-touchid-auth.service/.socket`, `t1bridge-fingerprint.socket`, `t1bridge-import.service`. Unità utente: `t1-touchbar.service`. Inoltre preset, sysusers, tmpfiles, `50-t1bridge-ncm.link`, udev `99-zz-t1bridge-touchbar.rules` e `90-t1bridge-xart.rules` — `/home/drift/src/t1bridge/packaging/arch/t1bridge/PKGBUILD`
- [F] `t1bridge-dkms` (0.1.12-1): moduli `t1_cfgsel`, `appletbdrm`, `apple_t1_ncm`, `uvcvideo` in `/updates/dkms` con AUTOINSTALL. `/etc/mkinitcpio.conf.d/t1bridge.conf` aggiunge `MODULES+=(t1_cfgsel)`. `modules-load.d`. `modprobe.d` con `install apple_ibridge /usr/bin/true`, `install apple_touchbar /usr/bin/true`, `install apple_ib_tb /usr/bin/true`, `install apple_ib_als /usr/bin/true` ("legacy firmware-mode HID drivers conflict") — `/home/drift/src/t1bridge/packaging/arch/t1bridge-dkms/`; `/home/drift/src/t1bridge/kernel/dkms/dkms.conf`
- [F] Preset: abilita `t1-touchbar-hw.service`, `t1-touchid-auth.socket` e `t1bridge-fingerprint.socket`; disabilita `t1bridge-keybag.service`. Il README fa abilitare a mano gli stessi tre e aggiungere l'utente al gruppo `t1bridge` — `/home/drift/src/t1bridge/systemd/80-t1bridge.preset`; [README.md](https://github.com/standardagents/t1bridge/blob/v0.1.12/README.md#3-enable-hardware-support)
- [F] I PKGBUILD non hanno script `.install`: nessun hook post-install o post-remove — `/home/drift/src/t1bridge/packaging/arch/` (nessun file `*.install`)
- [F] Versioni provate: kernel Arch `7.1.9-arch1-2` su hardware; in CI compilati i moduli anche su `7.2.2-arch1-1`. "These are tested versions, not a guarantee for every kernel" — [docs/dependencies.md](https://github.com/standardagents/t1bridge/blob/v0.1.12/docs/dependencies.md#supported-and-tested-versions)
- [F] Disinstallazione documentata: prima ripristinare e provare l'autenticazione con sola password; fermare renderer, servizi, socket e istanze xART; rimuovere i pacchetti; "restore the distribution's matched libfprint/fprintd pair if needed"; rigenerare l'initramfs. "Package removal is not authorization to erase protected state or the preserved Apple EFI partition." — [docs/setup.md](https://github.com/standardagents/t1bridge/blob/v0.1.12/docs/setup.md#firewall-recovery-and-removal)
- [F] Su dracut (Ubuntu) i moduli DKMS finiscono nell'initrd. Un tester chiede che il pacchetto rigeneri l'initrd anche alla rimozione, altrimenti `t1_cfgsel` resta nel vecchio initrd — [Issue #62](https://github.com/standardagents/t1bridge/issues/62)
- [F] Il README avverte di non lanciare procedure guidate desktop che sostituiscono la coppia libfprint/fprintd. La configurazione impronte di Omarchy la sostituirebbe con `libfprint-git`/`fprintd` (correzione in omacom/omarchy#14627) — [README.md](https://github.com/standardagents/t1bridge/blob/v0.1.12/README.md#4-set-up-touch-id); [Issue #50](https://github.com/standardagents/t1bridge/issues/50)

### Inferences
- [I] Dopo `pacman -R` restano: `/var/lib/t1bridge` (keybag, catacomb, xART, calibrazione), utente/gruppo `t1bridge` creati da sysusers, link di abilitazione creati a mano con `systemctl enable` (dangling), regole firewall aggiunte a mano, le impronte nel SEP del T1. Su CachyOS non restano libfprint/fprintd: pacman li ha rimossi per conflitto e vanno reinstallati.
- [I] Il T1 resterebbe nella configurazione USB scelta fino al riavvio. Dopo la rimozione di `t1_cfgsel` e dei blocchi in modprobe, e la rigenerazione dell'initramfs, dovrebbe tornare la configurazione 1 con i driver `apple-ibridge` attuali [NV].
- [I] I DKMS di T1Bridge non impostano `LLVM=1` in `dkms.conf`. Su `linux-cachyos` compilato con clang potrebbe servire lo stesso accorgimento usato per `apple-ibridge` in `patches/touchbar/` [NV].
- [I] Conflitti con questa repo: (1) blocco di `apple_ibridge`/`apple_ib_tb`/`apple_ib_als`: Touch Bar in modalità tastiera, sensore di luce attuale e curva KWin che ne dipende; (2) `uvcvideo` DKMS al posto di quello del kernel; (3) la Touch Bar grafica [F] già in uso con `install-touchbar-display.sh` (T1Bridge) va verificata per versione e coerenza con i pacchetti fingerprint; (4) usbmuxd (#64) e ufw (sezione 4).

### Gaps
- Nessun tester ha documentato una disinstallazione completa con verifica del ritorno allo stato originale (driver legacy, fprintd di distribuzione).
- Non verificato se le impronte restano nel SEP dopo la disinstallazione, né se interferiscono con un reinstallo o con macOS.
