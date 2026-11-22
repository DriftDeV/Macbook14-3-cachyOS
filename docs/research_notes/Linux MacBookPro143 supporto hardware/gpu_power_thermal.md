# MacBookPro14,3 on Linux: GPU, power, thermals, suspend, battery (research date 2026-11-23)

Scope note: research hit limits. Arch Wiki pages (MacBookPro11,x / 13,3 / Laptop/Apple) returned an Anubis bot-block and could not be read; the Dunedan README was only readable to ~100k of 129k chars (Touch Bar, keyboard backlight, rest of Thunderbolt truncated). Most hard evidence is for 13,3 (the 15" 2016 sibling) or 13" 2017 models. Nothing found is a verified, complete 14,3 recipe. Many sources are 2017-2021 (stale).

## Hybrid graphics (apple-gmux, which GPU boots, amdgpu vs i915, switcheroo, dGPU power/fan, cmdline options, Wayland, HiDPI)

### Takeaway
On 14,3 both Intel and AMD graphics work out of the box (AMD by default); the Intel iGPU is only usable after an Apple-OS-spoof (apple_set_os.efi / gpu-switch), and the dGPU cannot be reliably powered off (amdgpu + gmux), so the battery/fan penalty of the always-on Radeon is the main unsolved problem. Resume is reported to work only on the Intel GPU.

### Cited Findings
- Dunedan's table: AMD graphics "works out of the box" on MacBookPro13,3 and 14,3; Intel works out of the box on 13,1/13,2 (no dGPU), but on 13,3 only the AMD GPU is enabled when booting non-macOS systems; enabling Intel needs the workaround in issue #6. 14,3 listed: Intel and AMD graphics working. — [Dunedan/mbp-2016-linux README](https://github.com/Dunedan/mbp-2016-linux/blob/master/README.md)
- "On 15" models with the AMD GPU, resume only works when using the internal Intel GPU." — [Dunedan README](https://github.com/Dunedan/mbp-2016-linux/blob/master/README.md)
- Same README: external displays over USB-C-to-DP work including MST daisy-chain (internal + two FHD tested); battery life still suboptimal (family-wide, "less than 4 hours" claim via search snippet, not 14,3-specific). — [Dunedan README](https://github.com/Dunedan/mbp-2016-linux/blob/master/README.md)
- Default GPU is chosen by EFI firmware; when booting a non-Apple OS firmware leaves only the dGPU enabled on 13,3/14,3. Kernel docs: gmux EFI variable `gpu-power-prefs-fa4ce28d-b62f-4c99-9cc3-6815686e30f9`, 5th byte 1=IGD, 0=DIS. — [kernel vga_switcheroo docs](https://docs.kernel.org/gpu/vga-switcheroo.html)
- Kernel docs on gmux: pre-T2 retina models use a Renesas R4F2113 gmux; retina models use a separate eDP mux chip controlled by gmux; backlight PWM on dual-GPU models comes from a TI LP854x controlled by gmux; later models can drive the external port only from the dGPU. — [kernel docs](https://docs.kernel.org/gpu/vga-switcheroo.html)
- vga_switcheroo debugfs (`/sys/kernel/debug/vgaswitcheroo/switch`): OFF powers off unused GPU; IGD switches and powers dGPU off (fails if userspace holds GPU/audio device open; use lsof/fuser); DIGD/DDIS delayed switches. OFF/ON are no-ops when the driver does runtime PM; `amdgpu.runpm=0` disables driver runtime PM. On muxed machines ON/OFF become a no-op for the dGPU. — [kernel docs](https://docs.kernel.org/gpu/vga-switcheroo.html)
- Recipe for 13,3/14,3 (older, 2017-2018): put apple_set_os.efi in /boot/efi/EFI/custom, chainload from a grub custom.cfg, run `gpu-switch -i` (0xbb/gpu-switch) so iGPU is default, then a oneshot systemd unit disable-dgpu.service writing `OFF` to the vgaswitcheroo switch file (ExecStop writes `ON`). Reported saving ~5-6 W (~1/3 of power). Author says enabling at boot causes hangs (start manually after login); needs disabling for external displays; amdgpu handles disable poorly (shutdown may hang for minutes). — [roadrunner2 gist](https://gist.github.com/roadrunner2/1289542a748d9a104e7baec6a92f9cd7)
- Alternative OS-spoof: rEFInd `spoof_osx_version 10.12` in refind.conf; gpu-switch -i then reboot; optional `blacklist amdgpu`. 2017 recipe tested on 13,3 only. gpu-switch writes a persistent NVRAM variable (macOS may hang at boot until `gpu-switch -d`); Dunedan suggested changing attribute byte 0x07->0x06 (untested). — [Dunedan issue #6](https://github.com/Dunedan/mbp-2016-linux/issues/6)
- 14,3 reports in issue #6 conflict: X failed with Intel enabled until `modprobe -r amdgpu`; another said blacklisting amdgpu stopped X starting. One user on FC33 kernel 5.9.15 blacklisted amdgpu + gpu-switch to stop dGPU flicker but could not switch the dGPU off. One user with `modprobe.blacklist=amdgpu acpi_backlight=intel_backlight` had no vgaswitcheroo entries and ~16 W idle. No complete 14,3 setup confirmed in thread. — [Dunedan issue #6](https://github.com/Dunedan/mbp-2016-linux/issues/6)
- Wayland/mutter fails when both GPUs load; roadrunner2 reported fixing with `MUTTER_ALOW_HYBRID_GPUS=1` in /etc/environment (spelling as in the thread; 2017 GNOME-era, likely stale). — [Dunedan issue #6](https://github.com/Dunedan/mbp-2016-linux/issues/6)
- Powering dGPU off under X causes long hangs because X still touches it. — [Dunedan issue #6](https://github.com/Dunedan/mbp-2016-linux/issues/6)
- Kernel params from old guide: kernels >=4.11 need none on this family; <4.10 `intremap=nosid`; very old live media `nomodeset`. — [roadrunner2 gist](https://gist.github.com/roadrunner2/1289542a748d9a104e7baec6a92f9cd7)
- A 2016 15" commenter reported `nomodeset` gave stability but poor performance; without it solid-colour screen crashes on UI clicks (old kernel era). — [almas gist](https://gist.github.com/almas/5f75adb61bccf604b6572f763ce63e3e)
- 2023: amdgpu change registers a vga_switcheroo client for Apple dual-GPU MacBooks using apple_gmux_detect() (skips Thunderbolt eGPUs); this is context only, T2-focused. — via [Phoronix/search summary](https://www.phoronix.com/news/Linux-2026-Patches-For-2018-MBP)
- Aug 2026 (very recent): patches by Andre Eikmeyer for apple-gmux/amdgpu/HDA power lifecycle on MacBookPro15,1 (2018/19, T2) to save ~12 W of idle dGPU; I could not confirm merge status, and it targets T2 models, not 14,3. — [Phoronix](https://www.phoronix.com/news/Linux-2026-Patches-For-2018-MBP), [borncity](https://borncity.com/news/macbook-pro-2018-2019-linux-spart-12-watt-durch-dGPU-patches/) (title only seen in search)
- t2linux hybrid-graphics guide documents T2 behavior (dGPU primary, disable via systemd service); T2 only, analogous not identical. — [t2linux wiki](https://wiki.t2linux.org/guides/hybrid-graphics/)
- Brightness: gmux backlight works out of the box on 13,3 with recent kernels; kernels <4.14/4.14-4.14.21/4.15-4.15.5 needed a patched apple-gmux. Dunedan lists 13,3 needing the bugzilla 105051#c32 patch (historic). — [roadrunner2 gist](https://gist.github.com/roadrunner2/1289542a748d9a104e7baec6a92f9cd7), [Dunedan README](https://github.com/Dunedan/mbp-2016-linux/blob/master/README.md)

### Inferences
- With a 2026 kernel the gmux/backlight patches are long merged, so expect `gmux_backlight` or `intel_backlight`/`amdgpu_bl` to work; verify with `ls /sys/class/backlight`. (Inference from kernel version dates; not directly sourced for 14,3.)
- Practical fallback ladder: (1) default AMD-primary boot, accept battery/fans; (2) apple_set_os.efi/gpu-switch iGPU boot + `blacklist amdgpu` for battery/resume stability, losing external displays and dGPU; (3) try `OFF` debugfs only if vgaswitcheroo entries exist. No evidence found that dGPU can be hard-powered off cleanly on 14,3.
- Wayland (KDE Plasma 6 / GNOME 4x) status on 14,3 was not found; the hybrid-GPU mutter note is from 2017.

### Gaps
- No 14,3-specific report of PRIME offload / switcheroo-control / DRI_PRIME working on CachyOS.
- No sourced values for `i915.enable_psr`, `amdgpu.dc`, `pcie_aspm`, `acpi_osi=` effects on 14,3 (only the takachin 13" list below).
- HiDPI scaling (2880x1800) not found in sources; no fractional scaling findings.
- Whether Arch Wiki MacBookPro14,x says anything beyond Dunedan: unreadable (Anubis block).

## Suspend/resume, NVMe, Thunderbolt, lid wake

### Takeaway
Suspend works but resume is the weak spot: the Apple NVMe controller and PCIe switch/Thunderbolt fail to change power state, giving minutes-long or failed resumes unless d3cold is disabled; nothing confirmed for 14,3 on current kernels.

### Cited Findings
- Dunedan lists 14,3 suspend & hibernation as "partially working" (resume needs extra steps); Touch ID not working. — [Dunedan README](https://github.com/Dunedan/mbp-2016-linux/blob/master/README.md)
- Dunedan workaround (listed for 13,1/13,2/14,1/14,2 Apple NVMe models, i.e. not named for 14,3): `echo 0 > /sys/bus/pci/devices/0000\:01\:00.0/d3cold_allowed` as root, at every boot (reset to 1); resume still "up to a minute". — [Dunedan README](https://github.com/Dunedan/mbp-2016-linux/blob/master/README.md)
- almas 14,3 install gist: author said suspend did not work on 2017 model, hibernate shut down; commenter on 2016 15" got fix with d3cold_allowed=0 on 0000:01:00.0. Lid-open black-screen hang reported by a 13,2 commenter. — [almas gist](https://gist.github.com/almas/5f75adb61bccf604b6572f763ce63e3e)
- Kernel 6.15.4 on a 2017 13" (not 14,3): black screen/no input after resume, minutes to resume due to "Unable to change power state" for NVMe/Thunderbolt/PCI. Fix set: script setting `d3cold_allowed=0` for all devices under /sys/devices plus 0000:01:00.0, 1c:00.0, 05:00.0, 05:01.0, 05:02.0, 06:00.0 (PCI addresses are machine-specific) run via /lib/systemd/system-sleep hook in `pre`; cmdline `nvme_core.default_ps_max_latency_us=0 nvme.noacpi=1 pci=noaer i915.enable_dc=0 i915.enable_fbc=0 i915.enable_psr=0`; optional `blacklist thunderbolt` in /etc/modprobe.d. Author says Apple-specific PCIe switch is unsupported and delays device recovery; trade-off worse suspend battery drain; result "practically fast and stable". — [takachin note](https://takachin.github.io/mbp2017-linux-note/en/suspend-resume.html)
- NVMe: works out of the box; SSD does not appear to support APST so idle power is higher than necessary. — [Dunedan README](https://github.com/Dunedan/mbp-2016-linux/blob/master/README.md)
- Thunderbolt works out of the box (power-management details truncated). — [Dunedan README](https://github.com/Dunedan/mbp-2016-linux/blob/master/README.md)
- Generic suspend failure mode (other hardware): `mem_sleep_default=deep` helped on a MacBookPro15,1 with Intel forced via gmux and amdgpu blacklisted; success shows `s2idle [deep]` in /sys/power/mem_sleep. T2 model, analogy only. — [t2linux T2-Ubuntu issue 195 mirror](https://gh.r-mj.com/t2linux/T2-Ubuntu/issues/195)

### Inferences
- Start test matrix: d3cold_allowed=0 on the NVMe port + (if freezes) nvme.noacpi=1, nvme_core.default_ps_max_latency_us=0, then test mem_sleep deep vs s2idle with `cat /sys/power/mem_sleep`. Which of s2idle/deep default applies on 14,3 was not found.
- Resume reliability may be better with the Intel GPU primary (Dunedan statement) and with amdgpu not driving the panel.

### Gaps
- No source states default `mem_sleep` mode on 14,3 or whether `mem_sleep_default=deep` helps it.
- No 2025-2026 14,3 resume report; takachin is the newest (kernel 6.15, 13" model).
- Lid wake specifics (LID0/XHC wake via /proc/acpi/wakeup) not found.
- Hibernate on 14,3: only almas "shuts down" claim (old).

## Fans, sensors, power daemons, battery, keyboard/display backlight

### Takeaway
applesmc handles fans/temps/voltages out of the box; mbpfan is the suggested manual tool. Battery charge-limit and CachyOS-specific daemon guidance were not found.

### Cited Findings
- Fans, temperature and voltage sensors work out of the box via applesmc; manual fan speed works; `mbpfan` suggested. Ambient light sensor on Touch Bar models is on the iBridge and needs third-party `apple-ib-als`. — [Dunedan README](https://github.com/Dunedan/mbp-2016-linux/blob/master/README.md)
- Touch Bar (14,3 partially working): Esc and F-keys are on the Touch Bar; commenter config `/etc/modprobe.d/apple_ib_tb.conf` with `options apple_ib_tb fnmode=2` and `idle_timeout=60`; Touch Bar may vanish after reboot, fixed by `GRUB_HIDDEN_TIMEOUT=1` / `GRUB_TIMEOUT_STYLE=menu` giving the driver time to load; camera `options uvcvideo quirks=0x100`; keyboard backlight idle-off done via a brightnessctl script. — [almas gist](https://gist.github.com/almas/5f75adb61bccf604b6572f763ce63e3e), [Dunedan README](https://github.com/Dunedan/mbp-2016-linux/blob/master/README.md)
- dGPU off savings ~5-6 W (see GPU section). — [roadrunner2 gist](https://gist.github.com/roadrunner2/1289542a748d9a104e7baec6a92f9cd7)

### Inferences
- Fan noise on this model is most plausibly driven by the always-on Radeon sharing the heatpipe; the iGPU-only route (gpu-switch + amdgpu blacklist) is the only sourced mitigation.

### Gaps
- No sourced TLP / power-profiles-daemon / thermald / auto-cpufreq settings for Kaby Lake on 14,3, nor CachyOS power-daemon specifics (CachyOS ships power-profiles-daemon by default, from my general knowledge, not verified here).
- No evidence found of SMC battery charge threshold (BCLM/applesmc charge_control) on 14,3.
- No sourced mbpfan.conf values for 14,3.
- No source checked on gmux_backlight vs intel_backlight vs amdgpu_bl selection on current kernels.

## Bootloader, EFI framebuffer, nomodeset, Touch Bar-specific, and Apple SSD quirks

### Takeaway
Boot works with GRUB/rEFInd; Apple-OS-spoofing is needed to light the Intel GPU. nomodeset appears only for ancient kernels. Apple SSD quirks are the d3cold/APST/noacpi ones above.

### Cited Findings
- apple_set_os.efi chainloaded from GRUB or rEFInd spoof_osx_version enables iGPU; kernel patches also exist but not upstream. — [roadrunner2 gist](https://gist.github.com/roadrunner2/1289542a748d9a104e7baec6a92f9cd7), [Dunedan issue #6](https://github.com/Dunedan/mbp-2016-linux/issues/6)
- `nomodeset` only recommended for live media with kernels <4.9. — [roadrunner2 gist](https://gist.github.com/roadrunner2/1289542a748d9a104e7baec6a92f9cd7)
- Dunedan project (maintains Apple 2016-2017 support) is the central reference; Wi-Fi needs brcmfmac43602 nvram txt (per almas). — [almas gist](https://gist.github.com/almas/5f75adb61bccf604b6572f763ce63e3e)

### Inferences
- Systemd-boot (CachyOS default alternative) lacks a spoof hook; GRUB custom.cfg or rEFInd would be needed for gpu-switch.

### Gaps
- No evidence on the exact SSD model (e.g. APPLE SSD AP0512) behaviour beyond the NVMe notes above.
- CachyOS-specific installer/bootloader behaviour on 14,3 not found.
