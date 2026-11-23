#!/usr/bin/env python3
"""Instrada l'audio SCO (profilo headset HSP/HFP) del Bluetooth Broadcom via HCI.

Sul MacBookPro14,3 il Bluetooth è un Broadcom su UART (ACPI BCM2E7C, hci_uart + btbcm).
Di default il chip manda l'audio SCO alla sua interfaccia PCM hardware invece che all'host:
il profilo headset si apre ma resta muto. Il comando del produttore Write_SCO_PCM_Int_Param
(OGF 0x3F, OCF 0x001C) con routing = 1 (transport/HCI) lo porta all'host, dove lo usa PipeWire.
Parametri: routing=0x01, pcm rate=0x02, frame=0x00, sync=0x01, clock=0x01 (ricetta usata per i
chip Broadcom dei Raspberry Pi). Si perde a ogni reset del controller (riavvio, Bluetooth spento).

Uso (root): bt-sco-route.py [hciN]   — default hci0
"""
import socket
import struct
import sys

SOL_HCI, HCI_FILTER = 0, 2
HCI_COMMAND_PKT, HCI_EVENT_PKT = 0x01, 0x04
EVT_CMD_COMPLETE, EVT_CMD_STATUS = 0x0E, 0x0F
OPCODE = (0x3F << 10) | 0x001C
PARAMS = bytes([0x01, 0x02, 0x00, 0x01, 0x01])


def main():
    dev = sys.argv[1] if len(sys.argv) > 1 else 'hci0'
    idx = int(dev.removeprefix('hci'))
    s = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_RAW, socket.BTPROTO_HCI)
    s.bind((idx,))
    events = (1 << EVT_CMD_COMPLETE) | (1 << EVT_CMD_STATUS)
    s.setsockopt(SOL_HCI, HCI_FILTER, struct.pack('<IIIHxx', 1 << HCI_EVENT_PKT, events, 0, 0))  # 16 byte: struct hci_ufilter con padding
    s.settimeout(3)
    s.send(struct.pack('<BHB', HCI_COMMAND_PKT, OPCODE, len(PARAMS)) + PARAMS)
    while True:
        pkt = s.recv(260)
        if pkt[0] == HCI_EVENT_PKT and pkt[1] == EVT_CMD_COMPLETE:
            _, op, status = struct.unpack('<BHB', pkt[3:7])
            if op == OPCODE:
                print(f'{dev}: SCO via HCI, stato {status:#04x}', 'OK' if status == 0 else 'ERRORE')
                sys.exit(0 if status == 0 else 1)
        elif pkt[0] == HCI_EVENT_PKT and pkt[1] == EVT_CMD_STATUS:
            status, _, op = struct.unpack('<BBH', pkt[3:7])
            if op == OPCODE and status != 0:
                print(f'{dev}: comando rifiutato, stato {status:#04x}')
                sys.exit(1)


if __name__ == '__main__':
    main()
