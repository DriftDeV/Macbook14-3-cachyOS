# MacBookPro14,3 (15" 2017) Linux audio on CachyOS (notes dated Nov 2026)

IMPORTANT PREMISE CORRECTION: the task brief assumed a Cirrus CS4208 codec. Sources found indicate the MacBookPro14,3 uses a Cirrus **CS8409** HDA codec, not CS4208. CS4208 is the codec of 2013-2015 models (MBP11,x/12,1, MBA6,x, MBP 9,1 12" etc.). Not verified from the machine itself: run `cat /proc/asound/card0/codec#0 | head` or `dmesg | grep -i cs8409` to confirm.

## Does mainline snd-hda-codec-cs420x support MacBookPro14,3? Which quirk applies?

### Takeaway
No. Mainline cs420x (CS4206/4207/4208) has no entry for MacBookPro14,x and does not cover CS8409. Internal audio on the 14,3 depends on the out-of-tree davidjo driver; the CS4208 quirks (CS4208_MBP11 etc.) do not apply.

### Cited Findings
- Current mainline `cs420x.c` (path `sound/hda/codecs/cirrus/cs420x.c`, moved in the newer tree layout) has Apple fixup entries only up to "MacBookPro 12,1" (0x106b7b00 -> CS4208_MBP11), plus MBP 11,2, MBA6,x, MacMini 7,1, MacPro 6,1, iMac 16,1. Neither "MacBookPro14" nor "CS8409" appears in the file. Model options: cs4208 `gpio0, mba6, mbp11, macmini`; cs420x `mbp53, mbp55, imac27, imac27_122, apple, mbp101, mbp81, mba42` — [torvalds/linux cs420x.c](https://raw.githubusercontent.com/torvalds/linux/master/sound/hda/codecs/cirrus/cs420x.c)
- On a MacBookPro14,3 (Arch, kernel 6.1.4) dmesg shows `snd_hda_codec_cs8409 ... UNKNOWN subsystem id 0x10138409`, the codec falls back to generic with no outputs — [davidjo issue #80](https://github.com/davidjo/snd_hda_macbookpro/issues/80)
- A Manjaro thread states that CS4206/4207/4208 `model=` options are not likely to work for the CS8409 codec (reported via search summary; page not fetched) — [Manjaro forum](https://forum.manjaro.org/t/macbook-pro-does-not-have-sound-seems-as-passive-button-after-re-installing-pulseaudio/166262/5)
- Upstream references for this hardware class: kernel bugzilla [195671 "no sound on macbook pro 2016"](https://bugzilla.kernel.org/show_bug.cgi?id=195671) and [110561](https://bugzilla.kernel.org/show_bug.cgi?id=110561) (both linked by the mbp-2016-linux README; pages returned 403 to me, contents unread).

### Inferences
- `model=mbp11` / `intel-mac-auto` style modprobe options are useless for 14,3; do not recommend them.
- From my background knowledge (NOT sourced here): mainline `patch_cs8409.c` covers Dell Dolphin/Cyborg designs, not Apple's CS8409+amp setup. No source found showing Apple CS8409 merged upstream as of Nov 2026.

### Gaps
- Could not read kernel git history or the lore thread "CS8409 Macbook Pro 2016 2017" (Takashi Iwai; [lore](https://lore.kernel.org/all/s5h1sbcu1t1.wl-tiwai@suse.de/T/) returned 403), so no confirmed statement on upstream refusal/merge status or kernel versions fixing anything.
- Codec not confirmed on-device.

## Does davidjo/snd_hda_macbookpro apply to 14,3? What works?

### Takeaway
Yes, it is the relevant driver (CS8409 + MAX98706/SSM3515/TAS5764L amps). 14,3 is reported working for output; mic input is the weak point.

### Cited Findings
- Repo README: supports Cirrus 8409 HDA with MAX98706, SSM3515 or TAS5764L amplifiers, "will NOT work with other amplifiers"; no model list; primary test kernel Ubuntu 24.04 / 6.8; kernel 6.17 reorganized the sound tree and `install.cirrus.driver.sh` auto-selects `install.cirrus.driver.pre617.sh` for older kernels — [davidjo/snd_hda_macbookpro](https://github.com/davidjo/snd_hda_macbookpro)
- README status: output via internal speakers and headphones "reasonably complete"; hw:0,0 / plughw:0,0 have no volume control and are very loud; hardware format limited to 2 or 4 channels at 44.1 kHz S24_LE/S32_LE (others via default plug/volume control); power management untested (everything permanently powered); recorded level very low; internal and headset mic "not yet fully interfaced" — same README
- mbp-2016-linux status table: 14,3 "Working" (internal input and output verified with the davidjo patch); 13,1 and 13,3 working; 14,1 partial (output only); 14,2 and 13,2 not working — [Dunedan/mbp-2016-linux](https://github.com/Dunedan/mbp-2016-linux/blob/master/README.md). Claim of "works out of the box" for 14,3 from a search summary conflicts with this and with issue #80; treat as unreliable.
- Arch mailing list reply (via search summary): 15" 14,3 had working audio with the patch, and the patch "never made it into the (arch) kernel" so DKMS/build needed — [arch-general](https://lists.archlinux.org/archives/list/arch-general@lists.archlinux.org/thread/NJMHKOIFIWHLKW4EV32UHAJEAQ3OKCY4/) (page itself blocked; summary only)
- Ubuntu Studio 24 user on 14,3 reported no audio; a suggested leifliddy/macbook12-audio-driver (CS4208 12" driver) did not work on 14,3 — [Ubuntu Discourse](https://discourse.ubuntu.com/t/macbook-pro-14-3-installed-ubuntu-studio-24-no-audio/79058) (closed 24 Apr 2026, unresolved). Confirms the 12" CS4208 driver is the wrong one.
- Related fork (iMac18,3, same CS8409 base): https://github.com/egorenar/snd_hda_macbookpro (mentioned in search results; unverified relevance to 14,3).

### Inferences
- The "no sound after boot" bug below makes first-boot success unreliable; a user may wrongly blame the driver.

### Gaps
- No evidence found of 14,3 mic working; no recent (2026) 14,3 success reports with kernel 6.17+/CachyOS found. Repo commit activity/recency not checked.

## Known bugs: invalid subsystem ID after cold boot, suspend, volume, mic, pops

### Takeaway
Biggest 14,3-specific bug: after some boots the codec reports bogus subsystem id 0x10138409 and the driver fails; NVRAM reset / booting via Option key / reinstalling the bootloader worked around it for some users.

### Cited Findings
- Issue #80 (14,3): maintainer says 0x10138409 is a device ID, not subsystem ID, suspects boot-time corruption of the subsystem ID, not a kernel-version cause. Reporter fixed it by NVRAM reset then booting with Option held and selecting Linux; EFI vars `BootCurrent`, `GR_CAUSE`, `HW_BOOT_DATA`, `MTC` differed between good/bad boots. Another user confirmed Aug 2024 — [issue #80](https://github.com/davidjo/snd_hda_macbookpro/issues/80)
- Issue #134 comments: check with `sudo dmesg | grep -i cs8409`; after NVRAM reset, `sudo grub-install --target=x86_64-efi --efi-directory=/boot/efi --bootloader-id=GRUB` and `sudo grub-mkconfig -o /boot/grub/grub.cfg` kept audio working through reboot and suspend for LukeW2002; Option-key boot works only until a cold start for KiLLeRRaT; `pci=nocrs` did not help — [issue #134](https://github.com/davidjo/snd_hda_macbookpro/issues/134)
- Low recorded level: README suggests amplification (e.g. PulseEffects) — [README](https://github.com/davidjo/snd_hda_macbookpro)
- Output not Apple-like because macOS applies CoreAudio DSP filtering — README.
- Ubuntu Studio user: laptop did not wake from sleep (possibly unrelated to audio) — [Ubuntu Discourse](https://discourse.ubuntu.com/t/macbook-pro-14-3-installed-ubuntu-studio-24-no-audio/79058)
- Workaround for any Mac with broken analog: HDMI or USB audio works — [mbp-2016-linux](https://github.com/Dunedan/mbp-2016-linux/blob/master/README.md); and on PulseAudio, "Analog Stereo Duplex" profile suggested for input — same.

### Gaps
- Headphone jack auto-switching/jack detect behavior on 14,3: no source found.
- Speaker pops, "speaker volume too low" (beyond README's remarks), post-suspend behavior of the driver: no reliable 14,3 source found.
- HDMI/DP audio: only a generic statement that HDMI audio works (Dunedan README, for models without internal audio). Intel/Kaby Lake HDMI codec is handled by mainline snd_hda_codec_hdmi; not sourced for 14,3 specifically (note 14,3 DP goes via Thunderbolt 3/USB-C and the AMD dGPU HDMI codec may differ).
- No UCM profile or alsa-ucm-conf entry for this machine found; no documented modprobe.d or WirePlumber rule for 14,3 found. I will not invent them.

## Install procedure for Arch/CachyOS

### Takeaway
Use the upstream script (or the AUR DKMS package, with caveats). CachyOS kernels: headers must match the running kernel package.

### Cited Findings
- Upstream (Arch) per README: `sudo pacman -S gcc linux-headers make patch wget; git clone https://github.com/davidjo/snd_hda_macbookpro.git; cd snd_hda_macbookpro/; sudo ./install.cirrus.driver.sh; reboot`. DKMS variant: install `dkms`, run `sudo ./install.cirrus.driver.sh -i`; remove with `-r` — [README](https://github.com/davidjo/snd_hda_macbookpro)
- AUR: `snd-hda-macbookpro-dkms-git` 0.1-1, maintainer kyeh, first submitted Nov 2023, last updated 2023-11-09 in the snippet seen (stale). A MBP14,1 commenter on Manjaro kernel 6.9.12 hit "DKMS will not replace this module... use --force"; upstream script worked for them; maintainer advised checking `/lib/modules/$(uname -r)/updates/` — [AUR](https://aur.archlinux.org/packages/snd-hda-macbookpro-dkms-git)

### Inferences
- On CachyOS, install headers for the exact kernel flavour (e.g. `linux-cachyos-headers`, or `linux-cachyos-lts-headers`), not generic `linux-headers`. Package name is my inference from CachyOS conventions, not sourced. Rebuild is needed on kernel updates; the AUR package was last updated 2023, so check it is current with kernel 6.17+ tree layout before relying on it. Prefer the upstream script with `-i` (DKMS) if kernel >=6.17 reorg matters.

### Gaps
- Not tested on CachyOS kernels (BORE/EEVDF patchsets); no source confirming compatibility.

## PipeWire / low-latency / DAW tuning on CachyOS

### Takeaway
Generic PipeWire pro-audio tuning applies; nothing 14,3-specific found. The driver's fixed 44.1 kHz and 2/4-channel hardware format limits likely constrain low-latency use; the README does not document latency measurements.

### Cited Findings
- Realtime scheduling: install `rtkit` and `realtime-privileges`, enable `rtkit-daemon`, add user to `realtime` group (CachyOS forum-derived advice via search summary) — [CachyOS forum DAW thread](https://discuss.cachyos.org/t/should-daw-bitwig-studio-users-on-cachyos-avoid-kde-plasma-de/4999)
- Example quantum config: default.clock.quantum=128, min-quantum=64, max-quantum=1024 at 48000 Hz; check with `pw-top`; Pro Audio profile selectable via pavucontrol — [Configure PipeWire for Pro Audio](https://linuxjunkies.org/guides/install-pipewire-pro-audio), [Arch Wiki PipeWire](https://wiki.archlinux.org/title/PipeWire) (Arch wiki fetch blocked by Anubis; I could not read exact config text)
- Bitwig on CachyOS: using ALSA instead of PipeWire gave about 6 ms minimum latency in one report — [CachyOS forum](https://discuss.cachyos.org/t/should-daw-bitwig-studio-users-on-cachyos-avoid-kde-plasma-de/4999)

### Inferences
- Because the out-of-tree driver sets hw rate to 44.1 kHz and hw nodes are very loud with no volume control, route apps through PipeWire (default volume path) rather than direct hw: access. Set `default.clock.rate = 44100` if rate mismatch causes resampling (my inference).
- `threadirqs`, RT kernel: not covered by any 14,3 source; CachyOS ships its own scheduler-tuned kernels.

### Gaps
- Exact config files with content for 14,3 (modprobe.d, WirePlumber): none documented in sources I could read. Arch Wiki MacBookPro14,x page ([wiki.archlinux.org/title/MacBookPro14,x](https://wiki.archlinux.org/title/MacBookPro14,x)) was blocked (Anubis) and should be read manually; it is the most likely place for such config. Also check [mbp-2016-linux README](https://github.com/Dunedan/mbp-2016-linux) beyond char 100000 (unread).

## Staleness flags
- Issue #80/#134 data is from 2023-2024 (kernel 6.1-6.9); no 2026 confirmation. Ubuntu thread is Apr 2026 and unresolved. AUR DKMS package last updated Nov 2023.
- Several claims come from search-result summaries rather than fetched pages (Arch mailing list, Manjaro threads); marked above.
