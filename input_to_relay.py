#!/usr/bin/env python3
"""
Input-to-Relay Trigger Script
IN1 → Relay 1, IN2 → Relay 2, IN3 → Relay 3, IN4 → Relay 4

Inputs are active LOW (connect to GND to trigger)

Optimized timings: ~80ms round-trip response
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
    msg = bytes([device_id, function]) + address.to_bytes(2, 'big') + value.to_bytes(2, 'big')
    return msg + calc_crc16(msg)

class RelayBoard:
    def __init__(self, port=PORT):
        self.ser = serial.Serial(port, BAUDRATE, timeout=SERIAL_TIMEOUT)
        self.device_id = DEVICE_ID
        time.sleep(0.1)

    def close(self):
        self.ser.close()

    def read_inputs(self):
        """Read input states (active LOW: 0=triggered)"""
        req = build_request(self.device_id, 0x02, 0x0000, 0x0008)
        self.ser.reset_input_buffer()
        self.ser.write(req)
        self.ser.flush()
        time.sleep(TX_WAIT)
        resp = self.ser.read(20)
        if resp and len(resp) >= 4 and resp[1] == 0x02:
            raw = resp[3]
            # Return True if triggered (active LOW inverted)
            return [
                not bool(raw & 0x01),  # IN1
                not bool(raw & 0x02),  # IN2
                not bool(raw & 0x04),  # IN3
                not bool(raw & 0x08),  # IN4
            ]
        return [False, False, False, False]

    def read_relays(self):
        """Read relay states"""
        req = build_request(self.device_id, 0x01, 0x0000, 0x0008)
        self.ser.reset_input_buffer()
        self.ser.write(req)
        self.ser.flush()
        time.sleep(TX_WAIT)
        resp = self.ser.read(20)
        if resp and len(resp) >= 4 and resp[1] == 0x01:
            raw = resp[3]
            return [
                bool(raw & 0x01),  # R1
                bool(raw & 0x02),  # R2
                bool(raw & 0x04),  # R3
                bool(raw & 0x08),  # R4
            ]
        return [False, False, False, False]

    def set_relay(self, relay_num, state):
        """Set relay (0-3) on/off"""
        val = 0xFF00 if state else 0x0000
        req = build_request(self.device_id, 0x05, relay_num, val)
        self.ser.reset_input_buffer()
        self.ser.write(req)
        self.ser.flush()
        time.sleep(TX_WAIT)
        self.ser.read(20)


def main():
    board = RelayBoard()

    print("=" * 50)
    print("INPUT → RELAY TRIGGER")
    print("=" * 50)
    print()
    print("  IN1 → Relay 1")
    print("  IN2 → Relay 2")
    print("  IN3 → Relay 3")
    print("  IN4 → Relay 4")
    print()
    print("Connect input to GND to trigger its relay")
    print("Press Ctrl+C to stop")
    print()
    print("IN:  1 2 3 4  |  Relay: 1 2 3 4")
    print("-" * 50)

    # Track previous states to only update on change
    prev_inputs = [None, None, None, None]

    try:
        while True:
            inputs = board.read_inputs()

            # Check each input and update relay if changed
            for i in range(4):
                if inputs[i] != prev_inputs[i]:
                    board.set_relay(i, inputs[i])
                    prev_inputs[i] = inputs[i]

            # Display status
            in_str = ' '.join(['■' if x else '□' for x in inputs])
            relay_str = ' '.join(['■' if x else '□' for x in board.read_relays()])
            print(f"\r     {in_str}  |        {relay_str}  ", end='', flush=True)

            time.sleep(0.01)  # Fast polling

    except KeyboardInterrupt:
        print("\n\nStopping... turning off all relays")
        for i in range(4):
            board.set_relay(i, False)

    board.close()
    print("Done.")


if __name__ == '__main__':
    main()
