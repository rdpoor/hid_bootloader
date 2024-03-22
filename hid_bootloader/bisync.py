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

SOH = 1
EOT = 4
DLE = 16

class BiSync:
    """
    Support for encoding and decoding BiSync protocol buffers.  Encoding a
    binary buffer using BySync protocol results in the following:
        [SOH *binary_data EOT]
    where each instance of SOH, EOT and DLE within binary data is preceeded with
    a DLE byte.
    """

    @classmethod
    def encode(cls, buf):
        """
        Wrap a byte array with bisync framing to produce:
           [SOH binary_data* EOT]
        Within the binary_data*, any occurance of SOH, EOT or DLE is preceded
        with a DLE.
        """
        encoded = bytearray([SOH]); # start with SOH
        for b in buf:
            if b == EOT or b == SOH or b == DLE:
                # use DLE to escape special chars
                encoded.append(DLE)
            encoded.append(b)
        encoded.append(EOT)
        return encoded

    @classmethod
    def decode(cls, buf):
        """
        Extract binary data from a bisync encoded frame: expects
            [SOH binary_data* EOT ...]
        where each instance of SOH, EOT or DLE escaped with a DLE byte.  Stops
        when it encouters an un-escaped EOT and returns a bytearray:
            [binary_data*]
        or raises an error if byte_array is improperly formatted.
        """
        # encoded data must start with SOH
        if buf[0] != SOH:
            raise ValueError("BiSync data must start with SOH")

        decoded = bytearray()
        escaping = False  # True if previous byte was DLE
        eot_seen = False

        for b in buf[1:]:
            if escaping:
                decoded.append(b)
                escaping = False
            elif b == DLE:
                escaping = True
            elif b == EOT:
                eot_seen = True
                break;
            else:
                decoded.append(b)
        # Error if left with a dangling DLE
        if not eot_seen:
            raise ValueError("BiSync data must end with EOT")
        return decoded

