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
    * The fromAddress is an SRAM address. When the SRAM pointer reaches the fromAddress, this jump table operation executes.
    * The toAddress is an SRAM address that is used in the CHECK, CYCLE, and JUMP operations.
  * Jump table operations can manipulate both the SRAM pointer and the jump table pointer.

# Jump Table Operations

Let's make this concrete by enumerating the allowed jump table operations. Each jump table operation is given by a two byte operation code (opcode), as well as two SRAM addresses, the fromAddress and toAddress. The last few bits of the opcode specify the type of command, and the other bits are arguments. Byte 1 is commonly devoted to a jump table index. The code for this is `xxjjjjjj`, which means the first two bits `x` are ignored, while the six bits `j` form a single number, the use of which is given in the description.

 Name |   Byte 1   |   Byte 2   | Description
------|------------|------------|-------------
IDLE  | `dddddddd` | `ddddddd0` | Wait for n+1 cycles, with n defined by the fifteen bits `d`.
NOP   | `xxxxxxxx` | `xxxx0101` | Null operation: move both the SRAM pointer and the jump table pointer forward by one.
CHECK | `xxjjjjjj` | `iiiin001` | Query the daisy chain bit at index `iiii`. If it is equal to `n`, move the SRAM pointer to the toAddress and the jump table pointer to the jump table index indicated by `jjjjjj`. If not, move both the SRAM pointer and the jump table pointer forward by one.
JUMP  | `xxjjjjjj` | `xxxx1101` | Move the SRAM pointer to the toAddress, and the jump table pointer to `jjjjjj`.
CYCLE | `xxjjjjjj` | `xxccx011` | Compare the counter* (index given by `cc`) with its countTo parameter (also index `cc`). If false (counter != countTo): increment counter, move SRAM pointer to toAddress, move jump table pointer to `jjjjjj`. If true (counter == countTo): reset counter to 0, move both SRAM pointer and jump table pointer forward by one.
END   | `xxxxxxxx` | `xxxxx111` | End. The SRAM pointer will stop at fromAddress + 2.

*About the counters: there are four counters, and each has a corresponding countTo parameter. The countTo parameters are set at the same time as the jump table (see below).
