# Webcam del T1 in configurazione USB 2 (solo H.264): uvcvideo di Linux 7.3 con le due patch di
# T1Bridge v0.1.12 (kernel/uvcvideo-t1/upstream: parser H.264, niente autosospensione per il T1).
# Differenze rispetto a Linux 7.3: uvcvideo-t1-on-linux-7.3.patch, più uvcvideo-t1-h264-big-frames.patch
# (nostra: buffer da un fotogramma intero, la camera ne dichiara 270 KB ma ne manda fino a ~330 KB). Modulo con nome diverso
# (uvcvideo_t1), bloccato dal caricamento automatico: lo carica solo la modalità display.
obj-m := uvcvideo_t1.o
uvcvideo_t1-objs := src/uvc_driver.o src/uvc_h264.o src/uvc_queue.o src/uvc_v4l2.o src/uvc_video.o \
	src/uvc_ctrl.o src/uvc_status.o src/uvc_isight.o src/uvc_debugfs.o src/uvc_metadata.o
ifeq ($(CONFIG_MEDIA_CONTROLLER),y)
uvcvideo_t1-objs += src/uvc_entity.o
endif

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
