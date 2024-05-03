# This file is part of the libsigrokdecode project.
#
# Copyright (C) 2012 Bert Vermeulen <bert@biot.com>
# Copyright (C) 2012 Uwe Hermann <uwe@hermann-uwe.de>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, see <http://www.gnu.org/licenses/>.

# ============================================================================
# OUTPUT_PYTHON format from I2C decoder:
# Packet:
# [<ptype>, <pdata>]

# <ptype>:
#  - 'START' (START condition)
#  - 'START REPEAT' (Repeated START condition)
#  - 'ADDRESS READ' (Slave address, read)
#  - 'ADDRESS WRITE' (Slave address, write)
#  - 'DATA READ' (Data, read)
#  - 'DATA WRITE' (Data, write)
#  - 'STOP' (STOP condition)
#  - 'ACK' (ACK bit)
#  - 'NACK' (NACK bit)
#  - 'BITS' (<pdata>: list of data/address bits and their ss/es numbers)

# <pdata> is the data or address byte associated with the 'ADDRESS*' and 'DATA*'
# command. Slave addresses do not include bit 0 (the READ/WRITE indication bit).
# For example, a slave address field could be 0x51 (instead of 0xa2).
# For 'START', 'START REPEAT', 'STOP', 'ACK', and 'NACK' <pdata> is None.
# For 'BITS' <pdata> is a sequence of tuples of bit values and their start and
# stop positions, in LSB first order (although the I2C protocol is MSB first).
# ============================================================================

# ============================================================================
# I2C Notes
# Trigger on a high to low transition of the clock line.
# Ack/Nack: The I2C protocol specifies that every byte sent must be acknowledged by the receiver. This is implemented with a single bit: 0 for ACK and 1 for NACK. At the end of every byte, the transmitter releases the SDA line, and on the next clock cycle the receiver must pull the line low to acklowledged the byte
#   1. A NACK after an address is sent means no slave responded to that address
#   2. A NACK after write data means the slave either did not recognize the command, or that it cannot accept any more data
#   3. A NACK during read data means the master does not want the slave to send any more bytes.
#   Note: A NACK is not necessarily an error condition, it sometimes can be used to end a read.
# START/STOP: Every I2C command starts with a START condition and ends with a STOP condition.
#   To send a START, an I2C master must pull the SDA line low while the SCL line is high. After a START condition, the I2C master must pull the SCL line low and start the clock.
#   To send a STOP, an I2C master releases the SDA line to high while the SCL line is high.
# RESTART: A Repeated Start or Restart condition is identical to a Start condition. A master device can issue a Restart condition instead of a Stop condition if it intends to hold the bus after completing the current data transfer. A Restart condition has the same effect on the slave as a Start condition would, resetting all slave logic and preparing it to receive an address. The Restart condition is always initiated by the master.
# I2C addresses are 7 bits, a few addresses are reserved and the rest are allocated by the I2C-bus committee.
#   An I2C master simply needs to write its 7-bit address on the bus after the START condition.
#   Read or write to slave devices is indicated with a single bit transmitted after the address bits. A 1 means the command is a read, and a 0 means it is a write.
# ============================================================================

import copy
from typing import Optional, List
import sigrokdecode as srd
#  ================ For debugging ===============
import sys
import os
sys.path.insert(0, "/home/scirelli/Projects/C1/sigrokdecoder_i2c_PCA9534/.venv/lib/python3.12/site-packages")
sys.path.insert(0, "/home/scirelli/Projects/C1/sigrokdecoder_i2c_PCA9534/.venv/bin")
#  ==============================================


I2C_BUS = 2
I2C_BUS_ADDR = 0x20  # Default address of the PCA9534 chip
INPUT_REG = 0x00
OUTPUT_REG = 0x01
POLARITY_REG = 0x02
CONFIG_REG = 0x03


def printErr(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


registers = {
    INPUT_REG: "Input",
    OUTPUT_REG: "Output",
    POLARITY_REG: "Polarity",
    CONFIG_REG: "Config",
    I2C_BUS_ADDR: "PCA9534",
}

START = "START"
RESTART = "START REPEAT"
STOP = "STOP"
ACK = "ACK"
NACK = "NACK"
BIT = "BIT"
ADDR_READ = "ADDRESS READ"
ADDR_WRITE = "ADDRESS WRITE"
DATA_READ = "DATA READ"
DATA_WRITE = "DATA WRITE"
WARN = "WARN"


# Notes:
# Allow BITs messages to pass through.
#
#
class Decoder(srd.Decoder):
    api_version = 3
    id = "pca9534"
    name = "PCA9534"
    longname = "I²C PCA9534 device decoder"
    desc = "Requires to be stacked on top of I²C filter decoder and filtered by the PCA9534 address. This will then decode the I²C PCA9534 messages."
    license = "gplv3+"
    inputs = ["i2c"]
    outputs = ["i2c"]
    tags = ["Util"]
    _parsable_commands = (START, ADDR_WRITE, ADDR_READ, ACK, NACK, DATA_WRITE, DATA_READ, STOP)
    _end_states = (STOP, RESTART)

    options = (
        {'id': 'address', 'desc': 'Slave (PCA9534) address (decimal)', 'default': 0x20},
    )

    annotations = (
        # (class/id, description)
        # ("device-read", "Address read"),  # 0
        # ("device-write", "Address write"),  # 1
        # ("data-read", "Data read"),  # 2
        # ("data-write", "Data write"),  # 3
        ("message", "Message"),  # 0
    )
    annotation_rows = (
        # id, name/description, tuple of indices
        ("pca9543-message", "Messages", (0, )),  # 0
    )

    def __init__(self):
        #  ================ For debugging ===============
        # import rpdb2
        # rpdb2.start_embedded_debugger("steve", fAllowRemote=True, timeout=50000000)
        #  ==============================================
        self._device_addr = 0x20
        self.out_python: srd.OutputType
        self.out_ann: srd.OutputType
        self._seen_packets = []
        self._state = _state_machine
        self._reg_to_read = None
        self.reset()

    def reset(self):
        self._state = _state_machine
        self._seen_packets.clear()

    def start(self):
        self.out_python = self.register(srd.OUTPUT_PYTHON, proto_id="i2c")  # Used to pass data to the next decoder
        self.out_ann = self.register(srd.OUTPUT_ANN, proto_id="i2c")  # Used to display text in PulseView

        if 0 <= int(self.options['address']) <= 127:
            raise Exception('Invalid slave (must be 0..127).')

        if self.options['address']:
            self._device_addr = int(self.options['address'])

    # Accumulate observed I2C packets until a STOP or REPEATED START
    # condition is seen. These are conditions where transfers end or
    # where direction potentially changes. Forward all previously
    # accumulated traffic if it passes the slave address and direction
    # filter. This assumes that the slave address as well as the read
    # or write direction was part of the observed traffic. There should
    # be no surprise when incomplete traffic does not match the filter
    # condition.
    def decode(self, start_sample, end_sample, data):
        print(f"█████████████████████████████████\n\tStart Idx:{start_sample}\n\tEnd Idx: {end_sample}\n\tData: {data}\n")
        # Unconditionally accumulate every lower layer packet we see.
        # Keep deep copies for later, only reference caller's values
        # as long as this .decode() invocation executes.
        self._seen_packets.append([start_sample, end_sample, copy.deepcopy(data)])

        cmd, _ = data

        if cmd not in self._parsable_commands:
            print(f"Not a parsable command {cmd}")
            return

        self._state = self._state.get(cmd, self._state)
        print(f"State: {cmd}: {self._state}")
        if callable(getattr(self, self._state.get("func", ""), False)):
            self.put_gui(
                self._seen_packets[0][0],
                self._seen_packets[-1][0],
                0,
                getattr(self, self._state["func"])(list(filter(lambda x: x[2][0] in self._parsable_commands, self._seen_packets)))
            )

        if cmd in self._end_states:
            self._forward_seen_packets()
            self.reset()

    def msg_write_to_register(self, packets) -> List[str]:
        """
        Write to X register value V
          0          1          2         3          4         5          6       7
        START -> ADDR_WRITE -> ACK -> DATA_WRITE -> ACK -> DATA_WRITE -> ACK -> STOP
        """
        print("msg_write_to_register", packets)
        wr_add = hex(packets[1][2][1])
        register = registers.get(packets[3][2][1], 'Unknown')
        data = f"0b{packets[5][2][1]:08b}"

        if register == registers[CONFIG_REG]:
            return [f"PCA9534({wr_add}): {register} pins to {data}", f"{wr_add} {register} pins to {data}", "W"]

        return [f"PCA9534({wr_add}): {register} pins pull up/down set to {data}", f"{wr_add} {register} pins pull up/down {data}", "W"]

    def msg_set_register_as_read_from(self, packets) -> List[str]:
        """
        Set X register as register to read from.
        START -> ADDR_WRITE -> ACK -> DATA_WRITE -> ACK -> STOP
        """
        print("msg_set_register_as_read_from", packets)
        wr_add = hex(packets[1][2][1])
        register = registers.get(packets[3][2][1], 'Unknown')
        self._reg_to_read = register
        return [f"PCA9534({wr_add}): {register} register set to read from", f"{wr_add} {register} set to read", "R"]

    def msg_read_from_register(self, packets) -> List[str]:
        """
        Read from X register
        START -> ADDR_READ -> ACK -> DATA_READ -> ACK -> STOP
        """
        print("msg_read_from_register", packets)
        wr_add = hex(packets[1][2][1])
        data = hex(packets[3][2][1])
        register = self._reg_to_read
        self._reg_to_read = None
        return [f"PCA9534({wr_add}): Read data {data} from {register} register", f"{wr_add} data {data} {register}", "D"]

    def msg_noop(self, packets) -> str:
        print("msg_noop", packets)
        return ["msg_noop", "noop", "n"]

    def put_gui(self, ss, es, annotation_class_idx, text_list):
        self.put(ss, es, self.out_ann, [annotation_class_idx, text_list])

    def put_python(self, ss, es, data):
        self.put(ss, es, self.out_python, data)

    def _forward_seen_packets(self):
        for ss, es, data in self._seen_packets:
            self.put_python(ss, es, data)


# Quick and dirty state table.
_state_machine = {
    START: {
        ADDR_WRITE: {
            ACK: {
                DATA_WRITE: {
                    ACK: {
                        DATA_WRITE: {
                            ACK: {
                                STOP: {
                                    # Write to X register value V
                                    "func": "msg_write_to_register"
                                },
                            },
                            NACK: {
                                STOP: {
                                    # Write to X register value V
                                    "func": "msg_write_to_register"
                                },
                            },
                        },
                        STOP: {
                            # Set X register as register to read from.
                            "func": "msg_set_register_as_read_from"
                        }
                    },
                    NACK: {},
                },
                DATA_READ: {},
            },
            NACK: {},
        },
        ADDR_READ: {
            ACK: {
                DATA_READ: {
                    ACK: {
                        STOP: {
                            # Read from X register
                            "func": "msg_read_from_register"
                        },
                    },
                    NACK: {
                        STOP: {
                            # Read from X register
                            "func": "msg_read_from_register"
                        },
                    },
                }
            }
        }
    }
}

_state_machine[START][ADDR_WRITE][ACK][DATA_WRITE][ACK][DATA_WRITE][ACK][RESTART] = _state_machine[START][ADDR_WRITE][ACK][DATA_WRITE][ACK][DATA_WRITE][ACK][STOP]
_state_machine[START][ADDR_WRITE][ACK][DATA_WRITE][ACK][RESTART] = _state_machine[START][ADDR_WRITE][ACK][DATA_WRITE][ACK][STOP]
_state_machine[START][ADDR_WRITE][NACK] = _state_machine[START][ADDR_WRITE][ACK]
_state_machine[START][ADDR_READ][ACK][DATA_READ][ACK][RESTART] = _state_machine[START][ADDR_READ][ACK][DATA_READ][ACK][STOP]
_state_machine[STOP] = {
    # NOOP
    "func": "msg_noop"
}
_state_machine[RESTART] = _state_machine[STOP]
