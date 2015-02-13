# Copyright (C) 2007, 2008, 2009, 2010  Matthew Neeley
# Copyright (C) 2010, 2011, 2012, 2013
#               2014 Daniel Sank, James Wenner
#
# 
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


# CHANGELOG:
#
# 2011 November 30 - Daniel Sank / Jim Wenner
#
# Run Sequence setting now only tries to get ADC demodulation ranges when
# getTimingData is True. If getTimingData is False, no data is extracted,
# so it's impossible to store the I and Q ranges.
#
# 2011 November 29 - Jim Wenner
#
# Removed adc_recalibrate from adc_bringup since this may randomize order of
# I,Q outputs.
#
# 2011 November 16 - Dan Sank/Jim Wenner
#
# Fixed documentation for dac_lvds and dac_fifo.
# Changed return type tag for dac_bringup. Now an array of clusters instead of
# a cluster of clusters.
#
# For dac and adc device objects, changed device.params to device.buildParams.
# This was done because we now have _build_ specific, and _board_ specific
# parameters stored in the registry and we need to distinguish these in the
# variable names.
#
# In other words, build specific data are in device.buildParams
# and board specific data are in device.boardParams
#
# 2011 November 10 - Jim Wenner
#
# Fixed bug where, in list_dacs and list_adcs, looked for (name,id) in devices 
# when checking board groups even though only name present by this point.
#
# 2011 November 4 - Daniel Sank
#
# The code around line 1172 which read "c[runner.dev]['ranges']=runner.ranges"
# didn't work because I had never assigned runner.ranges. This is now assigned
# near line 601.
#
# 2011 November 2 - Jim Wenner
#
# Moved bringup code into the server. This was done to help keep bringup and
# server code synchronized with each other.
#
# DAC bringup now has signed data as default. Added
# functions to return list of DACs or of ADCs.
#
# In setFIFO, removed reset of LVDS sample delay. Changed how check FIFO
# counter to ensure final value same as what thought setting to. In both
# setFIFO and setLVDS, added success/ failure checks and modified return
# parameters. Changed default FIFO counter from 3 to value in registry provided 
# for each board. Changed default setLVDS behavior from optimizing LVDS SD to
# getting SD from board-specific registry key while adding option to use
# optimal SD instead. setLVDS returns MSD, MHD even if sample delay specified.
#
# Board specific registry keys are located in ['Servers','GHz FPGAs'] and are
# of form:
# dacN=[('fifoCounter', 3), ('lvdsSD', 3), ('lvdsPhase', 180)]
#
# 2011 February 9 - Daniel Sank
# Removed almost all references to hardcoded hardware parameters, for example
# the various SRAM lengths. These values are now board specific.
# As an example of how this is implemented, we used to have something like
# this:
# def adc_filter_func(self, c, bytes, stretchLen=0, stretchAt=0):
#     assert len(bytes) <= FILTER_LEN, 'Filter function max length is %d' \
#                                       % FILTER_LEN
#     dev = self.selectedADC(c)
#     ...
# where FILTER_LEN was a global constant. We now instead have this:
# def adc_filter_func(self, c, bytes, stretchLen=0, stretchAt=0):
#     dev = self.selectedADC(c)
#     assert len(bytes) <= dev.buildParams['FILTER_LEN'], 'Filter function max\
#                          length is %d' % dev.buildParams['FILTER_LEN']
#     ...    
# so that the filter length is board specific. These board specific parameters
# are loaded by the board objects when they are created, See dac.py and adc.py
# for details on how these parameters are loaded.


# + DOCUMENTATION
#
# Communication between the computer and the FPGA boards works over ethernet.
# This server and the associated board type definition files dac.py and adc.py
# abstract away this ethernet communication. This means that you don't have
# to explicitly tell the direct ethernet server to send packets to the boards.
# Instead you call, for example, this server's Memory command and the server
# will build the appropriate packets for the board you've selected and the
# memory sequence you want to send. No packets are actually sent to the boards
# until you tell them to turn using one of the following commands:
# DAC Run SRAM      - Runs SRAM on one board without waiting for a daisychain
#                     pulse.
# ADC Run Demod     - Runs ADC demod mode on one board without waiting for a
#                     daisychain pulse.
# ADC Run Average   - Runs ADC average mode on one board without waiting for a
#                     daisychain pulse.
# Run Sequence      - Runs multiple boards synchronously using the daisychain
#                     (DACs and ADCs).
# When one of the one-off (no daisychain) commands is sent, whichever DAC
# or ADC you have selected in your context will run and return data as
# appropriate. The use of Run Sequence is slightly more complicated. See below.
#
# ++ USING RUN SEQUENCE
# The Run Sequence command is used to run multiple boards synchronously using
# daisychain pulses to trigger SRAM execution. Here are the steps to use it:
# 1. "Daisy Chain" to specify what boards will run
# 2. "Timing Order" to specify which boards' data you will collect
# 3. Set up DACS - for each DAC you want to run call Select Device and then:
#   a. SRAM or SRAM dual block
#   b. Memory
#   c. Start Delay
# 4. Set up ADCs - for each ADC you want to run call Select Device and then:
#   a. ADC Run Mode
#   b. ADC Filter Func (set this even if you aren't using demodulation mode)
#   c. ADC Demod Phase
#   d. ADC Trig Magnitude
#   e. Start Delay
# For information on the format of the data returned by Run Sequence see its
# docstring.
#
# ++ REGISTRY KEYS
# In order for the server to set up the board groups and fpga devices properly
# there are a couple of registry entries that need to be set up. Registry keys
# for this server live in ['','Servers','GHz FPGAs']
#
# boardGroups: *(ssw*(sw)), [(groupName,directEthernetServername,portNumber,
#                               [(boardName,daisychainDelay),...]),...]
# This key tells the server what boards groups should exist, what direct
# ethernet server controlls that group, which ethernet port is connected to the
# boards (via an ethernet switch) and what boards exist on each group. Board
# names should be of the form "DAC N" or "ADC N" where N is the number
# determined by the DIP switches on the board. The number after each board name
# is the number of clock cycles that board should wait after receiving a
# daisychain pulse before starting to run its SRAM.
#
# dacBuildX: *(s?), [(parameterName,value),(parameterName,value),...]
# adcBuildX: *(s?), [(parameterName,value),(parameterName,value),...]
# When FPGA board objects are created they read the registry to find hardware
# parameter values. For example, the DAC board objects need to know how long
# their SRAM memory is, and each board may have a different value depending on
# its specific FPGA chip. Details, lists of necessary parameters and example
# values for each board type are given in dac.py and adc.py
#
# dacN: *(s?), [(parameterName,value),(parameterName,value),...] Parameters
# which are specific to individual boards. This is used for the default FIFO
# counter, LVDS SD, etc. See examples in dac.py

from __future__ import with_statement

"""
TODO
cmdTime_cycles does not properly estimate sram length


"""


"""
### BEGIN NODE INFO
[info]
name = GHz FPGAs
version = 4.0
description = Talks to DAC and ADC boards

[startup]
cmdline = %PYTHON% %FILE%
timeout = 20

[shutdown]
message = 987654321
timeout = 20
### END NODE INFO
"""

import sys
import os
import itertools
import struct
import time
def timeString():
    t = time.localtime()
    ts = '%s %s %s %s %s %s' %(t.tm_year, t.tm_mon, t.tm_mday, t.tm_hour,
                                  t.tm_min, t.tm_sec)
    return ts

import random

from msvcrt import getch, kbhit
def waitForkey():
    while kbhit():
        getch()
    getch()

import numpy as np

from twisted.internet import defer
from twisted.internet.defer import inlineCallbacks, returnValue

from labrad import types as T
import labrad.units as U
from labrad.units import Unit, Value
from labrad.devices import DeviceServer
from labrad.server import setting

from .Cleanup import dac, adc, fpga
from . import jumpTable

from util import TimedLock, LoggingPacket
LOGGING_PACKET=False

from matplotlib import pyplot as plt

NUM_PAGES = 2

I2C_RB = 0x100
I2C_ACK = 0x200
I2C_RB_ACK = I2C_RB | I2C_ACK
I2C_END = 0x400

# TODO: Remove the constants from above and put them in the registry to be
# read by individual DAC board instances. See DacDevice.connect to see how
# this is done
# TODO: make sure paged operations (datataking) don't conflict with e.g.
#       bringup
# - want to do this by having two modes for boards, either 'test' mode
#   (when a board does not belong to a board group) or 'production' mode
#   (when a board does belong to a board group).  It would be nice if boards
#   could be dynamically moved between groups, but we'll see about that...
# TODO: store memory and SRAM as numpy arrays, rather than lists and strings,
#       respectively
# TODO: run sequences to verify the daisy-chain order automatically
# TODO: when running adc boards in demodulation (streaming mode), check
#       counters to verify that there is no packet loss
# TODO: think about whether page selection and pipe semaphore can interact
#       badly to slow down pipelining


class TimeoutError(Exception):
    """Error raised when boards timeout."""
    
class BoardGroup(object):
    """Manages a group of GHz DAC boards that can be run simultaneously.
    
    All the fpga boards must be daisy-chained to allow for synchronization,
    and also must be connected to the same network card.  Currently, one
    board group is created automatically for each detected network card.
    Only one sequence at a time can be run on a board group, but memory
    and SRAM updates can be pipelined so that while a sequence is running
    on some set of the boards in the group, new sequence data for the next
    point can be uploaded.
    """
    def __init__(self, fpgaServer, server, port):
        self.fpgaServer = fpgaServer
        self.server = server
        self.port = port
        self.cxn = server._cxn
        self.ctx = server.context()
        #self.sourceMac = getLocalMac(port)
        self.pipeSemaphore = defer.DeferredSemaphore(NUM_PAGES)
        self.pageNums = itertools.cycle(range(NUM_PAGES))
        self.pageLocks = [TimedLock() for _ in range(NUM_PAGES)]
        self.runLock = TimedLock()
        self.readLock = TimedLock()
        self.setupState = set()
        self.runWaitTimes = []
        self.prevTriggers = 0
    
    @inlineCallbacks
    def init(self):
        """Set up the direct ethernet server in our own context."""
        p = self.server.packet(context=self.ctx)
        p.connect(self.port)
        #p.source_mac(self.sourceMac)
        yield p.send()
    
    @inlineCallbacks
    def shutdown(self):
        """Clean up when this board group is removed."""
        # expire our context with the manager
        yield self.cxn.manager.expire_context(self.server.ID, context=self.ctx)
        
    def configure(self, name, boards):
        """Update configuration for this board group."""
        self.name = name
        self.boardOrder = ['%s %s' % (name, boardName) for \
                              (boardName, delay) in boards]
        self.boardDelays = [delay for (boardName, delay) in boards]
        
    @inlineCallbacks
    def detectBoards(self):
        """Detect boards on the ethernet adapter managed by this board group.
        
        The autodetect operation is guarded by board group locks so that it
        will not conflict with sequences running on this board group.
        """
        try:
            # acquire all locks so we can ping boards without
            # interfering with board group operations
            for i in xrange(NUM_PAGES):
                yield self.pipeSemaphore.acquire()
            for pageLock in self.pageLocks:
                yield pageLock.acquire()
            yield self.runLock.acquire()
            yield self.readLock.acquire()
            
            # detect each board type in its own context
            detections = [self.detectDACs(), self.detectADCs()]
            answer = yield defer.DeferredList(detections, consumeErrors=True)
            found = []
            for success, result in answer:
                if success:
                    found.extend(result)
                else:
                    print 'autodetect error:'
                    result.printTraceback()
            
            # Clear detection packets which may be buffered in device contexts
            # TODO: check that this actually clears packets
            devices = self.devices()
            clears = []
            for dev in devices:
                clears.append(dev.clear().send())
            
            returnValue(found)
        finally:
            # release all locks once we're done with autodetection
            for i in xrange(NUM_PAGES):
                self.pipeSemaphore.release()
            for pageLock in self.pageLocks:
                pageLock.release()
            self.runLock.release()
            self.readLock.release()

    def detectDACs(self, timeout=1.0):
        """Try to detect DAC boards on this board group."""
        def callback(src, data):
            board = int(src[-2:], 16)
            build = dac.DAC.readback2BuildNumber(data)
            devName = '%s DAC %d' % (self.name, board)
            args = devName, self, self.server, self.port, board, build
            return (devName, args)
        macs = [dac.DAC.macFor(board) for board in range(256)]
        return self._doDetection(macs, dac.DAC.regPing(),
                                 dac.DAC.READBACK_LEN, callback)
    
    def detectADCs(self, timeout=1.0):
        """Try to detect ADC boards on this board group."""
        def callback(src, data):
            board = int(src[-2:], 16)
            build = adc.ADC.readback2BuildNumber(data)
            devName = '%s ADC %d' % (self.name, board)
            args = devName, self, self.server, self.port, board, build
            return (devName, args)
        macs = [adc.ADC.macFor(board) for board in range(256)]
        return self._doDetection(macs, adc.ADC.regPing(),
                                 adc.ADC.READBACK_LEN, callback)

    @inlineCallbacks
    def _doDetection(self, macs, packet, respLength, callback, timeout=1.0):
        """
        Try to detect a boards at the specified mac addresses.
        
        For each response of the correct length received within the timeout
        from one of the given mac addresses, the callback function will be
        called and should return data to be added to the list of found
        devices.
        """
        try:
            ctx = self.server.context()
            
            # prepare and send detection packets
            p = self.server.packet()
            p.connect(self.port)
            #p.source_mac(self.sourceMac)
            p.require_length(respLength)
            p.timeout(T.Value(timeout, 's'))
            p.listen()
            for mac in macs:
                p.destination_mac(mac)
                p.write(packet.tostring())
            yield p.send(context=ctx)
            # listen for responses
            start = time.time()
            found = []
            while (len(found) < len(macs)) and (time.time() - start < timeout):
                try:
                    src, dst, eth, data = yield self.server.read(context=ctx)
                    if src in macs:
                        devInfo = callback(src, data)
                        found.append(devInfo)
                except T.Error:
                    break # read timeout
            returnValue(found)
        finally:
            # expire the detection context
            yield self.cxn.manager.expire_context(self.server.ID, context=ctx)

    def devices(self):
        """
        Return a list of known device objects belonging to this board group.
        """
        return [dev for dev in self.fpgaServer.devices.values()
                    if dev.boardGroup == self]
        
    @inlineCallbacks
    def testMode(self, func, *a, **kw):
        """
        Call a function in test mode.
        
        This makes sure that all currently-executing pipeline stages
        are finished by acquiring the pipe semaphore for all pages,
        then runs the function, and finally releases the semaphore
        to allow the pipeline to continue.
        """
        for i in xrange(NUM_PAGES):
            yield self.pipeSemaphore.acquire()
        try:
            ans = yield func(*a, **kw)
            returnValue(ans)
        finally:
            for i in xrange(NUM_PAGES):
                self.pipeSemaphore.release()


    def makePackets(self, runners, page, reps, timingOrder, sync=249):
        """Make packets to run a sequence on this board group.

        Running a sequence has 4 stages:
        - Load memory and SRAM into all boards in parallel.
          If possible, this is done in the background using a separate
          page while another sequence is running.

        - Run sequence by firing a single packet that starts all boards.
          To ensure synchronization the slaves are started first, in
          daisy-chain order, followed at the end by the master.

        - Collect timing data to ensure that the sequence is finished.
          We instruct the direct ethernet server to collect the packets
          but not send them yet.  Once collected, direct ethernet triggers
          are used to immediately start the next sequence if one was
          loaded into the next page.

        - Read timing data.
          Having started the next sequence (if one was waiting) we now
          read the timing data collected by the direct ethernet server,
          process it and return it.

        This function prepares the LabRAD packets that will be sent for
        each of these steps, but does not actually send anything.  By
        preparing these packets in advance we save time later when we
        are in the time-critical pipeline sections
        
        
        loadPkts: list of packets, one for each board
        setupPkts: list of (packet,setup state). Only for ADC
        runPkts: wait, run, both. These packets are sent in the master
                 context, and are placed carefully in order so that the
                 master board runs last.
        collectPkts: list of packets, one for each board. These packets
                     tell the direct ethernet server to collect, and then
                     if successful, send triggers to the master context.
        readPkts: list of packets. Simply read back data from direct
                  ethernet buffer for each board's context.
        
        Packets generated by dac and adc objects are make with the
        context set to that device's context. This ensures that the
        packets have the right destination MAC and therefore arrive in
        the right place.
        """
        # dictionary of devices to be run
        runnerInfo = dict((runner.dev.devName, runner) for runner in runners)
        
        # upload sequence data (pipelined)
        loadPkts = []
        for board in self.boardOrder:
            if board in runnerInfo:
                runner = runnerInfo[board]
                isMaster = len(loadPkts) == 0
                p = runner.loadPacket(page, isMaster)
                if p is not None:
                    loadPkts.append(p)
        
        # setup board state (not pipelined)
        # Build a list of (setupPacket, setupState)
        setupPkts = []
        for board in self.boardOrder:
            if board in runnerInfo:
                runner = runnerInfo[board]
                p = runner.setupPacket()
                if p is not None:
                    setupPkts.append(p)
        # Run all boards (master last)
        # Set the first board which is both in the boardOrder and
        # which is also in the list of runners for this sequence as
        # the master. Any subsequent boards for which we have a runner
        # are set to slave mode, while subsequent unused boards are
        # set to idle mode. For example:
        # All boards:   000000
        # runners:      --XX-X
        # mode:           msis (i: idle, m: master, s: slave) -DTS
        boards = [] #List of (<device object>, <register bytes to write>)
        for board, delay in zip(self.boardOrder, self.boardDelays):
            if board in runnerInfo:
                runner = runnerInfo[board]
                slave = len(boards) > 0
                regs = runner.runPacket(page, slave, delay, sync)
                boards.append((runner.dev, regs))
            elif len(boards):
                # This board is after the master, but will not itself run, so
                # we put it in idle mode
                dev = self.fpgaServer.devices[board] # Look up device wrapper
                if isinstance(dev, dac.DAC):
                    regs = dev.regIdle(delay)
                    boards.append((dev, regs))
                elif isinstance(dev, adc.ADC):
                    # ADC boards always pass through signals, so no need for
                    # Idle mode
                    pass
        boards = boards[1:] + boards[:1] # move master to the end
        runPkts = self.makeRunPackets(boards)
        
        # collect and read (or discard) timing results
        seqTime = max(runner.seqTime for runner in runners)
        collectPkts = [runner.collectPacket(seqTime, self.ctx) \
                           for runner in runners]
        readPkts = [runner.readPacket(timingOrder) for runner in runners]
            
        return loadPkts, setupPkts, runPkts, collectPkts, readPkts

    def makeRunPackets(self, data):
        """Create packets to run a set of boards.
        
        There are two options as to how this can work, depending on
        whether the setup state from the previous run is the same as
        for this run.  If no changes to the setup state are required,
        then we can wait for triggers and immediately start the next
        run; this is what the 'both' packet does.  If the setup state
        has changed, we must wait for triggers, then send setup packets,
        and then start the next run.  This two-stage operation is what
        the 'wait' and 'run' packets do.  We create both here because
        we can't tell until it is our turn in the pipe which method
        will be used.
        """

        wait = self.server.packet(context=self.ctx)
        run = self.server.packet(context=self.ctx)
        both = self.server.packet(context=self.ctx)
        if LOGGING_PACKET:
            wait = LoggingPacket(wait, name='run=wait')
            run = LoggingPacket(run, name='run=run')
            both = LoggingPacket(both, name='run=both')
        # wait for triggers and discard them
        # The actual number of triggers to wait for will be decided
        # later. The 0 is a placeholder here.
        wait.wait_for_trigger(0, key='nTriggers')
        both.wait_for_trigger(0, key='nTriggers')
        # run all boards
        for dev, regs in data:
            bytes = regs.tostring()
            #We must switch to each board's destination MAC each time we
            #write data because our packets for the direct ethernet
            #server is in the main context of the board group, and
            #therefore does not have a specific destination MAC.
            run.destination_mac(dev.MAC).write(bytes)
            both.destination_mac(dev.MAC).write(bytes)
        return wait, run, both

    @inlineCallbacks
    def run(self, runners, reps, setupPkts, setupState, sync, getTimingData,
            timingOrder):
        """Run a sequence on this board group."""
        
        # check whether this sequence will fit in just one page
        if all(runner.pageable() for runner in runners):
            # lock just one page
            page = self.pageNums.next()
            pageLocks = [self.pageLocks[page]]
        else:
            # start on page 0 and set pageLocks to all pages.
            print 'Paging off: SRAM too long.'
            page = 0
            pageLocks = self.pageLocks
        
        # prepare packets
        pkts = self.makePackets(runners, page, reps, timingOrder, sync)
        loadPkts, boardSetupPkts, runPkts, collectPkts, readPkts = pkts
        
        # add setup packets from boards (ADCs) to that provided in the args
        # setupPkts is a list
        # setupState is a set
        setupPkts.extend(pkt for pkt, state in boardSetupPkts)
        setupState.update(state for pkt, state in boardSetupPkts)
        
        try:
            yield self.pipeSemaphore.acquire()
            try:
                # stage 1: load
                for pageLock in pageLocks: # lock pages to be written
                    yield pageLock.acquire()
                # Send load packets. Do not wait for response.
                # We already acquired the page lock, so sending data to
                # SRAM and memory is kosher at this time
                # XXX Need to check what "load packets" is for ADC and make
                # sure sending load packets here is ok.
                loadDone = self.sendAll(loadPkts, 'Load')
                # stage 2: run
                # Send a request for the run lock, do not wait for response.
                runNow = self.runLock.acquire()
                try:
                    yield loadDone # wait until load is finished.
                    yield runNow # Wait for acquisition of the run lock.
                    
                    # Set the number of triggers needed before we can actually
                    # run. We expect to get one trigger for each board that
                    # had to run and return data. This is the number of
                    # runners in the previous sequence.
                    waitPkt, runPkt, bothPkt = runPkts
                    waitPkt['nTriggers'] = self.prevTriggers
                    bothPkt['nTriggers'] = self.prevTriggers
                    # store the number of triggers for the next run
                    self.prevTriggers = len(runners)
                    
                    # If the passed in setup state setupState, or the current
                    # actual setup state, self.setupState are empty, we need
                    # to set things up. Also if the desired setup state isn't
                    # a subset of the actual one, we need to set up.
                    # XXX Check what setup state means for ADC. Should this
                    # include the trigger/demodulator tables or not?
                    needSetup = (not setupState) or (not self.setupState) or \
                                    (not (setupState <= self.setupState))
                    if needSetup:
                        # we require changes to the setup state so first, wait
                        # for triggers indicating that the previous run has
                        # collected.
                        # If this fails, something BAD happened!
                        r = yield waitPkt.send()
                        try:
                            # Then set up
                            # print "fpga server: type(setupPkts): ",type(setupPkts)
                            # for idx, sp in enumerate(setupPkts):
                                # print "type setupPkt[%d]: %s.  setupPkt: " % (idx, type(sp))
                                # print str(sp)
                                # for idx, rec in enumerate(sp._packet):
                                    # print "record %d types: %s, %s, %s, %s" % (idx, type(rec[0]), type(rec[1]), type(rec[2]), type(rec[3]))
                                    # print "record %d data %s,%s,%s,%s" % (idx, rec[0], rec[1], rec[2], rec[3])
                            # print("fpga server: run: sending setup packets")
                            yield self.sendAll(setupPkts, 'Setup')
                            # print setupPkts
                            self.setupState = setupState
                        except Exception:
                            # if there was an error, clear setup state
                            self.setupState = set()
                            raise
                        # and finally run the sequence
                        yield runPkt.send()
                    else:
                        # if this fails, something BAD happened!
                        r = yield bothPkt.send()
                    
                    # Keep track of how long the packet waited before being
                    # able to run.
                    # XXX How does this work? Why is r['nTriggers'] the wait
                    # time?
                    # print "fpga server: r['nTriggers']: %s" % (r['nTriggers'])
                    self.runWaitTimes.append(r['nTriggers']['s'])
                    if len(self.runWaitTimes) > 100:
                        self.runWaitTimes.pop(0)
                    
                    yield self.readLock.acquire() # wait for our turn to read
                    
                    # stage 3: collect
                    # Collect appropriate number of packets and then trigger
                    # the master context.
                    collectAll = defer.DeferredList( \
                        [p.send() for p in collectPkts], consumeErrors=True)
                finally:
                    # by releasing the runLock, we allow the next sequence to
                    # send its run packet. if our collect fails due to a
                    # timeout, however, our triggers will not all be sent to
                    # the run context, so that it will stay blocked until
                    # after we cleanup and send the necessary triggers
                    
                    # We now release the run lock. Other users will now be
                    # able to send their run packet to the direct ethernet,
                    # but the direct ethernet will not actually send run
                    # commands to the FPGA boards until the master context
                    # receives all expected triggers. These triggers are sent
                    # along with the collect packets, and succeed only if the
                    # collect commands do not time out. This means that the
                    # boards won't run until either our collect succeeds,
                    # meaning we're finished running and got all expected
                    # data, or we clean up from a timeout and manually send
                    # the necessary number of triggers. Note that we release
                    # the run lock IMMEDIATELY after sending the request to
                    # collect so that other users can get going ASAP.
                    # The direct ethernet server will allow other run commands
                    # to go as soon as our triggers are received, but only if
                    # that run command has been sent!
                    self.runLock.release()
                # Wait for data to be collected.
                results = yield collectAll
            finally:
                for pageLock in pageLocks:
                    pageLock.release()
            
            # check for a timeout and recover if necessary
            if not all(success for success, result in results):
                for success, result in results:
                    if not success:
                        result.printTraceback()
                yield self.recoverFromTimeout(runners, results)
                self.readLock.release()
                raise TimeoutError(self.timeoutReport(runners, results))
            
            # stage 4: read
            # no timeout, so go ahead and read data
            boardOrder = [runner.dev.devName for runner in runners]
            readAll = self.sendAll(readPkts, 'Read', boardOrder)
            self.readLock.release()
            #This line scales really badly with incrasing stats
            #At 9600 stats the next line takes 10s out of 20s per
            #sequence.
            results = yield readAll # wait for read to complete
            
            if getTimingData:
                # print("fpga server: run: %s"%(timingOrder,))
                answers = []
                # Cache of already-parsed data from a particular board.
                # Prevents un-flattening a packet more than once.
                extractedData = {}
                for dataChannelName in timingOrder:
                    # If dataChannelName has a :: in it, it's an ADC with specified demod
                    # channel
                    if "::" in dataChannelName:
                        boardName, channel = dataChannelName.split('::')
                        channel = int(channel)
                    elif 'DAC' in dataChannelName:
                        raise RuntimeError("DAC data readback not supported")
                    else:
                        raise RuntimeError('channel format not understood')
                    
                    # If we have already parsed the packet for this board, fetch the
                    # cached result.
                    if boardName in extractedData:
                        extracted = extractedData[boardName]
                        extracted = extracted[0][channel]
                    # Otherwise, extract the data, cache it, and add the relevant part
                    # to the list of returned data.
                    else:
                        idx = boardOrder.index(boardName)
                        runner = runners[idx]
                        result = [data for src, dest, eth, data in results[idx]['read']]
                        # print("fpga server: run: result is %s"%(result,))
                        # Array of all timing results (DAC)
                        extracted = runner.extract(result)
                        extractedData[boardName] = extracted
                        
                        # XXX I'm about to re-define extracted. This is ok
                        # because it's a tuple and won't mutate the thing in the
                        # cache, but it's bad and I should rename the variables.
                        
                        # XXX Ranges code needs to be updated. Next line obsolete.
                        # runner.ranges = extracted[1]
                        # Add extracted data to the list of data to be returned.
                        # If this is an ADC demod channel, grab that channel's
                        # data only
                        # print("fpga_server: extracted: %s"%(extracted,))
                        extracted = extracted[0]
                        # print("fpga_server: extacted no pkt counters: %s"%(type(extracted),))
                        # print("fpga_server: channel: %d"%(channel,))
                        extracted = extracted[channel]
                    answers.append(extracted)
                returnValue(tuple(answers))
        finally:
            self.pipeSemaphore.release()
    
    @inlineCallbacks
    def sendAll(self, packets, info, infoList=None):
        """Send a list of packets and wrap them up in a deferred list."""
        # Remove packets which contain no actual requests.
        packets = [p for p in packets if p._packet]
        results = yield defer.DeferredList([p.send() for p in packets],
                            consumeErrors=True)#[(success, result)...]
        if all(s for s, r in results):
            # return the list of results
            returnValue([r for s, r in results])
        else:
            # create an informative error message
            msg = 'Error(s) occured during %s:\n' % info
            if infoList is None:
                msg += ''.join(r.getBriefTraceback() \
                    for s, r in results if not s)
            else:
                for i, (s, r) in zip(infoList, results):
                    m = 'OK' if s else ('error!\n' + r.getBriefTraceback())
                    msg += str(i) + (': %s\n\n' % m)
            raise Exception(msg)
        
    def extractTiming(self, packets):
        """Extract timing data coming back from a readPacket."""
        data = ''.join(data[3:63] for data in packets)
        return np.fromstring(data, dtype='<u2').astype('u4')

    @inlineCallbacks
    def recoverFromTimeout(self, runners, results):
        """Recover from a timeout error so that pipelining can proceed.
        
        We clear the packet buffer for all boards, whether or not they
        succeeded. We then check how many time each board executed its SRAM
        sequence (or demod sequence for ADC boards), and store this value
        in the respective runner object. Finally, for failed boards we
        send a trigger to the master context.
        """
        print 'RECOVERING FROM TIMEOUT'
        #TODO: add a timeout to the read. Possibly use _sendRegister from
        #      dac.py
        for runner, (success, result) in zip(runners, results):
            ctx = None if success else self.ctx
            # 1. Clear packet buffer for this board
            yield runner.dev.clear().send()
            # 2. Ping the board to read its execution counter
            try:
                p = runner.dev.regPingPacket()
                p.timeout(U.Value(1.0, 's')).collect(1).read(1)
                resp = yield p.send()
                ans = resp.read
                # This if construction exists only because right now I have
                # processReadback as a module level function in dac.py,
                # whereas in adc.py it's a staticmethod of the ADC class.
                if isinstance(runner, dac.DacRunner):
                    count = runner.dev.\
                            processReadback(ans[0][3])['executionCounter']
                elif isinstance(runner, adc.AdcRunner):
                    count = runner.dev.processReadback(ans[0][3])\
                                ['executionCounter']
                runner.executionCount = count
            except Exception as e:
                print e
                raise Exception('Recover from error failed')
            # Finally, clear the packet buffer and send trigger if this was a
            # failed board
            finally:
                yield runner.dev.clear().send()
                if ctx is not None:
                    yield runner.dev.trigger(ctx).send()
        
    def timeoutReport(self, runners, results):
        """Create a nice error message explaining which boards timed out."""
        lines = ['Some boards failed:']
        for runner, (success, result) in zip(runners, results):
            line = runner.dev.devName + ': ' + ('OK' if success else 'timeout!') 
            line += ' Expected executions: %d  Actual: %d' \
                        %(runner.reps, runner.executionCount)
            lines.append(line)
        return '\n'.join(lines)


class FPGAServer(DeviceServer):
    """Server for GHz DAC and ADC boards.
    """
    name = 'GHz FPGAs'
    retries = 5
    
    @inlineCallbacks
    def initServer(self):
        self.boardGroups = {}
        yield DeviceServer.initServer(self)
    
    @inlineCallbacks
    def loadBoardGroupConfig(self):
        print 'Loading board group definitions from registry...'
        p = self.client.registry.packet()
        p.cd(['', 'Servers', 'GHz FPGAs'], True)
        p.get('boardGroups', True, [], key='boardGroups')
        ans = yield p.send()
        print 'Board group definitions loaded.'
        # validate board group definitions
        valid = True
        names = set()
        adapters = set()
        for name, server, port, boards in ans['boardGroups']:
            if name in names:
                print "Multiple board groups with name '%s'" % name
                valid = False
            names.add(name)
            if (server, port) in adapters:
                print "Multiple board groups for adapter (%s, %s)" % \
                    (server, port)
                valid = False
            adapters.add((server, port))
        if valid:
            self.boardGroupDefs = ans['boardGroups']
            print 'Board group definitions ok.'
        else:
            print 'Please fix the board group configuration.'
    
    @inlineCallbacks    
    def adapterExists(self, server, port):
        """Check whether the specified ethernet adapter exists."""
        cxn = self.client
        if server not in cxn.servers:
            returnValue(False)
        else:
            de = cxn.servers[server]
            adapters = yield de.adapters()
            if len(adapters):
                ports, names = zip(*adapters)
            else:
                ports, names = [], []
            returnValue(port in ports)
    
    @inlineCallbacks
    def findDevices(self):
        print 'Refreshing client connection...'
        cxn = self.client
        yield cxn.refresh()
        
        # reload the board group configuration from the registry
        yield self.loadBoardGroupConfig() #Creates self.boardGroupDefs
        config = dict(((server, port), (name, boards)) #The keys are tuples!
                      for name, server, port, boards in self.boardGroupDefs)

        # determine what board groups are to be added, removed and kept as is
        existing = set(self.boardGroups.keys())
        configured = set((server, port) for name, server, port, boards in \
                                                self.boardGroupDefs)
        
        additions = configured - existing
        removals = existing - configured
        keepers = existing - removals
        
        # check each addition to see whether the desired server/port exists
        for key in set(additions):
            server, port = key
            exists = yield self.adapterExists(server, port)
            if not exists:
                print "Adapter '%s' (port %d) does not exist. Group will not be added." % (server, port)
                additions.remove(key)
        
        # check each keeper to see whether the server/port still exists
        for key in set(keepers):
            server, port = key
            exists = yield self.adapterExists(server, port)
            if not exists:
                print "Adapter '%s' (port %d) does not exist. Group will be removed." % (server, port)
                keepers.remove(key)
                removals.add(key)                
        
        print 'Board groups to be added:', additions
        print 'Board groups to be removed:', removals
        
        # remove board groups which are no longer configured
        for key in removals:
            bg = self.boardGroups[key]
            del self.boardGroups[key]
            yield bg.shutdown()
        
        # add new board groups
        for server, port in additions:
            name, boards = config[server, port]
            print "Creating board group '%s': server='%s', port=%d" \
                      % (name, server, port)
            de = cxn.servers[server]
            boardGroup = BoardGroup(self, de, port) #Sets attributes
            yield boardGroup.init() #Gets context with direct ethernet
            self.boardGroups[server, port] = boardGroup
        
        # update configuration of all board groups and detect devices
        detections = []
        groupNames = []
        for (server, port), boardGroup in self.boardGroups.items():
            name, boards = config[server, port]
            boardGroup.configure(name, boards)
            detections.append(boardGroup.detectBoards()) #Board detection#
            groupNames.append(name)
        answer = yield defer.DeferredList(detections, consumeErrors=True)
        found = []
        for name, (success, result) in zip(groupNames, answer):
            if success:
                if len(result):
                    print "Devices detected on board group '%s':" % name
                    for devName, args in result:
                        print " ", devName
                else:
                    print "No devices detected on board group '%s'." % name
                found.extend(result)
            else:
                print "Autodetection failed on board group '%s':" % name
                result.printBriefTraceback(elideFrameworkCode=1)
        returnValue(found)
    
    def chooseDeviceWrapper(self, name, *args, **kw):
        """Choose which FPGA class to use for this device"""
        _, boardGroup, ethernetServer, port, boardNumber, build = args
        _, boardType, _ = name.rsplit(' ', 2)
        return fpga.REGISTRY[(boardType, build)]
    
    ## Trigger refreshes if a direct ethernet server connects or disconnects
    def serverConnected(self, ID, name):
        if "Direct Ethernet" in name:
            self.refreshDeviceList()
    
    def serverDisconnected(self, ID, name):
        if "Direct Ethernet" in name:
            self.refreshDeviceList()
    
    ## allow selecting different kinds of devices in each context
    def selectedDAC(self, context):
        dev = self.selectedDevice(context)
        if not isinstance(dev, dac.DAC):
            raise Exception("selected device is not a DAC board")
        return dev
    
    def selectedADC(self, context):
        dev = self.selectedDevice(context)
        if not isinstance(dev, adc.ADC):
            raise Exception("selected device is not an ADC board")
        return dev
    
    def getBoardGroup(self, name):
        """Find a board group by name."""
        for boardGroup in self.boardGroups.values():
            if boardGroup.name == name:
                return boardGroup
        raise Exception("Board group '%s' not found." % name)
    
    def initContext(self, c):
        """Initialize a new context."""
        c['daisy_chain'] = []
        c['timing_order'] = None
        c['master_sync'] = 249
    
    ## remote settings
    
    @setting(1, 'List Devices', boardGroup='s', returns='*(ws)')
    def list_devices(self, c, boardGroup=None):
        """List available devices.
        
        If the optional boardGroup argument is specified, then only those
        devices belonging to that board group will be included.
        """
        IDs, names = self.deviceLists()
        devices = zip(IDs, names)
        if boardGroup is not None:
            # Make sure this board group exists
            bg = self.getBoardGroup(boardGroup)
            devices = [(id, name) for (id, name) in devices if \
                           name.startswith(boardGroup)]
        return devices
    
    @setting(10, 'List Board Groups', returns='*s')
    def list_board_groups(self, c):
        """Get a list of existing board groups."""
        return sorted(bg.name for bg in self.boardGroups.values())
    
    @setting(11, 'List DACs', boardGroup='s', returns='*s')
    def list_dacs(self, c, boardGroup=None):
        """List available DACs.
        
        If the optional boardGroup argument is specified, then only those
        devices belonging to that board group will be included.
        """
        IDs, names = self.deviceLists()
        
        devices = zip(IDs, names)
        devices = [name for (id, name) in devices if 'DAC' in name]
        if boardGroup is not None:
            # Make sure this board group exists
            bg = self.getBoardGroup(boardGroup)
            devices = [name for name in devices if name.startswith(boardGroup)]
        return devices
    
    @setting(12, 'List ADCs', boardGroup='s', returns='*s')
    def list_adcs(self, c, boardGroup=None):
        """List available ADCs.
        
        If the optional boardGroup argument is specified, then only those
        devices belonging to that board group will be included.
        """
        IDs, names = self.deviceLists()
        
        devices = zip(IDs, names)
        devices = [name for (id, name) in devices if 'ADC' in name]
        if boardGroup is not None:
            # Make sure this board group exists
            bg = self.getBoardGroup(boardGroup)
            devices = [name for name in devices if name.startswith(boardGroup)]
        return devices
    
    ## Memory and SRAM upload

    @setting(20, 'SRAM', data='*w: SRAM Words to be written', returns='')
    def dac_sram(self, c, data):
        """Writes data to the SRAM at the current starting address.
        
        Data can be specified as a list of 32-bit words, or a pre-flattened
        byte string.
        """
        # Dev is a unique DAC device object. The command
        # d = c.setdefault(dev, {})
        # uses dev as a key in this context pointing at this context's
        # parameters for this DAC object.
        dev = self.selectedDAC(c)
        d = c.setdefault(dev, {})
        if not isinstance(data, str):
            data = np.array(data, dtype='<u4').tostring()
        d['sram'] = data

    @setting(21, 'SRAM dual block',
             block0='*w: SRAM Words for first block',
             block1='*w: SRAM Words for second block',
             delay='w: nanoseconds to delay',
             returns='')
    def dac_sram_dual_block(self, c, block0, block1, delay):
        """
        Writes a dual-block SRAM sequence with a delay between the two blocks.
        
        COMMENTS
        block0 and block1 should be passed in as byte strings.
        Recall that each SRAM word is 4 bytes ;)
        
        The amount of time spent idling between blocks is
        SRAM_DELAY_LEN * N where N is the value sent into register
        d[19] (zero indexed).
        """
        dev = self.selectedDAC(c)
        d = c.setdefault(dev, {})
        sram = d.get('sram', '')
        #Convert SRAM blocks to byte strings
        if not isinstance(block0, str):
            block0 = np.array(block0, dtype='<u4').tostring()
        if not isinstance(block1, str):
            block1 = np.array(block1, dtype='<u4').tostring()
        #Block delays come in chunks of 1024ns. Thus we need to package
        #the desired delay into an integral number of delay blocks, with
        #the difference made up by adding data to block1
        delayPad = delay % dev.SRAM_DELAY_LEN
        delayBlocks = delay / dev.SRAM_DELAY_LEN
        # add padding to beginning of block1 to get delay right
        block1 = block0[-4:] * delayPad + block1
        # add padding to end of block1 to ensure that its length is a
        # multiple of 4
        endPad = 4 - (len(block1) / 4) % 4
        if endPad != 4:
            block1 = block1 + block1[-4:] * endPad
        d['sram'] = (block0, block1, delayBlocks)

    @setting(22, 'SRAM Address', addr='w', returns='')
    def dac_sram_address(self, c, addr):
        """Sets address for next SRAM write.
        
        DEPRECATED: This function no longer does anything and you should not
        call it!
        """
        dev = self.selectedDAC(c)
        print 'Deprecation warning: SRAM Address called unnecessarily'

    @setting(30, 'Memory', data='*w: Memory Words to be written', returns='')
    def dac_memory(self, c, data):
        """Writes data to the Memory at the current starting address."""
        dev = self.selectedDAC(c)
        d = c.setdefault(dev, {})
        d['mem'] = data
    
    # ADC configuration (pre v7)
    
    @setting(40, 'ADC Filter Func', bytes='s', stretchLen='w', stretchAt='w',
                                    returns='')
    def adc_filter_func(self, c, bytes, stretchLen=0, stretchAt=0):
        """
        Set the filter function to be used with the selected ADC board.
        (ADC only)
        
        Each byte specifies the filter weight for a 4ns interval.  In addition,
        you can specify a stretch which will repeat a value in the middle of
        the filter for the specified length (in 4ns intervals).
        """
        raise Exception("Deprecated for ADC V7")
        dev = self.selectedADC(c)
        assert len(bytes) <= dev.FILTER_LEN, \
            'Filter function max length is %d' % dev.FILTER_LEN
        bytes = np.fromstring(bytes, dtype='<u1')
        d = c.setdefault(dev, {})
        d['filterFunc'] = bytes
        d['filterStretchLen'] = stretchLen
        d['filterStretchAt'] = stretchAt
    
    @setting(41, 'ADC Trig Magnitude', channel='w', sineAmp='w',
                                       cosineAmp='w', returns='')
    def adc_trig_magnitude(self, c, channel, sineAmp, cosineAmp):
        """
        Set the magnitude of sine and cosine functions for a demodulation
        channel. (ADC only)
        
        
        The channel indicates which demodulation channel to use, in the range
        0 to N-1 where N is the number of channels (currently 4).
        sineAmp and cosineAmp are the magnitudes of the respective sine and
        cosine functions, ranging from 0 to 255.
        
        Data is stored in c[dev][channel], which is a dictionary. The following
        keys are set:
            'sineAmp' - int: Amplitude of sine lookup table
            'cosineAmp' - int: Amplitude of cosine lookup table
            'sine' - ndarray (uint8): sine table data
            'cosine' - ndarray (uint8): cosine table data
        
        Why do we store both eg. 'sineAmp' and 'sine'? The 'sine' key stores a
        numpy array of the actual data for the sine lookup table. The
        amplitudes are stored so that we can detect changes. If the trig table
        amplitudes change, then we need to re-upload the data to the board in
        a setup packet.
        """
        # Get the ADC selected in this context. Raise an exception if selected
        # device is not an ADC
        raise Exception("Deprecated for ADC V7")
        dev = self.selectedADC(c)
        assert 0 <= channel < dev.DEMOD_CHANNELS, \
            'channel out of range: %d' % channel
        assert 0 <= sineAmp <= dev.TRIG_AMP, \
            'sine amplitude out of range: %d' % sineAmp
        assert 0 <= cosineAmp <= dev.TRIG_AMP, \
            'cosine amplitude out of range: %d' % cosineAmp
        d = c.setdefault(dev, {})
        ch = d.setdefault(channel, {})
        ch['sineAmp'] = sineAmp
        ch['cosineAmp'] = cosineAmp
        N = dev.LOOKUP_TABLE_LEN
        phi = np.pi/2 * (np.arange(N) + 0.5) / N
        # Sine waveform for this channel
        ch['sine'] = np.floor(sineAmp * np.sin(phi) + 0.5).astype('uint8')
        # Cosine waveform for this channel, note that the function is still a
        # SINE function!
        ch['cosine'] = np.floor(cosineAmp * np.sin(phi) + 0.5).astype('uint8')
    
    @setting(42, 'ADC Demod Phase', channel='w', dPhi='i', phi0='i',
             returns='')
    def adc_demod_frequency(self, c, channel, dPhi, phi0=0):
        """
        Set the trig table address step and initial phase for a demodulation
        channel. (ADC only)
        
        dPhi: number of trig table addresses to step through each time sample
        (2ns for first version of board).
        
        The trig lookup table address is stored in a 16 bit accumulator. The
        lookup table has 1024 addresses. The six least significant bits are
        ignored when accessing the accululator to read the lookup table. This
        gives sub-address timing resolution.
        
        The physical demodulation frequency is related to dPhi as follows:
        Since the least significant bits of the accumulator are dropped, it
        takes 2^6=64 clicks to increment the lookup table address by one.
        Therefore, if we incriment the accumulator by 1 click each time step
        then we go through
        ((1/64)*Address)*(1 cycle/1024 Address) = (2**-16)cycle.
        This happens every 2ns, so we have
        2**-16 cycle/2ns = 2**-17 GHz = 7.629 KHz
        Therefore, dPhi = desiredFrequency/7629Hz.
        
        The initial phase works the same way. We specify a sixteen bit number
        to determine the initial lookup table address, but only the six least
        significant bits are dropped. Since the trig table is 2^10 addresses
        long and once trip through the table is one cycle, you have to
        increment by 2^16 clicks to go through the table once. Therefore, the
        starting phase is determined as phi0 = phase0*(2^16) where phase0 is
        the starting phase in CYCLES!
        """
        # 16 bit 2's compliment number for demod trig function
        raise Exception("Deprecated for ADC V7")
        assert -2**15 <= dPhi < 2**15, 'delta phi out of range'
        assert -2**15 <= phi0 < 2**15, 'phi0 out of range'
        dev = self.selectedADC(c)
        d = c.setdefault(dev, {})
        ch = d.setdefault(channel, {})
        ch['dPhi'] = dPhi
        ch['phi0'] = phi0


    @setting(44, 'ADC Run Mode', mode='s', returns='')
    def adc_run_mode(self, c, mode):
        """
        Set the run mode for the current ADC board, 'average' or 'demodulate'.
        (ADC only)
        """
        # print "setting ADC run mode to: ", mode
        mode = mode.lower()
        assert mode in ['average', 'demodulate'], 'unknown mode: "%s"' % mode
        dev = self.selectedADC(c)
        # if c[dev] exists, d = c[dev]. Otherwise d = {} and c[dev] = {}
        d = c.setdefault(dev, {})
        # d points to the same object as c[dev], which is MUTABLE. Mutating d
        # mutates c[dev]!!!
        d['runMode'] = mode

    @setting(45, 'Start Delay', delay='w', returns='')
    def start_delay(self, c, delay):
        dev = self.selectedDevice(c)
        d = c.setdefault(dev, {})
        d['startDelay'] = delay

    @setting(46, 'ADC Demod Range',
             returns='i{Imax}, i{Imin}, i{Qmax}, i{Qmin}')
    def adc_demod_range(self, c):
        """
        Get the demodulation ranges for the last sequence run in this context.
        (ADC only)
        """
        raise Exception("Deprecated for ADC V7")
        dev = self.selectedADC(c)
        return c[dev]['ranges']

    # ADC configuration (v7)
        
    @setting(47, 'ADC Trigger Table', data='*(i, i, i, i)', returns='')
    def adc_trigger_table(self, c, data):
        """
        Set the ADC trigger table
        
        data: A list of (count, delay, length, rchan) tuples, one per jump table entry.
        assume that all channels are read out for every trigger (rchan set by nDemod).
        """
        dev = self.selectedADC(c)
        info = c.setdefault(dev, {})
        info['triggerTable'] = data
    
    @setting(48, 'ADC Mixer Table', channel='w', data='*2i {Nx2 array of IQ values}')
    def adc_mixer_table(self, c, channel, data):
        """
        Set the ADC mixer table for a given demodulator channel
        """
        dev = self.selectedADC(c)
        info = c.setdefault(dev, {})
        channel = info.setdefault(channel, {})
        channel['mixerTable'] = data

    # multiboard sequence execution

    @setting(50, 'Run Sequence', reps='w', getTimingData='b',
                             setupPkts='?{(((ww), s, ((s?)(s?)(s?)...))...)}',
                             setupState='*s',
                             returns=['*4i',''])
    def run_sequence(self, c, reps=30, getTimingData=True, setupPkts=[],
                     setupState=[]):
        """Executes a sequence on one or more boards.

        reps:
            specifies the number of repetitions ('stats') to perform
            (rounded up to the nearest multiple of 30).

        getTimingData:
            specifies whether timing data should be returned.
            the timing data will be returned for those boards
            specified by the "Timing Order" setting, and in
            the order specified there as well.

        setupPkts:
            specifies packets to be sent to other servers before this
            sequence is run, e.g. to set the microwave frequency.
            
        setupState:
            a list of strings describing the setup state for this point.
            if this matches the last setup state used (up to reordering),
            the setup packets will not be sent for this point.  For example,
            the setupState might describe the amplitude and frequency of
            the various microwave sources for this sequence.
            
        If only DAC boards are run and all boards return the same number of
        results (because all boards have the same number of timer calls),
        then a 2D list of results of type *2w will be returned.  Otherwise,
        a cluster of results will be returned, in the order specified by
        timing order.  Individual DAC boards always return *w; ADC boards in
        average mode return (*i,{I} *i{Q}); and ADC boards in demodulate
        mode also return (*i,{I} *i{Q}) for each channel.
        """
        # determine timing order
        if getTimingData:
            if c['timing_order'] is None:
                if len(c['daisy_chain']):
                    # Changed in this version: require timing order to be
                    # specified for multiple boards.
                    raise Exception('You must specify a timing order to get data back from multiple boards')
                else:
                    # Only running one board, which must be a DAC, so just get
                    # timing from it.
                    timingOrder = [d.devName for d in devs]
            else:
                timingOrder = c['timing_order']
        else:
            timingOrder = []
        
        #Round reps to multiple of 30 if DACs are in timing order
        for chan in timingOrder:
            if 'DAC' in chan:
                # Round stats up to multiple of the timing packet length
                reps += dac.DAC.TIMING_PACKET_LEN - 1
                reps -= reps % dac.DAC.TIMING_PACKET_LEN
                break
        
        if len(c['daisy_chain']):
            # run multiple boards, with first board as master
            devs = [self.getDevice(c, name) for name in c['daisy_chain']]
        else:
            # run the selected device only (must be a DAC)
            devs = [self.selectedDAC(c)]

        # check to make sure that all boards are in the same board group
        if len(set(dev.boardGroup for dev in devs)) > 1:
            raise Exception("Can only run multiboard sequence if all boards are in the same board group!")
        bg = devs[0].boardGroup
        
        # build a list of runners which have necessary sequence information
        # for each board
        # print "fpga server: buildRunner reps: %s" % (reps,)
        runners = [dev.buildRunner(reps, c.get(dev, {})) for dev in devs]
        
        # build setup requests
        setupReqs = processSetupPackets(self.client, setupPkts)

        # run the sequence, with possible retries if it fails
        retries = self.retries
        attempt = 1
        while True:
            try:
                ans = yield bg.run(runners, reps, setupReqs, set(setupState),
                                   c['master_sync'], getTimingData,
                                   timingOrder)
                # For ADCs in demodulate mode, store their I and Q ranges to
                # check for possible clipping.
                for runner in runners:
                    if getTimingData and isinstance(runner, adc.AdcRunner) and \
                      runner.runMode == 'demodulate' and \
                      runner.dev.devName in timingOrder:
                        c[runner.dev]['ranges'] = runner.ranges
                returnValue(ans)
            except TimeoutError, err:
                # log attempt to stdout and file
                import os
                userpath = os.path.expanduser('~')
                logpath = os.path.join(userpath, 'dac_timeout_log.txt')
                with open(logpath, 'a') as logfile:
                    print 'attempt %d - error: %s' % (attempt, err)
                    print >>logfile, 'attempt %d - error: %s' % (attempt, err)
                    if attempt == retries:
                        print 'FAIL!'
                        print >>logfile, 'FAIL!'
                        #TODO: notify users via SMS
                        raise
                    else:
                        print 'retrying...'
                        print >>logfile, 'retrying...'
                        attempt += 1
    
    @setting(52, 'Daisy Chain', boards='*s', returns='*s')
    def sequence_boards(self, c, boards=None):
        """
        Set or get the boards to run.
        
        The actual daisy chain order is determined automatically, as
        configured in the registry for each board group. This setting controls
        which set of boards to run, but does not determine the order. Set
        daisy_chain to an empty list to run the currently-selected board only.
        
        DACs not listed here will be set to idle mode, and will pass the
        daisychain pulse through to the next board.
        
        ADCs always pass the daisychain pulse.
        """
        if boards is None:
            boards = c['daisy_chain']
        else:
            c['daisy_chain'] = boards
        return boards

    @setting(54, 'Timing Order', boards='*s', returns='*s')
    def sequence_timing_order(self, c, boards=None):
        """Set or get the timing order for boards.
        
        This specifies the boards from which you want to receive timing
        data, and the order in which the timing data should be returned.
        In addition, this will determine what kind of boards will return
        data (ADCs or DACs).  For ADC boards, the data specified here must
        agree with the selection made for run mode for that board.
        
        To get DAC timing data or ADC data in average mode, specify the
        device name as a string.  To get ADC data in demodulation mode,
        specify a string in the form "<device name>::<channel>" where
        channel is the demodulation channel number.
        
        Note that you can get data from more than one demodulation channel,
        so that a given ADC board can appear multiple times in the timing
        order, however each ADC board must be run either in average mode
        or demodulation mode, not both.
        
        Note that the boards parameter must be a list of strings, *s! If you
        send in a single string, pylabrad will accept it as a *s but it will
        be treated as a list of single character strings and you'll get
        unexpected behavior. For example, if you send in 'abcde' it will be
        treated like ['a','b','c','d','e'].
        
        Parameters:
        boards: INSERT EXAMPLE!!!
        """
        if boards is None:              #Get timing order
            boards = c['timing_order']
        else:                           #Set timing order
            c['timing_order'] = boards

        return boards

    @setting(55, 'Master Sync', sync='w', returns='w')
    def sequence_master_sync(self, c, sync=None):
        """Set or get the master sync.
        
        This specifies a counter that determines when the master
        is allowed to start, to control the microwave phase.  The
        default is 249, which sets the master to start only every 1 us.
        """
        if sync is None:
            sync = c['master_sync']
        else:
            c['master_sync'] = sync
        return sync

    @setting(59, 'Performance Data', returns='*((sw)(*v, *v, *v, *v, *v))')
    def sequence_performance_data(self, c):
        """Get data about the pipeline performance.
        
        For each board group (as defined in the registry),
        this returns times for:
            page lock (page 0)
            page lock (page 1)
            run lock
            run packet (on the direct ethernet server)
            read lock

        If the pipe runs dry, the first time that will go to zero will
        be the run packet wait time.  In other words, if you have non-zero
        times for the run-packet wait, then the pipe is saturated,
        and the experiment is running at full capacity.
        """
        ans = []
        for (server, port), group in sorted(self.boardGroups.items()):
            pageTimes = [lock.times for lock in group.pageLocks]
            runTime = group.runLock.times
            runWaitTime = group.runWaitTimes
            readTime = group.readLock.times
            ans.append(((server, port), (pageTimes[0], pageTimes[1], runTime,
                                         runWaitTime, readTime)))
        return ans
    
    @setting(200, 'PLL Init', returns='')
    def pll_init(self, c, data):
        """Sends the initialization sequence to the PLL. (DAC and ADC)
    
        The sequence is [0x1FC093, 0x1FC092, 0x100004, 0x000C11].
        """
        dev = self.selectedDevice(c)
        yield dev.initPLL()
    
    @setting(201, 'PLL Reset', returns='')
    def pll_reset(self, c):
        """Resets the FPGA internal GHz serializer PLLs. (DAC only)"""
        dev = self.selectedDAC(c)
        yield dev.resetPLL()
    
    @setting(202, 'PLL Query', returns='b')
    def pll_query(self, c):
        """
        Checks the FPGA internal GHz serializer PLLs for lock failures.
        (DAC and ADC)
        
        Returns True if the PLL has lost lock since the last reset.
        """
        dev = self.selectedDevice(c)
        unlocked = yield dev.queryPLL()
        returnValue(unlocked)

    @setting(203, 'Build Number', returns='s')
    def build_number(self, c):
        """Gets the build number of selected device (DAC and ADC)"""
        dev = self.selectedDevice(c)
        buildNumber = yield dev.buildNumber()
        returnValue(buildNumber)
    
    @setting(204, 'Execution count', returns='i')
    def execution_counter(self, c):
        """Query sequence executions since last start command"""
        dev = self.selectedDevice(c)
        count = yield dev.executionCount()
        returnValue(int(count))
    
    @setting(1080, 'DAC Debug Output', data='wwww', returns='')
    def dac_debug_output(self, c, data):
        """Outputs data directly to the output bus. (DAC only)"""
        dev = self.selectedDAC(c)
        yield dev.debugOutput(*data)
    
    @setting(1081, 'DAC Run SRAM', data='*w', loop='b', blockDelay='w',
                                   returns='')
    def dac_run_sram(self, c, data, loop=False, blockDelay=0):
        """Loads data into the SRAM and executes as master. (DAC only)
        
        If loop is True, the sequence will be repeated forever,
        otherwise it will be executed just once.  Sending
        an empty list of data will clear the SRAM.  The blockDelay
        parameters specifies the number of microseconds to delay
        for a multiblock sequence.
        """
        if not len(data):
            return

        if len(data) < 20:
            # pad out to 20 with zeros
            d2 = np.zeros(20)
            d2[0:len(data)] = data
            data = d2
            data = list(data) + [data[0]] * (20-len(data))

        dev = self.selectedDAC(c)
        yield dev.runSram(data, loop, blockDelay)

    @setting(1082, "Add jump table entry", name='s', arg=['ww{IDLE}', 'www{JUMP}', 'w{NOP,END}', 'wwww{CYCLE}'])
    def add_jt_entry(self, c, name, arg=None):
        dev = self.selectedDAC(c)
        assert(isinstance(dev, dac.DAC_Build13))
        d = c.setdefault(dev, {})
        entries = d.setdefault('jt_entries', [])
        if name == 'CHECK':
            raise NotImplementedError("Check not implemented yet")
        elif name == 'IDLE':
            from_address, idle_duration_ns = arg
            if idle_duration_ns % 4 != 0:
                raise ValueError("Idle duration must be divisible by four")
            op = jumpTable.IDLE(idle_duration_ns//4)
            entry = jumpTable.JumpEntry(from_address, 0, op)
            entries.append(entry)
        elif name == 'JUMP':
            from_address, to_address, jt_idx = arg
            op = jumpTable.JUMP(jt_idx)
            entry = jumpTable.JumpEntry(from_address, to_address, op)
            entries.append(entry)
        elif name == 'CYCLE':
            from_address, to_address, jt_idx, counter_idx = arg
            if counter_idx >= dev.NUM_COUNTERS:
                raise ValueError("Cannot specify counter > {0} (you said {1})".format(dev.NUM_COUNTERS, counter_idx))
            entries.append(jumpTable.JumpEntry(from_address, to_address, jumpTable.CYCLE(counter_idx, jt_idx)))
        elif name == 'NOP':
            from_address = int(arg)
            entries.append(jumpTable.JumpEntry(from_address, 0, jumpTable.NOP))
        elif name == 'END':
            from_address = int(arg)
            entries.append(jumpTable.JumpEntry(from_address, 0, jumpTable.END))

    @setting(1083, "Clear jump table")
    def clear_jt(self, c):
        dev = self.selectedDAC(c)
        d = c.setdefault(dev, {})
        d['jt_entries'] = []
        d['jt_counters'] = []

    @setting(1084, "Set Jump Table Counters", counters='*w')
    def set_jt_counters(self, c, counters):
        dev = self.selectedDAC(c)
        d = c.setdefault(dev, {})
        assert(isinstance(dev, dac.DAC_Build13))
        if len(counters) >= dev.NUM_COUNTERS:
            raise ValueError("More than {0} counters specified: '{1}'".format(dev.NUM_COUNTERS, counters))
        d['jt_counters'] = counters


    
    @setting(1100, 'DAC I2C', data='*w', returns='*w')
    def dac_i2c(self, c, data):
        """Runs an I2C Sequence (DAC only)
        
        The entries in the WordList to be sent have the following meaning:
          0..255 : send this byte
          256:     read back one byte without acknowledging it
          512:     read back one byte with ACK
          1024:    send data and start new packet
        For each 256 or 512 entry in the WordList to be sent, the read-back
        byte is appended to the returned WordList. In other words: the length
        of the returned list is equal to the count of 256's and 512's in the
        sent list.
        """
        dev = self.selectedDAC(c)
        
        # split a list into sublists delimited by a sentinel value
        def partition(l, sentinel):
            if len(l) == 0:
                return []
            try:
                i = l.index(sentinel) # find next occurence of sentinel
                rest = partition(l[i+1:], sentinel) # partition rest of list
                if i > 0:
                    return [l[:i]] + rest
                else:
                    return rest
            except ValueError: # no more sentinels
                return [l]
            
        # split data into packets delimited by I2C_END
        pkts = partition(data, I2C_END)
        
        return dev.runI2C(pkts)
    
    @setting(1110, 'DAC LEDs', data=['w', 'bbbbbbbb'], returns='w')
    def dac_leds(self, c, data):
        """Sets the status of the 8 I2C LEDs. (DAC only)"""
        dev = self.selectedDAC(c)
        
        if isinstance(data, tuple):
            # convert to a list of digits, and interpret as binary int
            data = long(''.join(str(int(b)) for b in data), 2)
        
        pkts = [[200, 68, data & 0xFF]] # 192 for build 1
        yield dev.runI2C(pkts)  
        returnValue(data)
    
    @setting(1120, 'DAC Reset Phasor', returns='b: phase detector output')
    def dac_reset_phasor(self, c):
        """Resets the clock phasor. (DAC only)"""
        dev = self.selectedDAC(c)

        pkts = [[152, 0, 127, 0],  # set I to 0 deg
                [152, 34, 254, 0], # set Q to 0 deg
                [112, 65],         # set enable bit high
                [112, 193],        # set reset high
                [112, 65],         # set reset low
                [112, 1],          # set enable low
                [113, I2C_RB]]     # read phase detector

        r = yield dev.runI2C(pkts)
        returnValue((r[0] & 1) > 0)

    @setting(1121, 'DAC Set Phasor',
                  data=[': poll phase detector only',
                        'v[rad]: set angle (in rad, deg, \xF8, \', or ")'],
                  returns='b: phase detector output')
    def dac_set_phasor(self, c, data=None):
        """
        Sets the clock phasor angle and reads the phase detector bit.
        (DAC only)
        """
        dev = self.selectedDAC(c)

        if data is None:
            pkts = [[112, 1],
                    [113, I2C_RB]]
        else:
            sn = int(round(127 + 127*np.sin(data))) & 0xFF
            cs = int(round(127 + 127*np.cos(data))) & 0xFF
            pkts = [[152,  0, sn, 0],
                    [152, 34, cs, 0],
                    [112, 1],
                    [113, I2C_RB]]
                   
        r = yield dev.runI2C(pkts)
        returnValue((r[0] & 1) > 0)

    @setting(1130, 'DAC Vout', chan='s', V='v[V]', returns='w')
    def dac_vout(self, c, chan, V):
        """
        Sets the output voltage of any Vout channel, A, B, C or D.
        (DAC only)
        """
        cmd = dac.DAC.getCommand({'A': 16, 'B': 18, 'C': 20, 'D': 22}, chan)
        dev = self.selectedDAC(c)
        val = int(max(min(round(V*0x3333), 0x10000), 0))
        pkts = [[154, cmd, (val >> 8) & 0xFF, val & 0xFF]]
        yield dev.runI2C(pkts)
        returnValue(val)

    @setting(1135, 'DAC Ain', returns='v[V]')
    def dac_ain(self, c):
        """Reads the voltage on Ain. (DAC only)"""
        dev = self.selectedDAC(c)
        pkts = [[144, 0],
                [145, I2C_RB_ACK, I2C_RB]]
        r = yield dev.runI2C(pkts)
        returnValue(T.Value(((r[0] << 8) + r[1]) / 819.0, 'V'))

    @setting(1200, 'DAC PLL', data='*w', returns='*w')
    def dac_pll(self, c, data):
        """Sends a sequence of commands to the PLL. (DAC only)

        The returned WordList contains any read-back values.
        It has the same length as the sent list.
        """
        dev = self.selectedDAC(c)
        return dev.runSerial(1, data)

    @setting(1204, 'DAC Serial Command', chan='s', data='*w', returns='*w')
    def dac_cmd(self, c, chan, data):
        """Send a sequence of commands to either DAC. (DAC only)

        The DAC channel must be either 'A' or 'B'.
        The returned list of words contains any read-back values.
        It has the same length as the sent list.
        """
        cmd = dac.DAC.getCommand({'A': 2, 'B': 3}, chan)
        dev = self.selectedDAC(c)
        return dev.runSerial(cmd, data)

    @setting(1206, 'DAC Clock Polarity', chan='s', invert='b', returns='b')
    def dac_pol(self, c, chan, invert):
        """Sets the clock polarity for either DAC. (DAC only)"""
        dev = self.selectedDAC(c)
        yield dev.setPolarity(chan, invert)
        returnValue(invert)

    @setting(1220, 'DAC Init', chan='s', signed='b', returns='b')
    def dac_init(self, c, chan, signed=False):
        """Sends an initialization sequence to either DAC. (DAC only)
        
        For unsigned data, this sequence is 0026, 0006, 1603, 0500
        For signed data, this sequence is 0024, 0004, 1603, 0500
        """
        cmd = dac.DAC.getCommand({'A': 2, 'B': 3}, chan)
        dev = self.selectedDAC(c)
        pkt = [0x0024, 0x0004, 0x1603, 0x0500] if signed else \
              [0x0026, 0x0006, 0x1603, 0x0500]
        yield dev.runSerial(cmd, pkt)
        returnValue(signed)

    @setting(1221, 'DAC LVDS', chan='s', optimizeSD='b', data='w',
                               returns='bwww(*w*b*b)w')
    def dac_lvds(self, c, chan, optimizeSD=False, data=None):
        """
        Set or determine DAC LVDS phase shift and return y, z check data.
        (DAC only)
        
        If optimizeSD=False but sd is None, sd will be set to a value
        retrieved from the registry entry for this board.
        
        Returns success, MSD, MHD, SD, timing profile, checkHex
        """
        cmd = dac.DAC.getCommand({'A': 2, 'B': 3}, chan)
        dev = self.selectedDAC(c)
        ans = yield dev.setLVDS(cmd, data, optimizeSD)
        returnValue(ans)

    @setting(1222, 'DAC FIFO', chan='s', targetFifo='w', returns='bbiww')
    def dac_fifo(self, c, chan, targetFifo=None):
        """Adjust FIFO buffer. (DAC only)
        
        If no targetFifo is provided, the target FIFO will be retrieved from
        the registry entry for this board.
        
        If no PHOF can be found to get an acceptable FIFO counter, PHOF will
        be returned as -1, and success will be False.
        
        Returns success, clock polarity, PHOF, number of tries, FIFO counter
        """
        op = dac.DAC.getCommand({'A': 2, 'B': 3}, chan)
        dev = self.selectedDAC(c)
        ans = yield dev.setFIFO(chan, op, targetFifo)
        returnValue(ans)

    @setting(1223, 'DAC Cross Controller', chan='s', delay='i', returns='i')
    def dac_xctrl(self, c, chan, delay=0):
        """Sets the cross controller delay on either DAC. (DAC only)

        Range for delay is -63 to 63.
        """
        dev = self.selectedDAC(c)
        cmd = dac.DAC.getCommand({'A': 2, 'B': 3}, chan)
        if delay < -63 or delay > 63:
            raise T.Error(11, 'Delay must be between -63 and 63')

        seq = [0x0A00, 0x0B00 - delay] if delay < 0 \
            else [0x0A00 + delay, 0x0B00]
        yield dev.runSerial(cmd, seq)
        returnValue(delay)

    @setting(1225, 'DAC BIST', chan='s', data='*w', returns='b(ww)(ww)(ww)')
    def dac_bist(self, c, chan, data):
        """Run a BIST on the given SRAM sequence. (DAC only)
        
        Returns success, theory, LVDS, FIFO
        """
        cmd, shift = dac.DAC.getCommand({'A': (2, 0), 'B': (3, 14)}, chan)
        dev = self.selectedDAC(c)
        ans = yield dev.runBIST(cmd, shift, data)
        # This is coming back with 64-bit ints, the coercing of which needs to be fixed in pylabrad
        # for now we manually cast to 32-bit (long)
        # See pylabrad github issue #43
        returnValue((ans[0],
                    [long(x) for x in ans[1]], [long(x) for x in ans[2]], [long(x) for x in ans[3]],
                     ))

    @setting(1301, 'DAC Bringup New', lvdsOptimize='b', lvdsSD='w', signed='b', targetFifo='w',
             returns='*(bw)')
    def dac_bringup(self, c, lvdsOptimize=False, lvdsSD=None, signed=True, targetFifo=None):
        """

        :param c:
        :param lvdsOptimize:
        :param lvdsSD:
        :param signed:
        :param targetFifo:
        :return: list of (bool, string) tuples indicating success of each test
        """
        dev = self.selectedDAC(c)
        yield dev.initPLL()
        time.sleep(0.100)
        yield dev.resetPLL()
        results = []
        for dac, cmd, shift in zip(['A', 'B'], (2, 3), (0, 14)):
            ansDAC = [('dac', dac)]
            #Initialize DAC
            #See HardRegProgram.txt for byte sequence definition
            pkt = [0x0024, 0x0004, 0x1603, 0x0500] if signed else \
                  [0x0026, 0x0006, 0x1603, 0x0500]
            yield dev.runSerial(cmd, pkt)
            lvdsAns = yield dev.setLVDS(cmd, lvdsSD, lvdsOptimize)
            results.append((lvdsAns[0], "setLVDS"))
            fifoAns = yield dev.setFIFO(dac, cmd, targetFifo)
            results.append((fifoAns[0], "setFIFO"))  # TODO: do we want to keep num. tries as a result?
            bistData = np.random.random_integers(0, 0x3FFF, 1000)
            bistAns = yield dev.runBIST(cmd, shift, bistData)
            results.append((bistAns[0], "runBIST"))
        returnValue(results)

    @setting(1300, 'DAC Bringup', lvdsOptimize='b', lvdsSD='w', signed='b',
             targetFifo='w',
             returns='*((ss)(sb)(sw)(sw)(sw)(s(*w*b*b))(sw)(sb)(sb)(si)(sw)(sw)(sb)(s(ww))(s(ww))(s(ww)))')
    def dac_bringup(self, c, lvdsOptimize=False, lvdsSD=None, signed=True,
                             targetFifo=None):
        """
        Runs the bringup procedure.
        
        This code initializes the PLL, initializes the DAC, sets the LVDS SD,
        sets the FIFO, and runs the BIST test on each DAC channel. The output
        is (in tuple format) a list of two (one for each DAC) pairs of
        (string,data) with all the calibration parameters.
        """
        dev = self.selectedDAC(c)
        ans = []
        yield dev.initPLL()
        time.sleep(0.100)
        yield dev.resetPLL()
        for dac in ['A','B']:
            ansDAC = [('dac',dac)]
            cmd, shift = {'A': (2, 0), 'B': (3, 14)}[dac]
            #Initialize DAC
            #See HardRegProgram.txt for byte sequence definition
            pkt = [0x0024, 0x0004, 0x1603, 0x0500] if signed else \
                  [0x0026, 0x0006, 0x1603, 0x0500]
            yield dev.runSerial(cmd, pkt)
            lvdsAns = yield dev.setLVDS(cmd, lvdsSD, lvdsOptimize)
            lvdsKeys = ['lvdsSuccess', 'lvdsMSD', 'lvdsMHD', 'lvdsSD',
                'lvdsTiming','lvdsCheck']
            for key,val in zip(lvdsKeys,lvdsAns):
                ansDAC.append((key,val))
            fifoAns = yield dev.setFIFO(dac, cmd, targetFifo)
            fifoKeys = ['fifoSuccess', 'fifoClockPolarity', 'fifoPHOF',
                'fifoTries','fifoCounter']
            for key,val in zip(fifoKeys,fifoAns):
                ansDAC.append((key,val))
            bistData = [random.randint(0, 0x3FFF) for i in range(1000)]
            bistAns = yield dev.runBIST(cmd, shift, bistData)
            bistKeys = ['bistSuccess','bistTheory','bistLVDS','bistFIFO']
            for key,val in zip(bistKeys,bistAns):
                ansDAC.append((key,val))
            ans.append(tuple(ansDAC))
        returnValue(ans)
    
    @setting(2500, 'ADC Recalibrate', returns='')
    def adc_recalibrate(self, c):
        """Recalibrate the analog-to-digital converters. (ADC only)"""
        dev = self.selectedADC(c)
        yield dev.recalibrate()
        
    @setting(2501, 'ADC Register Readback', returns='s')
    def adc_register_readback(self, c):
        """Register Readback. (ADC only)"""
        dev = self.selectedADC(c)
        ans = yield dev.registerReadback()
        returnValue(str(ans))
        
    @setting(2502, 'ADC Monitor Outputs', mon0=['s','w'], mon1=['s','w'])
    def adc_monitor_outputs(self, c, mon0, mon1):
        """Specify monitor outputs. (ADC only)"""
        dev = self.selectedADC(c)
        info = c.setdefault(dev, {})
        info['mon0'] = mon0
        info['mon1'] = mon1
        
    @setting(2600, 'ADC Run Average', returns='*i{I}, *i{Q}')
    def adc_run_average(self, c):
        """Run the selected ADC board once in average mode. (ADC only)
        
        The board will start immediately using the trig lookup and demod
        settings already specified in this context (although these settings
        have no effect in average mode). Returns the acquired I and Q
        waveforms.
        
        Returns:
        (I: np.array(int), Q: np.array(int))
        """
        dev = self.selectedADC(c)
        info = c.setdefault(dev, {})
        #demods = dict((i, info[i]) for i in \
        #    range(dev.DEMOD_CHANNELS) if i in info)
        ans = yield dev.runAverage()
        returnValue(ans)
    
    @setting(2601, 'ADC Run Calibrate', returns='')
    def adc_run_calibrate(self, c):
        """Recalibrate the ADC chips
        """
        raise Exception("Depricated. Use ADC Recalibrate instead")
        dev = self.selectedADC(c)
        info = c.setdefault(dev, {})
        filterFunc = info.get('filterFunc', np.array([255], dtype='<u1'))
        # Default to no stretch
        filterStretchLen = info.get('filterStretchLen', 0)
        # Default to stretch at 0
        filterStretchAt = info.get('filterStretchAt', 0)
        demods = dict((i, info[i]) for i in \
            range(dev.DEMOD_CHANNELS) if i in info)
        yield dev.runCalibrate()
    
    @setting(2602, 'ADC Run Demod', mode='s',
             returns='*3i{I,Q}, *i, *i')
    #@setting(2602, 'ADC Run Demod', returns='*i')
    def adc_run_demod(self, c, mode='iq'):
        '''
        Run the ADC in demod mode but with no synchronization to the DAC.
        This runs only a single shot, and returns (*I, *Q) with a single I
        and Q for each demodulator, and also the max and min of I and Q.
        
        Returns data, pktCounters, readbackCounters
        data[qubit, time_step, (I=0, Q=1)] dim=3 array
        '''
        dev = self.selectedADC(c)
        info = c.setdefault(dev, {})
        info['mode'] = mode
        ans = yield dev.runDemod(info)
        returnValue(ans)
    
    @setting(2700, 'ADC Bringup', returns='')
    def adc_bringup(self, c):
        """Runs the bringup procedure.
        
        This code initializes the PLL and recalibrates the ADC.
        """
        dev = self.selectedADC(c)
        yield dev.initPLL()

    # TODO: new settings
    # - set up ADC options for data readout, to be used with the next
    #   daisy-chain run
    #   - DAC boards: one number (timing result) per repetition
    #   - ADC boards: either one waveform (averaged) for whole run
    #                 or one demodulation packet for each repetition

# Runners contain information for running a sequence on a particular board
#
# other info these should provide:
# - what to upload
# - whether upload is optional (based on setup state)
# - how many packets to expect, based on repetitions
# - whether discard is possible

# some helper methods

def processSetupPackets(cxn, setupPkts):
    """
    Process packets sent in flattened form into actual labrad packets on the
    given connection.
    """
    pkts = []
    for ctxt, server, settings in setupPkts:
        if ctxt[0] == 0:
            print 'Using a context with high ID = 0 for packet requests might not do what you want!!!'
        p = cxn[server].packet(context=ctxt)
        for rec in settings:
            if len(rec) == 2:
                setting, data = rec
                p[setting](data)
            elif len(rec) == 1:
                setting, = rec
                p[setting]()
            else:
                raise Exception('Malformed setup packet: ctx=%s, server=%s, settings=%s' % (ctxt, server, settings))
        pkts.append(p)
    return pkts

__server__ = FPGAServer()

if __name__ == '__main__':
    from labrad import util
    util.runServer(__server__)
