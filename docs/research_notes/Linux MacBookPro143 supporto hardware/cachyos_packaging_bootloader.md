# CachyOS packaging, installer and Apple-EFI bootloader notes for a MacBookPro14,3 hardware-support repo

Research date: 2026-11-23. Note: MacBookPro14,3 (15" 2017, Touch Bar) has NO T2 chip (T2 starts 2018). The CachyOS "T2 MacBook" wiki page and linux-t2 patches do NOT apply; do not mix them up.

## 1. Current CachyOS ISO names, download URLs, checksum and signature locations

### Takeaway
Latest ISO I could confirm is 260809 (August 2026 release, kernel 7.1 per search summary), `cachyos-desktop-linux-260809.iso`; two editions exist (Desktop, Handheld). No Sept/Oct/Nov ISO was found, but absence in search is not proof: check cachyos.org/download before pinning. Checksum is a `.sha256` file next to the ISO; signature is a `.iso.sig` verified with key F3B607488DB35A47.

### Cited Findings
- Download page lists two editions: Desktop (17+ DEs online installer) and Handheld (KDE Plasma only; ROG Ally, Steam Deck, Legion Go) — [cachyos.org/download](https://cachyos.org/download/)
- Wiki (page updated Aug 10 2026) gives ISO `cachyos-desktop-linux-260809.iso`, sha256 `959f6577f45e25ee9fd8c220fd221b08e4ea79412c7315c0f922dd6d86d5e33c`; checksum file https://mirror.cachyos.org/ISO/desktop/260809/cachyos-desktop-linux-260809.iso.sha256 — [CachyOS wiki download](https://wiki.cachyos.org/cachyos_basic/download/)
- Signature: https://cdn77.cachyos.org/ISO/desktop/260809/cachyos-desktop-linux-260809.iso.sig ; `gpg --keyserver hkps://keys.openpgp.org --recv-key F3B607488DB35A47`; primary fingerprint 882D CFE4 8E20 51D4 8E25 62AB F3B6 0748 8DB3 5A47 — [CachyOS wiki download](https://wiki.cachyos.org/cachyos_basic/download/)
- Mirrors: iso.cachyos.org/desktop/260809/..., cdn77.cachyos.org/ISO/desktop/260809/..., mirror.cachyos.org/ISO/..., us.cachyos.org/ISO/..., mirrors.tuna.tsinghua.edu.cn/cachyos/desktop/260809/..., SourceForge cachyos-arch — [August 2026 release blog](https://cachyos.org/blog/2608-august-release/)
- August 2026 release: fifth ISO refresh of 2026; earlier 2026 snapshots Jan, Mar (260308), Apr (260426), Jun (260628) — [linux.org/Linux Journal aggregation](https://www.linuxjournal.com/tag/cachyos) (search-result summaries; secondary)
- Handheld ISO exact filename not published on the wiki download page — [CachyOS wiki download](https://wiki.cachyos.org/cachyos_basic/download/)
- ISO layout pattern: `<edition>/<YYMMDD>/cachyos-<edition>-linux-<YYMMDD>.iso`, so handheld is probably `handheld/.../cachyos-handheld-linux-<date>.iso` (inference, unverified).

### Inferences
- Cadence is roughly bi-monthly (Jan, Mar, Apr, Jun, Aug); a Oct/Nov 2026 ISO may exist. Script the download to resolve the newest directory at https://mirror.cachyos.org/ISO/desktop/ rather than hardcoding 260809.
- Wiki hash for a different date (260628) appeared in a search summary and an older page showed 260426: stale cached wiki pages exist; always use the .sha256 file from the mirror.

### Gaps
- Could not confirm any ISO newer than 260809 or the Handheld filename. Kernel version on the ISO (7.1) comes from a search summary only.

## 2. Can the ISO be remastered with extra files/packages/cmdline?

### Takeaway
Yes, in principle: the ISO is built from an archiso profile in CachyOS/CachyOS-Live-ISO with `buildiso.sh`, so you can fork the profile (packages list, airootfs overlay, pacman.conf, bootloader entries). Remastering the official squashfs by hand is possible but rebuilding from the profile is the supported path. Simpler alternative: leave the ISO untouched and run an `install.sh` post-install.

### Cited Findings
- Repo https://github.com/CachyOS/CachyOS-Live-ISO: dirs `archiso/`, `machines/`, `testcases/`, scripts `buildiso.sh`, `ci.build.sh`, `testiso.sh`, `util*.sh` — [repo](https://github.com/CachyOS/CachyOS-Live-ISO)
- Build: install `archiso mkinitcpio-archiso git squashfs-tools grub`; `sudo ./buildiso.sh -p desktop -v -w`; output in `out/`; options `-c -r -w -p -v` — [repo README](https://github.com/CachyOS/CachyOS-Live-ISO)
- `archiso/` contains `airootfs/`, `efiboot/loader`, `grub/`, `syslinux/`, `bootstrap_packages.x86_64`, `packages_desktop.x86_64`, `pacman.conf`, `profiledef.sh` — [archiso dir](https://github.com/CachyOS/CachyOS-Live-ISO/tree/master/archiso)
- `profiledef.sh`: iso_name="cachyos", bootmodes=('bios.syslinux' 'uefi.grub') (systemd-boot variant commented), squashfs xz; file_permissions list includes `/usr/local/bin/calamares-online.sh`, `prepare-live-desktop.sh`, `remove-nvidia`, `removeun` — [profiledef.sh](https://github.com/CachyOS/CachyOS-Live-ISO/blob/master/archiso/profiledef.sh)
- Live ISO boots via GRUB on UEFI (so live ISO uses GRUB, not systemd-boot) — same file.
- Calamares fork: https://github.com/CachyOS/cachyos-calamares, branch `cachyos`, has `settings.conf`, `settings_online.conf`, `settings_offline.conf`; 12k commits — [repo](https://github.com/CachyOS/cachyos-calamares)
- CLI installer repo: https://github.com/CachyOS/cachyos-cli-installer (files `cachyos_install.py`, `install_cachyos`, `archinstall_patches/`); no README description fetched — [repo](https://github.com/CachyOS/cachyos-cli-installer) (page returned 404 under the capitalised URL, lowercase name is the one in the fetched page text; verify)
- August 2026 release added experimental Server Edition profiles to CLI installer — [blog](https://cachyos.org/blog/2608-august-release/)
- Installer wiki: manual partitioning strongly preferred; Secure Boot and CSM must be disabled for UEFI install — [wiki installation_on_root](https://wiki.cachyos.org/installation/installation_on_root/)

### Inferences
- To inject a local/offline repo: add `[mac-hw]` repo to `archiso/pacman.conf`, add package names to `archiso/packages_desktop.x86_64`, put the repo dir in `airootfs/` and a matching `[mac-hw] Server = file:///...` in the live pacman.conf; the installed target would also need the repo added post-install (Calamares `shellprocess` / `shellprocess@...` in `settings*.conf`). Calamares module names (`shellprocess`, `packages`, `bootloader`) are upstream Calamares concepts I did not verify in CachyOS' files.
- Custom kernel cmdline on live media: edit `archiso/grub/*.cfg` (and `syslinux/`) in the profile. Not verified.
- Recommended pragmatic route: stock ISO + `install.sh` run after first boot (or from live environment via chroot) — far less maintenance than tracking a monthly ISO.

### Gaps
- No documentation found for unattended Calamares install, CLI installer config-file/JSON mode, or post-install hook mechanism. Read `cachyos_install.py` and the cachyos-calamares `settings_*.conf` directly before relying on them.

## 3. Bootloaders in installer and which works on a 2017 MacBook Pro

### Takeaway
Installer offers Limine, systemd-boot, rEFInd, GRUB (BIOS: GRUB and Limine only). For a 2017 Apple EFI Mac, GRUB with `--removable` (copy at `/EFI/BOOT/BOOTX64.EFI`) or rEFInd are the safest; systemd-boot is reported to be unreliable on some older Macs; Limine does not register an NVRAM entry automatically and has no evidence of Mac testing. Choose rEFInd or GRUB; verify on the machine.

### Cited Findings
- Bootloaders offered: Limine, systemd-boot, rEFInd, GRUB — [wiki installation_on_root](https://wiki.cachyos.org/installation/installation_on_root/)
- Limine: snapshot integration enabled by default on CachyOS with Btrfs via `limine-snapper-sync`, `limine-entry-tool` preinstalled; does not add a UEFI NVRAM entry automatically (use efibootmgr or limine-entry-tool). GRUB: snapshots via grub-btrfs-support. systemd-boot: no native snapshot rollback. rEFInd: auto-detects, snapshots only with custom setup — [wiki boot managers](https://wiki.cachyos.org/installation/boot_managers/)
- Kernel cmdline locations: systemd-boot `/etc/sdboot-manage.conf` `LINUX_OPTIONS=` then `sudo sdboot-manage gen`; rEFInd `/boot/refind_linux.conf`; GRUB `/etc/default/grub` `GRUB_CMDLINE_LINUX_DEFAULT` then `grub-mkconfig -o /boot/grub/grub.cfg`; Limine `/etc/default/limine` `KERNEL_CMDLINE[default]` then `limine-mkinitcpio` — [wiki boot manager configuration](https://wiki.cachyos.org/configuration/boot_manager_configuration/)
- Macs only list EFI entries found at default path; put loader at `/EFI/BOOT/BOOTX64.EFI`; GRUB: `grub-install --target=x86_64-efi --efi-directory=... --removable`; hold Option (Alt) to get the Apple picker and choose "EFI Boot"; passing i386-pc target ignores --removable — [Arch Wiki Mac via search summary of bbs/wiki](https://wiki.archlinux.org/title/Mac) (direct fetch blocked by Anubis; secondary summary)
- Some users report systemd-boot entry visible in Apple menu but freezing on older Macs (MBP 9,2); rEFInd worked — [Arch forum threads](https://bbs.archlinux.org/viewtopic.php?id=294136) (user reports, not first-hand verified)
- One user with a 2017 MBP14,1 on Arch saw "EFI Boot" in the Option menu for default-path loader — same search summary.
- rEFInd on Mac: `bless --mount /Volumes/ESP --setBoot --file /Volumes/ESP/efi/refind/refind_x64.efi --shortform` from macOS; ESP not mounted by macOS by default (`mount -t msdos /dev/disk0s1 /Volumes/ESP`); re-bless after macOS updates; drop the HFS+ driver; `refind-install --root /mnt` installs for another target OS — [rEFInd installing](https://www.rodsbooks.com/refind/installing.html)
- Apple's firmware includes its own HFS+ driver; rEFInd 0.12.0 hung on some Apple EFI, upgrade recommended — same page.
- MBP13/14 Touch Bar models: iBridge firmware lives on the ESP in macOS, keep original ESP contents when dual-booting; AutoBoot EFI variable can be changed via efivars — [Dunedan/mbp-2016-linux](https://github.com/Dunedan/mbp-2016-linux)
- Default FS Btrfs with subvolumes `@ @home @root @srv @cache @tmp @log`, zstd level 3; XFS cannot be shrunk; ext4 shrinks offline only; alternatives ZFS, F2FS — [wiki filesystem](https://wiki.cachyos.org/installation/filesystem/)
- Linux News: CachyOS installer dropped bcachefs (headline only) — [linux.org thread](https://www.linux.org/threads/phoronix-cachyos-handheld-edition-switches-to-wayland-cachyos-installer-drops-bcachefs.63529/latest)

### Inferences
- Recommended: rEFInd (installed on ESP, ESP shared with macOS if dual-booting, or `refind-install --root /mnt` from live ISO) with CachyOS "refind" option; `refind_linux.conf` holds cmdline. Fallback: GRUB `--removable` + `grub-btrfs`. Btrfs snapshots then go through grub-btrfs (GRUB) or Btrfs + snapper without boot menu integration (rEFInd). rEFInd-btrfs is a separate AUR-style tool I did not verify.
- Snapshot tooling default (Limine+limine-snapper-sync) is bound to Limine; choosing rEFInd/GRUB loses that default; ext4/xfs gives simplest Mac behaviour but no snapshots.
- /boot placement: with Limine/systemd-boot the kernels must be on the ESP; on Apple EFI keep ESP small-risk (~512MB-1GB); GRUB/rEFInd can read /boot on btrfs/ext4.
- Required kernel cmdline for this Mac: no evidence of a mandatory parameter (Dunedan notes `intremap=nosid` unnecessary since 4.10). Treat Wi-Fi workaround `brcmfmac.feature_disable=0x82000` as a modprobe option, not cmdline.

### Gaps
- Arch Wiki pages (Mac, MacBookPro14,x) blocked by Anubis; Apple EFI specifics come from secondary summaries. Not verified: whether CachyOS Calamares refind/GRUB paths pass `--removable`; `bless` behaviour with Linux root; Option-key picker behaviour with Limine.

## 4. Packaging patches/modules for CachyOS (PKGBUILD, DKMS, headers, repos)

### Takeaway
linux-cachyos has no user patch directory: patches are only added by editing the PKGBUILD `source` array (loop applies every `*.patch` in `source`). For this Mac, prefer DKMS packages plus linux-cachyos-headers instead of patching the kernel.

### Cited Findings
- Repo https://github.com/CachyOS/linux-cachyos has dirs `linux-cachyos`, `-bmq`, `-bore`, `-deckify`, `-eac`, `-eevdf`, `-hardened`, `-lts`, `-rc`, `-rt-bore`, `-server`; scripts `script.sh`, `srcinfo.sh` — [repo](https://github.com/CachyOS/linux-cachyos)
- PKGBUILD: no `_patches` var or user patch dir; patches come from `source+=` (CachyOS kernel-patches); `prepare()` applies `*.patch` from `source` with `patch -Np1` — [raw PKGBUILD](https://raw.githubusercontent.com/CachyOS/linux-cachyos/master/linux-cachyos/PKGBUILD) (summary by fetch model)
- Options as env vars: `_use_llvm_lto` (thin default), `_cpusched`, `_localmodcfg`, `_use_current`, `_makenconfig`; e.g. `_cpusched=bore makepkg -s` — same.
- Built packages: `linux-cachyos` + `linux-cachyos-headers` (optionally `-dbg`, `-zfs`, `-nvidia-open`, `-nvidia-580xx`, `-r8125`); hardened naming `linux-cachyos-hardened-{,lto-}headers` — same; [wiki kernel](https://wiki.cachyos.org/features/kernel/)
- Patch source repo https://github.com/CachyOS/kernel-patches has one directory per kernel version (5.15 ... 7.x) — [repo](https://github.com/CachyOS/kernel-patches)
- Prebuilt ZFS/NVIDIA modules ship with kernels and replace -dkms packages — [wiki kernel](https://wiki.cachyos.org/features/kernel/)
- CachyOS repos: `cachyos`, `cachyos-v3/-core-v3/-extra-v3`, `-v4`, `-znver4`; `cachyos-repo.sh` script; keyring key F3B607488DB35A47; repos placed above Arch repos — [wiki optimized repos](https://wiki.cachyos.org/features/optimized_repos/)
- Hardware status for MBP14,3: keyboard/trackpad works out of box; Touch Bar partially via `apple-ib-tb` (roadrunner2 / PatrickVerner fork); Wi-Fi BCM43602 brcmfmac firmware problems (2.4 GHz only); webcam works via iBridge since 4.13; audio needs Cirrus 8409 patch (davidjo/snd_hda_macbookpro); AMD dGPU works, Intel works; suspend partially; Touch ID not working — [Dunedan/mbp-2016-linux](https://github.com/Dunedan/mbp-2016-linux)
- snd_hda_macbookpro: install script `install.cirrus.driver.sh`; README does not mention DKMS or AUR; output works, input "still needs work"; kernel headers via `pacman -S linux-headers` — [egorenar/snd_hda_macbookpro](https://github.com/egorenar/snd_hda_macbookpro)
- 2025 report: brcmfmac looks for `brcmfmac43602-pcie.Apple Inc.-MacBookPro14,3.bin` + .txt/.clm_blob/.txcap_blob; workaround `options brcmfmac feature_disable=0x82000` limits to 2.4 GHz — [Debian list 2025](https://lists.debian.org/debian-amd64/2025/05/msg00002.html)

### Inferences
- Header packages for DKMS: `linux-cachyos-headers`, `linux-cachyos-lts-headers`, `linux-cachyos-bore-headers` etc. (suffix per variant); a DKMS package should `depends=(dkms)` and a hook `dkms` (from Arch `dkms` package) rebuilds on header install. List the packages the user runs, or use a meta-package depending on `linux-cachyos-headers`.
- Legacy Dunedan info (kernel <=5.x era) is stale: Touch Bar on 6.x/7.x kernels may be handled by mainline `hid-appletb-kbd` / `appletbdrm` / `tiny-dfr` — I did not verify; re-check. Wi-Fi/Touch Bar claims are 2020-2021 era; flag stale.
- Prefer `.install` scripts and `pacman` hooks in `/usr/share/libalpm/hooks/` for firmware or modprobe tweaks. Modules in initramfs: add to `/etc/mkinitcpio.conf.d/macbookpro14-3.conf` `MODULES=(applespi intel_lpss_pci spi_pxa2xx_platform apple_ib_tb ...)`; mkinitcpio hooks `base udev autodetect microcode modconf kms keyboard keymap block filesystems` (standard Arch; applespi module names from the Arch wiki lore, unverified here). CachyOS uses mkinitcpio by default; limine-mkinitcpio hook exists for Limine.
- Repo layout suggestion: `pkgs/macbookpro14-3-meta/PKGBUILD` (depends on dkms packages, firmware, `linux-cachyos-headers`, config files), `pkgs/snd-hda-macbookpro-dkms/`, `pkgs/apple-ib-tb-dkms/` (+ `dkms.conf`), `pkgs/macbookpro14-3-hooks`, `install.sh` (adds repo via `[macbookpro] SigLevel=Optional/Required`, `pacman -Syu`, `pacman -S macbookpro14-3-meta`), GitHub Actions build in an `archlinux`/`cachyos/cachyos-v3` container with `makepkg`, `repo-add` to publish via GitHub Releases/Pages, sign with a repo GPG key.

### Gaps
- Did not retrieve: Arch Wiki DKMS/PKGBUILD/Creating packages pages; chaotic-aur details; actual `applespi`/`apple-ib-tb` current kernel status for 7.x; whether `pacman -S linux-cachyos-headers` naming for the LTS/bore variants matches inference; Touch Bar/audio status in 2026.
