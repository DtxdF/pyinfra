"""
Manipulate system rc files.
"""

from __future__ import annotations

from enum import Enum

from typing_extensions import List, Optional, Union

from pyinfra import host
from pyinfra.api import QuoteString, StringCommand, operation
from pyinfra.api.exceptions import OperationValueError
from pyinfra.facts.freebsd import Sysrc


class SysrcCommands(Enum):
    SYSRC_ADD: int = 0
    SYSRC_SUB: int = 1
    SYSRC_SET: int = 2
    SYSRC_DEL: int = 3


@operation()
def sysrc(
    parameter: str,
    value: str,
    jail: Optional[str] = None,
    command: "SysrcCommands" = SysrcCommands.SYSRC_SET,
    overwrite: bool = False,
):
    """
    Safely edit system rc files.

    + parameter: Parameter to manipulate.
    + value: Value, if the parameter requires it.
    + jail: See ``-j`` in ``sysrc(8)``.
    + command: Desire state of the parameter.
    + overwrite: Overwrite the value of the parameter when ``command`` is set to ``SYSRC_SET``.

    Commands:
        There are a few commands you can use to manipulate the rc file:

        - SYSRC_ADD: Adds the value to the parameter.
        - SYSRC_SUB: Delete the parameter value.
        - SYSRC_SET: Change the parameter value. If the parameter already has a value
                     set, the changes will not be applied unless ``overwrite`` is set
                     to ``True``.
        - SYSRC_DEL: Delete the parameter.

    **Example:**

    .. code:: python

        sysrc.sysrc(
            "beanstalkd_enable",
            "YES",
            command=sysrc.sysrc.SysrcCommands.SYSRC_SET
        )
    """

    args: List[Union[str, "QuoteString"]] = []

    args.extend(["sysrc", "-i"])

    if command == SysrcCommands.SYSRC_DEL:
        sign = "="

        if not host.get_fact(Sysrc, parameter=parameter, jail=jail):
            host.noop(f"Cannot find sysrc(8) parameter '{parameter}'")
            return

    elif command == SysrcCommands.SYSRC_SET:
        sign = "="

        if not overwrite and host.get_fact(Sysrc, parameter=parameter, jail=jail):
            host.noop(f"sysrc(8) parameter '{parameter}' already set")
            return

    elif command == SysrcCommands.SYSRC_ADD:
        sign = "+="

    elif command == SysrcCommands.SYSRC_SUB:
        sign = "-="

    else:
        raise OperationValueError("Invalid sysrc command!")

    if jail is not None:
        args.extend(["-j", QuoteString(jail)])

    args.extend(["--", QuoteString(f"{parameter}{sign}{value}")])

    yield StringCommand(*args)
