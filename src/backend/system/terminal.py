import asyncio
import errno
import json
import os
import shutil
import sys
import threading
import websockets as ws

if sys.platform == "win32":
    from winpty import PtyProcess
else:
    import fcntl
    import pty
    import signal
    import struct
    import termios

WINDOWS = sys.platform == "win32"
BUFFER_LIMIT = 60000

class TerminalSession:
    def __init__(self, tabId, loop, savedHistory="", projectPath=""):
        self.tabId = tabId
        self.loop = loop
        self.buffer = savedHistory[-BUFFER_LIMIT:]
        self.websocket = None
        self.closed = False
        self.exitSent = False
        self.process = spawnShell(projectPath)

        if WINDOWS:
            self._startWindowsReaders()
        else:
            resizePty(self.process["masterFd"], 80, 24)
            self.readerTask = loop.create_task(self._pumpPosixOutput())

    async def send(self, payload):
        if self.websocket is None:
            return

        try:
            await self.websocket.send(json.dumps(payload))
        except Exception:
            self.websocket = None

    async def attach(self, websocket):
        if self.websocket is not None and self.websocket is not websocket:
            await self.websocket.close()

        self.websocket = websocket
        await self.send(
            {
                "type": "snapshot",
                "data": self.buffer,
                "closed": self.closed,
            }
        )

        if self.closed:
            await self._sendExit()

    def detach(self, websocket):
        if self.websocket is websocket:
            self.websocket = None

    async def writeInput(self, data):
        if self.closed or not data:
            return

        if WINDOWS:
            await asyncio.to_thread(writeProcessInput, self.process["pty"], data)
            return

        encodedData = data.encode("utf-8")
        await asyncio.to_thread(os.write, self.process["masterFd"], encodedData)

    async def writeBinaryInput(self, data):
        if self.closed or not data:
            return

        if WINDOWS:
            await asyncio.to_thread(
                writeProcessInput, self.process["pty"], data.encode("latin-1")
            )
            return

        encodedData = data.encode("latin-1")
        await asyncio.to_thread(os.write, self.process["masterFd"], encodedData)

    async def resize(self, cols, rows):
        if self.closed:
            return

        if WINDOWS:
            await asyncio.to_thread(resizeWindowsPty, self.process["pty"], cols, rows)
            return

        await asyncio.to_thread(resizePty, self.process["masterFd"], cols, rows)

    async def _pumpPosixOutput(self):
        try:
            while True:
                try:
                    chunk = await asyncio.to_thread(
                        os.read, self.process["masterFd"], 4096
                    )
                except OSError as exc:
                    if exc.errno == errno.EIO:
                        break
                    raise

                if not chunk:
                    break

                await self._recordOutput(chunk.decode("utf-8", errors="replace"))
        finally:
            self.closed = True
            await self._sendExit()

    def _startWindowsReaders(self):
        threading.Thread(
            target=self._readWindowsStream,
            args=(self.process["pty"],),
            daemon=True,
        ).start()
        threading.Thread(target=self._waitForWindowsExit, daemon=True).start()

    def _readWindowsStream(self, stream):
        while True:
            try:
                chunk = stream.read(4096)
            except Exception:
                chunk = ""

            if not chunk:
                break

            if isinstance(chunk, bytes):
                decodedChunk = chunk.decode("utf-8", errors="replace")
            else:
                decodedChunk = chunk

            future = asyncio.run_coroutine_threadsafe(
                self._recordOutput(decodedChunk),
                self.loop,
            )
            try:
                future.result()
            except Exception:
                break

    def _waitForWindowsExit(self):
        self.process["pty"].wait()
        future = asyncio.run_coroutine_threadsafe(self._handleExit(), self.loop)
        try:
            future.result()
        except Exception:
            return

    async def _recordOutput(self, chunk):
        if not chunk:
            return

        self.buffer = f"{self.buffer}{chunk}"[-BUFFER_LIMIT:]
        await self.send({"type": "output", "data": chunk})

    async def _handleExit(self):
        if self.closed:
            return

        self.closed = True
        await self._sendExit()

    async def _sendExit(self):
        if self.exitSent:
            return

        self.exitSent = True
        await self.send({"type": "exit"})

serverThread = None
serverLock = threading.Lock()
serverReady = threading.Event()
serverUrl = None
serverError = None
serverLoop = None
sessions = {}

def buildShellEnv():
    env = os.environ.copy()
    if not WINDOWS:
        env.setdefault("TERM", "xterm-256color")
    return env

def resolveShellCwd(projectPath):
    if not isinstance(projectPath, str):
        return None

    trimmedPath = projectPath.strip()
    if not trimmedPath:
        return None

    expandedPath = os.path.expanduser(trimmedPath)
    absolutePath = os.path.abspath(expandedPath)
    if not os.path.isdir(absolutePath):
        return None

    return absolutePath

def resolveShellCommand():
    if WINDOWS:
        powershell = shutil.which("pwsh") or shutil.which("powershell")
        if powershell:
            return [powershell, "-NoLogo"]

        comspec = os.environ.get("COMSPEC")
        if comspec:
            return [comspec]

        return ["cmd.exe"]

    shell = (
        os.environ.get("SHELL")
        or shutil.which("bash")
        or shutil.which("sh")
        or "/bin/sh"
    )
    shellName = os.path.basename(shell)
    shellCommand = [shell]
    if shellName in {"bash", "zsh", "sh", "fish"}:
        shellCommand.append("-i")
    return shellCommand

def spawnShell(projectPath=""):
    shellCommand = resolveShellCommand()
    shellCwd = resolveShellCwd(projectPath)
    env = buildShellEnv()

    if WINDOWS:
        ptyProcess = PtyProcess.spawn(
            shellCommand,
            cwd=shellCwd,
            env=env,
            dimensions=(24, 80),
        )
        return {"pty": ptyProcess}

    pid, masterFd = pty.fork()
    if pid == 0:
        if shellCwd:
            os.chdir(shellCwd)
        os.execvpe(shellCommand[0], shellCommand, env)

    return {"pid": pid, "masterFd": masterFd}

def writeProcessInput(stream, data):
    if stream is None:
        return

    stream.write(data)


def resizeWindowsPty(ptyProcess, cols, rows):
    if cols <= 0 or rows <= 0:
        return

    ptyProcess.setwinsize(rows, cols)

def resizePty(masterFd, cols, rows):
    if cols <= 0 or rows <= 0:
        return

    winsize = struct.pack("HHHH", rows, cols, 0, 0)
    fcntl.ioctl(masterFd, termios.TIOCSWINSZ, winsize)

def getOrCreateSession(tabId, savedHistory="", projectPath=""):
    session = sessions.get(tabId)
    if session is not None:
        return session

    session = TerminalSession(tabId, serverLoop, savedHistory, projectPath)
    sessions[tabId] = session
    return session

async def handleTerminal(websocket):
    try:
        attachMessage = await websocket.recv()
    except Exception:
        return

    if not isinstance(attachMessage, str):
        await websocket.close()
        return

    try:
        attachPayload = json.loads(attachMessage)
    except json.JSONDecodeError:
        await websocket.close()
        return

    if attachPayload.get("type") != "attach":
        await websocket.close()
        return

    tabId = str(attachPayload.get("tabId", "")).strip()
    savedHistory = str(attachPayload.get("history", ""))
    projectPath = str(attachPayload.get("projectPath", ""))
    if not tabId:
        await websocket.close()
        return

    session = getOrCreateSession(tabId, savedHistory, projectPath)
    await session.attach(websocket)

    try:
        async for message in websocket:
            if not isinstance(message, str):
                continue

            try:
                payload = json.loads(message)
            except json.JSONDecodeError:
                continue

            if payload.get("type") == "input":
                await session.writeInput(str(payload.get("data", "")))
            elif payload.get("type") == "inputBinary":
                await session.writeBinaryInput(str(payload.get("data", "")))
            elif payload.get("type") == "resize":
                cols = int(payload.get("cols", 0))
                rows = int(payload.get("rows", 0))
                await session.resize(cols, rows)
    finally:
        session.detach(websocket)

async def runServer():
    global serverUrl

    async with ws.serve(handleTerminal, "127.0.0.1", 0) as server:
        sock = server.sockets[0]
        host, port = sock.getsockname()[:2]
        serverUrl = f"ws://{host}:{port}"
        serverReady.set()
        await asyncio.Future()

def serverMain():
    global serverError, serverLoop

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    serverLoop = loop

    try:
        loop.run_until_complete(runServer())
    except Exception as exc:
        serverError = exc
        serverReady.set()
    finally:
        loop.close()

def terminalWebsocket():
    global serverError, serverThread, serverUrl

    with serverLock:
        if serverThread and serverThread.is_alive() and serverUrl is not None:
            return serverUrl

        serverError = None
        serverUrl = None
        serverReady.clear()
        serverThread = threading.Thread(target=serverMain, daemon=True)
        serverThread.start()

    serverReady.wait(timeout=5)

    if serverError is not None:
        raise RuntimeError("Failed to start terminal websocket server") from serverError

    if serverUrl is None:
        raise RuntimeError("Terminal websocket server did not start in time")

    return serverUrl
