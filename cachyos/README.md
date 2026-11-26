# CachyOS (KDE Plasma) sul MacBookPro14,3

Parti della repo che servono **solo su CachyOS / KDE**. La procedura completa è nel
[README principale](../README.md#installare-cachyos); tutto il resto è comune e lo installa `install.sh`.

| File | A cosa serve |
|---|---|
| [`macos/prepare.sh`](macos/prepare.sh) | da macOS, senza chiavetta: ridimensiona APFS, crea la partizione `COSLIVE` con la live di CachyOS e una partizione per Linux. Senza `--execute` mostra solo il piano. **Non vale per Omarchy**, il cui installatore esclude il disco della live |
| [`kde/90-macbookpro14-3-no-mangohud.conf`](kde/90-macbookpro14-3-no-mangohud.conf) | drop-in di `plasma-kwin_wayland`: MangoHud (limite FPS a batteria) fuori da KWin, che lo faceva crollare. Installato dal passo `power` solo su KDE |
