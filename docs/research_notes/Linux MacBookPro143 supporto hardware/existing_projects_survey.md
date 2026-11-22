# Existing community projects for Linux on MacBookPro14,1/14,2/14,3 (survey, as of 2026-11-23)

Method note: data comes from GitHub REST API (pushed_at dates) and raw READMEs. The Arch Wiki page and AUR were blocked by Anubis bot protection, so they were NOT read directly (see Gaps). Dates are "last push", not necessarily last substantive commit.

## Catalog of repos and guides (URL, maintainer, last push, what/what's broken, reusability)

### Takeaway
The core driver stack is old and mostly unmaintained upstream (roadrunner2 last push May 2024, Dunedan tracker Mar 2024). The live work in 2026 is a cluster of small 14,x-specific repos (Touch Bar DKMS ports to kernel 7.x, BCM43602 NVRAM, CS8409 audio DSP, suspend fixes). Together they cover most of the machine; none is a single unified Arch/CachyOS package set. DriftDeV's repo is only a submodule pointer with no content of its own.

### Cited Findings
**Reference trackers / foundational drivers**
- Dunedan/mbp-2016-linux, "State of Linux on the MacBook Pro 2016 & 2017", 2,316 stars, last push 2024-03-10 (STALE, >2 yrs), not archived — [API](https://api.github.com/repos/Dunedan/mbp-2016-linux), [README](https://github.com/Dunedan/mbp-2016-linux). Its table (assumes Linux >=5.4): 14,3 audio "working" with davidjo CS8409 patch; 14,2 audio not working; camera working on Touch Bar models via iBridge USB uvcvideo; AMD GPU working on 14,3; keyboard/touchpad via upstream applespi (since 5.3), palm rejection needs libinput patch; NVMe works but no APST; suspend "partial" on all; Thunderbolt works but power mgmt incomplete; Touch Bar "partial" on 14,2/14,3 needing apple-ib-tb, custom Touch Bar graphics missing; Touch ID not working; Wi-Fi 14,3 "not working" (BCM43602 shows only 2.4 GHz APs, failures due to firmware country detection); battery expect <4 h (no panel self-refresh, SSD and TB power saving) — [raw README](https://raw.githubusercontent.com/Dunedan/mbp-2016-linux/master/README.md)
- Dunedan: 14,1/14,2 need `echo 0 > /sys/bus/pci/devices/0000:01:00.0/d3cold_allowed` for resume; "14,3 isn't listed among the Apple NVMe models so the d3cold step doesn't apply"; resume with the AMD GPU only works when Intel GPU is in use; only kernel param mentioned is `intremap=nosid` (obsolete) — same README. NOTE contradicted in practice by [mihneadevries sleep-fix](https://github.com/mihneadevries/mbp14-3-linux-sleep-fix) (below), who found the 14,3 SSD is not at 01:00.0 (that is the Radeon) and NVMe d3cold still needed via PCI-class rule.
- roadrunner2/macbook12-spi-driver (applespi + apple-ibridge/apple-ib-tb/apple-ib-als), 289 stars, last push 2024-05-10, not archived — [API](https://api.github.com/repos/roadrunner2/macbook12-spi-driver). applespi is mainline since 5.3; the out-of-tree part still needed is the iBridge/Touch Bar stack. Per [cschaba](https://raw.githubusercontent.com/cschaba/macbookpro14-3-linux/main/README.md) the 2018 source fails on modern kernels (four API changes) and needs patching; per [nohzafk](https://raw.githubusercontent.com/nohzafk/omarchy-macbookpro-t1/main/README.md) `macbook12-spi-driver-dkms` fails to build on current kernels and its module names collide with the working fork (remove it).
- davidjo/snd_hda_macbookpro (CS8409 + MAX98706/SSM3515 amps, 2016-2017 Macs), 515 stars, last push 2026-11-14 (ACTIVE), not archived — [API](https://api.github.com/repos/davidjo/snd_hda_macbookpro). In-tree CS8409 quirks only target Dell subsystems so speakers are silent without it (nohzafk README).
- patjak/facetimehd (Broadcom 1570 PCIe camera), 1,515 stars, last push 2026-11-20 (ACTIVE) — [API](https://api.github.com/repos/patjak/facetimehd). NOT RELEVANT to 14,x: Touch Bar MBPs use the iBridge USB webcam with uvcvideo; cschaba says to remove `facetimehd`/`facetimehd-firmware` on T1 machines.

**14,x-specific / T1-specific 2026 repos (all small, 0-40 stars)**
- cschaba/macbookpro14-3-linux, 5 stars, push 2026-10-09 — Arch (Omarchy/Hyprland, kernel 7.2.x). Provides scripts: `fix-touchbar-t1.sh`, `fix-audio-cs8409.sh`, `fix-wifi-nvram.sh`, `backup-t1-firmware.sh`. Works: Touch Bar (patched apple-ibridge set), camera, speakers+mic, 5 GHz Wi-Fi, ALS. Broken: Touch ID (no Linux support for T1 or T2), dGPU never runtime-suspends (Radeon Pro 555/560 drives the panel, idles ~7 W; moving panel to Intel gives black screen), Touch Bar has no framebuffer (T1 draws 4 fixed layouts, so tiny-dfr can't work), touchpad palm rejection size-based only, keyboard chatter (hardware defect, debounce via interception-tools). Modules install to /lib/modules/<kver>/updates and must be re-run after each kernel upgrade (not DKMS). — [README](https://raw.githubusercontent.com/cschaba/macbookpro14-3-linux/main/README.md)
- nohzafk/omarchy-macbookpro-t1, 38 stars, push 2026-08-20 — verified on 14,2, kernel 7.1.8. Works: Touch Bar Esc/F-keys, 5 GHz WiFi, audio, webcam, keyboard/trackpad (mainline applespi), suspend with `pcie_ports=compat`, Bluetooth, fans via SMC. Broken: Touch ID, ALS needs userspace. Documents two Touch Bar bugs: mutex deadlock in `apple_ib_set_tb_mode()` (workaround `tb_mode_param=keyboard`), and `hid-sensor-hub` stealing HID interface (manual unbind/bind to apple-ibridge-hid). — [README](https://raw.githubusercontent.com/nohzafk/omarchy-macbookpro-t1/main/README.md)
- mihneadevries/mbp14-3-linux-sleep-fix, push 2026-11-22 (very fresh) — suspend fixes for 14,3 on Arch/Omarchy; see Suspend section. — [README](https://raw.githubusercontent.com/mihneadevries/mbp14-3-linux-sleep-fix/main/README.md)
- mihneadevries/mbp14-3-linux-wifi-fix (push 2026-11-22), dnlbtz/mbp143-wifi (2026-11-18), mandatti/macbookpro143-wifi-linux (2026-10-20, reversible, tested Ubuntu live) — BCM43602 5 GHz fixes — [GitHub search](https://api.github.com/search/repositories?q=macbookpro14,3+linux&per_page=15)
- dnlbtz/mbp143-audio, push 2026-11-18, tested on CachyOS (PipeWire 1.6.10, WirePlumber 0.5.18) — 14,3-only PipeWire/WirePlumber filter-chain: speaker DSP (HPF 88 Hz, compressor, EQ, crossover tweeter/woofer ~1 kHz, BuzzKill notch, limiters, thermal protection), +35 dB headset-mic gain. Needs davidjo driver, recommends fork `dnlbtz/snd_hda_macbookpro` branch `offlineDkmsDeb` because speakers are silent after hibernation and headset mic does not work without two unmerged fixes. Limits: hw:0 access bypasses protection, 44.1 kHz graph, browsers pause on jack events. — [README](https://raw.githubusercontent.com/dnlbtz/mbp143-audio/main/README.md)
- AJ-dev-i60/t1-touchbar, 14 stars, push 2026-07-01 — freeze-safe DKMS Touch Bar driver forked from t2linux/apple-ib-drv for kernel 7; only verified on 14,3, kernel 7.0.0-27 (Ubuntu 26.04); DMI-gated skip of a power-on ACPI call that freezes T1 machines (`skip_acpi_power`); installer is apt-only. Issues: needs reboot, usbmuxd grabs iBridge, Secure Boot MOK, silent DKMS rebuild failures. — [README](https://raw.githubusercontent.com/AJ-dev-i60/t1-touchbar/main/README.md)
- F13-Kr1pt0n/macbook-pro-touchbar-driver (fork of marc-git/macbook12-spi-driver, root cb22), 4 stars, push 2026-02-18 — basis for nohzafk's Touch Bar fork and cschaba's `--fork` option — [API](https://api.github.com/repos/F13-Kr1pt0n/macbook-pro-touchbar-driver)
- creolben/macbook-t1-touchbar (not a fork), push 2026-09-27; mihneadevries references a pending upstream PR #1 there for s2idle resume of apple-ib-tb — [API](https://api.github.com/repos/creolben/macbook-t1-touchbar)
- Others (descriptions only, not read): gavinmclelland/omarchy-macbookpro14-3 (7 stars, 2026-09-01), mythopoeic/macbookpro14-3-linux (Ubuntu notes + four apple-ibridge kernel patches, 2026-08-02), projectmushroom/macbookpro143-linux-fixes (2026-09-02), RevGap/mbp-2017-omarchy (2026-09-01), Phennova/apple-touchbar-driver (DKMS+systemd, 2026-09-08), DeyAgrO/macbook-pro-13-2-linux (BCM43602 + TB + kbd backlight, deb/rpm/Arch packaging, 2026-06-10), michaelahess/macbook-pro-t1-touchbar-linux (2026-08-20), seatrips/macbook-pro-t1-touchbar-linux (2026-10-04), stephen-bunting/macbookpro14-2-linux (2026-09-16), justinasvijeikis/macbookpro14-2-linux (Debian 13, 2026-11-12), paskaz/macbook-pro-linux-revival (virtual Touch Bar for dead T1, keyd, 2026-08-28), acmccubbin/fnstrip (Rust Touch Bar renderer "for T1Bridge", 2026-11-11) — [search 1](https://api.github.com/search/repositories?q=macbookpro14,3+linux&per_page=15), [search 2](https://api.github.com/search/repositories?q=macbook+pro+2017+linux+touchbar&per_page=15&sort=stars)

### Inferences
- Reusable now for a unified CachyOS repo: cschaba scripts (structure and T1 firmware backup), mihneadevries sleep fix (most thorough 14,3 suspend work), dnlbtz audio + wifi, nohzafk Touch Bar bug analysis, AJ-dev-i60 DKMS (kernel 7 + freeze guard). Licensing is mostly GPL-2.0 for driver code; check each repo's license before vendoring (only confirmed for cschaba's cited upstreams and AJ-dev-i60).
- The shape of activity (many repos created Jul-Nov 2026, many with 0-7 stars, several mutually citing) suggests partly AI-assisted guides; treat claims as unverified until reproduced on real hardware.
- Dunedan's "14,3 Wi-Fi not working" and "d3cold n/a for 14,3" statements are outdated relative to 2026 fixes.

### Gaps
- Arch Wiki "MacBookPro14,1/14,2/14,3" page could not be fetched (Anubis Access Denied on both normal and action=raw URL); its feature table is not captured. Canonical URL: https://wiki.archlinux.org/title/MacBookPro14,1/14,2/14,3 (name not verified).
- AUR could not be queried (Anubis), so DKMS package maintenance state (e.g. macbook12-spi-driver-dkms, snd_hda_macbookpro-dkms, facetimehd-dkms, apple-ibridge variants) is unverified. cschaba/nohzafk indicate `macbook12-spi-driver-dkms` is broken on current kernels.
- Not covered: Fedora, Ubuntu wiki, Gentoo, Void, linux-hardware.org, Reddit/Arch BBS, GitLab, nixos-hardware commit history. No "linux-surface-like" effort exists for these MacBooks that I found. Search for "cachyos macbook" repos was not run; GitHub search query "macbookpro14,3 linux" did not surface any CachyOS-specific repo other than DriftDeV and dnlbtz (tested on CachyOS).

## NixOS nixos-hardware apple/macbook-pro/14-1 (proven reference)

### Takeaway
The only formal distro hardware profile is minimal: early-boot module list, libinput quirks, firmware, IOMMU flag. It does not include Touch Bar, audio (CS8409) or Wi-Fi NVRAM fixes, and it is for 14,1 (non-Touch-Bar) so it is a weak reference for 14,3.

### Cited Findings
- Directory contains README.md, default.nix, disable-nvme-d3cold.sh — [folder](https://github.com/NixOS/nixos-hardware/tree/master/apple/macbook-pro/14-1)
- default.nix substance (fetched via [raw](https://raw.githubusercontent.com/NixOS/nixos-hardware/master/apple/macbook-pro/14-1/default.nix)): imports `../.` (apple common), `common/cpu/intel/kaby-lake`, `common/hidpi.nix`, `common/pc/ssd`. `boot.initrd.kernelModules = [ "applespi" "spi_pxa2xx_platform" "intel_lpss_pci" "applesmc" ]` (keyboard in stage 1). `boot.kernelParams = [ "intel_iommu=on" ]`. `kernelPackages = pkgs.linuxPackages_latest` if kernel older than 6.0. `services.libinput.enable = true`.
- libinput quirks written to /etc/libinput/local-overrides.quirks: `[MacBook(Pro) SPI Touchpads] MatchName=*Apple SPI Touchpad* ModelAppleTouchpad=1 AttrTouchSizeRange=200:150 AttrPalmSizeThreshold=1100`; `[MacBook(Pro) SPI Keyboards] MatchName=*Apple SPI Keyboard* AttrKeyboardIntegration=internal`; `[MacBookPro Touchbar] MatchBus=usb MatchVendor=0x05AC MatchProduct=0x8600 AttrKeyboardIntegration=internal` (the last one is directly relevant to 14,3 and makes disable-while-typing treat the Touch Bar as internal keyboard).
- Firmware: `networking.enableB43Firmware = lib.mkDefault true`, `hardware.enableRedistributableFirmware = true`, `hardware.cpu.intel.updateMicrocode = true`.
- Commented-out optional systemd service `disable-nvme-d3cold` (oneshot before suspend.target) running the script, which writes 0 to d3cold_allowed for PCI device 0000:01:00.0 if its driver is `nvme` (the script uses `-ne` string comparison, a bug per the fetch summary) — [script](https://raw.githubusercontent.com/NixOS/nixos-hardware/master/apple/macbook-pro/14-1/disable-nvme-d3cold.sh)
- README status (written for NixOS 24.05, summarized): audio broken until nixpkgs PR 322968, Bluetooth broken until PR 322964, touchpad works with disable-while-typing, Thunderbolt works, NVMe works (older may need resume workaround), Wi-Fi works 2.4/5 GHz (WEP broken), Thunderbolt/Wi-Fi/NVMe sometimes need reboot after suspend — [README](https://raw.githubusercontent.com/NixOS/nixos-hardware/master/apple/macbook-pro/14-1/README.md)

### Inferences
- Reuse the libinput quirks and stage-1 module list verbatim for CachyOS (mkinitcpio MODULES). Kernel params from the profile are minimal; actual 14,3 fixes come from the 2026 repos (`pcie_ports=compat`, brcmfmac `feature_disable=0x82000`, NVMe d3cold udev rule).

### Gaps
- Only the 14-1 module was read; whether nixos-hardware has 14,2/14,3 entries was not checked. Profile commit date not retrieved (stale-ish: README targets 24.05).

## Suspend, Thunderbolt, Wi-Fi, audio, Touch Bar: concrete settings from 2026 repos

### Takeaway
Each previously "partial" area now has a documented workaround on 14,x, but all are shell-script/DKMS glue, not upstream code.

### Cited Findings
- Suspend root causes on 14,3 (mihneadevries): Apple firmware cuts power to two Alpine Ridge Thunderbolt controllers during sleep and the kernel waits 80-100 s (fix: remove TB upstream ports pre-sleep, rescan post-sleep); NVMe at PCI 0x:xx not 01:00.0 so d3cold fix must match PCI class; amdgpu S3 resume fails with SMU firmware load error -22 (workaround `MemorySleepMode=s2idle`); hibernate disabled pending kernel patch "drm/amdgpu: reset VI ASIC on Apple boards with VRAM at 0"; brcmfmac unload/reload around sleep; apple-ib-tb needs `.resume` handler for s2idle (patch carried, upstream PR pending); Arch usbmuxd 1.1.1-4 still ships udev rule matching 05ac:8600 that forces config 0 (override 39-usbmuxd.rules); `pm_async=0` via tmpfiles; modprobe `options apple-ib-tb fnmode=1 idle_timeout=-1 dim_timeout=-1` (burn-in risk) — [README](https://raw.githubusercontent.com/mihneadevries/mbp14-3-linux-sleep-fix/main/README.md)
- Alternative suspend result (nohzafk, on 14,2): suspend works with `pcie_ports=compat` (fixes Thunderbolt xHCI reset failure leaving USB-C dead), `d3cold_allowed=0`; resume ~15 s and needs keypress — [README](https://raw.githubusercontent.com/nohzafk/omarchy-macbookpro-t1/main/README.md)
- Wi-Fi BCM43602: needs board NVRAM file (not in linux-firmware); without it MAC shows 00:90:4C prefix and 2.4 GHz only; `boardflags3=0x00000300` sufficient; `brcmfmac feature_disable=0x82000` for WPA handshakes; cschaba downloads NVRAM from an unmerged linux-firmware PR (pinned+checksum) or extracts from Boot Camp package — nohzafk and cschaba READMEs above.
- T1 firmware lives on the Apple ESP (EFI/APPLE/EMBEDDEDOS/combined.memboot, FDRData); wiping it puts iBridge in recovery (05ac:1281) and Touch Bar, camera, ALS, Touch ID all die; back up ESP before installing — cschaba and nohzafk READMEs.

### Inferences
- A CachyOS unified repo should: preserve Apple ESP, ship DKMS Touch Bar module (AJ-dev-i60/F13 base + sleep patch), CS8409 DKMS + PipeWire graph, brcmfmac NVRAM, sleep hooks, libinput quirks, and fix known pitfalls (usbmuxd rule, hid-sensor-hub binding, non-DKMS modules breaking on kernel update).

### Gaps
- Conflict: mihneadevries says 14,3 suspend works only with s2idle + TB hotplug workaround, nohzafk (14,2, no dGPU) only needs `pcie_ports=compat`. Not tested on same hardware; 14,3 dGPU is the differentiator.
- No issue-tracker links collected (issues pages not fetched).

## Remaining gaps for "100% working" and fix feasibility

### Takeaway
Unfixed: Touch ID, dGPU power (panel wired to Radeon, ~7 W idle, no gmux-style switching), custom Touch Bar graphics, hibernate, reliable palm rejection, upstream-quality packaging. Touch ID and Touch Bar graphics are reverse-engineering projects; dGPU/hibernate are kernel-patch tasks.

### Cited Findings
- Touch ID: no Linux driver for T1 or T2; DriftDeV/apple_biometrics_linuix "An attempt of porting T1 touchid", Python, last push 2026-04-28, 0 stars, no readme info found — [API](https://api.github.com/repos/DriftDeV/apple_biometrics_linuix); mihneadevries notes Touch ID and custom buttons "experimental in the t1bridge project" (not independently located).
- Touch Bar: T1 has no framebuffer, 4 fixed layouts, 3 brightness states — cschaba README. Contrast: acmccubbin/fnstrip claims a custom renderer "for T1Bridge" (2026-11-11, 0 stars; claim unverified) — [search](https://api.github.com/search/repositories?q=macbook+pro+2017+linux+touchbar&per_page=15&sort=stars)
- dGPU: Radeon Pro 555/560 never runtime-suspends; internal panel on dGPU; Intel-only gives black screen (cschaba); amdgpu S3/hibernate failure for Apple boards (mihneadevries). Dunedan: battery under 4 h.
- Palm rejection/keyboard chatter: libinput size-based only; chatter hardware defect (cschaba).

### Inferences
- Fixable by patches in 2026: amdgpu Apple-board reset patch (upstream candidate), apple-ib-tb s2idle resume, dGPU runtime-PM/gmux-like panel mux investigation (uncertain; apple-gmux may not apply since no mux driver on 14,x was documented), CS8409 hibernate fix (dnlbtz fork).
- Not realistically fixable: Touch ID (secure enclave-like T1 protocol unknown), Touch Bar framebuffer.

### Gaps
- Gmux: no 14,x gmux information found (Dunedan page does not mention it).
- No issue links for amdgpu/Apple VRAM patch or Touch ID.

## DriftDeV/Macbook14-3-cachyOS and DriftDeV's other repos

### Takeaway
The repo is an empty shell: two commits plus a submodule pointer; there is no README, guide, or code. Its description claims a tutorial, but none exists as of the last push (2026-04-16).

### Cited Findings
- Repo description: "A guide for running Arch Linux or CachyOS on a MacBook Pro model 14,3."; last push 2026-04-16T16:06:03Z, updated 2026-07-22, default branch main, 0 stars — [API](https://api.github.com/repos/DriftDeV/Macbook14-3-cachyOS)
- Tree has only `.gitattributes` and submodule `macbook-pro-touchbar-driver` pinned to commit 42034ae3b713da072c37b9819970f95a11eae257 (mode 160000) — [tree](https://api.github.com/repos/DriftDeV/Macbook14-3-cachyOS/git/trees/main)
- Commits: "Initial commit" 2026-04-13, "Create macbook-pro-touchbar-driver" 2026-04-13, "Update macbook-pro-touchbar-driver submodule" 2026-04-16, author Dr1ft (DriftDeV) — [commits](https://api.github.com/repos/DriftDeV/Macbook14-3-cachyOS/commits?per_page=10)
- `.gitmodules` returns 404 (raw), so the submodule URL is missing/not resolvable; the submodule target is therefore UNKNOWN. DriftDeV owns no repo named macbook-pro-touchbar-driver (no fork) — [user repos](https://api.github.com/users/DriftDeV/repos?per_page=100). Pinned SHA 42034ae returned HTTP 422 on both Phennova/apple-touchbar-driver and F13-Kr1pt0n/macbook-pro-touchbar-driver commit lookups (no match confirmed).
- DriftDeV's other repos relevant to Mac: apple_biometrics_linuix (T1 Touch ID attempt, 2026-04-28). Others unrelated (accessibility tools, Discord bot, postmarketOS ports, broadcast-linux, etc.). Owner appears active (pushes through 2026-11-19) — same user-repos listing.

### Inferences
- Likely candidate for the submodule is F13-Kr1pt0n/macbook-pro-touchbar-driver (cschaba and nohzafk both use it as the Touch Bar basis), but this is a guess, not confirmed. The broken submodule means `git clone --recursive` would fail or leave an empty dir.

### Gaps
- Real submodule URL: check local checkout's .gitmodules or `git ls-tree`/`git submodule status` in the user's repo copy.
