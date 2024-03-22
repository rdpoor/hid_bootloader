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

import argparse
from bl_host import BootloaderHost
from hexfile import HexFileParser, HexFileCrc
import hid

MCHIP_VID = 0x04d8
MCHIP_PID = 0x003f

class BlMain:

    def __init__(self, action, hexfile=None, vid=MCHIP_VID, pid=MCHIP_PID,
                 start_addr=None, end_addr=None, verbose=False, trace=False):
        self.action = action
        self.hexfile = hexfile
        self.vid = vid
        self.pid = pid
        self.start_addr = start_addr
        self.end_addr = end_addr
        self.verbose = verbose
        self.trace = trace
        self.usb_dev = None

    def bootload(self):
        """Write hexfile to target program memory after erasing it."""
        self.open_usb()
        blh = BootloaderHost(self.usb_dev, verbose=self.trace)
        with open(self.hexfile, 'r') as f:
            self.vprint(f'Erasing program memory')
            blh.erase_flash()
            self.vprint(f'Writing program memory from {self.hexfile}')
            for line in f:
                line = line.strip()
                line = line[1:]   # remove leading colon
                # convert hex ascii to binary bytes
                arr = [int(line[i:i+2], 16) for i in range(0, len(line), 2)]
                blh.program_flash(bytearray(arr))
                if self.verbose:
                    print('.', flush=True, end='')
        self.vprint('done!')

    def crc_memory(self):
        """
        Compute the CRC of target program memory.  If either start_addr or
        end_addr are omitted, hexfile must be provided and will determine
        start and/or end address for the CRC calculation.
        """
        self.open_usb()
        self.resolve_start_and_end()
        blh = BootloaderHost(self.usb_dev, verbose=self.trace)
        crc = blh.read_crc(self.start_addr, self.end_addr - self.start_addr)
        print(f'CRC of program memory from 0x{self.start_addr:x} '
              f'to 0x{self.end_addr:x} = 0x{crc:x}')
        return crc

    def crc_hexfile(self):
        """
        Compute the CRC of the given hexfile.  If either start_addr or
        end_addr are omitted, they are determined by the hexfile.  If
        either start_addr or end_addr are outside the bounds of the hexfile,
        the CRC calculation will use 0xff as padding.
        """
        self.resolve_start_and_end()
        hxf = HexFileCrc(self.hexfile, verbose=self.trace)
        crc = hxf.compute_crc(self.start_addr, self.end_addr)
        print(f'CRC of {self.hexfile} from 0x{self.start_addr:x} '
              f'to 0x{self.end_addr:x} = 0x{crc:x}')
        return crc

    def crc_compare(self):
        """
        Compute and report the CRC of the target program memory and of the
        hexfile, returning True if both are identical.  If either start_addr
        or end_addr are omitted, they are determined by the hexfile.
        """
        crc_mem = self.crc_memory()
        crc_hex = self.crc_hexfile()
        return crc_mem == crc_hex

    def run_program(self):
        """
        Exit bootloader, jump to target application.
        """
        self.open_usb()
        blh = BootloaderHost(self.usb_dev, verbose=self.trace)
        blh.jump_to_app()

    # helper functions

    def vprint(self, *args):
        if self.verbose:
            print(*args, flush=True)

    def open_usb(self):
        if self.usb_dev is None:
            self.usb_dev = hid.device()
            self.usb_dev.open(vendor_id=self.vid, product_id=self.pid)
            self.usb_dev.set_nonblocking(1)
            if self.verbose:
                blh = BootloaderHost(self.usb_dev)
                version = blh.read_boot_info()
                print(f'Bootloader Version = 0x{version:x}')
        return self.usb_dev

    def resolve_start_and_end(self):
        if self.start_addr is None or self.end_addr is None:
            # Parse hexfile to determine its start and end address
            if self.hexfile is None:
                raise ValueError('hexfile must be given if start_addr or end_addr are omitted')
            hfc = HexFileParser(self.hexfile)
            (s, e) = hfc.parse_hex_file()
            if self.start_addr is None:
                self.start_addr = s
            if self.end_addr is None:
                self.end_addr = e
        self.vprint(f'Setting start_addr = 0x{self.start_addr:x}, '
                    f'end_addr = 0x{self.end_addr:x}')

if __name__ == '__main__':

    def auto_int(x):
        """Accept hex or decimal argument"""
        return int(x, 0)

    parser = argparse.ArgumentParser()
    parser.add_argument('--vid', type=auto_int, default=MCHIP_VID, help='USB Vendor ID')
    parser.add_argument('--pid', type=auto_int, default=MCHIP_PID, help='USB Product ID')
    parser.add_argument('action', help=f'action to perform')
    parser.add_argument('-x', '--hexfile', default=None, help='.hex file for [bootload, crc_memory, crc_compare]')
    parser.add_argument('-s', '--start_addr', type=auto_int, default=None, help='starting address for CRC commands')
    parser.add_argument('-e', '--end_addr', type=auto_int, default=None, help='ending address for CRC commands')
    parser.add_argument('-v', '--verbose', action='store_true', help='enable debug printing')
    parser.add_argument('-t', '--trace', action='store_true', help='enable low-level trace printing')
    args = parser.parse_args()

    blm = BlMain(args.action, args.hexfile, args.vid, args.pid, args.start_addr,
        args.end_addr, args.verbose, args.trace)

    commands = {'bootload':blm.bootload,
                'crc_memory':blm.crc_memory,
                'crc_hexfile':blm.crc_hexfile,
                'crc_compare':blm.crc_compare,
                'run_program':blm.run_program
               }

    try:
        commands[args.action]()
    except KeyError:
        print(f'action must be one of [{", ".join(commands.keys())}]')
