# Adattatore CDC-NCM della rete privata del T1 (Touch ID): T1Bridge v0.1.12 (commit 81cbdf8,
# kernel/apple-t1-ncm, Dual MIT/GPL), sorgente invariato. Si aggancia solo a 05ac:8600 interfaccia 4,
# che esiste solo nella configurazione USB 2 (modalità display della Touch Bar).
obj-m := apple_t1_ncm.o

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
