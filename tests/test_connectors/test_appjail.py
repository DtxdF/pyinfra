# encoding: utf-8

import shlex
from subprocess import PIPE
from unittest import TestCase
from unittest.mock import MagicMock, mock_open, patch

from pyinfra.api import Config, State, StringCommand
from pyinfra.api.connect import connect_all
from pyinfra.api.exceptions import PyinfraError
from pyinfra.connectors.util import make_unix_command

from ..util import make_inventory


def fake_jail_shell(command, splitlines=None):
    if command == "appjail status not-a-jail":
        return True

    if command == "appjail cmd local not-a-jail pwd":
        return "/not-a-jail"

    raise PyinfraError("Invalid command: {0}".format(command))


@patch("pyinfra.connectors.appjail.local.shell", fake_jail_shell)
@patch("pyinfra.connectors.appjail.mkstemp", lambda: (None, "__tempfile__"))
@patch("pyinfra.connectors.appjail.os.remove", lambda f: None)
@patch("pyinfra.connectors.appjail.open", mock_open(read_data="test!"), create=True)
@patch("pyinfra.api.util.open", mock_open(read_data="test!"), create=True)
class TestAppJailConnector(TestCase):
    def setUp(self):
        self.fake_popen_patch = patch("pyinfra.connectors.util.Popen")
        self.fake_popen_mock = self.fake_popen_patch.start()

    def tearDown(self):
        self.fake_popen_patch.stop()

    def test_connect_all(self):
        inventory = make_inventory(hosts=("@appjail/not-a-jail",))
        state = State(inventory, Config())
        connect_all(state)
        assert len(state.active_hosts) == 1

    def test_connect_host(self):
        inventory = make_inventory(hosts=("@appjail/not-a-jail",))
        state = State(inventory, Config())
        host = inventory.get_host("@appjail/not-a-jail")
        host.connect(reason=True)
        assert len(state.active_hosts) == 0

    def test_connect_all_error(self):
        inventory = make_inventory(hosts=("@appjail/a-broken-jail",))
        state = State(inventory, Config())

        with self.assertRaises(PyinfraError):
            connect_all(state)

    def test_run_shell_command(self):
        inventory = make_inventory(hosts=("@appjail/not-a-jail",))
        State(inventory, Config())
        host = inventory.get_host("@appjail/not-a-jail")
        host.connect()

        command = "echo hoi"
        self.fake_popen_mock().returncode = 0
        out = host.run_shell_command(
            command,
            _stdin="hello",
            _get_pty=True,
            print_output=True,
        )
        assert len(out) == 2
        assert out[0] is True

        command = make_unix_command(StringCommand(*command.split(" "))).get_raw_value()
        command = shlex.quote(command)
        args = "appjail cmd jexec not-a-jail sh -c {0}".format(command)
        shell_command = make_unix_command(StringCommand(*args.split(" "))).get_raw_value()

        self.fake_popen_mock.assert_called_with(
            shell_command,
            shell=True,
            stdout=PIPE,
            stderr=PIPE,
            stdin=PIPE,
        )

    def test_run_shell_command_success_exit_codes(self):
        inventory = make_inventory(hosts=("@appjail/not-a-jail",))
        state = State(inventory, Config())
        connect_all(state)

        host = inventory.get_host("@appjail/not-a-jail")

        command = "echo hoi"
        self.fake_popen_mock().returncode = 1

        out = host.run_shell_command(command, _success_exit_codes=[1])
        assert len(out) == 2
        assert out[0] is True

    def test_run_shell_command_error(self):
        inventory = make_inventory(hosts=("@appjail/not-a-jail",))
        state = State(inventory, Config())
        connect_all(state)

        host = inventory.get_host("@appjail/not-a-jail")

        command = "echo hoi"
        self.fake_popen_mock().returncode = 1

        out = host.run_shell_command(command)
        assert len(out) == 2
        assert out[0] is False

    def test_put_file(self):
        inventory = make_inventory(hosts=("@appjail/not-a-jail",))
        state = State(inventory, Config())
        connect_all(state)

        host = inventory.get_host("@appjail/not-a-jail")

        fake_process = MagicMock(returncode=0)
        self.fake_popen_mock.return_value = fake_process

        host.put_file("not-a-file", "not-another-file", print_output=True)

        self.fake_popen_mock.assert_called_with(
            "sh -c 'cp __tempfile__ /not-a-jail/not-another-file'",
            shell=True,
            stdout=PIPE,
            stderr=PIPE,
            stdin=PIPE,
        )

    def test_put_file_error(self):
        inventory = make_inventory(hosts=("@appjail/not-a-jail",))
        state = State(inventory, Config())
        connect_all(state)

        host = inventory.get_host("@appjail/not-a-jail")

        fake_process = MagicMock(returncode=1)
        self.fake_popen_mock.return_value = fake_process

        with self.assertRaises(IOError):
            host.put_file("not-a-file", "not-another-file", print_output=True)

    def test_get_file(self):
        inventory = make_inventory(hosts=("@appjail/not-a-jail",))
        state = State(inventory, Config())
        connect_all(state)

        host = inventory.get_host("@appjail/not-a-jail")

        fake_process = MagicMock(returncode=0)
        self.fake_popen_mock.return_value = fake_process

        host.get_file("not-a-file", "not-another-file", print_output=True)

        self.fake_popen_mock.assert_called_with(
            "sh -c 'cp /not-a-jail/not-a-file __tempfile__'",
            shell=True,
            stdout=PIPE,
            stderr=PIPE,
            stdin=PIPE,
        )

    def test_get_file_error(self):
        inventory = make_inventory(hosts=("@appjail/not-a-jail",))
        state = State(inventory, Config())
        connect_all(state)

        host = inventory.get_host("@appjail/not-a-jail")

        fake_process = MagicMock(returncode=1)
        self.fake_popen_mock.return_value = fake_process

        with self.assertRaises(IOError):
            host.get_file("not-a-file", "not-another-file", print_output=True)
