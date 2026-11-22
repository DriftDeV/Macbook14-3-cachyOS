# MacBookPro14,3 (15" 2017, T1): Wi-Fi, Bluetooth, camera, SD, Thunderbolt/USB, sensors on Linux (as of Nov 2026)

Research limitations: wiki.archlinux.org and aur.archlinux.org returned Anubis "Access Denied" to the fetch tool, so the Arch Wiki MacBookPro14,x page and AUR package pages could NOT be read directly. Findings come from GitHub repos, a linux-hardware.org probe, Arch forum, gists and search snippets. Search-snippet-only items are marked.

## Premise check: FaceTime HD camera (facetimehd / Broadcom 1570 PCIe)

### Takeaway
The assumption in the brief is most likely wrong for this model. MacBookPro14,3 is a Touch Bar/T1 machine; its camera is exposed over USB through the T1 "iBridge" and uses in-kernel uvcvideo, not the PCIe facetimehd driver (14e4:1570). facetimehd/facetimehd-firmware are probably not needed.

### Cited Findings
- On Touch Bar models the FaceTime HD camera connects through the iBridge device over USB and works with `uvcvideo` out of the box; only the non-Touch-Bar MacBookPro13,1 uses PCIe + `bcwc_pcie` — [Dunedan/mbp-2016-linux README](https://github.com/Dunedan/mbp-2016-linux/blob/master/README.md)
- On 13,3 and 14,3 the camera works without extra setup on kernel 4.13+; other models need `bcwc_pcie` — [roadrunner2 gist](https://gist.github.com/roadrunner2/1289542a748d9a104e7baec6a92f9cd7)
- The linux-hardware.org probe of a MacBookPro14,3 lists no 14e4:1570 PCI device; it lists USB `05ac:8600` Apple iBridge (class camera, driver usbhid) — [HW probe be950ca432](https://linux-hardware.org/?probe=be950ca432)
- The iBridge boots in a limited USB configuration (two HID interfaces, no UVC) and falls back to configuration 0 after about two minutes if nothing claims it; forcing USB re-enumeration makes the camera appear (`ls /dev/video0`). A script `fix-touchbar-t1.sh` handles this — [cschaba/macbookpro14-3-linux](https://github.com/cschaba/macbookpro14-3-linux)
- Same repo: camera and Touch Bar stop working after a kernel upgrade until `fix-touchbar-t1.sh` is re-run (verified 7.2.2 to 7.2.4 on 2026-09-14); `lsusb` shows `05ac:8600` when T1 firmware is healthy and `05ac:1281` (recovery mode) when firmware is gone — [cschaba repo](https://github.com/cschaba/macbookpro14-3-linux)
- For reference only (not applicable to 14,3): facetimehd supports PCI ID 14e4:1570, firmware via separate repo https://github.com/patjak/facetimehd-firmware (default fw 5.60.0, 1.43.0 via `make FW_VER=1.43.0`, needs GNU cpio), driver repo https://github.com/patjak/facetimehd, wiki https://github.com/patjak/facetimehd/wiki; suspend refused while an app holds the camera; PipeWire fix PR #359 — [facetimehd wiki](https://github.com/patjak/facetimehd/wiki)
- AUR package facetimehd-dkms: a search snippet reports "module fails to build on kernel 7.0, package needs to be updated to 0.7.0.1"; NixOS lists facetimehd 0.6.13 for kernel 6.18; earlier 6.13 build failure fixed by upstream PR #304 — [search result AUR](https://aur.archlinux.org/packages/facetimehd-dkms?O=0), [Arch BBS 303758](https://bbs.archlinux.org/viewtopic.php?id=303758), [mynixos](https://mynixos.com/nixpkgs/package/linuxKernel.packages.linux_6_18.facetimehd) (snippet-level, not verified on page)

### Inferences
- Do not install facetimehd-dkms/facetimehd-firmware on 14,3 (no 1570 device; legal firmware-extraction question is moot). Verify with `lspci -nn | grep 14e4:1570` (expected empty) and `lsusb | grep 05ac:8600`.
- The real camera risk is T1 firmware on the ESP (`EFI/APPLE/EMBEDDEDOS/combined.memboot`): wiping the ESP kills camera, Touch Bar, ALS together. Back it up before installing CachyOS.

### Gaps
- Exact USB ID of the camera function after iBridge re-enumeration (the 05ac:8514 ID appears elsewhere but is not tied to 14,3 by any source found).
- Whether cschaba's uvc re-enumeration is still needed on every boot vs. only after upgrades on CachyOS kernels.

## Wi-Fi (Broadcom BCM43602, brcmfmac)

### Takeaway
Use in-kernel brcmfmac (no broadcom-wl). The 14,3 probe shows 14e4:43ba (subsys 106b:0173) bound to brcmfmac. Without the Apple board NVRAM .txt the card is crippled (2.4 GHz only, weak, dropouts); installing a BCM43602 NVRAM file restores 5 GHz. No clean, linux-firmware-distributed 14,3-specific file exists; the community file is an unlicensed/proprietary copy.

### Cited Findings
- PCI: `14e4:43ba:106b:0173`, BCM43602 802.11ac, driver brcmfmac, at 02:00-ish bus (probe "02-80") — [HW probe be950ca432](https://linux-hardware.org/?probe=be950ca432)
- Kernel looks for `brcm/brcmfmac43602-pcie.Apple Inc.-MacBookPro14,3.txt` then generic `brcmfmac43602-pcie.txt`, failing with -2 when missing — [search result snippet, kernel logs](https://lore.kernel.org/linux-wireless/907921df-34c1-6f08-1ece-bac896031397@jax.org/T/) (snippet-level)
- Models 13,2/13,3/14,2/14,3 have brcmfmac problems: 2.4 GHz only, weak reception, dropouts after 10-15 min; 13,1/14,1 (BCM4350) fine — [roadrunner2 gist](https://gist.github.com/roadrunner2/1289542a748d9a104e7baec6a92f9cd7)
- NVRAM file (`brcmfmac43602-pcie.txt`, board type 0x073e, rev 0x1101, rxchain/txchain=3, xtalfreq=40000) is circulated in a gist; install to `/lib/firmware/brcm/`, replace `macaddr` placeholder, reload brcmfmac; commenters report working on Arch, Debian, Ubuntu 26.04 (5 GHz about 327 Mbps), NixOS, incl. a MacBookPro14,2 — [MikeRatcliffe gist](https://gist.github.com/MikeRatcliffe/9614c16a8ea09731a9d5e91685bd8c80), [madfatcat88 fork](https://gist.github.com/madfatcat88/fb17a3ef6364a48a19ed57c143ddd383)
- Same gist comments: disabling MAC randomization suggested for "arp ip table err: -52"/bus disconnect after sleep — [MikeRatcliffe gist](https://gist.github.com/MikeRatcliffe/9614c16a8ea09731a9d5e91685bd8c80)
- 14,3-specific script `fix-wifi-nvram.sh` installs the NVRAM file, restores 5 GHz and real Apple MAC from EFI; it fetches the file from an unmerged PR (basecamp/omarchy#7487, pinned commit + checksum) or accepts `--file` extracted from Boot Camp/macOS; reloads brcmfmac (brief drop) — [cschaba repo](https://github.com/cschaba/macbookpro14-3-linux)
- Kernel bug 193121 hosts the NVRAM config used by users (renamed per board, e.g. `brcmfmac43602-pcie.Apple Inc.-MacBookPro13,3.txt`); the page itself returned 403 so contents unverified — [bugzilla 193121](https://bugzilla.kernel.org/show_bug.cgi?id=193121), usage per [Arch BBS 313054](https://bbs.archlinux.org/viewtopic.php?id=313054)
- Arch BBS thread (MBP13,3, Fedora 43, posted 2026-04-10, reply 2026-08-30): module option `feature_disable=0x82000` stopped firmware crashes/dropouts; `.clm_blob` and `.txcap_blob` still missing (-2); generic linux-firmware clm_blob crashed the chip; firmware in use generic 7.35.177.61 (Nov 10 2015); no confirmed fix for weak signal; OP asks for Apple-extracted bin/clm/txcap — [Arch BBS 313054](https://bbs.archlinux.org/viewtopic.php?id=313054)
- Qubes report: injecting generic CLM blob crashes chip; BCM43602 freezes on Qubes 4.0 — [Qubes thread](https://groups.google.com/g/qubes-users/c/aOJG58VcjS8/m/xwneAUcZDwAJ) (snippet-level)
- Some users report wpa_supplicant 2.10-8 as last reliably working version — [search snippet via mbp-2016-linux results](https://github.com/Dunedan/mbp-2016-linux/blob/master/README.md) (weak, unverified; consider iwd instead)
- Suspend: one commenter reports MacBook14,3 freezes on suspend and hibernate fails (hard reset) — [search snippet, mbp-2016-linux results](https://github.com/Dunedan/mbp-2016-linux/blob/master/README.md) (unverified, age unknown)

### Inferences
- Base `brcmfmac43602-pcie.bin` is in linux-firmware (Arch package `linux-firmware-broadcom`/`linux-firmware`); the board `.txt` is the missing piece. Practical CachyOS recipe: place NVRAM as `/usr/lib/firmware/brcm/brcmfmac43602-pcie.Apple Inc.-MacBookPro14,3.txt` (board-specific name avoids overriding other devices), set correct macaddr (cschaba script reads from EFI), `modprobe -r brcmfmac && modprobe brcmfmac`.
- Set regdomain via `iw reg set <CC>` / `/etc/conf.d/wireless-regdom`; missing clm_blob limits channels, so 5 GHz DFS channels may be unavailable. Try `feature_disable=0x82000` only if firmware crashes occur.
- I could not verify linux-firmware ships brcmfmac43602 clm_blob/txcap_blob for Apple; treat as absent.

### Gaps
- Exact Arch Wiki guidance (page blocked). Exact file contents/licence of the Apple NVRAM; whether newer kernels (6.17+/7.x) changed behaviour. Whether suspend/resume Wi-Fi bug persists on 7.x for 14,3 (cschaba page does not cover suspend).

## Bluetooth

### Takeaway
No reliable 14,3-specific source found. Evidence suggests Bluetooth works out of the box on 13,x/14,x with in-kernel drivers, with a patch needed on non-Touch-Bar models only.

### Cited Findings
- Bluetooth status "working" for 14,3 and "works out of the box"; models without Touch Bar needed an extra patch (issue #29); A2DP audio choppy — [Dunedan README](https://github.com/Dunedan/mbp-2016-linux/blob/master/README.md)
- Bluetooth needs kernel 4.16+ for full support — [roadrunner2 gist](https://gist.github.com/roadrunner2/1289542a748d9a104e7baec6a92f9cd7)
- The 14,3 probe lists Intel UARTs (intel_lpss_pci) and no Bluetooth USB device in the captured rows (possibly truncated, so not conclusive) — [HW probe](https://linux-hardware.org/?probe=be950ca432)

### Inferences
- No .hcd firmware sourcing needed per available evidence (not confirmed). Confirm with `bluetoothctl list`, `dmesg | grep -i bluetooth`.

### Gaps
- Bluetooth chip/USB ID and driver (btusb vs hci_bcm), .hcd firmware, and known bugs for 14,3 specifically could not be found.

## SD card reader

### Takeaway
Unresolved. Probe shows Genesys Logic 05e3:0749 "SD Card Reader and Writer" (x2) on USB (uas/usb_storage), but this may be an external dongle/dock; no source confirms an internal reader (the 15" 2017 MBP is generally known to lack an SD slot, unverified here).

### Cited Findings
- Probe row `05e3:0749` Genesys Logic SD Card Reader, 2 instances, alongside a Realtek RTL8153 NIC, VIA Labs hubs and an iPhone, i.e. a dock/dongle context — [HW probe](https://linux-hardware.org/?probe=be950ca432)

### Inferences
- No Realtek RTS5227/5229 evidence for 14,3; the brief's guess is unsupported. If a reader exists it would be generic usb-storage.

### Gaps
- No source confirming an internal reader on MacBookPro14,3.

## Thunderbolt 3 / USB-C / USB

### Takeaway
Works out of the box with in-kernel thunderbolt/xhci; power management of TB controllers not working (battery cost).

### Cited Findings
- Controllers: Intel JHL6540 Thunderbolt 3 NHI `8086:15d2` (x2, driver thunderbolt), JHL6540 USB controller `8086:15d4` (x2, xhci_hcd), DSL6540/JHL6540 bridges `8086:1578`/`8086:15d3`, Sunrise Point xHCI `8086:a12f` — [HW probe](https://linux-hardware.org/?probe=be950ca432)
- Thunderbolt and USB "working" for 14,3; USB-C to DisplayPort adapters work incl. daisy-chain; Thunderbolt controller power saving not working — [Dunedan README](https://github.com/Dunedan/mbp-2016-linux/blob/master/README.md)
- VIA Labs `2109:0100` USB 2.0 Billboard has no driver ("failed") — [HW probe](https://linux-hardware.org/?probe=be950ca432)

### Inferences
- Authorization: use `bolt`/boltd (`boltctl`) if devices need enrolling; not verified in sources.

### Gaps
- USB-C PD charging behaviour, hotplug authorization problems on 7.x not found.

## Sensors and other onboard devices

### Cited Findings
- Fans/temps/voltage via `applesmc`; ALS on Touch Bar models via iBridge needs out-of-tree `apple-ib-als`; no accelerometer — [Dunedan README](https://github.com/Dunedan/mbp-2016-linux/blob/master/README.md)
- Touch Bar/ALS: out-of-tree `apple-ibridge`, `apple-ib-tb`, `apple-ib-als` from https://github.com/roadrunner2/macbook12-spi-driver, patched for modern kernels (four API patches); install via `fix-touchbar-t1.sh`; taints kernel; `hid-sensor-hub` can steal the bar's HID interface — [cschaba repo](https://github.com/cschaba/macbookpro14-3-linux)
- Keyboard/touchpad need `macbook12-spi-driver`/applespi (Intel GSPI/LPSS); reports it breaks on newer kernels such as 6.10 — [roadrunner2 gist](https://gist.github.com/roadrunner2/1289542a748d9a104e7baec6a92f9cd7)
- Audio CS8409: patched https://github.com/davidjo/snd_hda_macbookpro (DKMS); WirePlumber may store near-silent volume — [cschaba repo](https://github.com/cschaba/macbookpro14-3-linux)
- GPU: AMD Baffin Radeon Pro 555 `1002:67ef:106b:0179` (amdgpu) drives the panel; dGPU idles about 7 W; NVMe Samsung `144d:a804` (nvme); Touch ID not supported — [HW probe](https://linux-hardware.org/?probe=be950ca432), [cschaba repo](https://github.com/cschaba/macbookpro14-3-linux)
- Expected PCI/USB inventory (probe was Ubuntu 20.04, kernel 5.4, probe date not shown): Wi-Fi 14e4:43ba, Radeon 1002:67ef, HDA 8086:a170, MEI 8086:a13a, SMBus 8086:a123, NVMe 144d:a804, USB 05ac:8600 iBridge — [HW probe](https://linux-hardware.org/?probe=be950ca432)

### Gaps
- Probe is old (kernel 5.4); Arch Wiki table not retrievable. cschaba repo is the only 2026-dated source for 14,3 and is a single-maintainer project (kernel 7.2 claimed; verify independently).
