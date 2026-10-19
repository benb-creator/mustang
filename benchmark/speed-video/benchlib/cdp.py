import itertools
import json
import time
import urllib.request

import websocket


class CdpError(Exception):
    pass


class CdpClient:
    """Chrome DevTools Protocol client for the page of an Electron app started with --remote-debugging-port."""

    def __init__(self, socket, timeout_s: float):
        self.socket = socket
        self.timeout_s = timeout_s
        self.ids = itertools.count(1)

    @classmethod
    def connect(cls, port: int, timeout_s: float = 60, url_contains: str = "") -> "CdpClient":
        deadline = time.monotonic() + timeout_s
        last_error = None
        while time.monotonic() < deadline:
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list", timeout=5) as response:
                    targets = json.load(response)
                pages = [t for t in targets if t.get("type") == "page" and url_contains in t.get("url", "")]
                if pages:
                    socket = websocket.create_connection(pages[0]["webSocketDebuggerUrl"], timeout=30,
                                                         suppress_origin=True)
                    client = cls(socket, 30)
                    client.evaluate("1")
                    return client
            except (OSError, ValueError, websocket.WebSocketException, CdpError) as ex:
                last_error = ex
            time.sleep(0.5)
        raise CdpError(f"No DevTools page on port {port} within {timeout_s:.0f} s: {last_error}")

    def call(self, method: str, **params) -> dict:
        message_id = next(self.ids)
        self.socket.send(json.dumps({"id": message_id, "method": method, "params": params}))
        while True:
            try:
                message = json.loads(self.socket.recv())
            except websocket.WebSocketTimeoutException as ex:
                raise CdpError(f"{method}: no answer within {self.timeout_s:.0f} s") from ex
            if message.get("id") == message_id:
                if "error" in message:
                    raise CdpError(f"{method}: {message['error']}")
                return message["result"]

    def evaluate(self, expression: str):
        result = self.call("Runtime.evaluate", expression=expression, returnByValue=True, awaitPromise=True)
        if "exceptionDetails" in result:
            details = result["exceptionDetails"]
            text = (details.get("exception") or {}).get("description") or details.get("text")
            raise CdpError(f"JavaScript error: {text}")
        return result["result"].get("value")

    def close(self):
        try:
            self.socket.close()
        except (OSError, websocket.WebSocketException):
            pass
