interface PyWebviewAPI {
  terminalWebsocket?: () => Promise<string> | string;
  loadAppState?: () => Promise<unknown> | unknown;
  saveAppState?: (state: unknown) => Promise<boolean> | boolean;
  resolveProjectPath?: (projectPath: string) => Promise<{ ok: boolean; path?: string; error?: string }> | { ok: boolean; path?: string; error?: string };
  getOS?: () => string;
}

declare global {
  interface Window {
    pywebview: {
      api: PyWebviewAPI;
    };
  }
}

export {};
