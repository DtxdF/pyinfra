"""
Manage FreeBSD services.
"""

from __future__ import annotations

from enum import Enum

from typing_extensions import List, Optional, Union

from pyinfra import host
from pyinfra.api import QuoteString, StringCommand, operation
from pyinfra.api.exceptions import OperationValueError
from pyinfra.facts.freebsd import ServiceScript, ServiceStatus


class ServiceStates(Enum):
    SRV_STARTED: int = 0
    SRV_STOPPED: int = 1
    SRV_RESTARTED: int = 2
    SRV_RELOADED: int = 3
    SRV_CUSTOM: int = 4


@operation()
def service(
    srvname: str,
    jail: Optional[str] = None,
    state: "ServiceStates" = ServiceStates.SRV_STARTED,
    command: Optional[Union[str, List[str]]] = None,
    environment: Optional[List[str]] = None,
    verbose: bool = False,
):
    """
    Control (start/stop/etc.) ``rc(8)`` scripts.

    + srvname: Service.
    + jail: See ``-j`` in ``service(8)``.
    + state: Desire state of the service.
    + command: When ``state`` is ``SRV_CUSTOM``, the command to execute.
    + environment: See ``-E`` in ``service(8)``.
    + verbose: See ``-v`` in ``service(8)``.

    States:
        There are a few states you can use to manipulate the service:

        - SRV_STARTED: The service must be started.
        - SRV_STOPPED: The service must be stopped.
        - SRV_RESTARTED: The service must be restarted.
        - SRV_RELOADED: The service must be reloaded.
        - SRV_CUSTOM: Run a custom command for this service.

    **Examples:**

    .. code:: python

        # Start a service.
        service.service(
            "beanstalkd",
            state=service.ServiceStates.SRV_STARTED
        )

        # Execute a custom command.
        service.service(
            "sopel",
            state=service.ServiceStates.SRV_CUSTOM,
            command="configure"
        )
    """

    if not host.get_fact(ServiceScript, srvname=srvname, jail=jail):
        host.noop(f"Cannot find rc(8) script '{srvname}'")
        return

    args = ["service"]

    if verbose:
        args.append("-v")

    if jail is not None:
        args.extend(["-j", QuoteString(jail)])

    if environment is not None:
        for env_var in environment:
            args.extend(["-E", QuoteString(env_var)])

    if state == ServiceStates.SRV_STARTED:
        if host.get_fact(ServiceStatus, srvname=srvname, jail=jail):
            host.noop(f"Service '{srvname}' already started")
            return

        args.extend([QuoteString(srvname), "start"])

    elif state == ServiceStates.SRV_STOPPED:
        if not host.get_fact(ServiceStatus, srvname=srvname, jail=jail):
            host.noop(f"Service '{srvname}' already stopped")
            return

        args.extend([QuoteString(srvname), "stop"])
    elif state == ServiceStates.SRV_RESTARTED:
        args.extend([QuoteString(srvname), "restart"])

    elif state == ServiceStates.SRV_RELOADED:
        args.extend([QuoteString(srvname), "reload"])

    elif state == ServiceStates.SRV_CUSTOM:
        args.append(QuoteString(srvname))

        if not isinstance(command, str):
            command = [command]

        args.extend((QuoteString(c) for c in command))

    else:
        raise OperationValueError("Invalid service command!")

    yield StringCommand(*args)
