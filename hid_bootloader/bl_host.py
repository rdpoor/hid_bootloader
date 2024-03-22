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
from bisync import BiSync

"""
Interact with HID bootloader using Microchip HID bootloader protocol

When the target processor is in bootloader mode, it listens on the USB port for
the following commands:

    READ_BOOT_INFO - see BootloaderHost.read_boot_info()
    ERASE_FLASH - see BootloaderHost.erase_flash()
    PROGRAM_FLASH - see BootloaderHost.program_hex_record()
    READ_CRC - see BootloaderHost.read_crc()
    JMP_TO_APP - see BootloaderHost.jmp_to_app()

Were these written as C functions, these might be documented as follows:

    typedef enum {
      READ_BOOT_INFO = 1,
      ERASE_FLASH,
      PROGRAM_FLASH,
      READ_CRC,
      JMP_TO_APP
    } bootloader_op_t;

    typedef struct {
        bootloader_op_t op;
        uint8_t version_lo;
        uint8_t version_hi
    } read_boot_info_resp_t;

    /**
     * @brief Request the bootloader version number.
     *
     * @return A three-byte packet with READ_BOOT_INFO, version_hi, version_lo.
     */
    read_boot_info_resp_t read_boot_info(void);

    /**
     * @brief Erase program memory.
     *
     * NOTE: The range of program memory erased is determined at compile time
     * on the target processor: you cannot specify the range dynamically.
     *
     * Return ERASE_FLASH.
     */
    bootloader_op_t erase_flash(void);

    /**
     * @brief Write one .hex record into program memory.
     *
     * Note 1: program memory must have been previously be erased.
     * Note 2: The addresses in the .hex records must monotonically increase
     *         (i.e. the .hex file must be normalized).
     *
     * Return PROGRAM_FLASH.
     */
    bootloader_op_t program_flash(uint8_t *hex_record_sans_colon);

    typedef struct {
        bootloader_op_t op;
        uint8_t crc_lo;
        uint8_t crc_hi
    } read_crc_resp_t;

    /**
     * @brief Perform a CRC on a range of program memory.
     *
     * @return A three-byte packet with READ_CRC, crc_hi, crc_lo.
     */
    read_crc_resp_t read_crc(uint32_t address, uint32_t length);

    /**
     * @brief Jump to an app loaded in program memory.
     *
     * Note: the entry vector address is hardwired into the bootloader code.
     *
     * @return Does not return (i.e. does not generate a response)
     */
    void jmp_to_app(void);


Note: to avoid confusion, realize that there are two distinct CRC algorithms and
one checksum algorithm in the bootloader/*.c files:

1. bootloader_usb_device_hid.c:compute() generates a 16 bit CRC and is called:
* to check each request (after stripping bisync encoding)
* to generate a CRC for each response (before wrappping with bisync encoding)
* to calculate the CRC over the flash-resident code in a call to READ_CRC

2. bootloader_common.c:bootloader_CRCGenerate(), as far as I can determine, is
never called.

3. The .hex file format specifies a one-byte checksum at the end of each record.
On the target processor, this is handled in
  bootloader_nvm_interface.c:bootloader_NvmProgramHexRecord()

"""

MAX_MSG = 64

class MsgInfo:
    """
    MsgInfo holds attributes for each message type recognized by the HID
    bootloader.
    """
    def __init__(self, msg_op, name, decoder):
        self.op = msg_op
        self.name = name
        self.decoder = decoder

class BootloaderHost:

    def __init__(self, usb_dev, timeout_ms=5000, verbose=False):
        self.usb_dev = usb_dev
        self.timeout_ms = timeout_ms
        self.verbose = verbose
        self.vprint(f'USB VID: {usb_dev.get_manufacturer_string()} '
                    f'PID:{usb_dev.get_product_string()}')

    def usb_send(self, rqst):
        """
        Send a request to the USB device.
        """
        # prepend a 0 as required by the Windows USB driver (?)
        tx_buf = bytearray([0]) + rqst
        self.vprint('>>> rqst',' '.join(format(x, '02x') for x in tx_buf[1:]))
        self.usb_dev.write(tx_buf)

    def usb_recv(self):
        """
        Read a response from the USB device.
        """
        rx_buf = self.usb_dev.read(MAX_MSG, self.timeout_ms)
        self.vprint('<<< resp',' '.join(format(x, '02x') for x in rx_buf))
        return rx_buf

    def vprint(self, *args):
        if self.verbose:
            print(*args, flush=True)

    def usb_xchg(self, rqst, expect_response = True):
        # append 16 bit crc to the rqst, apply bisync encoding and send
        rqst_crc = Crc16.compute(rqst)
        rqst_with_crc = rqst + bytearray([rqst_crc & 0xff, rqst_crc >> 8])
        # Frame with bisync encoding and send to bootloader
        self.usb_send(BiSync.encode(rqst_with_crc))

        if expect_response:
            # Wait for response, strip bisync encoding and check CRC
            resp_with_crc = BiSync.decode(self.usb_recv())
            computed_crc = Crc16.compute(resp_with_crc[0:-2])
            received_crc = resp_with_crc[-2] | (resp_with_crc[-1] << 8)
            if computed_crc != received_crc:
                raise ValueError(
                    f'computed CRC = {computed_crc:04x} but '
                    f'received CRC = {received_crc:04x}'
                )

            # Decode and print the response
            resp = resp_with_crc[0:-2]  # strip CRC
            return self.decode_resp(resp)
        else:
            return None

    def decode_resp(self, resp):
        if resp is None or len(resp) == 0:
            raise ValueError(f'No data to decode in {resp}')
        op = resp[0]
        msg_info = self.get_msg_info(op)
        if msg_info is None:
            raise ValueError(f'Unrecognized message type {op}')
        return msg_info.decoder(self, resp)

    # **************************************************************************
    # **************************************************************************
    # Functions that send requests to the bootloader

    def read_boot_info(self):
        """
        Get the bootloader version number (two bytes)

        Invokes bootloader_GetVersion()
        response is [op version_lo version_hi]
        returns version
        """
        return self.usb_xchg(bytes([self.HID_BL_CMD_READ_BOOT_INFO.op]))

    def erase_flash(self):
        """
        Erase program memory (but not the bootloader)

        Invokes bootloader_NvmAppErase(APP_START_ADDRESS, FLASH_END_ADDRESS)

        Note: compile-time constants APP_START_ADDRESS and FLASH_END_ADDRESS
        define what gets erased - additional params are neither needed nor
        possible.
        """
        self.usb_xchg(bytes([self.HID_BL_CMD_ERASE_FLASH.op]))

    def program_flash(self, hex_record):
        """
        Write one hex record to program memory.  Note that erase_flash() must
        have been called previously.

        Invokes bootloader_NvmProgramHexRecord(uint8_t* HexRecord, uint32_t totalLen)
        Responds with [op] on success, no response on failure

        Note: hex_record is an array of bytes, not hex ASCII.
        """
        msg = bytes([self.HID_BL_CMD_PROGRAM_FLASH.op]) + hex_record
        self.usb_xchg(msg)

    def read_crc(self, address, length):
        """
        Read all of program memory to compute its CRC.

        Invokes compute(uint8_t *data, uint32_t len)
        response is [op, crc_lo, crc_hi]
        returns crc
        """
        fields = (self.HID_BL_CMD_READ_CRC.op, address, length)
        return self.usb_xchg(struct.pack('<BII', *fields))

    def jump_to_app(self):
        """
        Jumps to app by issuing a processor reset.  Unless the bootloader
        trigger condition is met (action button held or magic number written
        into RAM), this will cause the target processor to jump to the main app.

        No response sent.
        """
        msg = bytes([self.HID_BL_CMD_JMP_TO_APP.op])
        self.usb_xchg(msg, expect_response = False)

    # **************************************************************************
    # **************************************************************************
    # Functions that decode responses from the bootloader

    def decode_HID_BL_CMD_READ_BOOT_INFO_resp(self, resp):
        resp_fmt = '<BH'
        size = struct.calcsize(resp_fmt)
        (op, version) = struct.unpack(resp_fmt, resp[0:size])
        msg_info = self.get_msg_info(op)
        self.vprint(f'cmd: {op:02x} {msg_info.name} version:{version:04x}')
        return version

    def decode_HID_BL_CMD_ERASE_FLASH_resp(self, resp):
        op = int(resp[0])
        msg_info = self.get_msg_info(op)
        self.vprint(f'cmd: {op:02x} {msg_info.name}')
        return None

    def decode_HID_BL_CMD_PROGRAM_FLASH_resp(self, resp):
        op = int(resp[0])
        msg_info = self.get_msg_info(op)
        # print(f'cmd: {op:02x} {msg_info.name}')
        return None

    def decode_HID_BL_CMD_READ_CRC_resp(self, resp):
        resp_fmt = '<BH'
        size = struct.calcsize(resp_fmt)
        (op, crc) = struct.unpack(resp_fmt, resp[0:size])
        msg_info = self.get_msg_info(op)
        self.vprint(f'cmd: {op:02x} {msg_info.name} crc:{crc:04x}')
        return crc

    def decode_HID_BL_CMD_JMP_TO_APP_resp(self, resp):
        """
        Never called.
        """
        return None

    # Define the commands that the HID bootloader recognizes.
    # Note: the values for <op> must match the BOOTLOADER_COMMANDS enum defined
    # bootloader_usb_device_hid.c
    #
    # MsgInfo(msg_op, name, decoder)
    HID_BL_CMD_READ_BOOT_INFO = MsgInfo(1, 'HID_BL_CMD_READ_BOOT_INFO', decode_HID_BL_CMD_READ_BOOT_INFO_resp)
    HID_BL_CMD_ERASE_FLASH = MsgInfo(2, 'HID_BL_CMD_ERASE_FLASH', decode_HID_BL_CMD_ERASE_FLASH_resp)
    HID_BL_CMD_PROGRAM_FLASH = MsgInfo(3, 'HID_BL_CMD_PROGRAM_FLASH', decode_HID_BL_CMD_PROGRAM_FLASH_resp)
    HID_BL_CMD_READ_CRC = MsgInfo(4, 'HID_BL_CMD_READ_CRC', decode_HID_BL_CMD_READ_CRC_resp)
    HID_BL_CMD_JMP_TO_APP = MsgInfo(5, 'HID_BL_CMD_JMP_TO_APP', decode_HID_BL_CMD_JMP_TO_APP_resp)

    _msg_info_dict = None

    @classmethod
    def get_msg_info(cls, op):
        """
        Map a message op to its MsgInfo
        """
        if cls._msg_info_dict is None:
            # Lazy creation of _msg_info_dict
            cls._msg_info_dict = {getattr(cls, name).op: getattr(cls, name)
                              for name in cls.__dict__
                              if isinstance(getattr(cls, name), MsgInfo)}
        # look up MsgInfo from op
        msg_info = cls._msg_info_dict.get(op)
        return msg_info


