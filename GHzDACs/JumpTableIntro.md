# Introduction
This is a beginner's documentation for the jump table version of the DACs.

You can think of the DACs as serving one basic function: you give it a (digital) waveform, and then it plays it out (analog). The pre-jump table version of the DACs had two separate types of commands you could issue: "SRAM write", which defines the waveform (in the SRAM memory); and "memory", which defines the control sequences that play the SRAM. The memory commands were limited to fairly basic operations, such as start, stop, repeat, and wait--it was not possible to have branching code.

The jump table is a replacement for the memory commands that allows for much more complex control. The jump table commands form their own mini-programming language, which contains branching (if-thens) and subroutines (in the form of jumps).

There are now two pointers that can be manipulated:
* The SRAM pointer determines what the DACs are outputting.
  * This holds a memory address. The DACs play what is at this address, and the pointer gets incremented sequentially.
* The jump table pointer holds the index of the currently active jump table operation.
  * A jump table operation has a few parts:
    * The operation code defines the type of command: e.g. IDLE, CHECK, CYCLE, JUMP, NOP, END
    * The fromAddress is an SRAM address. When the SRAM pointer reaches the fromAddress, this jump table operation executes.
    * The toAddress is an SRAM address that is used in the CHECK, CYCLE, and JUMP operations.
  * Jump table operations can manipulate both the SRAM pointer and the jump table pointer.
