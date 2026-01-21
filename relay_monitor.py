#!/usr/bin/env python3
"""
485 Relay 4CH v1.1 - Monitor and Control Script
Board settings: 9600 baud, 8N1, Device ID 1

Optimized timings (benchmarked):
- Serial timeout: 25ms
- Post-TX wait: 8ms
- Round-trip time: ~80ms
"""

import serial
import time
import sys

PORT = '/dev/ttyUSB0'
BAUDRATE = 9600
DEVICE_ID = 1
SERIAL_TIMEOUT = 0.025  # 25ms - optimized
TX_WAIT = 0.008         # 8ms post-TX wait - optimized

def calc_crc16(data):
    """Calculate Modbus CRC16"""
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x0001:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return crc.to_bytes(2, 'little')

def build_request(device_id, function, address, value):
    """Build Modbus RTU request frame"""
    msg = bytes([device_id, function]) + address.to_bytes(2, 'big') + value.to_bytes(2, 'big')
    return msg + calc_crc16(msg)

class RelayBoard:
    def __init__(self, port=PORT, baudrate=BAUDRATE, device_id=DEVICE_ID):
        self.ser = serial.Serial(port, baudrate, timeout=SERIAL_TIMEOUT)
        self.device_id = device_id
        time.sleep(0.1)

    def close(self):
        self.ser.close()

    def read_status(self):
        """Read relay status using Function 01 (Read Coils) - must request 8 bits"""
        req = build_request(self.device_id, 0x01, 0x0000, 0x0008)
        self.ser.reset_input_buffer()
        self.ser.write(req)
        self.ser.flush()
        time.sleep(TX_WAIT)
        resp = self.ser.read(20)
        if resp and len(resp) >= 4 and resp[1] == 0x01:
            return resp[3]
        return None

    def set_relay(self, relay_num, state):
        """Set relay state (relay_num: 1-4, state: True=ON, False=OFF)"""
        if relay_num < 1 or relay_num > 4:
            raise ValueError("relay_num must be 1-4")
        addr = relay_num - 1
        val = 0xFF00 if state else 0x0000
        req = build_request(self.device_id, 0x05, addr, val)
        self.ser.reset_input_buffer()
        self.ser.write(req)
        self.ser.flush()
        time.sleep(TX_WAIT)
        return self.ser.read(20)

    def relay_on(self, relay_num):
        """Turn relay ON"""
        return self.set_relay(relay_num, True)

    def relay_off(self, relay_num):
        """Turn relay OFF"""
        return self.set_relay(relay_num, False)

    def all_off(self):
        """Turn all relays OFF"""
        for i in range(1, 5):
            self.relay_off(i)

    def all_on(self):
        """Turn all relays ON"""
        for i in range(1, 5):
            self.relay_on(i)

    def get_relays(self):
        """Get relay states as dict"""
        status = self.read_status()
        if status is None:
            return None
        return {
            'R1': bool(status & 0x01),
            'R2': bool(status & 0x02),
            'R3': bool(status & 0x04),
            'R4': bool(status & 0x08),
        }

    def get_inputs(self):
        """Get input states using Function 02 (Discrete Inputs) at address 0x0000
        IMPORTANT: Must request 8 bits - board doesn't respond to 4-bit requests!
        Inputs are ACTIVE LOW: 0 = triggered (connected to GND), 1 = not triggered
        """
        req = build_request(self.device_id, 0x02, 0x0000, 0x0008)  # Must be 8!
        self.ser.reset_input_buffer()
        self.ser.write(req)
        self.ser.flush()
        time.sleep(TX_WAIT)
        resp = self.ser.read(20)
        if resp and len(resp) >= 4 and resp[1] == 0x02:
            status = resp[3]
            # Invert logic so True = triggered (active)
            return {
                'IN1': not bool(status & 0x01),  # bit 0
                'IN2': not bool(status & 0x02),  # bit 1
                'IN3': not bool(status & 0x04),  # bit 2
                'IN4': not bool(status & 0x08),  # bit 3
            }
        return None

    def read_inputs_raw(self):
        """Read raw input byte (for debugging)"""
        req = build_request(self.device_id, 0x02, 0x0000, 0x0008)  # Must be 8!
        self.ser.reset_input_buffer()
        self.ser.write(req)
        self.ser.flush()
        time.sleep(TX_WAIT)
        resp = self.ser.read(20)
        if resp and len(resp) >= 4 and resp[1] == 0x02:
            return resp[3]
        return None


def monitor_mode():
    """Continuous monitoring of relays and inputs"""
    board = RelayBoard()

    print("=" * 60)
    print("485 RELAY 4CH - REAL-TIME MONITOR")
    print("=" * 60)
    print()
    print("INPUTS ARE ACTIVE LOW:")
    print("  - Connect input to GND = TRIGGERED (shows 1)")
    print("  - Input floating/open = NOT triggered (shows 0)")
    print()
    print("Press Ctrl+C to stop")
    print()
    print("Relays (F01)  | Inputs (F02)")
    print("R4 R3 R2 R1   | IN4 IN3 IN2 IN1")
    print("-" * 60)

    last_relay = None
    last_input = None
    try:
        while True:
            relay_status = board.read_status()
            input_raw = board.read_inputs_raw()

            if relay_status != last_relay or input_raw != last_input:
                if relay_status is not None:
                    r1 = relay_status & 0x01
                    r2 = (relay_status >> 1) & 0x01
                    r3 = (relay_status >> 2) & 0x01
                    r4 = (relay_status >> 3) & 0x01
                else:
                    r1 = r2 = r3 = r4 = '?'

                if input_raw is not None:
                    # Invert for display (0=triggered shows as 1)
                    i1 = 1 if not (input_raw & 0x01) else 0
                    i2 = 1 if not (input_raw & 0x02) else 0
                    i3 = 1 if not (input_raw & 0x04) else 0
                    i4 = 1 if not (input_raw & 0x08) else 0
                else:
                    i1 = i2 = i3 = i4 = '?'

                marker = " ← CHANGE!" if last_relay is not None else ""
                print(f" {r4}  {r3}  {r2}  {r1}    |  {i4}   {i3}   {i2}   {i1}  {marker}")
                last_relay = relay_status
                last_input = input_raw
            time.sleep(0.01)  # Fast polling
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        board.close()


def test_relays():
    """Test each relay"""
    board = RelayBoard()

    print("Testing relays...")
    board.all_off()
    time.sleep(0.1)

    for i in range(1, 5):
        print(f"  Relay {i} ON...")
        board.relay_on(i)
        time.sleep(0.2)
        board.relay_off(i)
        time.sleep(0.1)

    print("Done!")
    board.close()


def interactive_mode():
    """Interactive command mode"""
    board = RelayBoard()

    print("=" * 60)
    print("485 RELAY 4CH - INTERACTIVE MODE")
    print("=" * 60)
    print()
    print("Commands:")
    print("  1-4      : Toggle relay 1-4")
    print("  on N     : Turn relay N on")
    print("  off N    : Turn relay N off")
    print("  all on   : All relays on")
    print("  all off  : All relays off")
    print("  status   : Read current status")
    print("  monitor  : Start continuous monitoring")
    print("  quit     : Exit")
    print()

    try:
        while True:
            cmd = input("> ").strip().lower()

            if cmd in ['q', 'quit', 'exit']:
                break
            elif cmd == 'status':
                status = board.read_status()
                if status:
                    print(f"  Status: 0x{status:02X} = {status:08b}")
                    print(f"  Relays: {board.get_relays()}")
                    print(f"  Inputs: {board.get_inputs()}")
            elif cmd in ['1', '2', '3', '4']:
                n = int(cmd)
                relays = board.get_relays()
                if relays[f'R{n}']:
                    board.relay_off(n)
                    print(f"  Relay {n} OFF")
                else:
                    board.relay_on(n)
                    print(f"  Relay {n} ON")
            elif cmd.startswith('on '):
                n = int(cmd.split()[1])
                board.relay_on(n)
                print(f"  Relay {n} ON")
            elif cmd.startswith('off '):
                n = int(cmd.split()[1])
                board.relay_off(n)
                print(f"  Relay {n} OFF")
            elif cmd == 'all on':
                board.all_on()
                print("  All relays ON")
            elif cmd == 'all off':
                board.all_off()
                print("  All relays OFF")
            elif cmd == 'monitor':
                board.close()
                monitor_mode()
                board = RelayBoard()
            else:
                print("  Unknown command. Type 'quit' to exit.")
    except KeyboardInterrupt:
        print()
    finally:
        board.close()


if __name__ == '__main__':
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == 'monitor':
            monitor_mode()
        elif cmd == 'test':
            test_relays()
        elif cmd == 'interactive':
            interactive_mode()
        else:
            print(f"Unknown command: {cmd}")
            print("Usage: python relay_monitor.py [monitor|test|interactive]")
    else:
        interactive_mode()
