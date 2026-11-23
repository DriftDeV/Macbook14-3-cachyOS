# Sospensione su MacBookPro14,3: risultati verificati

Data: 23 novembre 2026. Macchina: MacBookPro14,3, CachyOS, kernel `7.3.5-2-cachyos`, KDE Plasma 6.8 (Wayland),
caricatore collegato, nessuna periferica USB-C. Tag come in [`README.md`](README.md).

## Problema

- [F] Installazione pulita: `/sys/power/mem_sleep` = `s2idle [deep]`, cioè S3 di default. Chiudendo il coperchio
  il Mac non si risvegliava più (segnalato dall'utente; il blocco non è nel journal, che conserva solo i boot successivi).
- Cause secondo `mihneadevries/mbp14-3-linux-sleep-fix` (commit `4fc3328`, 14,3, kernel 7.2), codice letto prima dell'uso:
  1. [F fonte] Il firmware toglie corrente ai due controller Thunderbolt Alpine Ridge; il kernel resta fermo 80-100 s
     (o non riparte) sui bridge spenti, sia in S3 sia in s2idle.
  2. [F fonte] In S3 `amdgpu` (Radeon Pro 560) non riparte: "SMU load firmware failed (-22)". Stesso errore con l'ibernazione.
  3. [F fonte] L'SSD (SM961, `02:00.0` su questa macchina) non torna da D3cold.

## Topologia di questa macchina [F]

| Dispositivo | Indirizzo |
|---|---|
| Radeon Pro 555/560 | `01:00.0` (non è l'SSD, a differenza dei 13") |
| SSD NVMe Samsung SM961 | `02:00.0` |
| Wi-Fi BCM43602 | `03:00.0` (root port `00:1c.0`) |
| Thunderbolt upstream port (8086:1578) | `04:00.0` (root `00:01.1`), `7a:00.0` (root `00:01.2`) |

Identica a quella della fonte.

## Correzione (in `scripts/install-sleep.sh`)

| File | Effetto |
|---|---|
| `config/sleep/macbookpro14-3-sleep.sh` → `/usr/lib/systemd/system-sleep/` | prima: rimuove gli upstream port TB (cercati come `8086:1578`) e scarica `brcmfmac`; dopo: rescan dei root port e ricarica `brcmfmac` |
| `config/sleep/s2idle.conf` → `/etc/systemd/sleep.conf.d/10-macbookpro14-3.conf` | `MemorySleepMode=s2idle` di ripiego, ibernazione/ibride disattivate |
| `config/systemd/macbookpro14-3-sleep-mode.service` + `config/sleep/deep.conf` | sui kernel >= 7.3 copia `MemorySleepMode=deep` in `/run/systemd/sleep.conf.d/20-macbookpro14-3-deep.conf` (vince sul file sopra); `systemctl stop` torna a s2idle fino al riavvio |
| `config/udev/90-macbookpro14-3-nvme-no-d3cold.rules` | `d3cold_allowed=0` sulle classi `0x010802` |
| `config/tmpfiles/macbookpro14-3-pm.conf` | `pm_async=0` |

- Touch Bar: niente in più. `apple-ibridge` chiama già `ASOC.SOCW` 0/1 e `apple-ib-tb` (`t1-fixes`) ha il `.resume`
  per s2idle, quindi `acpi_call` e la patch del driver della fonte non servono.
- UPower è su `CriticalPowerAction=Auto`: senza ibernazione ripiega sullo spegnimento, non è stato toccato.
- Logind/KDE: la chiusura del coperchio sospende già di default, nessuna configurazione aggiunta.

## Prove (`scripts/sleep-test.sh`) [F]

| Prova | Risultato |
|---|---|
| `platform` (pm_test, tutte le fasi senza dormire) | ripresa in 10 s; 37 funzioni PCI, 3 xHCI, Wi-Fi, Touch Bar (`suspended`/`resumed`) tornati |
| `real 60` (sveglia RTC) | ripresa riuscita; in sleep 36 s, cioè svegliato **prima** della sveglia (forse un tasto, vedi sotto) |
| coperchio chiuso ~20 s | sospeso 3 s dopo la chiusura, svegliato dall'apertura, ripresa ~1 s; tutto funzionante secondo l'utente |

`suspend_stats`: 3 successi, 0 fallimenti. Il coperchio (`LID0`) risveglia la macchina da s2idle.

Nota: nel journal i timestamp monotonic non avanzano durante lo sleep; per le durate usare `journalctl -o short-iso`.

## s2idle non è un vero sonno su questo Mac → S3 (23/11/2026) [F]

Segnalato dall'utente: dopo una lunga sospensione a coperchio chiuso ventole accese e Mac tiepido (rischio in uno zaino).

| Misura (s2idle) | Risultato |
|---|---|
| FADT, flag `LOW_POWER_S0_IDLE` (bit 21) | assente (`flags=0x0000c4a5`); niente tabella LPIT né dispositivo LPS0 (`PNP0D80`) |
| Package C-state più profondo (`pmc_core`) | **C3**; C6-C10 sempre a 0 |
| Ventole | restano al minimo (~2160 rpm): l'SMC non vede la piattaforma ferma |
| Risvegli spontanei | 2 in ~1 h 40 min, dopo 31 e 40 min di sospensione; logind risospende dopo ~18 s perché il coperchio è chiuso |
| Causa dell'ultimo risveglio | IRQ 9 (ACPI SCI, controller embedded) |

Conclusione: senza S0ix nel firmware, s2idle lascia piattaforma, ventole e Radeon accese. Lo stato "congelato"
come su macOS è S3.

| Prova S3 (`deep`), kernel 7.3.5-2-cachyos, Touch Bar in modalità display | Risultato |
|---|---|
| sveglia RTC 60 s | `ACPI: PM: Preparing to enter system sleep state S3`, ripresa riuscita. amdgpu fa `PCI CONFIG reset` prima dello sleep e riparte (GART, UVD, VCE) **senza** l'errore SMU -22 della fonte (kernel 7.2); Radeon in D0. Svegliato dopo ~30 s invece di 60, causa ignota (la sveglia RTC è scattata dopo il risveglio; vedi la stessa anomalia con s2idle sopra) |
| coperchio chiuso ~1 min | sospeso 10 s dopo la chiusura, ripreso all'apertura; Touch Bar (display), Wi-Fi, Thunderbolt tornati |
| ventole | **ferme** durante la sospensione (sentito dall'utente) |

La Radeon `1002:67ef`, subsystem `106b:0179`, rev `c0` non è nella tabella `vi_reset_quirks` di v7.3 e il commit
generico `92a5184787b8` non è in v7.3 [F dal sorgente]: la ripresa funziona comunque [F], meccanismo non chiarito [I].
Per prudenza S3 si attiva solo sui kernel >= 7.3 (servizio con `ConditionKernelVersion`); LTS 6.18 resta su s2idle.

Controllo dopo una notte: `scripts/sleep-test.sh report` (senza root) elenca ogni sospensione con durata, modalità,
batteria (l'hook scrive % e mAh prima e dopo) e se il Mac si è svegliato **senza** aprire il coperchio.

## Da verificare [NV]

- S3 a lungo (notte, zaino): risvegli spuri e consumo (atteso molto più basso di s2idle).

- Kernel LTS 6.18.
- Periferiche USB-C/Thunderbolt collegate durante lo sleep (la fonte dice che possono sparire fino al prossimo sleep).
- Molti cicli di fila (il report di ricerca indica 20 cicli come obiettivo).
- Ibernazione: resta disattivata finché il kernel non ha la patch amdgpu "reset VI ASIC on Apple boards with VRAM at 0".
