# MIT License
#
# Copyright (c) 2024 R. Dunbar Poor <rdpoor # gmail.com>
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import hid
import struct
import sys
from crc16 import Crc16

class HexFileParser:

    def __init__(self, filename):
        self.filename = filename
        self.emitter = None
        self.xaddr = 0
        self.start_addr = None
        self.end_addr = None
        self.eof_seen = False

    def parse_hex_file(self, emitter=None):
        """
        Parse a .hex file.  If emitter is given, call emitter(addr, byte) for
        each byte processed.  Return (start_addr, end_addr) found in the .hex
        file.
        """
        self.emitter = emitter
        with open(self.filename, 'r') as f:
            for line in f:
                self.process_line(line)
        return (self.start_addr, self.end_addr)

    def process_line(self, line):
        line = line.strip()
        if len(line) == 0 or line[0] == '#':
            return
        elif line[0] != ':':
            raise ValueError(f'hexfile line must start with ":"')

        addr, record_type, data, chx = self.unpack_line(line)
        if self.verify_line_checksum(addr, record_type, data, chx) == False:
            raise ValueError(f'Incorrect checksum in line {line}')

        addr = self.compute_xaddr(addr)
        if record_type == 0x00:
            self.parse_data(addr, record_type, data)
        elif record_type == 0x01:
            self.parse_end_of_file(addr, record_type, data)
        elif record_type == 0x02:
            self.parse_extended_segment_address(addr, record_type, data)
        elif record_type == 0x03:
            self.parse_start_segment_address(addr, record_type, data)
        elif record_type == 0x04:
            self.parse_extended_linear_address(addr, record_type, data)
        elif record_type == 0x05:
            self.parse_start_linear_address(addr, record_type, data)
        else:
            raise ValueError(f'Unrecognzied record type {record_type}')

    def verify_line_checksum(self, addr, record_type, data, expected_chx):
        computed_chx = len(data)
        computed_chx += (addr >> 8) + (addr & 0xff)
        computed_chx += record_type
        computed_chx += sum(data)
        return (computed_chx + expected_chx) & 0xff == 0

    # idx = 01234567890123456
    # str = :0300300002337A1E
    #         b   a  r    d c
    # b = line[1:3]          (byte count)
    # a = line[3:7]          (address)
    # r = line[7:9]          (record type)
    # d = line[9:9+2*b]      (data)
    # c = line[9+2*b:11+2*b] (checksum)
    def unpack_line(self, line):
        if len(line) < 11:
            # not enough chars
            raise ValueError(f'hexfile line too short: "{line}"')
        byte_count = int(line[1:3], 16)
        addr = int(line[3:7], 16)
        record_type = int(line[7:9], 16)
        data = bytearray(byte_count);
        for i in range(byte_count):
            data[i] = int(line[9+i*2:11+i*2], 16)
        checksum = int(line[9+byte_count*2:11+byte_count*2], 16)
        return (addr, record_type, data, checksum)

    def parse_data(self, addr, record_type, data):
        if self.eof_seen:
            raise ValueError(f'data record seen after EOF: {data}')

        # capture starting address
        if self.start_addr == None:
            self.start_addr = addr

        for i, b in enumerate(data):
            if self.emitter is not None:
                self.emitter(addr+i, b)
        # end address is one byte past last byte read
        self.end_addr = addr + len(data)

    def parse_end_of_file(self, addr, record_type, data):
        self.eof_seen = True

    def parse_extended_segment_address(self, addr, record_type, data):
        # not implemented
        pass

    def parse_start_segment_address(self, addr, record_type, data):
        # not implemented
        pass

    def parse_extended_linear_address(self, addr, record_type, data):
        if len(data) != 2:
            raise ValueError(f'Extended linear address mut be two bytes')
        self.xaddr = data[0] << 16 + data[1] << 24

    def parse_start_linear_address(self, addr, record_type, data):
        # not implemented
        pass

    def compute_xaddr(self, addr):
        return addr + self.xaddr


class CrcComplete(Exception):
    """Exception used to terminate CRC calculation early"""
    pass

class HexFileCrc:

    def __init__(self, filename, verbose = False):
        """
        Compute the CRC of the given hex file.  If start_addr or end_addr is
        None, derive them from hexfile.  If the hexfile ends before end_addr,
        pad the hex data with 0xff values upto end_addr.
        """
        self.filename = filename
        self.verbose = verbose

    def vprint(self, *args):
        if self.verbose:
            print(*args, flush=True)

    def compute_crc(self, start_addr = None, end_addr = None):
        self.start_addr = start_addr
        self.end_addr = end_addr
        self.crc = 0
        self.addr = None

        if self.start_addr is None or self.end_addr is None:
            # make one pass over the hex file to discover start and end
            (s, e) = HexFileParser(self.filename).parse_hex_file()
            self.vprint(f'{f} start_addr=0x{s:x}, end_addr=0x{e:x}')
            if self.start_addr is None:
                self.start_addr = s
            if self.end_addr is None:
                self.end_addr = e

        self.vprint(f'Computing crc of {self.filename} from 0x{self.start_addr:x} to 0x{self.end_addr:x}')
        # Parse the hex file and accumulate CRC
        try:
            HexFileParser(self.filename).parse_hex_file(emitter=self.crc_byte)

            # parse_hex_file has finished parsing and calling emitter.
            if self.addr < self.end_addr:
                self.vprint(f'Padding with 0xff bytes from 0x{self.addr:x} to 0x{self.end_addr:x}')
                while self.addr < self.end_addr:
                    self.crc_one_byte(0xff)
        except CrcComplete:
            pass
        return self.crc

    def crc_byte(self, addr, b):
        # Called by HexFileParser as the emitter function, add b to the CRC
        # calculation, padding with 0xff if the addr is non-contiguous
        if addr < self.start_addr:
            # skip starting bytes if needed
            return

        elif addr >= self.end_addr:
            # quit early  as needed
            raise CrcComplete

        elif self.addr is None:
            # Here on first call to crc_byte()
            self.addr = addr

        else:
            # If addr is non-contiguous, compute gap as if filled with 0xff
            while self.addr < addr:
                self.crc_one_byte(0xff)

        # Add the byte to the crc calculation
        self.crc_one_byte(b)

    def crc_one_byte(self, b):
        self.crc = Crc16.crc_byte(b, self.crc)
        self.addr += 1
