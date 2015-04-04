# Copyright (C) 2013  Daniel Sank
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

"""
### BEGIN NODE INFO
[info]
name = Oscilloscope
version = 0.1
description = Talks to oscilloscopes

[startup]
cmdline = %PYTHON% %FILE%
timeout = 20

[shutdown]
message = 987654321
timeout = 20
### END NODE INFO
"""

from labrad import types as T, util
from labrad.server import setting
from labrad.gpib import GPIBManagedServer, GPIBDeviceWrapper
from twisted.internet.defer import inlineCallbacks, returnValue

from struct import unpack

import numpy


def require_is_in(obj, collection):
    if obj not in collection:
        raise ValueError("%s not in %s"%(obj, collection))


class NotImplementedAttribute(object):
    """An attribute which has not been implemented."""

    def __init__(self, label):
        self.label = label

    def __get__(self, inst, cls):
        """Raise AttributeError because this attribute should be overridden"""
        raise AttributeError("Attribute {} of class {} not implemented".format(
            self.label,
            cls
        )


class OscilloscopeWrapper(GPIBDeviceWrapper):

    # Constant parameters

    # CHANNEL

    # input
    
    CHANNEL_STATES = ['ON', 'OFF']
    COUPLINGS = ['AC', 'DC']
    PROBE_FACTORS = NotImplementedAttribute('PROBE_FACTORS')

    TRIGGER_SOURCES = ['AUX', 'LINE', 'CH1', 'CH2', 'CH3', 'CH4']
    TRIGGER_MODES = ["AUTO", "NORM"]


    # GPIB string generation functions
    #
    # The following code provides functions which, when evaluated, produce GPIB
    # strings to be sent to the oscilloscope. The functions are actually the
    # .format methods of string literals. Consider the string
    # 'CH{0}:COUP {1}'.
    # This string has a .format method, which is a function that takes two
    # arguments. When you call that function with arguments 0 and "ON", the
    # result is
    # 'CH0:COUP ON'
    # which is the GPIB string that turns on channel 0.
    # We do it this way because it makes the code declarative and therefore
    # it is easy to see what each function does.

    # CHANNEL SETTINGS

    # input

    channel_on_off_write = NotImplementedAttribute('channel_on_off_write')
    channel_on_off_query = NotImplementedAttribute('channel_on_off_query')
    channel_on_off_parse = NotImplementedAttribute('channel_on_off_parse')

    coupling_write = 'CH{0}:COUP {1}'.format
    coupling_query = 'CH{0}:COUP?'.format
    coupling_parse = str

    probe_factor_write = 'CH{0}:PRO {1}'.format
    probe_factor_query = 'CH{0}:PRO?'.format
    probe_factor_parse = NotImplementedAttribute('probe_factor_parse')

    termination_write = 'CH{1}:TER {1}'.format
    termination_query = 'CH{1}:TER?'.format
    termination_parse = str  # XXX Is this correct?

    # scale, position, etc.

    invert_write = 'CH{0}:INV {1}'.format
    invert_query = 'CH{0}:INV?'.format
    invert_parse = bool

    VERT_SCALE_UNIT = NotImplementedAttribute('VERT_SCALE_UNIT')
    vert_scale_write = 'CH{0}:SCA {1}'.format
    vert_scale_query = 'CH{0}:SCA?'.format
    @classmethod
    def vert_scale_parse(cls, s):
        return float(s) * cls.VERT_SCALE_UNIT

    VERT_POSITION_UNIT = NotImplementedAttribute('VERT_POSITION_UNIT')
    vert_position_write = 'CH{0}:POS {1}'.format
    vert_position_query = 'CH{0}:POS?'.format
    vert_position_parse = float

    HORIZ_SCALE_UNIT = NotImplementedAttribute('HORIZ_SCALE_UNIT')
    horiz_scale_write = 'HOR:SCA {0}'.format
    horiz_scale_query = 'HOR:SCA?'.format
    @classmethod
    def horiz_scale_parse(cls, s):
        return float(s) * cls.HORIZ_SCALE_UNIT

    horiz_position_write = 'HOR:POS {0}'.format
    horiz_position_query = 'HOR:POS?'.format
    horiz_position_parse = float

    # TRIGGER

    # XXX Tek scope servers had TRIG:A:...
    # I've taken the A out to see if it still works, because that would mean
    # Agi and Tek code is the same.

    trigger_slope_write = 'TRIG:EDGE:SLO {0}'.format
    trigger_slope_query = 'TRIG:EDGE:SLO?'.format
    trigger_slope_parse = lambda x: x  # Is this right?

    trigger_level_write = 'TRIG:LEV {0}'.format
    trigger_level_query = 'TRIG:LEV?'.format
    trigger_level_parse = int  # XXX Is this right?

    trigger_source_write = 'TRIG:EDGE:SOU {0}'.format
    trigger_source_query = 'TRIG:EDGE:SOU?'.format
    trigger_source_parse = str  # XXX Is this correct?

    trigger_mode_write = 'TRIG:MOD {0}'.format
    trigger_mode_query = 'TIRG:MOD?'.format
    trigger_mode_parse = str  # XXX is this correct?

    # MATH

    math_define_write = 'MATH{0}:DEFI {1}'.format
    math_define_query = 'MATH{0}:DEFI?'.format
    math_define_parse = lambda x: x

    MATH_VERT_SCALE_UNIT = NotImplementedAttribute('MATH_VERT_SCALE_UNIT')
    math_vert_scale_write = 'MATH{0}:VERT:SCA {1}'.format
    math_vert_scale_query = 'MATH{0}:VERT:SCA?'.format
    @classmethod
    def math_vert_scale_parse(cls, s):
        return float(s) * cls.MATH_VERT_SCALE_UNIT


    # DEVICE COMMUNICATION

    @inlineCallbacks
    def reset(self):
        """Reset the oscilloscope to factory settings."""

        yield self.write('*RST')

    @inlineCallbacks
    def clear_buffers(self):
        """Clear all device status bytes"""

        yield dev.write('*CLS')

    # CHANNEL SETTINGS

    @inlineCallbacks
    def channel_on_off(self, channel, state=None):
        """Get or set channel on/off.

        Args:
            channel - int: The channel to get or set.
            state - str: 'ON' or 'OFF'.

        Returns:
            String giving the state of the channel.
        """

        if state is not None:
            require_is_in(state, self.CHANNEL_STATES)
            yield self.write(self.channel_on_off_write(channel, state))
        resp = yield self.query(self.channel_on_off_query(channel))
        returnValue(self.channel_on_off_parse(resp))

    # probe settings

    @inlineCallbacks
    def coupling(self, channel, coupling=None):
        """Get or set the coupling for a channel.

        Args:
            channel: The channel to get or set. Typically this is a number from
                1 to 4.
            coupling: The coupling for this channel. If None (the default) then
                the current coupling is queried and returned. Otherwise the
                coupling is set and then queried and the result is returned.
        """

        if coupling is not None:
            require_is_in(coupling, self.COUPLINGS)
            yield self.write(self.coupling_write(channel, coupling))
        resp = yield self.query(self.coupling_query(channel))
        returnValue(self.coupling_parse(resp))

    @inlineCallbacks
    def probe(self, channel, factor=None):
        """Get or set the probe factor.

        Args:
            channel - int: The channel on which we get or set the probe factor.
            factor - int: The probe scaling factor

        Returns:
            Int. The resuling probe factor.
        """

        if factor is not None:
            require_is_in(factor, self.PROBE_FACTORS)
            yield self.write(self.probe_factor_write(channel, probe))
        resp = yield.self.query(self.probe_factor_query(channel))
        returnValue(self.probe_factor_parse(resp))

    @inlineCallbacks
    def termination(self, channel, impedance=None):
        """Get or set the channel's termination impedance.

        Args:
            Channel: The channel on which we get or set the impedance.
            impedance: The impedance to set. If None (the default) we just query
                the current impedance. Otherwise we set the impedance to the
                given value.

        Returns:
            The termination impedance of the channel.
        """

        if impedance is not None:
            require_is_in(impedance, self.IMPEDANCES)
            impedance_str = impedance[self.IMPEDANCE_UNIT]
            yield self.write(self.termination_write(channel, impedance_str))
        resp = yield self.query(self.termination_query(channel))
        returnValue(self.termination_parse(resp))

    # scale, position, etc.

    @inlineCallbacks
    def invert(self, channel, invert=None):
        """Get or set the polarity of a channel.

        Args:
            channel - int: The channel on which we get or set the polarity.
            invert - bool: If None (the default) we get the channel polarity.
                If True, invert the channel. If False, set the channel to normal
                polarity.

        Returns:
            Boolean. If True, the channel is inverted. If False, it is not
            inverted.
        """

        if invert is not None:
            yield self.write(self.invert_write(channel, invert))
        resp = yield self.query(self.invert_query(channel))
        returnValue(self.invert_parse(resp))

    @inlineCallbacks
    def vert_scale(self, channel, scale):
        """Get or set the verical scale of a channel.

        Args:
            channel - int: The channel to get or set.
            scale - Value[V]: The vertical scale for the channel. If None
                (the default) we query the current scale. Otherwise we set the
                scale and then query it.

        Returns:
            Vertical scale in Voltage units.
        """

        is scale is not None:
            scale_str = scale[self.VERT_SCALE_UNIT]
            scale_str = format(scale_str,'E')
            yield dev.write(self.vert_scale_write(channel, scale_str))
        resp = yield dev.query(self.vert_scale_query(channel))
        returnValue(self.vert_scale_parse(resp))

    @inlineCallbacks
    def vert_position(self, channel, position=None):
        """Get or set the channel vertical position.

        Args:
            channel - int: The channel to get or set.
            position - Value['V']: The vertical position to set for the channel.
                If None (the default) we just query the current position.
        """

        if position is not None:
            pos = position[self.VERT_POSITION_UNIT]
            yield self.write(self.vert_position_write(channel, pos))
        resp = yield dev.query(self.vert_position_query(channel))
        returnValue(self.parse_vert_position(resp))

    @inlineCallbacks
    def horiz_scale(self, scale):
        """Get or set the horizontal scale of a channel.

        Args:
            channel: The channel to get or set.
            scale value[s]: The horizontal scale for the channel. If None
                (the default) we query the current scale. Otherwise we set the
                scale and then query it.

        Returns:
            Horizontal scale in dimensions of time.
        """

        if scale is not None:
            scale = scale[self.HORIZ_SCALE_UNIT]
            yield dev.write(self.horiz_scale_write(scale))
        resp = yield dev.query(self.horiz_scale_query(scale))
        returnValue(self.horiz_scale_parse(resp))

    @inlineCallbacks
    def horiz_position(self, position):
        """Get or set the horizontal position.

        Args:
            position: The position in XXX units.

        Returns:
            The resulting position.
        """

        if position is not None:
            yield self.write(self.horiz_position_write())
        resp = yield self.query(self.horiz_position_query())
        returnValue(self.horiz_position_parse(resp))

    # TRIGGER

    @inlineCallbacks
    def trigger_slope(self, slope=None):
        """Get or set the trigger slope.

        Args:
            slope - str: Which slope to use for trigger.

        Returns:
            The trigger slope.
        """

        if slope is not None:
            require_is_in(slope, self.TRIGGER_SLOPES)
            yield self.write(self.trigger_slope_write(slope))
        resp = yield self.query(self.trigger_slope_query())
        returnValue(self.trigger_slope_parse(resp))

    @inlineCallbacks
    def trigger_level(self, level=None):
        """Get or set the trigger level.

        Args:
            level: The trigger level in units of divisions.

        Returns:
            The trigger level in units of divisions.
        """

        if level is not None:
            level_str = level[self.TRIGGER_LEVEL_UNIT]
            yield self.write(self.trigger_level_write(level_str))
        resp = yield self.query(self.trigger_level_query())
        returnValue(self.trigger_level_parse(resp))

    @inlineCallbacks
    def trigger_source(self, source=None):
        """Get or set the trigger source.

        Args:
            source: The source for the trigger. If None (the default) then we
                just query the current trigger source.

        Returns:
            The trigger source.
        """

        if source is not None:
            require_is_in(source, self.TRIGGER_SOURCES)
            yield self.write(self.trigger_source.write(source))
        resp = yield self.query(self.trigger_source_query())
        returnValue(self.trigger_source_parse(resp))

    @inlineCallbacks
    def trigger_mode(self, mode=None):
        """Get or set the trigger mode.

        Args:
            mode: The trigger mode. If None (the default) then we just query the
                current trigger mode.

        Returns:
            The trigger mode.
        """

        if mode is not None:
            require_is_in(mode, self.TRIGGER_MODES)
            yield self.write(self.trigger_mode_write(mode))
        resp = yield self.query(self.trigger_mode_query())
        returnValue(self.trigger_mode_parse(resp))

    # MATH

    @inlineCallbacks
    def math_define(self, channel, definition=None):
        """Define or query a math definition.

        Args:
            channel - int: The math channel to set or query.
            definition - str: The math definition, e.g. 'CH1-CH2'.

        Returns:
            String representing the math definition.
        """

        if definition is not None:
            yield dev.write(self.math_define_write(definition))
        resp = yield self.query(self.math_define_query())
        returnValue(self.math_define_parse(resp))

    @inlineCallbacks
    def math_vert_scale(self, channel, scale=None):
        """Get or set the vertical scale of a math channel.

        Args:
            channel - int: The math channel to get or set.
            scale - Value[V]: The vertical scale of the channel.

        Returns:
            Value indicating the math channel's scale.
        """

        if scale is not None:
            scale = format(scale[self.MATH_VERT_SCALE_UNIT], 'E')
            yield self.write(self.math_vert_scale_write(channel, scale))
        resp = yield self.query(self.math_vert_scale_query(channel))
        returnValue(self.math_vert_scale_parse(resp))


    # TEKTRONIX OSCILLOSCOPES

class TektronixWrapper(OscilloscopeWrapper):
    """Wrapper for Tektronix oscilloscopes"""

    channel_on_off_write = 'SEL:CH{0} {1}'.format
    channel_on_off_query = 'SEL:CH{0}'.format
    channel_on_off_parse = str


class Tektronix2014BWrapper(TektronixWrapper):
    """Wrapper for the Tektronix 2014B"""

    PROBE_FACTORS = [1, 10, 20, 50, 100, 500, 1000]

    COUPLINGS = ['AC', 'DC']
    IMPEDANCES = 

    VERT_DIVISIONS = NotImplementedAttribute('VERT_DIVISIONS')  # 8
    HORIZ_DIVISIONS = NotImplementedAttribute('HORIZ_DIVISIONS')  # 10


class Tektronix5054BWrapper(TektronixWrapper):
    """Wrapper for a Tektronix 5054B"""

    PROBE_FACTORS = NotImplementedAttribute('PROBE_FACTORS')

    COUPLINGS = ['AC', 'DC', 'GND']
    IMPEDANCES = [50*Ohm, 1E6*Ohm]

    VERT_DIVISIONS = NotImplementedAttribute('VERT_DIVISIONS')  # 8
    HORIZ_DIVISIONS = NotImplementedAttribute('HORIZ_DIVISIONS')  # 10


    # AGILENT OSCILLOSCOPES

class AgilentWrapper(OscilloscopeWrapper):

    channel_on_off_write = 'CHAN{0}:DISP {1}'.format
    channel_on_off_query = 'CHAN{0}:DISP?'.format
    channel_on_off_parse = str


class AgilentDSO91304AWrapper(AgilentWrapper):

    PROBE_FACTORS = NotImplementedAttribute('PROBE_FACTORS')

    COUPLINGS =
    IMPEDANCES =

    VERT_DIVISIONS = NotImplementedAttribute('VERT_DIVISIONS')  # 8
    HORIZ_DIVISIONS = NotImplementedAttribute('HORIZ_DIVISIONS')  # 10


class AgilentDSO7104BWrapper(AgilentWrapper):

    PROBE_FACTORS = NotImplementedAttribute('PROBE_FACTORS')

    COUPLINGS =
    IMPEDANCES =

    VERT_DIVISIONS = NotImplementedAttribute('VERT_DIVISIONS')  # 8
    HORIZ_DIVISIONS = NotImplementedAttribute('HORIZ_DIVISIONS')  # 10

    TRIGGER_SLOPES = ['RISE', 'FALL', 'POS', 'NEG']


    # MAIN SERVER

class OscilloscopeServer(GPIBManagedServer):
    name = 'oscilloscope_server'

    deviceWrappers = {
                     'Tektronix 2014B': Tektronix2014BWrapper,
                     'Tektronix 5054B': Tektronix5054BWrapper,
                     'Agilent DSO91304': AgilentDSO91304Wrapper
                     }

    # SYSTEM

    @setting(11, returns='')
    def reset(self, c):
        """Reset the oscilloscope to factory settings."""

        dev = self.selectedDevice(c)
        yield dev.reset()

    @setting(12, returns='')
    def clear_buffers(self, c):
        """Clear device status buffers."""

        dev = self.selectedDevice(c)
        yield dev.clear_buffers()

    # VERTICAL

    # HORIZONTAL

    @setting(..., channel='i')
    def get_trace(self, c, channel):
        """Get a trace for a single channel.

        Args:
            channel: The channel for which we want to get the trace.

        Returns a tuple of (time axis, vertical values, both with units.
        """

        dev = self.selectedDevice(c)
        result = yield dev.get_trace(channel)
        returnValue(result)


__server__ = OscilloscopeServer()

if __name__ == '__main__':
    from labrad import util
    util.runServer(__server__)
