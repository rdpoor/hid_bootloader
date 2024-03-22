# hid_bootloader

Interact with a Microchip Harmony bootloader running on a target microcontroller
via USB HID.

## Overview

Microchip's MPLAB / Harmony3 provides a drop-in bootloader module for MPLAB.X
project.  `hid_bootloader` is a Python module that allows you to interact with
the bootloader and hexfiles from the command line.  Written in Python, it should
work on Windows, Linux and macOS host platforms.

## `hid_bootloader` commands

hid_bootloader recognizes the following commands:

### `bootload`
```
$ hid_bootloader/bl_main.py bootload -x <hex_file>
   [--vid <vid>] [--pid <pid>] [--verbose] [--trace]
```
Download `hexfile` into the target program memory.

### `crc_memory`
```
$ hid_bootloader/bl_main.py crc_memory [-x <hex_file>]
   [-s <start_addr>] [-e <end_addr>] [--verbose] [--trace]
```
Compute CRC16 over the target program memory.  If either `start_addr` or
`end_addr` are omitted, they will be filled in by parsing `hex_file`.

### `crc_hexfile`
```
$ hid_bootloader/bl_main.py crc_hexfile -x <hex_file> [--verbose] [--trace]
```
Compute CRC16 over the given hexfile.

### `crc_compare`
```
$ hid_bootloader/bl_main.py crc_memory -x <hex_file> [--verbose] [--trace]
```
Compute and print CRC16 on the target memory and CRC16 on the hexfile.

### `run_program`
```
$ hid_bootloader/bl_main.py run_program [--verbose] [--trace]
```
Jump to the program resident in program memory.  Does not return to the
bootloader.

## About Harmony Bootloader

The `hid_bootloader` commands listed above call upon underlying Harmony
Bootloader commands.  This section describes the low-level Harmony Bootloader
commands.

When in bootloader mode, the target microcontroller listens for the
following commands:

| opcode | name           | description                                       |
| ------ | -------------- | ------------------------------------------------- |
| 1      | READ_BOOT_INFO | Returns the version number of the bootloader      |
| 2      | ERASE_FLASH    | Erases program memory in the target system        |
| 3      | PROGRAM_FLASH  | Write program memory from one line in a .hex file |
| 4      | READ_CRC       | Compute the CRC16 for a range of addresses        |
| 5      | JMP_TO_APP     | Jump to the application, leaving bootloader mode  |

### `READ_BOOT_INFO`

Requests bootload version.  Host sends request: `[READ_BOOT_INFO]`  Target sends
response: `[READ_BOOT_INFO, <version_lo>, <version_hi>]`.

### `ERASE_FLASH`

Erases all program memory (except for the bootloader itself).  Host sends
request: `[ERASE_FLASH]`  Target sends response: `[ERASE_FLASH]`.

### `PROGRAM_FLASH`

Program one record of hex data.  Note that the program memory must have been
previously erase with an `ERASE_FLASH` command.

Host sends request: `[PROGRAM_FLASH hex_data...]`  where `hex_data` is one line
from a file in Intel Hex format, where each pair of hex digits has been
converted into a single byte.  Target sends response: `[PROGRAM_FLASH]`.

### `READ_CRC`

Calculate the CRC over a range of bytes in program memory.

Host sends `[READ_CRC start_addr byte_count]`.  Target sends response
`[READ_CRC, crc_lo, crc_hi]`.

### `JMP_TO_APP`

Exit the bootloader and start the target application.

Host sends `[JMP_TO_APP]`.  Target does not respond.
