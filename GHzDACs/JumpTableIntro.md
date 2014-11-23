# Introduction
This is a beginner's documentation for the jump table version of the DACs.

You can think of the DACs as serving one basic function: you give it a (digital) waveform, and then it plays it out (analog). The pre-jump table version of the DACs had two separate types of commands you could issue: "SRAM write", which defines the waveform (in the SRAM memory); and "memory", which defines the control sequences that play the SRAM. The memory commands were limited to fairly basic operations, such as start, stop, repeat, and wait--it was not possible to have branching code.

The jump table is a replacement for the memory commands that allows for much more complex control. The jump table commands form their own mini-programming language, which contains branching (if-thens) and subroutines (in the form of jumps), as well as the ability to read output from the ADC on the daisy chain.

There are now two pointers that can be manipulated:

* The SRAM pointer determines what the DACs are outputting.
  * This holds a memory address. The DACs play what is at this address, and the pointer gets incremented sequentially.
* The jump table pointer holds the index of the currently active jump table operation.
  * A jump table operation has a few parts:
    * The operation code defines the type of command: e.g. IDLE, CHECK, CYCLE, JUMP, NOP, END
    * The fromAddress is an SRAM address. When the SRAM pointer reaches the fromAddress, this jump table operation is called, and will execute on the _next_ cycle (i.e. the SRAM pointer will be at fromAddress+1 when the jump table operation executes).
    * The toAddress is an SRAM address that is used in the CHECK, CYCLE, and JUMP operations.
  * Jump table operations can manipulate both the SRAM pointer and the jump table pointer.

# Jump Table Operations

Let's make this concrete by enumerating the allowed jump table operations. Each jump table operation is given by a two byte operation code (opcode), as well as two three-byte SRAM addresses, the fromAddress and toAddress. The last few bits of the opcode specify the type of command, and the other bits are arguments. Byte 1 is commonly devoted to a jump table index. The code for this is `xxjjjjjj`, which means the first two bits `x` are ignored, while the six bits `j` form a single number, the use of which is given in the description.

 Name |   Byte 1   |   Byte 2   | Description
------|------------|------------|-------------
IDLE  | `dddddddd` | `ddddddd0` | Wait for n+1 cycles, with n defined by the fifteen bits `d`. SRAM pointer will remain at fromAddress+1.
NOP   | `xxxxxxxx` | `xxxx0101` | Null operation: move both the SRAM pointer and the jump table pointer forward by one.
CHECK | `xxjjjjjj` | `iiiin001` | Query the daisy chain bit at index `iiii`. If it is equal to `n`, move the SRAM pointer to the toAddress and the jump table pointer to the jump table index indicated by `jjjjjj`. If not, move both the SRAM pointer and the jump table pointer forward by one.
JUMP  | `xxjjjjjj` | `xxxx1101` | Move the SRAM pointer to the toAddress, and the jump table pointer to `jjjjjj`.
CYCLE | `xxjjjjjj` | `xxccx011` | Compare the counter* (index given by `cc`) with its countTo parameter (also index `cc`). If false (counter != countTo): increment counter, move SRAM pointer to toAddress, move jump table pointer to `jjjjjj`. If true (counter == countTo): reset counter to 0, move both SRAM pointer and jump table pointer forward by one.
END   | `xxxxxxxx` | `xxxxx111` | End. The SRAM pointer will stop and idle at fromAddress + 2.

*About the counters: there are four counters, and each has a corresponding countTo parameter. The countTo parameters are set at the same time as the jump table (see below).

# Example

We now explain the examples in John's documentation. Note that the startAddress, toAddress, and fromAddress are in hexadecimal.

Notation: the prefix 0x means a number is being expressed in hexadecimal, and 0b is for binary. Hence one byte could be written as 0x1A = 0b00011010 = 26.

Jump Table Index | Opcode | toAddress | fromAddress | Comment
-----------------|--------|-----------|------------|--------
**Normal Sequence** | | | |
0 | `0005` | `000000` | `000000` | First JT entry defines the start address of the SRAM pointer (here, 0). The command is a no-op: 0x05 = `0b00000101` = NOP.
1 | `0007` | `000000` | `000050` | When SRAM reaches the from address (0x50), the sequence will end (0x07 = 0b0111 = END). The SRAM will run to address 0x52 and idle.
**Spin Echo** | | | |
0 | `0005` | `000007` | `000007` | Start at address 7. For the start command, toAddress must be the same as fromAddress.
1 | `0200` | `000000` | `000010` | When SRAM pointer reaches address 0x10 (fromAddress), the IDLE command will be activated: 0x0200 = 0b00000010 00000000 = IDLE of length 256+1. The SRAM pointer will idle at address 0x11 for 257 cycles. Then the SRAM pointer will continue advance and the JT pointer will increase by one, to 2 (the next command)
2 | `0400` | `000000` | `000020` | Same as above: the SRAM pointer will idle at address 0x21 for 512+1 cycles.
3 | `0007` | `000000` | `000050` | End at address 0x52.
 | | | | To work as a spin echo, the SRAM should contain a pi/2 pulse from 0x07 to 0x10, nothing (or a detuning) for 0x11 (which is held during the idle), a pi pulse for 0x12 to 0x20, nothing again for 0x21, and a pi/2 and readout for addresses 0x22 through 0x52. (A true spin echo would have the two delays equal, of course.)
 **All operations** | | | |
 0 | `0005` | `000003` | `000003` | Start at address 3.
 1 | `0129` | `000007` | `000010` | `0x0129 = 0b00000001 00101001` CHECK if daisychain bit 2 (0b0010) is 1. If so, jump SRAM pointer to 7 and JT pointer to 1 (this command again). If not, proceed to next jump table entry.
 2 | `0213` | `000028` | `000030` | `0x0213 = 0b00000010 00010011` CYCLE counter #1, going back to SRAM address 0x28 and JT index 2 (this operation) each time. When cycle completes, advance to next operation.
 3 | `040D` | `000048` | `000040` | `0x040D = 0b00000100 00001101` JUMP SRAM pointer to 0x48 and JT pointer to 4.
 4 | `0004` | `000000` | `000050` | Idle for 2+1 cycles at SRAM address 0x51.
 5 | `0007` | `000000` | `000060` | End at SRAM address 0x62.
 
 The last example does the following:
 
 * Start at 0x03
 * proceed to 0x10 and repeat 0x07 through 0x11 (note the off by one here) until daisy chain bit #2 is 1
 * proceed to 0x30 and repeat 0x28 through 0x30 N times (N is defined elsewhere, see the full protocol below)
 * proceed to 0x40 and then jump to 0x48
 * proceed to 0x51 and idle for 3 cycless 
 * proceed to 0x62 and end.

# The Jump Table Write

This is the specification for defining the jump table. The ethernet packet to write the jump table consists of a 2-byte length header and a 528-byte body. The contents of the packet are detailed below. (The header is generated by the direct ethernet server and so is not listed here.)

Byte Index (0-indexed) | Name | Description
-----------------------|------|------------
 | | The first 16 bytes define the four counters.
    0 | CountTo0 [0] | Byte 0 (least significant) of counter 0
    1 | CountTo0 [1] | Byte 1 (i.e. bits 8-15.)
    2 | CountTo0 [2] |
    3 | CountTo0 [3] | Last byte of counter 0
  4-7 | CountTo1 [0-3] | Counter 1
 8-11 | CountTo2 [0-3] | Counter 2
12-15 | CountTo3 [0-3] | Counter 3
 | | The remainder of the packet defines the 64 jump table operations, 8 bytes each.
 | | The first JT operation is a special case
16-18 | StartAdr [0-2] | SRAM pointer start address
19-21 | StartAdr [0-2] | must duplicate 16-18
22-23 | StartOpCode [0-1] | The first JT opcode (must=5 for NOP?)
 | | Each normal JT operation is 3 bytes for the fromAddress, 3 bytes for the toAddress, and 2 bytes for the opcode
24-26 | fromAddress [0-2] | fromAddress of JT operation, index 1
27-29 | toAddress [0-2] | toAddress of JT operation, index 1
30-31 | opcode [0-1] | opcode of JT operation, index 1
32-39 | | fromAddress, toAddress, opcode of JT operation, index 2
... | |
521-528 | | ... JT operation, index 63
   
# Questions

* The JT operation is actually executed at fromAddress + 1. Does this mean that JT index 2 in the final example will cycle between 0x28 and 0x31, actually? And the JUMP operation (3) will jump from 0x41 to 0x48?
* Can the start operation be something other than a NOP?
