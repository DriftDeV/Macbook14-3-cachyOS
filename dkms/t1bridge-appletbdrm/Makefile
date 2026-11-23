# Driver display della Touch Bar T1 (configurazione USB 2): appletbdrm di Linux 7.1.8 adattato da
# T1Bridge v0.1.12 (commit 81cbdf8, kernel/appletbdrm-t1, GPL-2.0). Stesso nome del modulo del kernel:
# DKMS lo installa in updates/ e lo sostituisce; per i T2 si comporta come quello del kernel.
obj-m := appletbdrm.o

KVERSION := $(KERNELRELEASE)
ifeq ($(origin KERNELRELEASE), undefined)
KVERSION := $(shell uname -r)
endif
KDIR := /lib/modules/$(KVERSION)/build
ifneq ($(shell grep -s '^CONFIG_CC_IS_CLANG=y' $(KDIR)/.config),)
LLVM_FLAG := LLVM=1
endif

all:
	$(MAKE) -C $(KDIR) M=$(CURDIR) $(LLVM_FLAG) modules

clean:
	$(MAKE) -C $(KDIR) M=$(CURDIR) $(LLVM_FLAG) clean
