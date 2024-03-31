# Klipper Save-Restore  Position
# Toollock and general Tool support
#
# Copyright (C) 2024 Andrei Ignat <andrei@ignat.se>
#
# This file may be distributed under the terms of the GNU GPLv3 license.
#
from __future__ import annotations
import typing

# Only import these modules in Dev environment. Consult Dev_doc.md for more info.
if typing.TYPE_CHECKING:
    from ...klipper.klippy import configfile, gcode
    from ...klipper.klippy.extras import gcode_move as klippy_gcode_move

# Constants for the restore_axis_on_toolchange variable.
XYZ_TO_INDEX: dict[str, int] = {"x": 0, "X": 0, "y": 1, "Y": 1, "z": 2, "Z": 2}
INDEX_TO_XYZ: dict[int, str] = {0: "X", 1: "Y", 2: "Z"}
DEFAULT_WAIT_FOR_TEMPERATURE_TOLERANCE = 1  # Default tolerance in degC.
# Don't wait for temperatures below this because they might be ambient.
LOWEST_ALLOWED_TEMPERATURE_TO_WAIT_FOR = 40


class KlipperSaveRestorePosition():
    '''Feature removed from KTC v2.0.0. This class is made for backward compatibility if needed.'''
    def __init__(self, config: "configfile.ConfigWrapper"):

        self.printer : 'klippy.Printer' = config.get_printer()
        self.gcode = typing.cast('gcode.GCodeDispatch', self.printer.lookup_object("gcode"))
        self._saved_position = [None, None, None]

        # Register commands
        handlers = [
            "KTC_SAVE_POSITION",
            "KTC_SAVE_CURRENT_POSITION",
            "KTC_RESTORE_POSITION",
        ]
        for cmd in handlers:
            func = getattr(self, "cmd_" + cmd)
            desc = getattr(self, "cmd_" + cmd + "_help", None)
            self.gcode.register_command(cmd, func, False, desc)

    _offset_help = ("\n[X: X position] or [X_ADJUST: X adjust]\n" +
        "[Y: Y position] or [Y_ADJUST: Y adjust]\n" +
        "[Z: Z position] or [Z_ADJUST: Z adjust]\n"
    )

    def offset_from_gcmd(self, gcmd: "gcode.GCodeCommand", offset: list) -> list[float]:
        '''Get offset coordinates from G-Code command. If not present, use the current offset.'''
        for axis in ["X", "Y", "Z"]:
            pos = gcmd.get_float(axis, None)
            adjust = gcmd.get_float(axis + "_ADJUST", None)
            if pos is not None:
                offset[XYZ_TO_INDEX[axis]] = pos
            elif adjust is not None:
                offset[XYZ_TO_INDEX[axis]] += adjust
        return offset

    cmd_KTC_SAVE_POSITION_help = (
    "Save the specified G-Code position for later restore." +
    "Axis not mentioned will not be reset to not saving them." + _offset_help
    )
    def cmd_KTC_SAVE_POSITION(self, gcmd: "gcode.GCodeCommand"):  # pylint: disable=invalid-name
        try:
            self._saved_position = self.offset_from_gcmd(gcmd, [None, None, None])
        except Exception as e:
            raise gcmd.error("KTC_SAVE_POSITION: Error: %s" % str(e)) from e

    cmd_KTC_SAVE_CURRENT_POSITION_help = (
        "Save the current G-Code position." +
        "If not specified, save all axis."
    )
    def cmd_KTC_SAVE_CURRENT_POSITION(self, gcmd: "gcode.GCodeCommand"):  # pylint: disable=invalid-name
        '''Save the current G-Code position. If not specified, save all axis.'''
        restore_axis = typing.cast(str, gcmd.get("AXIS", "XYZ")).replace(" ", "")
        self.SaveCurrentPosition(restore_axis)

    def SaveCurrentPosition(self, restore_axis: str):   # pylint: disable=invalid-name
        '''Save the current G-Code position.'''
        gcode_move = typing.cast(
            "klippy_gcode_move.GCodeMove", self.printer.lookup_object("gcode_move")
        )
        # TODO: Try to find a public method to get the current position.
        current_position = gcode_move._get_gcode_position()
        self._saved_position = [None, None, None]
        for axis in restore_axis:
            if axis in XYZ_TO_INDEX:
                i = XYZ_TO_INDEX[axis]
                self._saved_position[i] = current_position[i]   # pylance: reportCallIssue=false

    cmd_KTC_RESTORE_POSITION_help = (
        "Restore from previously saved G-Code position axis,call saved or those specified.\n" +
        "AXIS= XYZ to restore, optional. Will otherwise restore all saved.\n" +
        "SPEED= Speed to restore at, optional."
    )

    def cmd_KTC_RESTORE_POSITION(self, gcmd: "gcode.GCodeCommand"): # pylint: disable=invalid-name
        '''Restore from previously saved G-Code position axis, call saved or those specified.'''
        axis_to_restore = typing.cast(str, gcmd.get("AXIS", "XYZ")).strip()  # type: str
        speed = gcmd.get_int("SPEED", None)
        try:
            self.restore_position(axis_to_restore, speed)
        except Exception as e:
            raise gcmd.error from e

    def restore_position(self, axis_to_restore: str ="XYZ", speed: int = None):
        '''Restore from previously saved G-Code position axis, call saved or those specified.'''
        try:
            cmd = "G0"
            for axis in axis_to_restore:
                if self._saved_position[XYZ_TO_INDEX[axis]] is not None:
                    cmd += " %s%.3f" % (axis, self._saved_position[XYZ_TO_INDEX[axis]])
            if cmd != "G0":
                if speed:
                    cmd += " F%i" % (speed,)
                self.gcode.run_script_from_command(cmd)
        except Exception as e:
            raise Exception("Error restoring position: %s" % str(e)) from e

    def get_status(self, eventtime=None):  # pylint: disable=unused-argument
        status = {
            "saved_position": self._saved_position,
        }
        return status

def load_config(config):
    return KlipperSaveRestorePosition(config)
