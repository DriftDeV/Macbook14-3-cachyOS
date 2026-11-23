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
| `config/sleep/s2idle.conf` → `/etc/systemd/sleep.conf.d/10-macbookpro14-3.conf` | `MemorySleepMode=s2idle`, ibernazione/ibride disattivate |
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

## Da verificare [NV]

- Sospensioni lunghe (notte, a batteria): consumo e risvegli spuri (la prova `real` è finita 24 s prima della sveglia RTC).
- Kernel LTS 6.18.
- Periferiche USB-C/Thunderbolt collegate durante lo sleep (la fonte dice che possono sparire fino al prossimo sleep).
- Molti cicli di fila (il report di ricerca indica 20 cicli come obiettivo).
- Ibernazione: resta disattivata finché il kernel non ha la patch amdgpu "reset VI ASIC on Apple boards with VRAM at 0".
