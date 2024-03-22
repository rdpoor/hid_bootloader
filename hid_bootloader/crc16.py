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

class Crc16:
    """Compute a CRC for a given buffer using CRC-16-CCITT-FALSE"""

    CRC_TABLE = [
        0x0000, 0x1021, 0x2042, 0x3063, 0x4084, 0x50a5, 0x60c6, 0x70e7,
        0x8108, 0x9129, 0xa14a, 0xb16b, 0xc18c, 0xd1ad, 0xe1ce, 0xf1ef
    ]

    @classmethod
    def compute(cls, buf):
        """
        Compute CRC16 over buf.
        """
        crc = 0
        for b in buf:
            crc = cls.crc_byte(b, crc)
        return crc

    @classmethod
    def crc_byte(cls, b, crc):
        crc &= 0xffffffff
        i = (crc >> 12) ^ (b >> 4)
        crc = cls.CRC_TABLE[i & 0x0f] ^ (crc << 4)
        crc &= 0xffffffff
        i = (crc >> 12) ^ (b >> 0)
        crc = cls.CRC_TABLE[i & 0x0f] ^ (crc << 4)
        return crc & 0xffff

