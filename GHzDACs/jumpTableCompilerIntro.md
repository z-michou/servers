# Jump Table Compiler 
This is an introduction to the jump table compiler, a set of code analagous to gate compiler that allows a user to easily program sequences using the jump table. 

## Compromises
There FPGA code for the jump table is very powerful and flexible. However, we have chosen to make some of these features inaccessible to users at this level as 1) they are complicated to use and program and 2) certain limitations in the hardware make them impractical to use. 

### ADC
The first major compromise is that the ADC boards are not written with the jump table. The ADC currently uses a retrigger table, this table is such that the entire timeline of the experiment must be defined prior to the experiment beginning. For example, if the the DAC is programmed to branch depending on the output of the ADC, these branches must be of the same length or the DAC and ADC will get out of sync. **All potential branches of an experiment must be of the same length, or run parallel in time with respect to the ADC and readout.**

### Z crosstalk
Because we have non-negligible crosstalk between bias lines of qubits (~1%), we suppress this by applying compensation pulses on other bias lines. For this reason, it is impractical to have DAC boards jump separately to one another, as compensation pulses will get out of sync. **All DACs progress, cycle, jump, in unision.**

### Sram pointer and jump table index
The FPGA software has can separately move the jump table index and the SRAM address pointer. This is fairly confusing but potentially powerful. After some discussion, we cannot find a reason where we would really want to use this, so we have decided to link them. What this means will become more obvious in the syntax section. **SRAM pointer and jump table index are linked together.**

## Syntax
### High level
At a high level, we can think of the jump table compiler as a way of moving between different sub-algorithms. For example, a spin-echo sequence can be though of as three algorithms: 
1) Initialization: pi/2 pulse
2) Refocusing: pi pulse
3) Measurement: pi pulse and readout

Then, the jump table sequence would execute algorithm 1, idle, algorithm 2, idle, and finally algorithm 3. 

We would like a syntax that reflects this line of thinking, and uses the heavily used gate compiler as much as possible. For this reason, we've implemented a new class of algorithm, a jumpTableAlgorithm, that acts on gateCompiler algorithms. 

### Example - Spin Echo

    from pyle import gateCompiler as gc
    from pyle import jumpTableCompiler as jt
    from pyle import gates
    from pyle.plotting import plotHelper as ph

    # Pull qubit dictionary objects out of the registry
    # If you want to run this yourself, this code was written with 
    # pyle branch JumpTable (commit # 6bfab67842b415e039670a58b1b0fe50390b5761)
    # and sample object ['', 'Julian', 'Qubit', '9Xmon', '140927']
    measure = 'q0'
    sample, devs, qubit, Qubit = gc.loadQubits(Sample, measure, write_access=True)

    # 1) INITIALIZATION
    alg0 = gc.Algorithm(agents=devs)
    alg0[gates.PiHalfPulse([alg0.q0])]
    alg0.compile()

    # 2) REFOCUSING
    alg1 = gc.Algorithm(agents = devs)
    alg1[gates.PiPulse([alg1.q0])]
    alg1.compile()

    # 3) MEASUREMENT
    alg2 = gc.Algorithm(agents=devs)
    alg2[gates.PiHalfPulse([alg2.q0])]
    alg2[gates.Readout([alg2.q0])]
    alg2.compile()

    # Jump Table Algorithm
    jtAlg = jt.JumpTableAlgorithm(devs)
    jtAlg[jt.JumpTableEntry('INITIALIZATION', alg0, jt.IDLE(200*ns))]
    jtAlg[jt.JumpTableEntry('REFOCUSING', alg1, jt.IDLE(200*ns))]
    jtAlg[jt.JumpTableEntry('MEASUREMENT', alg2, jt.END())]
    jtAlg.compile()

The jumpTableAlgorithm syntax can be ready from left to right. The first step runs alg0, and then excecutes the jumpTable IDLE command. The second line executes alg1 and then executes the IDLE jumpTable command. The last line excecutes alg2 then excecutes the END jumpTable command. 

One of the ways that we can check that the experiment is being executed as we expect is to look at the waveform data. There are two things we might want to do: 1) Look at the experiment as it would appear on the oscilloscope 2) look at the actual data as it will be written into SRAM. Because the jump table can reuse SRAM data or insert delays, these are now different. 

To do this, we can use ph.pulses and the jtAlg.waveform methods:

    # Experimental data
    jtAlg.waveform('TIME')
    ph.pulses(jtAlg)

    # SRAM data
    jtAlg.waveform('SRAM')
    ph.pulses(jtAlg)

## ADC Readout windows and emulating the jump table
One of the funny things that is going on behind the scenes here is telling the ADC when to demodulate. To do this, jumpTableCompiler effectively emulates the DAC boards as they go through the experiment when compile() is called to figure out the precise timing. (It also needs to emulate the DAC timing to figure out qubit phases, more on this later). 

## Phases
One of the tricky things about the jump table is keeping track of qubit phases due to sideband mixing. This was easier with one SRAM block, played from beginning to end, as we can easily make the entire sequence self-consistent. However, cycling or jumping makes this tricky. One thing that we would like to preserve, is that single qubit phases do not have to be thought about for simple experiments, such as the spin-echo experiment above. The expert will note that the phases of the pulses saved in SRAM have to be carefully chosen to align with the qubit frame. 

### Phases in simple experiments
As the jumpTableCompiler emulates the DAC sequence, it figures out at exactly what time each piece of SRAM will be be played. In doing this, for simple experiments, it will automatically add the appropriate global phases to ensure that the SRAM will be aligned with the qubit frame, as expected. 

### Phases from gateCompiler
This is a bit of a sidenote, but important to understand. gateCompiler builds sequences backwards. This makes certain sequences much easier to build, but does something a little bit funny when we care about the jump table. When gate compiler initializes a sequence, it chooses the convention that at t=0 phase=0. It then builds the sequence backwards, and finally shifts the entire sequence forwards to have it begin at t=0 (to within 4 ns). However, this process effectively adds a global phase releated to how long the sequence is. One of the first things the jumpTableCompiler does when it gets its hands on an algorjthm is to remove this global phase, bringing back the convention that at t=0 phase=0. Then, the authomatic phase to make 'simple experiments' execute as desired is added. 

### Phases in loops, jumps
A tricky fact about re-using SRAM is that qubit phases must be accounted for. For example, if one piece of SRAM is repeatedly looped, it is clear that the phase must be compensated for **in hardware** at the end of the sequence, so that phases will align with the beginning of the sequence. Thus, **any piece of SRAM that is run more than once must compensate for qubit phases at the end**.
