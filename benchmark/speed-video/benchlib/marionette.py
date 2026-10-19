import json
import socket
import time


class MarionetteError(Exception):
    pass


class MarionetteClient:
    """Marionette (Gecko's remote protocol) in the chrome context of Thunderbird, started with `-marionette
    -remote-allow-system-access` and the pref `marionette.port`."""

    def __init__(self, sock: socket.socket):
        self.sock = sock
        self.buffer = b""
        self.message_id = 0
        self.read()

    @classmethod
    def connect(cls, port: int, timeout_s: float = 60) -> "MarionetteClient":
        deadline = time.monotonic() + timeout_s
        last_error = None
        while time.monotonic() < deadline:
            try:
                client = cls(socket.create_connection(("127.0.0.1", port), timeout=30))
                client.command("WebDriver:NewSession", {"capabilities": {}})
                client.command("Marionette:SetContext", {"value": "chrome"})
                return client
            except (OSError, MarionetteError, ValueError) as ex:
                last_error = ex
                time.sleep(0.5)
        raise MarionetteError(f"No Marionette on port {port} within {timeout_s:.0f} s: {last_error}")

    def read(self):
        while b":" not in self.buffer:
            chunk = self.sock.recv(65536)
            if not chunk:
                raise MarionetteError("Marionette connection closed")
            self.buffer += chunk
        length, rest = self.buffer.split(b":", 1)
        length = int(length)
        while len(rest) < length:
            chunk = self.sock.recv(65536)
            if not chunk:
                raise MarionetteError("Marionette connection closed")
            rest += chunk
        self.buffer = rest[length:]
        return json.loads(rest[:length])

    def command(self, name: str, params: dict | None = None):
        self.message_id += 1
        data = json.dumps([0, self.message_id, name, params or {}]).encode()
        try:
            self.sock.sendall(b"%d:%s" % (len(data), data))
            while True:
                message = self.read()
                if message[0] == 1 and message[1] == self.message_id:
                    if message[2]:
                        raise MarionetteError(f"{name}: {message[2].get('message', message[2])}")
                    return message[3]
        except socket.timeout as ex:
            raise MarionetteError(f"{name}: no answer") from ex

    def execute(self, script: str, args: list | None = None):
        return self.command("WebDriver:ExecuteScript", {"script": script, "args": args or []})["value"]

    def close(self):
        try:
            self.command("WebDriver:DeleteSession")
        except (MarionetteError, OSError):
            pass
        try:
            self.sock.close()
        except OSError:
            pass
