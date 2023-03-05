from typing import *
import httpx
import requests
import psutil
import os
import sys
import json

DEFAULT_ID = -1
DEFAULT_HOST = "http://localhost"
DEFAULT_PORT = 6800
DEFAULT_TIMEOUT: float = 60.0

JSONRPC_PARSER_ERROR = -32700
JSONRPC_INVALID_REQUEST = -32600
JSONRPC_METHOD_NOT_FOUND = -32601
JSONRPC_INVALID_PARAMS = -32602
JSONRPC_INTERNAL_ERROR = -32603
JSONRPC_CODES = {
    JSONRPC_PARSER_ERROR: "Invalid JSON was received by the server.",
    JSONRPC_INVALID_REQUEST: "The JSON sent is not a valid Request object.",
    JSONRPC_METHOD_NOT_FOUND: "The method does not exist / is not available.",
    JSONRPC_INVALID_PARAMS: "Invalid method parameter(s).",
    JSONRPC_INTERNAL_ERROR: "Internal JSON-RPC error.",
}
CallReturnType = Union[dict, list, str, int]


class ClientException(Exception):  # noqa: N818
    """An exception specific to JSON-RPC errors."""

    def __init__(self, code: int, message: str) -> None:
        """
        Initialize the exception.
        Arguments:
            code: The error code.
            message: The error message.
        """
        super().__init__()
        if code in JSONRPC_CODES:
            message = f"{JSONRPC_CODES[code]}\n{message}"

        self.code = code
        self.message = message

    def __str__(self):
        return self.message

    def __bool__(self):
        return False


class Aria2Client:
    ADD_URI = "aria2.addUri"
    ADD_TORRENT = "aria2.addTorrent"
    ADD_METALINK = "aria2.addMetalink"
    REMOVE = "aria2.remove"
    FORCE_REMOVE = "aria2.forceRemove"
    PAUSE = "aria2.pause"
    PAUSE_ALL = "aria2.pauseAll"
    FORCE_PAUSE = "aria2.forcePause"
    FORCE_PAUSE_ALL = "aria2.forcePauseAll"
    UNPAUSE = "aria2.unpause"
    UNPAUSE_ALL = "aria2.unpauseAll"
    TELL_STATUS = "aria2.tellStatus"
    GET_URIS = "aria2.getUris"
    GET_FILES = "aria2.getFiles"
    GET_PEERS = "aria2.getPeers"
    GET_SERVERS = "aria2.getServers"
    TELL_ACTIVE = "aria2.tellActive"
    TELL_WAITING = "aria2.tellWaiting"
    TELL_STOPPED = "aria2.tellStopped"
    CHANGE_POSITION = "aria2.changePosition"
    CHANGE_URI = "aria2.changeUri"
    GET_OPTION = "aria2.getOption"
    CHANGE_OPTION = "aria2.changeOption"
    GET_GLOBAL_OPTION = "aria2.getGlobalOption"
    CHANGE_GLOBAL_OPTION = "aria2.changeGlobalOption"
    GET_GLOBAL_STAT = "aria2.getGlobalStat"
    PURGE_DOWNLOAD_RESULT = "aria2.purgeDownloadResult"
    REMOVE_DOWNLOAD_RESULT = "aria2.removeDownloadResult"
    GET_VERSION = "aria2.getVersion"
    GET_SESSION_INFO = "aria2.getSessionInfo"
    SHUTDOWN = "aria2.shutdown"
    FORCE_SHUTDOWN = "aria2.forceShutdown"
    SAVE_SESSION = "aria2.saveSession"

    def __init__(self, host: str = DEFAULT_HOST, port: str = DEFAULT_PORT, secret: str = "", timeout: float = DEFAULT_TIMEOUT):
        host = host.rstrip("/")
        self.host = host
        self.port = port
        self.secret = secret
        self.timeout = timeout

    def __str__(self):
        return self.server

    def __repr__(self):
        return f"Client(host='{self.host}', port={self.port}, secret='********')"

    def init_client(self):
        pids = []
        for proc in psutil.process_iter():
            if proc.name == "aria2c.exe":
                if len(pids) >= 1:
                    proc.kill()
                else:
                    pids.append(proc.pid)

        if len(pids) == 0:
            path1 = f"{os.path.dirname(os.path.realpath(sys.argv[0]))}/Aria2/aria2c.exe"
            path2 = f"{os.path.dirname(os.path.realpath(sys.argv[0]))}/Aria2/aria2.conf"
            cmd = f"{path1}  -D --conf-path={path2}"
            os.popen(cmd)

    @property
    def server(self) -> str:
        """
        Return the full remote process / server address.
        Returns:
            The server address.
        """
        return f"{self.host}:{self.port}/jsonrpc"

    def call(self,
             method: str,
             params: Union[List[Any], None] = None,
             msg_id: Union[int, str, None] = None,
             insert_secret: bool = True) -> Union[dict, list, str, int]:

        params = self.get_params(*(params or []))
        if insert_secret and self.secret:
            params.insert(0, f"token:{self.secret}")
        payload: str = self.get_payload(method, params, msg_id=msg_id)
        return self.res_or_raise(self.post(payload))

    def post(self, payload: str) -> dict:
        """
        Send a POST request to the server.
        The response is a JSON string, which we then load as a Python object.
        Arguments:
            payload: The payload / data to send to the remote process. It contains the following key-value pairs:
                "jsonrpc": "2.0", "method": method, "id": id, "params": params (optional).
        Returns:
            The answer from the server, as a Python dictionary.
        """
        return requests.post(self.server, data=payload, timeout=self.timeout).json()

    @staticmethod
    def response_as_exception(response: dict) -> ClientException:
        """
        Transform the response as a [`ClientException`][aria2p.client.ClientException] instance and return it.
        Arguments:
            response: A response sent by the server.
        Returns:
            An instance of the [`ClientException`][aria2p.client.ClientException] class.
        """
        return ClientException(response["error"]["code"], response["error"]["message"])

    @staticmethod
    def res_or_raise(response: dict) -> CallReturnType:
        """
        Return the result of the response, or raise an error with code and message.
        Arguments:
            response: A response sent by the server.
        Returns:
            The "result" value of the response.
        Raises:
            ClientException: When the response contains an error (client/server error).
                See the [`ClientException`][aria2p.client.ClientException] class.
        """
        if "error" in response:
            raise Aria2Client.response_as_exception(response)
        return response["result"]

    @staticmethod
    def get_payload(
        method: str,
        params: Union[List[Any], None] = None,
        msg_id: Union[int, str, None] = None,
        as_json: bool = True,
    ) -> CallReturnType:

        payload: dict[str, Any] = {"jsonrpc": "2.0", "method": method}

        if msg_id is None:
            payload["id"] = DEFAULT_ID
        else:
            payload["id"] = msg_id

        if params:
            payload["params"] = params

        return json.dumps(payload) if as_json else payload

    @staticmethod
    def get_params(*args: Any) -> list:
        return [_ for _ in args if _ is not None]

    def add_uri(
        self,
        uris: List[str],
        options: Union[Dict, None] = None,
        position: Union[int, None] = None,
    ) -> str:
        return self.call(self.ADD_URI, params=[uris, options, position])


# aria2 = Aria2c()
# aria2.init_client()
