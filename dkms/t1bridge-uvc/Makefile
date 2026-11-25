# Webcam del T1 in configurazione USB 2 (solo H.264): uvcvideo del kernel di destinazione con le due patch di questa
# cartella, preparato da prepare-src.sh (PRE_BUILD di DKMS) in build/src: uvcvideo-t1-on-linux-7.3.patch (T1Bridge
# v0.1.12: parser H.264, niente autosospensione per il T1) e uvcvideo-t1-h264-big-frames.patch (nostra: buffer da un
# fotogramma intero, la camera ne dichiara 270 KB ma ne manda fino a ~330 KB). src/ è la copia già corretta di Linux 7.3,
# usata senza rete per la serie 7.3. Modulo uvcvideo_t1, bloccato dal caricamento automatico: lo carica solo la
# modalità display.
KVERSION := $(KERNELRELEASE)
ifeq ($(origin KERNELRELEASE), undefined)
KVERSION := $(shell uname -r)
endif
KDIR := /lib/modules/$(KVERSION)/build
ifneq ($(shell grep -s '^CONFIG_CC_IS_CLANG=y' $(KDIR)/.config),)
LLVM_FLAG := LLVM=1
endif

all:
	@[ -f build/src/Kbuild ] || ./prepare-src.sh $(KVERSION)
	$(MAKE) -C $(KDIR) M=$(CURDIR)/build/src $(LLVM_FLAG) modules

clean:
	rm -rf build
