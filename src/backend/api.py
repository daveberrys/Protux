import json
import os
import sys

import webview as wv
import src.backend.system.terminal as system

defaultState = {
    "activeProjectId": "project-1",
    "sidebarWidth": 260,
    "projects": [
        {
            "id": "project-1",
            "name": "Project 1",
            "projectPath": "",
            "splitRatio": 0.5,
            "leftTabs": [
                {
                    "id": "tab-left-1",
                    "title": "~",
                    "history": "",
                }
            ],
            "rightTabs": [
                {
                    "id": "tab-right-1",
                    "title": "~",
                    "history": "",
                }
            ],
            "activeLeftTabId": "tab-left-1",
            "activeRightTabId": "tab-right-1",
            "splitView": True,
        }
    ],
}


class API:
    def __init__(self):
        self.window = wv.active_window()
        self.appID = "dev.pages.codedave.protux"

    def getConfigPath(self):
        if sys.platform == "win32":
            return os.path.join(os.getenv("APPDATA"), self.appID)

        if sys.platform == "darwin":
            return os.path.join(os.getenv("HOME"), "Library", "Application Support", self.appID)

        return os.path.join(os.getenv("HOME"), ".config", self.appID)

    def _getStatePath(self):
        return os.path.join(self.getConfigPath(), "state.json")

    def _ensureConfigDir(self):
        os.makedirs(self.getConfigPath(), exist_ok=True)

    def loadAppState(self):
        self._ensureConfigDir()
        statePath = self._getStatePath()

        if not os.path.exists(statePath):
            self.saveAppState(defaultState)
            return defaultState

        with open(statePath, "r", encoding="utf-8") as stateFile:
            return json.load(stateFile)

    def saveAppState(self, state):
        self._ensureConfigDir()
        statePath = self._getStatePath()

        with open(statePath, "w", encoding="utf-8") as stateFile:
            json.dump(state, stateFile, indent=2)

        return True

    def resolveProjectPath(self, projectPath):
        if not isinstance(projectPath, str):
            return {"ok": False, "error": "Project path must be a string."}

        trimmedPath = projectPath.strip()
        if not trimmedPath:
            return {"ok": True, "path": ""}

        expandedPath = os.path.expanduser(trimmedPath)
        absolutePath = os.path.abspath(expandedPath)

        if not os.path.isdir(absolutePath):
            return {"ok": False, "error": "Project path must point to an existing folder."}

        return {"ok": True, "path": absolutePath}

    def terminalWebsocket(self):
        return system.terminalWebsocket()
