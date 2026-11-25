#!/usr/bin/env bash
# PRE_BUILD di DKMS: prepara build/src per il kernel <kernelver> con i sorgenti uvcvideo DI QUEL KERNEL (kernel-src.sh,
# da kernel.org, con cache) più le due patch: uvcvideo-t1-on-linux-7.3.patch (T1Bridge: parser H.264, niente
# autosospensione per il T1) e uvcvideo-t1-h264-big-frames.patch (nostra: buffer da un fotogramma intero).
# Se le patch non si applicano o i sorgenti non si trovano: per la serie 7.3 usa la copia già corretta in src/,
# altrimenti si ferma (DKMS segnala l'errore; la modalità display resta senza webcam, il resto non cambia).
set -eu
kver="${1:?uso: prepare-src.sh <kernelver>}"
cd "$(dirname "$0")"
rm -rf build
mkdir -p build/src

from=""
if tag="$(./kernel-src.sh "$kver" drivers/media/usb/uvc build/src)"; then
    if (cd build/src && patch -s -p1 -F2 --no-backup-if-mismatch < ../../uvcvideo-t1-on-linux-7.3.patch \
            && patch -s -p1 -F3 --no-backup-if-mismatch < ../../uvcvideo-t1-h264-big-frames.patch); then
        from="Linux $tag + patch T1"
    else
        echo "prepare-src: le patch non si applicano ai sorgenti uvcvideo di $tag" >&2
    fi
fi
if [ -z "$from" ]; then
    case "$kver" in
        7.3.*) rm -rf build/src; mkdir -p build/src; cp src/* build/src/; from="copia inclusa (Linux 7.3 già corretta)" ;;
        *) echo "prepare-src: nessun sorgente uvcvideo utilizzabile per $kver" >&2; exit 1 ;;
    esac
fi

# Kbuild del modulo, dal Makefile di uvcvideo (o dal suo contenuto in 7.3 se manca): stesso elenco di oggetti, nome
# uvcvideo_t1 (non sostituisce uvcvideo del kernel; lo carica solo la modalità display) e in più uvc_h264.o.
# shellcheck disable=SC1003,SC2016  # righe di Makefile letterali
if [ -s build/src/Makefile ] && grep -q 'uvcvideo-objs' build/src/Makefile; then
    sed -e 's/uvcvideo-objs/uvcvideo_t1-objs/g' -e '/^obj-/d' build/src/Makefile > build/src/Kbuild
else
    printf '%s\n' 'uvcvideo_t1-objs := uvc_driver.o uvc_queue.o uvc_v4l2.o uvc_video.o uvc_ctrl.o uvc_status.o \' \
        '        uvc_isight.o uvc_debugfs.o uvc_metadata.o' 'ifeq ($(CONFIG_MEDIA_CONTROLLER),y)' \
        'uvcvideo_t1-objs += uvc_entity.o' 'endif' > build/src/Kbuild
fi
printf '%s\n' 'uvcvideo_t1-objs += uvc_h264.o' 'obj-m := uvcvideo_t1.o' >> build/src/Kbuild
rm -f build/src/Makefile build/src/Kconfig
echo "prepare-src: build/src pronto per $kver ($from)"
