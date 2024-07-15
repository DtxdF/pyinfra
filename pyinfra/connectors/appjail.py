from __future__ import annotations

import os
from tempfile import mkstemp
from typing import TYPE_CHECKING

import click
from typing_extensions import List, TypedDict, Union, Unpack

from pyinfra import local
from pyinfra.api import QuoteString, StringCommand
from pyinfra.api.exceptions import ConnectError, InventoryError, PyinfraError
from pyinfra.api.util import get_file_io
from pyinfra.progress import progress_spinner

from .base import BaseConnector, DataMeta
from .local import LocalConnector
from .util import CommandOutput, extract_control_arguments, make_unix_command_for_host

if TYPE_CHECKING:
    from pyinfra.api.arguments import ConnectorArguments
    from pyinfra.api.host import Host
    from pyinfra.api.state import State


class ConnectorData(TypedDict):
    jail: str


connector_data_meta: dict[str, DataMeta] = {
    "jail": DataMeta("Jail to start from"),
}


class AppJailConnector(BaseConnector):
    """
    The AppJail connector allows you to modify running jails.

    Note: Jails must have been previously created by AppJail.

    .. code:: shell

        # A jail must be provided
        pyinfra @appjail/mariadb ...

        # pyinfra can run on multiple jails in parallel
        pyinfra @appjail/mariadb,@appjail/nginx ...
    """

    data_cls = ConnectorData
    data_meta = connector_data_meta
    data: ConnectorData

    local: LocalConnector

    jail: str

    handles_execution = True

    def __init__(self, state: "State", host: "Host"):
        super().__init__(state, host)
        self.local = LocalConnector(state, host)

    @staticmethod
    def make_names_data(name=None):
        if not name:
            raise InventoryError("No jail name provided!")

        yield (
            "@appjail/{0}".format(name),
            {"jail": name},
            ["@appjail"],
        )

    def connect(self) -> None:
        self.local.connect()

        jail = self.host.data.jail

        with progress_spinner({"prepare appjail jail"}):
            try:
                local.shell("appjail status {0}".format(jail))
            except PyinfraError as err:
                raise ConnectError(err.args[0])

        self.jail = jail

    def run_shell_command(
        self,
        command: StringCommand,
        print_output: bool = False,
        print_input: bool = False,
        **arguments: Unpack["ConnectorArguments"],
    ) -> tuple[bool, CommandOutput]:
        local_arguments = extract_control_arguments(arguments)

        jail = self.jail

        command = make_unix_command_for_host(self.state, self.host, command, **arguments)
        quoted_command = QuoteString(command)

        args: List[Union[str, "QuoteString"]] = ["appjail", "cmd", "jexec", jail]

        if self.host.data.get("noclean"):
            args.append("-l")

        if self.host.data.get("jail_user"):
            args.extend(["-U", self.host.data.get("jail_user")])

        elif self.host.data.get("host_user"):
            args.extend(["-u", self.host.data.get("host_user")])

        args.extend(["sh", "-c", quoted_command])

        return self.local.run_shell_command(
            StringCommand(*args),
            print_output=print_output,
            print_input=print_input,
            **local_arguments,
        )

    def put_file(
        self,
        filename_or_io,
        remote_filename,
        remote_temp_filename=None,  # ignored
        print_output: bool = False,
        print_input: bool = False,
        **arguments,
    ) -> bool:
        _, temp_filename = mkstemp()

        try:
            with get_file_io(filename_or_io) as file_io:
                with open(temp_filename, "wb") as temp_f:
                    data = file_io.read()

                    if isinstance(data, str):
                        data = data.encode()

                    temp_f.write(data)

            jail_directory = local.shell("appjail cmd local {0} pwd".format(self.jail))
            args = StringCommand(
                "cp",
                temp_filename,
                f"{jail_directory}/{remote_filename}",
            )

            status, output = self.local.run_shell_command(
                args,
                print_output=print_output,
                print_input=print_input,
            )
        finally:
            os.remove(temp_filename)

        if not status:
            raise IOError(output.stderr)

        if print_output:
            click.echo(
                "{0}file uploaded to jail: {1}".format(
                    self.host.print_prefix,
                    remote_filename,
                ),
                err=True,
            )

        return status

    def get_file(
        self,
        remote_filename,
        filename_or_io,
        remote_temp_filename=None,  # ignored
        print_output: bool = False,
        print_input: bool = False,
        **arguments,
    ) -> bool:
        _, temp_filename = mkstemp()

        try:
            jail_directory = local.shell("appjail cmd local {0} pwd".format(self.jail))
            args = StringCommand(
                "cp",
                f"{jail_directory}/{remote_filename}",
                temp_filename,
            )

            status, output = self.local.run_shell_command(
                args,
                print_output=print_output,
                print_input=print_input,
            )

            with open(temp_filename, encoding="utf-8") as temp_f:
                with get_file_io(filename_or_io, "wb") as file_io:
                    data = temp_f.read()
                    data_bytes: bytes

                    if isinstance(data, str):
                        data_bytes = data.encode()
                    else:
                        data_bytes = data

                    file_io.write(data_bytes)
        finally:
            os.remove(temp_filename)

        if not status:
            raise IOError(output.stderr)

        if print_output:
            click.echo(
                "{0}file downloaded from jail: {1}".format(
                    self.host.print_prefix,
                    remote_filename,
                ),
                err=True,
            )

        return status
