# USB-less CachyOS live/install boot from macOS on a MacBookPro14,3 (Intel, T1-era, Apple EFI)

Research date: 2026-11-23. Tool budget limited; Arch Wiki (Mac, Archiso, Multiboot USB drive, GRUB) and the GitLab archiso docs were blocked by Anubis bot protection during fetching, so several Arch Wiki claims below are NOT directly verified and are placed in Inferences/Gaps. Nothing here was run on a real Mac.

## 1. Shrinking APFS from macOS (diskutil), snapshots, FileVault, partition creation

### Takeaway
`diskutil apfs resizeContainer <container> <size> [fmt name size ...]` can shrink the container and create new partitions in the freed space in one step; failures are most often caused by local Time Machine snapshots/APFS tidemarks (error -69531) or locked volumes (-69582), and require thinning snapshots or fsck first. No SIP change is needed for the resize itself.

### Cited Findings
- Syntax: `diskutil apfs resizeContainer containerReferenceDevice | physicalStoreDevice limits [-plist] | size [part1Format part1Name part1Size part2Format ...]`; `limits` takes no action and prints valid size range; a size of 0 fills remaining space; shrinking can create new partitions in freed space using the same format/name/size triplets as partitionDisk; growing is limited by free map space after the container — [ss64 diskutil](https://ss64.com/mac/diskutil.html)
- Requirement quote: "Ownership of the affected disks is required, and all APFS Volumes on the Container must be unlocked." (resizeContainer) — [ss64 diskutil](https://ss64.com/mac/diskutil.html)
- `diskutil addPartition device format name size`: starts right after the existing partition's end; map must be GPT with a gap at the target; for an unformatted raw-type partition pass format as `%<GPT UUID or type name>%` and name as `%noformat%`; size 0 = fit-to-fill — [ss64 diskutil](https://ss64.com/mac/diskutil.html)
- `diskutil apfs listSnapshots volumeDevice` and `diskutil apfs deleteSnapshot volumeDevice -uuid <uuid> | -xid <xid> | -name <name>` exist; deleting removes ability to revert, not current contents — [ss64 diskutil](https://ss64.com/mac/diskutil.html)
- Unlock/decrypt verbs: `diskutil apfs unlockVolume`, `decryptVolume` (volume must be unlocked first) — [ss64 diskutil](https://ss64.com/mac/diskutil.html)
- Common failure: "Error: -69531: There is not enough free space in the APFS Container for this operation due to APFS limits or APFS tidemarks (perhaps caused by APFS Snapshot usage by Time Machine)"; community advice: pause Time Machine, delete local snapshots, retry; one user had to delete snapshots with `diskutil apfs deleteSnapshot` from Recovery because `tmutil` did not work — [Apple Community resize threads (search results)](https://discussions.apple.com/thread/8090902) and [Apple Community 252978188](https://discussions.apple.com/thread/252978188)
- Other reported errors: 49153/49180/49187/49174 generic "problem occurred while resizing", some fixed by `diskutil unmountDisk diskN; fsck_apfs -s -o -y /dev/rdiskN` from Recovery; -69582 = a volume is locked (unresolved in sources) — [Apple Community 8090902](https://discussions.apple.com/thread/8090902), [253374779](https://discussions.apple.com/thread/253374779)
- A guide (low quality) suggests `diskutil apfs resizeContainer disk0s2 50G` then `diskutil partitionDisk disk0s2 2 GPT JHFS+ Linux 0b` — that second command targets a slice, would be wrong/dangerous and the article itself never creates the volume it copies into; do NOT use it — [developnsolve](https://www.developnsolve.com/linux/installing-linux-on-a-mac-without-usb)

### Inferences
- Recommended safe form (from the documented syntax, untested): `diskutil apfs resizeContainer disk1 <NEW_APFS_SIZE>g fat32 COSLIVE 6g` (or `ExFAT`, or `"Free Space" %noformat% 0` for the rest). `diskutil apfs resizeContainer disk1 limits` first to get the minimum size. Parse container via `diskutil list -plist` / `diskutil info -plist /` (`APFSContainerReference`, `ParentWholeDisk`) rather than text.
- On MBP14,3 internal NVMe: disk0 is physical store (disk0s2 APFS), disk1 synthesized container. Recovery lives in a separate APFS container/partition (disk0s3) after the main container on older layouts; if the Recovery/other partition sits after the container, free space created by shrinking sits between them and is usable for addPartition. Verify with `diskutil list` before acting (not sourced).
- Before resize: `tmutil disable` / `tmutil listlocalsnapshots /`, `tmutil thinlocalsnapshots / 99999999999 4`, `tmutil deletelocalsnapshots <date>` (commonly cited but not verified in my fetches), check FileVault via `fdesetup status`; the volume must be unlocked (it is when booted into macOS). Maybe run `diskutil verifyVolume /` first.
- Wider caution: Apple Fusion not applicable (NVMe).

### Gaps
- Official Apple documentation for tmutil snapshot flags and Recovery position not fetched; whether purgeable space affects the shrink minimum is not verified.
- Behaviour on macOS 15 Sequoia vs 13: not found. Not confirmed whether Sequoia changed resizeContainer. Note: MacBookPro14,3 officially supports up to macOS 13 Ventura; the "host" statement of Sequoia 15 would only run via OCLP-type patches. Not verified here.

## 2. Making the internal disk boot the live environment without USB

### Takeaway
Best-evidenced route: create a small FAT32 (ESP-readable by Apple EFI and rEFInd/GRUB) partition on the internal disk, extract the ISO there, provide an EFI loader (rEFInd on the ESP and/or GRUB EFI) that boots the CachyOS kernel/initramfs with archiso parameters pointing at that partition; then use `bless --mount ... --setBoot [--nextonly]` or Option-key picker. No tested, documented end-to-end example of this exact procedure was found; "dd the ISO to a partition" and Ventoy-on-internal are weakly supported.

### Cited Findings
- CachyOS live ISO profile: `iso_name="cachyos"`, `iso_label="COS_YYYYMM"`, `install_dir="arch"`, `bootmodes=('bios.syslinux' 'uefi.grub')` (systemd-boot commented out), airootfs is squashfs (xz) — [cachyos-live-iso profiledef.sh (master branch; may be stale)](https://raw.githubusercontent.com/CachyOS/cachyos-live-iso/master/archiso/profiledef.sh)
- ISO GRUB entry: `linux /%INSTALL_DIR%/boot/%ARCH%/vmlinuz-linux-cachyos archisobasedir=%INSTALL_DIR% archisosearchuuid=%ARCHISO_UUID% cow_spacesize=10G copytoram=auto module_blacklist=pcspkr i915.modeset=1 amdgpu.modeset=1 nvme_load=yes`; `initrd /%INSTALL_DIR%/boot/%ARCH%/initramfs-linux-cachyos.img`; an LTS entry with `vmlinuz-linux-cachyos-lts`; and a legacy-GPU entry adding `module_blacklist=nvidia,nvidia_modeset,nvidia_uvm,nvidia_drm nomodeset nvme_load=yes` — [CachyOS grub.cfg template](https://raw.githubusercontent.com/CachyOS/cachyos-live-iso/master/archiso/grub/grub.cfg)
- CachyOS ISO now contains Stable and LTS kernels, Limine as default for installed systems (installer), boot managers offered: systemd-boot, rEFInd, GRUB, Limine — [CachyOS wiki boot managers](https://wiki.cachyos.org/ko/installation/boot_managers), [GamingOnLinux Jan 2026](https://www.gamingonlinux.com/2026/01/the-popular-arch-based-distro-cachyos-gets-a-new-release-with-a-significantly-reworked-installer)
- Archiso initramfs params: `archisobasedir` (default arch); `archisosearchuuid` (UUID of device holding files, overrides archisodevice; falls back to searching for `archisosearchfilename`); `archisolabel`; `archisodevice` (default /dev/disk/by-label/${archisolabel}); `copytoram` y/auto (auto: only if image <4GiB and free RAM > image+2GiB); `cow_spacesize` default 256M (tmpfs, bytes/%/k m g); `cow_label`/`cow_device` for persistent COW; loopback hook `archiso_loop_mnt` with `img_dev` and `img_loop` (full ISO path on img_dev) — [mkinitcpio-archiso README.bootparams](https://raw.githubusercontent.com/archlinux/mkinitcpio-archiso/master/docs/README.bootparams)
- rEFInd on Macs: rEFInd detects kernels named vmlinuz*/bzImage*/kernel* as EFI stubs (kernel >=3.3, bitness must match firmware), picks an initrd by version string in the same directory, and `refind_linux.conf` in the kernel dir gives options; if the entry gives an `initrd=` option rEFInd adds none. A Mac Mini was reported to hang booting an EFI-stub kernel from the ESP but worked from an HFS+ partition — [rodsbooks rEFInd Linux](https://www.rodsbooks.com/refind/linux.html)
- rEFInd docs don't cover ISO loopback; rEFInd offers an ISO-9660 driver only — [rodsbooks rEFInd Linux](https://www.rodsbooks.com/refind/linux.html)
- Firmware check: `ioreg -l -p IODeviceTree | grep firmware-abi` — EFI32 → refind_ia32.efi, EFI64 → refind_x64.efi — [rodsbooks installing](https://www.rodsbooks.com/refind/installing.html)
- Apple's EFI has an HFS+ driver; rEFInd's own HFS+ driver can hang rEFInd on Macs and should be removed — [rodsbooks installing](https://www.rodsbooks.com/refind/installing.html)
- Ventoy has no macOS version; only a third-party app (Mactoy) for USB; Mac Linux USB Loader exists but targets USB — [Ventoy discussion 1361](https://github.com/ventoy/Ventoy/discussions/1361), [MLUL](https://sourceforge.net/projects/mlul/)
- Community report of rEFInd seeing live drives but not booting them on a Mac, and that a Linux bootloader may not "see" internal storage — [Apple Community 255901693](https://discussions.apple.com/thread/255901693), [winesapOS #544](https://www.github.com/LukeShortCloud/winesapOS/issues/544)

### Inferences
- Concrete plan (A, recommended): partition `COSLIVE` FAT32 (≈6-8 GB; ISO ~3+ GB, FAT32 4 GiB single-file limit OK for the airootfs.sfs unless it exceeds 4 GiB — check). `hdiutil attach -nomount cachyos.iso` / `hdiutil mount` and `rsync -a` contents (ISO9660 mounts read-only; Joliet/Rock Ridge name mapping can mangle names — verify case/long names; use `hdiutil attach -readonly -mountpoint`). Put a grub.cfg or `refind.conf` entry with loader `/arch/boot/x86_64/vmlinuz-linux-cachyos` and options `initrd=/arch/boot/x86_64/initramfs-linux-cachyos.img archisobasedir=arch archisolabel=COSLIVE copytoram=y cow_spacesize=4G nomodeset` (archisosearchuuid in the ISO's template is a build-time substitution for ISO fs UUID; for a copied tree use archisolabel or archisodevice=/dev/disk/by-label/COSLIVE or create `/arch/<uuid>.uuid`-style file — latter unverified).
- rEFInd will likely need `refind.conf` `scanfor`/manual stanza; rEFInd can scan the FAT partition kernel directly. If kernel stub hangs from FAT, fallback is GRUB EFI (grub-mkstandalone) — untested.
- Plan B: ISO file on FAT + GRUB `loopback loop /cachyos.iso` + `linux (loop)/arch/boot/x86_64/vmlinuz-linux-cachyos img_dev=/dev/disk/by-label/COSLIVE img_loop=/cachyos.iso archisobasedir=arch` — requires the ISO initramfs to include `archiso_loop_mnt` hook (present in mkinitcpio-archiso, but not verified for CachyOS image). Also requires GRUB EFI binary; the ISO's own efiboot image contains one that could be extracted (unverified).
- `dd` of ISO to an internal partition: hybrid ISO partition table (isohybrid GPT/MBR) is built for whole-device, not partition; Apple EFI via rEFInd cannot boot the ISO9660 El Torito EFI image from a partition unless EFI System Partition recognized — no sources; discourage.
- One-time boot: `sudo bless --mount /Volumes/EFI --setBoot --nextonly --file /Volumes/EFI/EFI/refind/refind_x64.efi --shortform` (documented flags; behaviour on modern macOS unreliable, see below). Fallback: user holds Option at boot to pick EFI Boot.
- Kernel parameters likely needed on this laptop: `nomodeset` (CachyOS offers "Legacy hardware" entry), maybe `intel_iommu=off` no source; MBP14,3 has Intel iGPU + AMD Radeon Pro 4xx dGPU (not sourced) — nomodeset is the safe first try. `efi=noruntime` has no source here.
- Keyboard/trackpad: applespi upstream since 5.3 and works for MacBookPro13,*/14,* on Fedora/Ubuntu/Arch live media; Debian DVD/RHEL installers reported failing; reports note intel_lpss_pci and spi_pxa2xx_platform must be modules — CachyOS kernel config not verified; keep an external USB keyboard as insurance (note the MBP14,3 has only USB-C ports) — [Debian-cd list msg](https://lists.debian.org/debian-cd/2025/08/msg00006.html), [cb22 macbook12-spi-driver](https://github.com/cb22/macbook12-spi-driver)

### Gaps
- No Arch Wiki Mac/GRUB/Archiso pages could be read (Anubis block), so statements about hybrid ISO on Mac EFI and Arch-specific Mac quirks are unverified.
- No documented example of CachyOS or Arch live env booted from an extracted ISO on the same internal disk of an Intel Mac.
- Real CachyOS ISO boot config in the latest ISO (2026) not verified; master-branch files may differ from the shipped ISO (profile says `install_dir="arch"`, historically CachyOS used archisobasedir=arch). A boot entry file in efiboot/loader returned 404.
- Whether `refind_linux.conf`/APFS-adjacent FAT booting works on 14,3 specifically: no data.
- 32-bit vs 64-bit EFI: MBP14,3 firmware is 64-bit EFI by Apple's lineage (inference); verify with the firmware-abi command above.

## 3. rEFInd installed from macOS, SIP, bless

### Takeaway
rEFInd's `refind-install` on macOS installs to the ESP by default (since 0.8.4); SIP blocks the final firmware registration step on El Capitan+, so either disable SIP (from Recovery: `csrutil disable`) or install from Recovery; bless one-time boot reports are mixed on newer macOS.

### Cited Findings
- SIP blocks the step that registers loader with firmware; disable SIP or install from Recovery; default target ESP since 0.8.4; `--notesp` installs to macOS root; with encrypted/logical volumes you cannot install to the macOS root (use ESP) — [rodsbooks installing](https://www.rodsbooks.com/refind/installing.html)
- Manual install steps: `mkdir /Volumes/ESP; sudo mount -t msdos /dev/disk0s1 /Volumes/ESP; sudo mkdir -p /Volumes/ESP/efi/refind`, copy files, remove unused arch binaries/drivers, `sudo mv refind.conf-sample refind.conf`, then `sudo bless --mount /Volumes/ESP --setBoot --file /Volumes/ESP/efi/refind/refind_x64.efi --shortform` — [rodsbooks installing](https://www.rodsbooks.com/refind/installing.html)
- Cautions: re-bless after Apple updates; ~30 s boot delay fixed by `--shortform`; uninstall by using Startup Disk to bypass rEFInd, delete rEFInd files, and never delete macOS `System/Library/CoreServices` — [rodsbooks installing](https://www.rodsbooks.com/refind/installing.html)
- On Macs rEFInd installs `gptsync.efi` (hybrid MBR, "a dangerous hack") only when run under macOS and only if enabled via showtools; Yosemite LVM and APFS made macOS-root installs unusable, hence ESP — [rodsbooks efi-bootloaders refind](https://rodsbooks.com/efi-bootloaders/refind.html)
- bless man page: `--nextonly` limits to next boot (efi-boot-device); `--mount` + `--setBoot` EFI only; NSHipster says `--setBoot` stopped working with SIP, suggests `systemsetup`; a user reports `bless --mount --setBoot --nextonly` stopped working after 10.13.6 while Option-boot works — [bless man (Apple opensource)](https://opensource.apple.com/source/bless/bless-166/bless.8.auto.html), [NSHipster bless](https://nshipster.com/bless/), [Apple Community 8470350](https://discussions.apple.com/thread/8470350)
- `brew install --cask refind` is suggested by one (low quality) guide — [developnsolve](https://www.developnsolve.com/linux/installing-linux-on-a-mac-without-usb)

### Inferences
- A script could avoid SIP changes entirely by writing the ISO tree + rEFInd/GRUB EFI files onto the FAT partition and relying on the user pressing Option at boot to choose the "EFI Boot" entry (the macOS firmware picker lists FAT partitions that contain `EFI/BOOT/BOOTX64.EFI`) — plausible, not sourced. Using `bless` without `--setBoot` (`bless --mount X --file ... --label ...`) may also avoid SIP issues — unverified.
- macOS 13 vs 15: SIP/bless behaviour on Sequoia not verified.

### Gaps
- Did not verify whether the T1 chip (touchbar MacBookPro14,3) imposes any firmware boot restrictions beyond Apple EFI; user states none.

## 4. Reuse of freed space after live boot; dual-boot safety

### Takeaway
Little sourced guidance; the safe design is to keep macOS ESP (disk0s1) untouched, install CachyOS into the freed GPT space (new partitions created by Calamares/manual), put its bootloader on a new or the existing ESP deliberately, and let rEFInd on the ESP chain to it. Avoid hybrid MBR.

### Cited Findings
- gptsync/hybrid MBR is "a dangerous hack" and installed only under macOS — [rodsbooks efi-bootloaders refind](https://rodsbooks.com/efi-bootloaders/refind.html)
- CachyOS offers rEFInd, systemd-boot, GRUB, Limine; systemd-boot and rEFInd UEFI-only — [CachyOS wiki](https://wiki.cachyos.org/ko/installation/boot_managers)
- rEFInd usually uses ESP; ESP location `/dev/disk0s1` on Macs in doc example — [rodsbooks installing](https://www.rodsbooks.com/refind/installing.html)
- Kali's dual-boot-with-Mac and Arch Mac pages exist as prior art ([Kali dual boot](https://www.kali.org/docs/installation/dual-boot-kali-with-mac/), [Kali hard disk on Mac](https://www.kali.org/docs/installation/hard-disk-install-on-mac/)); I could only read search snippets, not contents.

### Inferences
- Installer target: delete only the helper COSLIVE FAT32 partition (or reuse it for /boot/efi? no: FAT live partition size 6 GB could become the Linux ESP (set ESP flag, format fat32 512 MB+) — plausible), and create root (ext4/btrfs) in the remaining free space. Mount the Mac's disk0s1 ESP at /boot/efi only if the bootloader should be shared; otherwise a second ESP is simpler but Apple firmware/rEFInd scanning of multiple ESPs is untested.
- Installing to the macOS ESP: systemd-boot/Limine entries live next to Apple's `EFI/APPLE`; the macOS ESP is ~200 MB (check) and may be too small for many kernels.
- Keep Linux partitions after the APFS container but before Recovery? Avoid renumbering; use free space only.

### Gaps
- No sourced Calamares behaviour for pre-existing free space/ESP selection on Apple EFI in 2026 CachyOS installer (the "significantly reworked installer" is noted by GamingOnLinux but not read).

## 5. Safety design and rollback

### Takeaway
Scripted checks should gate on model, power, backups, SIP/FileVault state, snapshots; rollback = delete helper partitions, `resizeContainer` back to full, clean the blessed loader and use Startup Disk to restore macOS.

### Cited Findings
- `diskutil apfs resizeContainer ... limits` is a no-op query for valid sizes; growing is limited by free space after the container; size 0 fills remainder — [ss64 diskutil](https://ss64.com/mac/diskutil.html)
- Resizing the startup disk can invalidate Startup Disk setting; reset via Startup Disk preferences or `bless` — [ss64 diskutil](https://ss64.com/mac/diskutil.html)
- rEFInd uninstall/bypass: Startup Disk, delete files, don't remove CoreServices — [rodsbooks installing](https://www.rodsbooks.com/refind/installing.html)
- Disk map corruption/resize errors fixed by fsck_apfs from Recovery in reports — [Apple Community 8090902](https://discussions.apple.com/thread/8090902)
- Apple's Option-key boot still works when bless fails — [Apple Community 8470350](https://discussions.apple.com/thread/8470350)
- rEFInd cautions: wake problems `sudo pmset -a autopoweroff 0`; HFS+ driver may hang rEFInd — [rodsbooks installing](https://www.rodsbooks.com/refind/installing.html)

### Inferences (checklist, from the above plus general practice)
- Pre-flight: `sysctl -n hw.model` == `MacBookPro14,3`; `ioreg ... firmware-abi` shows EFI64; `pmset -g batt` on AC; `csrutil status` (only needed if using `refind-install`/`--setBoot`); `fdesetup status` (volume must be unlocked; FileVault on APFS is fine for resize but not required to disable); `tmutil listlocalsnapshots /`; `diskutil verifyVolume /`; require Time Machine backup within N days; `diskutil list -plist` stored as JSON backup of partition map (`diskutil list > backup`; `gpt -r show disk0`); free space check `limits`; `--dry-run` default; require typed confirmation of disk identifier; download ISO with `curl -L` and verify SHA256 (CachyOS publishes checksums next to ISO on its mirrors; not verified here) — ISO size vs. FAT32 4 GiB check.
- Rollback: `sudo diskutil eraseVolume free none diskXsY` (or `diskutil eraseVolume "Free Space" ...`) for helper/Linux partitions, then `sudo diskutil apfs resizeContainer disk1 0` to regain full; re-bless macOS: `sudo bless --mount / --setBoot` or `systemsetup -setstartupdisk`; delete `EFI/refind` and reset NVRAM (Cmd-Opt-P-R) — NVRAM reset standard Apple practice; deleting partitions: macOS cannot always remove "Free Space"; fallback is Recovery.
- Danger: partitions after the APFS container prevent growing it back unless those partitions are deleted and the free space is contiguous.

### Gaps
- No peer-reviewed/official source for tmutil flags in this run; `systemsetup` use on Intel Sequoia untested.
- Internet Recovery/PXE: not pursued (task said irrelevant); Apple Mac EFI network boot via NetBoot is deprecated on newer macOS — not researched.
- Existing scripts that fully automate this flow: none found. Prior-art adjacent: Asahi installer (Apple Silicon only, ties to resizeContainer of APFS + stub partitions; not researched here), Mac Linux USB Loader (needs USB).
