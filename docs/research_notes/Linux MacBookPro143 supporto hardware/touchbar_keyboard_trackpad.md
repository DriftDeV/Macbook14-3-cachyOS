# Linux support for Touch Bar (T1), keyboard, trackpad, keyboard backlight, ALS on MacBookPro14,3

Research date: 2026-11-23. Method note: GitHub REST API and AUR RPC/cgit were queried directly via curl (primary data); GitHub web pages via WebFetch; kernel Kconfig from torvalds/linux master. AUR HTML pages and the Arch Wiki were blocked by Anubis bot protection in WebFetch, so Arch Wiki content is NOT covered.

## 1. applespi (keyboard + trackpad): mainline status, MBP14,3 specifics, kernel params

### Takeaway
applespi (SPI keyboard/trackpad) has been in mainline since v5.3 and is still in master as KEYBOARD_APPLESPI, which explicitly names MacBookPro14,*. On 14,3 keyboard and trackpad work out of the box per the community tracker; the main caveats are early-boot/initramfs module inclusion and palm rejection via libinput.

### Cited Findings
- Roadrunner2 README: "The keyboard / trackpad driver here is now included in the kernel as of v5.3." The out-of-tree repo still ships applespi but it is redundant on modern kernels. — [roadrunner2/macbook12-spi-driver](https://github.com/roadrunner2/macbook12-spi-driver)
- Current kernel master Kconfig: `KEYBOARD_APPLESPI` ("Apple SPI keyboard and trackpad"), depends on ACPI && EFI, SPI, X86, LEDS_CLASS, selects CRC16; help text says it is for MacBook8,1 or later, or any MacBookPro13,* or MacBookPro14,*; also requires SPI master drivers (spi_pxa2xx_platform / spi_pxa2xx_pci for MacBook8,1; the rest of the text was cut off in my fetch). — [drivers/input/keyboard/Kconfig](https://raw.githubusercontent.com/torvalds/linux/master/drivers/input/keyboard/Kconfig)
- Dunedan/mbp-2016-linux status table: MacBookPro14,3 Keyboard = Working, Trackpad = Working (out of the box). Palm rejection / disable-touchpad-while-typing needs a libinput patch (gist). README assumes Linux 5.4+. Suspend/hibernation on 14,3 = "partially working" (suspend works, resume limited; on 15" AMD models resume only works with the internal Intel GPU, which is relevant to 14,3 only if it has the Radeon Pro 555/560 dGPU, as 15" 2017 models do). — [Dunedan/mbp-2016-linux README](https://github.com/Dunedan/mbp-2016-linux/blob/master/README.md); libinput patch: [gist](https://gist.github.com/peterychuang/5cf9bf527bc26adef47d714c758a5509)
- Fork README advice: put `applespi`, `spi_pxa2xx_platform`, and `intel_lpss_pci` in the initramfs so the keyboard works at the disk-password prompt. Kernel params `intremap=nosid` only for kernels <4.11 (irrelevant now). — [F13-Kr1pt0n fork README](https://raw.githubusercontent.com/F13-Kr1pt0n/macbook-pro-touchbar-driver/touchbar-driver-hid-driver/README.md)
- Debug: `echo 1 > /sys/kernel/debug/tracing/events/applespi/applespi_keyboard_data/enable`; touchpad/ALS logging under `/sys/kernel/debug/applespi/`. — same README.
- Out-of-tree issue still open for 6.17 on MacBook8,1 (not 14,3): SPI timeout, `intremap=nosid` needed again (issue #78, 2026-03-16). Also #81 touchpad ghost touch on MacBook9,1 (2026-09-23). Shows the SPI/LPSS area still regresses occasionally. — [roadrunner2 issues](https://github.com/roadrunner2/macbook12-spi-driver/issues)
- Do NOT use the AUR out-of-tree package for applespi on current kernels: its dkms.conf builds `applespi` in addition to apple-ibridge/ib-tb/ib-als (see section 4), which duplicates the mainline module. — [AUR PKGBUILD/dkms.conf](https://aur.archlinux.org/cgit/aur.git/plain/PKGBUILD?h=macbook12-spi-driver-dkms)
- A community fork (jussike, per issue #71) explicitly "drops applespi, which is now in mainline" and only builds the Touch Bar modules. — [issue #71](https://github.com/roadrunner2/macbook12-spi-driver/issues/71)

### Inferences
- On CachyOS, applespi comes with the stock linux-cachyos kernel only if CONFIG_KEYBOARD_APPLESPI is enabled in that config (I did not verify the CachyOS config; likely =m as Arch does, but check `zgrep APPLESPI /proc/config.gz`).
- The Dunedan table is dated (last commit 2024-03-10, README last-touched content from 2021 for some rows) so "Working" is from older kernels; no evidence found of a regression on 14,3 keyboard/trackpad in 6.x.

### Gaps
- Exact CachyOS kernel config for APPLESPI, SPI_PXA2XX, MFD_INTEL_LPSS: not checked.
- Arch Wiki MacBookPro14,x page: blocked, not read.
- Keyboard-specific bugs on 14,3 on 6.x (e.g. dropped keys, suspend/resume SPI failures): no specific issue links found.

## 2. Touch Bar on T1: drivers, forks, the repo's `macbook-pro-touchbar-driver` gitlink, tiny-dfr, modes

### Takeaway
The only working T1 Touch Bar stack is the out-of-tree apple-ibridge / apple-ib-tb / apple-ib-als family from roadrunner2/cb22. Upstream roadrunner2 is stagnant (last push 2024-05-10) and fails to build or work on 6.10+; the gitlink in your repo almost certainly points to the F13-Kr1pt0n fork (MBP14,3 owner), which is the most actively patched lineage (open PRs through Oct 2026 targeting kernels 6.8 to 7.1). Mainline hid-appletb-* and tiny-dfr are for T2/Apple Silicon, not T1.

### Cited Findings
**Where the repo's submodule points**
- DriftDeV/Macbook14-3-cachyOS contains a gitlink (mode 160000) `macbook-pro-touchbar-driver` at commit 42034ae3b713da072c37b9819970f95a11eae257, but NO `.gitmodules` (404) so the URL is not recorded; the repo has 3 commits (2026-04-13 initial, create, 2026-04-16 "Update macbook-pro-touchbar-driver submodule"). — [tree API](https://api.github.com/repos/DriftDeV/Macbook14-3-cachyOS/git/trees/main?recursive=1), [commits](https://api.github.com/repos/DriftDeV/Macbook14-3-cachyOS/commits)
- Commit 42034ae was NOT found (GitHub API "No commit found") in F13-Kr1pt0n/macbook-pro-touchbar-driver, roadrunner2/macbook12-spi-driver, marc-git/macbook12-spi-driver, JornUzon/macbook12-spi-driver, or the 4 forks of F13 (ffoxdd, nonderbe, nohzafk, pozylon, Usaamah99). F13's last commit on its branch is ecfadc3 (2025-09-03). So the commit is probably a local/unpushed commit or a private/unlisted fork; the name `macbook-pro-touchbar-driver` matches exactly the F13-Kr1pt0n repo name (the other lineages are named `macbook12-spi-driver`). — GitHub API queries (e.g. [F13 commit lookup](https://api.github.com/repos/F13-Kr1pt0n/macbook-pro-touchbar-driver/commits/42034ae3b713da072c37b9819970f95a11eae257))
- Recommendation derived: treat upstream as https://github.com/F13-Kr1pt0n/macbook-pro-touchbar-driver (branch `touchbar-driver-hid-driver`), and re-pin or add a `.gitmodules` entry; the pinned commit cannot be verified.

**F13-Kr1pt0n fork (most relevant)**
- Repo: https://github.com/F13-Kr1pt0n/macbook-pro-touchbar-driver; author states owning a MacBookPro14,3 (15" 2017 Touch Bar); GPL-2.0; 4 stars; default branch `touchbar-driver-hid-driver`; GitHub `pushed_at` 2026-02-18 (likely PR/branch activity), last commit on branch 2025-09-03. README credits maintainer "David Rodriguez". Forked from marc-git/macbook12-spi-driver. — [repo](https://github.com/F13-Kr1pt0n/macbook-pro-touchbar-driver), [API](https://api.github.com/repos/F13-Kr1pt0n/macbook-pro-touchbar-driver)
- Features: `tb_mode=auto|keyboard|display` (default auto), multi-touch shim for 6.15-6.16 ("upstream HID covers this in 6.17+" per the README; this claim is the author's and I could not verify it for T1), `prefer_apple_ib`, fn-mode toggling, `idle_timeout`/`dim_timeout`, ALS; claims to avoid conflicts with upstream `hid-appletb-kbd`, `hid-appletb-bl`, `appletbdrm`. Known limits stated: ISO layout autodetection. — [README](https://raw.githubusercontent.com/F13-Kr1pt0n/macbook-pro-touchbar-driver/touchbar-driver-hid-driver/README.md)
- Install per README: copy to `/usr/src/appleibridge-0.1`, `dkms add/build/install -m appleibridge -v 0.1`, `mkinitcpio -P`, `modprobe apple-ibridge apple-ib-tb apple-ib-als`, enable `touchbar-reset.service`. README bug: it clones `macbook-pro-touchbar-driver` but `cd`s into `macbook12-spi-driver`. Remove any old `appletb.ko` first. — same README
- Open PRs (all unmerged, none reviewed by the maintainer as of fetch):
  - PR #1 (pozylon, 2026-05-02) "Kernel 6.17 Compat": `struct tb_touch` used before definition, build fails on every kernel >= 6.15 with "field 'touch' has incomplete type"; tested on 6.17.0-23-generic and 6.14. — [PR 1](https://github.com/F13-Kr1pt0n/macbook-pro-touchbar-driver/pull/1)
  - PR #2 (nohzafk, 2026-08-18): same build fix plus a self-deadlock in `apple_ib_set_tb_mode()` (`usb_set_configuration()` called while holding `appleib_tbmode_lock`, re-enters probe; modprobe hangs in D state, blocks sysinit/login); reports Touch Bar working on MacBookPro14,2 with kernel 7.1.8-arch1-3 / gcc 16.2.1. — [PR 2](https://github.com/F13-Kr1pt0n/macbook-pro-touchbar-driver/pull/2)
  - PR #3 (nonderbe, 2026-10-18): 9 fixes tested on MBP14,2 (T1 05ac:8600), Ubuntu 26.04, kernel 7.0: build fix, dkms.conf `${kernelver}`, SRCU cleanup, ALS threaded pollfunc (fixes WARNING in `__setup_irq`), ALS polling (`poll_interval` default 1000 ms because "on the 14,2 the T1 never sends illuminance reports by itself"), `usb_driver_set_configuration()` instead of `usb_set_configuration()` from probe, default `tb_mode=keyboard` ("On the T1, `auto` picks configuration 2; on my 14,2 the Touch Bar works in configuration 1"; asks if display mode works on 14,3), no MT input device in config 1, README + udev rule for T1 (hid-sensor-hub can claim the display/ALS interface first; usbmuxd 1.1.1 deconfigures the T1). Written with Claude Code assistance per its body. — [PR 3](https://github.com/F13-Kr1pt0n/macbook-pro-touchbar-driver/pull/3)
  - PR #4 (ffoxdd, 2026-10-19): fails to build on kernels <6.12: `hid_driver.report_fixup` const return (since 6.12) and `platform_driver.remove` returning void (since 6.11); tested 6.8, works on MacBookPro13,2. — [PR 4](https://github.com/F13-Kr1pt0n/macbook-pro-touchbar-driver/pull/4)
- Implication: the F13 `touchbar-driver-hid-driver` HEAD (2025-09-03) does not compile on >=6.15 without PR #1/#2 fix, and not on <6.12 without PR #4. Forks with these fixes: https://github.com/nonderbe/macbook-pro-touchbar-driver (PR 3, most complete, pushed 2026-10-18), https://github.com/nohzafk/macbook-pro-touchbar-driver (PR 2), https://github.com/pozylon/macbook-pro-touchbar-driver (PR 1), https://github.com/ffoxdd/macbook-pro-touchbar-driver (PR 4). — [forks API](https://api.github.com/repos/F13-Kr1pt0n/macbook-pro-touchbar-driver/forks)

**roadrunner2 upstream and variants**
- roadrunner2/macbook12-spi-driver: fork of cb22; drivers applespi, apple_ibridge, apple_ib_tb, apple_ib_als; GPL-2.0; 289 stars; last push 2024-05-10; 41 open issues; default branch `touchbar-driver-hid-driver`. — [repo](https://github.com/roadrunner2/macbook12-spi-driver), [API](https://api.github.com/repos/roadrunner2/macbook12-spi-driver)
- Issue #71 "Driver not working on kernel 6.10.6" (2024-08-28, 22 comments): DKMS build errors (e.g. missing `owner` in `struct acpi_driver`); a 2025-05 finding by scuty2000: `hid-sensor-hub` claims USB interface 3 so `apple-ibridge-hid` never probes the display interface; udev rule to unbind and re-probe; on 2025-06 workarounds failed on CachyOS kernel 6.15; no fix merged upstream, maintainer away (2025-03). A 6.15.7 Arch success required replugging/booting quirks. — [issue #71](https://github.com/roadrunner2/macbook12-spi-driver/issues/71)
- Other open issues: #67 "Looking for support to kernel 6.0+" (2022), #74 not working on 6.14.7 (MacBook15,1), #75 not working on 6.14.0-28 Ubuntu, #47 "Touchbar doesn't start after Suspend" (2020), #46 Touch Bar does not visually change fn mode since 5.6.7, #64 `39-usbmuxd.rules` udev breaks Touch Bar. — [issues](https://github.com/roadrunner2/macbook12-spi-driver/issues)
- marc-git/macbook12-spi-driver (AUR source): last push 2024-06-02, 12 stars. — [API](https://api.github.com/repos/marc-git/macbook12-spi-driver)
- t2linux/apple-ib-drv (branch `mbp15`, GPL-2.0, 76 stars, pushed 2025-01-04) and Redecorating/apple-ib-drv (pushed 2022-10-05): README says it is a WIP driver for MacBook Pro Touch Bar + ALS; builds roadrunner2 code; intended for 2019 MBPs (T2); Touch Bar dims/off after 5 / 4.5 min (`idle_timeout`, `dim_timeout`); ALS picked up by `iio-sensor-proxy`. Not for T1 specifically. — [Redecorating](https://github.com/Redecorating/apple-ib-drv), [t2linux API](https://api.github.com/repos/t2linux/apple-ib-drv)
- Other forks seen but unverified: JornUzon/macbook12-spi-driver (branch touchbar-driver-hid-driver, 304 commits), PatrickVerner/macbook12-spi-driver (reported on forums as needed for >=5.9; stale), almas branch (mentioned in #71), jussike fork (builds 6.8, branches for 6.11 and 6.13; URL not found by search).

**Upstream/mainline status for T1 Touch Bar**
- Kernel master Kconfig has `HID_APPLETB_KBD` ("keyboard mode (escape, function, media and brightness keys) of Touch Bars on x86 MacBook Pros") and `HID_APPLETB_BL` (backlight), both X86; Kconfig text does not specify T1 vs T2. — [drivers/hid/Kconfig](https://raw.githubusercontent.com/torvalds/linux/master/drivers/hid/Kconfig). No `apple-ibridge` entry matched in the grep of Kconfig.
- T1 iBridge/Touch Bar was proposed upstream three times and never merged (as far as the lists show): 2019 (Ronald Tschalar, apple-ibridge MFD + apple-ib-tb + ALS), Feb 2021 (5-patch "Touch Bar and ALS support for MacBook Pro's", apple-ibridge + apple-touchbar), Feb 2023 (Aditya Garg, "Touch Bar and Keyboard backlight driver for Intel Macs"). — [2019 cover](https://lkml.iu.edu/hypermail/linux/kernel/1904.2/05194.html), [2021](https://lore.kernel.org/lkml/20210228144525.00000730@Huawei.com/T/), [2023](https://lkml.iu.edu/hypermail/linux/kernel/2302.1/02825.html). I did not confirm the final outcome beyond absence from Kconfig.
- Related: a mainline driver for "internal Magic Keyboard" backlight (apple-magic-backlight, Orlando Chamberlain) appears in the same patch lineage. — [lore](https://lore.kernel.org/all/20230210232043.18483401@redecorated-mbp/) (page returned 403 to my fetch; seen only as a search-result title).

**tiny-dfr**
- AsahiLinux/tiny-dfr: MIT, last push 2026-10-20, deps cairo/libinput/freetype/fontconfig/librsvg>=2.59/uinput. Its udev rule assigns DRM devices with drivers `adp|appletbdrm` and Touch Bar input devices ("Apple Inc. Touch Bar Display Touchpad", "MacBookPro17,1 Touch Bar", "Mac14,7 Touch Bar") to a dedicated seat. So it targets Apple Silicon (adp) and T2 (appletbdrm). — [README](https://raw.githubusercontent.com/AsahiLinux/tiny-dfr/master/README.md), [udev rule](https://raw.githubusercontent.com/AsahiLinux/tiny-dfr/master/etc/udev/rules.d/99-touchbar-seat.rules), [API](https://api.github.com/repos/AsahiLinux/tiny-dfr)
- The T1 uses its own HID/USB interfaces (05ac:8600), with no appletbdrm. I found no source stating tiny-dfr works on T1; no T1 issue/PR found. — see PR 3 above for the T1 device id.

**Touch Bar modes (T1)**
- apple-ib-tb provides escape/Fn/special-key mode switching, idle/dim/off timeouts via `idle_timeout`/`dim_timeout` — [F13 README](https://raw.githubusercontent.com/F13-Kr1pt0n/macbook-pro-touchbar-driver/touchbar-driver-hid-driver/README.md). The T1 exposes two USB configurations: config 1 works (keyboard-style), config 2 is "display mode"; whether display mode works on 14,3 is an open question in PR #3.
- Dunedan tracker: Touch Bar on 14,3 = "Partially working". — [Dunedan README](https://github.com/Dunedan/mbp-2016-linux/blob/master/README.md)
- Resume after suspend: roadrunner2 issue #47 (Touch Bar doesn't start after suspend, 2020); F13 ships `touchbar-reset.service` (contents not read) as mitigation; `usbmuxd` 1.1.1 / `39-usbmuxd.rules` can deconfigure the T1 (issue #64, PR #3).

### Inferences
- A CachyOS install in late 2026 (kernel 6.17-7.x with gcc 15/16) needs nonderbe's PR 3 branch (or nohzafk PR 2) rather than F13 HEAD or roadrunner2/AUR HEAD; PR 3 was tested on 14,2 not 14,3, so display-mode behaviour on 14,3 is untested.
- 14,2 and 14,3 share the T1 (05ac:8600), so 14,2 test reports likely transfer, but that is an assumption.
- tiny-dfr will most likely not work on T1 as it lacks the DRM/seat devices it expects; the apple-ib-tb in-kernel-style fn-mode switching replaces it.
- Mixed result: kernel 6.15+ in-tree hid-appletb-kbd could conflict with the out-of-tree apple-ibridge for the same device; F13 handles this with `prefer_apple_ib` and "blacklist handling" (README author-credited), but I did not read the source.

### Gaps
- Source/URL of commit 42034ae: not found on any public repo checked; may live in an unlisted fork. Verify locally with `git -C macbook-pro-touchbar-driver remote -v`.
- Whether F13 maintainer is still active (last commit Sept 2025, PRs unanswered Aug-Oct 2026).
- Actual contents of `touchbar-reset.service` and `.udev` rules.
- Whether in-kernel hid-appletb-kbd/bl bind to the T1 (05ac:8600): unverified; the author's README suggests the in-kernel drivers get in the way.
- Dunedan's detailed Touch Bar section (README was truncated at 100k chars; offset 100000 not read).
- Fedora/Debian community notes and Reddit/forum threads: not searched.

## 3. Ambient light sensor, keyboard backlight, display brightness

### Takeaway
ALS on T1 comes only from the out-of-tree `apple-ib-als` (IIO, consumed by iio-sensor-proxy) and on 14,2 needed polling because the T1 does not push illuminance reports. Keyboard backlight and display brightness have no dedicated findings in the sources I could read.

### Cited Findings
- apple-ib-als exposes the ALS and "works automatically with iio-sensor-proxy". — [F13 README](https://raw.githubusercontent.com/F13-Kr1pt0n/macbook-pro-touchbar-driver/touchbar-driver-hid-driver/README.md); same statement in [Redecorating/apple-ib-drv](https://github.com/Redecorating/apple-ib-drv).
- PR #3: on the T1 no illuminance reports arrive on their own (tested on 14,2); added `poll_interval` (default 1000 ms); iio buffer enable triggered a `WARNING` in `__setup_irq` without a threaded handler; `hid-sensor-hub` can claim the ALS/display interface before apple-ibridge. — [PR 3](https://github.com/F13-Kr1pt0n/macbook-pro-touchbar-driver/pull/3)
- Dunedan: Touch Bar models need the third-party apple-ib-als module for ALS; 13,3 (AMD GPU) needs a patch for adjustable display brightness (kernel bugzilla 105051 comment 32). No brightness statement for 14,3 in the portion read. — [Dunedan README](https://github.com/Dunedan/mbp-2016-linux/blob/master/README.md), [bugzilla](https://bugzilla.kernel.org/show_bug.cgi?id=105051#c32)
- Kernel Kconfig `HID_APPLETB_BL` is the Touch Bar's own backlight, not the screen or keyboard. — [Kconfig](https://raw.githubusercontent.com/torvalds/linux/master/drivers/hid/Kconfig)
- applespi `depends on LEDS_CLASS` (Kconfig), consistent with it registering a keyboard-backlight LED; I did not find a source describing the LED name or 14,3 behaviour. — [Kconfig](https://raw.githubusercontent.com/torvalds/linux/master/drivers/input/keyboard/Kconfig)

### Inferences
- Keyboard backlight on 14,3 likely works through applespi's LED class device (inferred from Kconfig dependency only; unverified).
- Display brightness on 14,3: the 15" has an Intel iGPU plus AMD dGPU; Dunedan's note about brightness needing a patch concerned the 13,3 AMD-only panel path; applicability to 14,3 unconfirmed.

### Gaps
- Keyboard backlight: no verified bug/limitation info for 14,3 (e.g. LED sysfs name `spi::kbd_backlight`, brightness persistence across suspend).
- Display brightness on 14,3 under Intel/AMD with recent kernels: not found.
- Auto-dim of keyboard backlight by ALS (userspace via upower/KDE): not researched.

## 4. AUR packages and maintenance state; how to install on Arch/CachyOS; patches for new kernels

### Takeaway
The AUR offers only stale T1 packages (macbook12-spi-driver-dkms last updated 2024-06-10; apple-ib-drv-dkms-git 2021-08-07). For a late-2026 kernel the practical route is a manual DKMS install from one of the patched forks (nonderbe/nohzafk), with mkinitcpio and udev handover rules.

### Cited Findings
- `macbook12-spi-driver-dkms` 0+git.315-1: maintainers Christoph Gysin and Andrey Melentyev (PKGBUILD header); AUR LastModified 2024-06-10; 3 votes; not flagged out-of-date; source `git+https://github.com/marc-git/macbook12-spi-driver.git#branch=touchbar-driver-hid-driver`; license GPL2; depends dkms; installs to `/usr/src/macbook12-spi-driver-0+git.315`; dkms.conf builds `applespi`, `apple-ibridge`, `apple-ib-tb`, `apple-ib-als` with `make KDIR=/usr/lib/modules/$kernelver/build`, AUTOINSTALL=yes. — [PKGBUILD](https://aur.archlinux.org/cgit/aur.git/plain/PKGBUILD?h=macbook12-spi-driver-dkms), [RPC](https://aur.archlinux.org/rpc/v5/search/macbook12?by=name)
- Pre-6.x-incompatibility: marc-git source predates the fixes in sec. 2, so this package will fail to build on current kernels (inferred from issue #71 and PRs #1/#2/#4; I did not test the build).
- `apple-ib-drv-dkms-git` r305.fc9aefa-1: orphaned (Maintainer None), LastModified 2021-08-07, 0 votes, source t2linux/apple-ib-drv. — [RPC](https://aur.archlinux.org/rpc/v5/search/apple-ib?by=name)
- `macbook12-bluetooth-driver` (2020-01-27, not needed for this research); `mac-touchbar-plus` 1.0.0-1 (muhammad-adel, 2025-09-22, 0 votes; https://github.com/dev-muhammad-adel/mac-touchbar-plus; not inspected; purpose unverified). No AUR package for the F13 fork, no `apple-ibridge-dkms`, no tiny-dfr-for-T1 found in AUR name searches ("macbook12", "apple-ib", "touchbar", "applespi" queries). I did not query `tiny-dfr` on the AUR.
- Manual install recipe (from F13 README, adapted): `sudo pacman -S dkms linux-cachyos-headers` (kernel-matching headers), clone fork (e.g. nonderbe), copy to `/usr/src/appleibridge-0.1`, `dkms add/build/install`, `mkinitcpio -P`, modprobe the three modules, enable `touchbar-reset.service`; blacklist/remove any old `appletb`/`apple-ib-*`; add the udev rule from PR #3 to hand interface 3 from hid-sensor-hub; ensure `usbmuxd` doesn't deconfigure T1 (>=1.1.1 issue). — [F13 README](https://raw.githubusercontent.com/F13-Kr1pt0n/macbook-pro-touchbar-driver/touchbar-driver-hid-driver/README.md), [PR 3](https://github.com/F13-Kr1pt0n/macbook-pro-touchbar-driver/pull/3)
- CachyOS-specific: a comment in issue #71 (2025-06-12, jussike) reports udev/systemd workarounds failed on CachyOS 6.15; a 6.13 branch compiled and worked on Arch (2025-03-26). — [issue #71](https://github.com/roadrunner2/macbook12-spi-driver/issues/71). Clang/LTO-built linux-cachyos kernels: DKMS needs kernel built with same compiler; I did not find a source confirming issues, so flagged as a gap.

### Inferences
- If gcc 16 / kernel 7.x is in CachyOS, only forks with PR 2/3 fixes are known (by report) to work (nohzafk on 7.1.8-arch1-3, nonderbe on 7.0).
- A local PKGBUILD pointing at nonderbe's branch (dropping applespi from the DKMS module list to avoid duplicating the mainline module) would be the cleanest packaging; this is a recommendation, not an existing package.

### Gaps
- No verified AUR page comments (Anubis blocked); AUR comment text on build failures not read.
- CachyOS-specific (clang/ThinLTO) DKMS behaviour: unknown.
- Exact kernel version numbering of the "latest" CachyOS kernel in Nov 2026: not checked (sources reference kernels 6.17, 7.0, 7.1.8).

## 5. What is NOT 100% working today (MBP14,3 / T1) and why

### Takeaway
Keyboard and trackpad are fine in mainline. Touch Bar is the weak point: out-of-tree, unmerged fixes, kernel-version-fragile, display/touch mode unverified on 14,3, USB interface-claim races, and resume issues. ALS needs polling; palm rejection needs libinput patch; suspend/resume is partial.

### Cited Findings
- Touch Bar = "partially working" on 14,3 (Dunedan tracker, last updated 2024). — [README](https://github.com/Dunedan/mbp-2016-linux/blob/master/README.md)
- Build breakage on kernels >=6.15 (incomplete type `struct tb_touch`), deadlock in `apple_ib_set_tb_mode()` (hang at boot, D-state modprobe), kernels <6.12 API mismatches: PRs #1, #2, #4 above (all unmerged).
- hid-sensor-hub races apple-ibridge for the display/ALS USB interface: issue #71 (scuty2000, May 2025) and PR #3 (udev rule).
- `usbmuxd` deconfigures T1: issue #64 (roadrunner2, 2022) and PR #3.
- `tb_mode=auto` selects config 2 on T1 and may break the Touch Bar on 14,2; unknown for 14,3 (PR #3 asks).
- ALS needs polling on T1 (PR #3).
- ISO layout autodetection missing (F13 README).
- Resume after suspend: roadrunner2 #47; Dunedan "partially working", 15" AMD-model resume only with internal Intel GPU.
- Palm rejection / disable-while-typing needs libinput patch (Dunedan README + gist).
- Stale tracker and unmaintained AUR: see sec. 4.

### Inferences
- Because upstream roadrunner2 has been inactive since May 2024 and the F13 fork has unanswered PRs for months, expect to carry patches yourself; pin a fork and commit.
- Mainlining T1 Touch Bar is not in sight (three failed submissions, no Kconfig entry).

### Gaps
- Camera/FaceTime excluded by request.
- No live testing on 14,3 hardware; all 6.15+ T1 test reports found are on 14,2 and 13,2.
- Did not search Reddit/Arch forums/Fedora Discussion in depth (a few hits seen: [Arch BBS 309376](https://bbs.archlinux.org/viewtopic.php?id=309376), [Arch BBS 306151](https://bbs.archlinux.org/viewtopic.php?id=306151), [Fedora Discussion](https://discussion.fedoraproject.org/t/grumpey-macbook12-spi-driver-kmod/37537): not opened).
