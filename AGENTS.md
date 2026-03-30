# AGENTS.md

This file tells coding agents how to work in this repository.

## Project Overview

Protux is a desktop app built with:

- Python backend
- `pywebview` desktop window host
- Svelte frontend
- Vite dev server for frontend development
- PTY-backed terminal sessions over local WebSockets

The project is currently organized like this:

- `run.py`
  Development/build entrypoint.
- `window.py`
  Creates and starts the pywebview window.
- `src/backend/api.py`
  Python API exposed to `window.pywebview.api`.
- `src/backend/system/aa.py`
  Terminal/session backend. PTYs, session registry, websocket handling.
- `src/frontend/src/App.svelte`
  Main frontend orchestration layer.
- `src/frontend/src/lib/workspace.ts`
  Shared workspace/project/tab types and helper functions.
- `src/frontend/src/lib/components/`
  Svelte UI components.

## Primary Goal

When making changes, preserve these behaviors:

- The app launches in dev mode via `python run.py dev`.
- The frontend talks to the Python backend only through `window.pywebview.api`.
- Terminal tabs are persistent by tab ID.
- Terminal sessions can survive tab switches and pane switches.
- Workspace state is stored in the config directory via `API.loadAppState()` and `API.saveAppState()`.

## Required Workflow

When changing code:

1. Read the relevant files first.
2. Keep changes small and local when possible.
3. Preserve existing behavior unless the task explicitly asks to change it.
4. Run verification after edits.

Minimum verification:

- Frontend changes: run `npm run check` in `src/frontend`
- Backend changes: run `python -m py_compile window.py run.py src/backend/api.py src/backend/system/aa.py`

If you change terminal/session logic, verify both:

- Creating a new tab
- Switching tabs
- Switching between single/split view
- Closing the app window

## Commands

Use these commands from the repo root:

```bash
python run.py dev
python run.py test
python run.py compile
```

Frontend-only checks:

```bash
cd src/frontend
npm run check
pnpm run dev
pnpm run build
```

Backend compile check:

```bash
python -m py_compile window.py run.py src/backend/api.py src/backend/system/aa.py
```

## Architecture Notes

### 1. Python window host

`window.py` owns pywebview window creation and application shutdown behavior.

Important:

- If window-close behavior is broken, inspect `window.py` first.
- Do not casually remove close/shutdown hooks.
- In dev mode the Vite server is external to pywebview and must be shut down cleanly.

### 2. Python API layer

`src/backend/api.py` is the boundary exposed to the frontend.

Rules:

- If the frontend needs backend functionality, add it here.
- Return plain JSON-serializable values where possible.
- Config-backed app state is loaded and saved here.
- Keep file system and persistence concerns in this layer, not in the frontend.

### 3. Terminal backend

`src/backend/system/aa.py` manages:

- PTY creation
- shell processes
- websocket server
- session registry keyed by tab ID
- attach/detach behavior
- session buffer/history

Critical rule:

- Do not revert to “one websocket = one terminal process”.

The app now relies on persistent sessions per tab ID. Breaking that will reintroduce:

- tabs dying when switching
- background sessions disappearing
- blank new tabs or split-pane reattach issues

If changing this file, think in terms of:

- session lifecycle
- websocket attachment lifecycle
- PTY lifecycle
- shutdown lifecycle

### 4. Frontend app orchestration

`src/frontend/src/App.svelte` is responsible for:

- loading/saving workspace state
- connecting panes to terminal sessions
- tab/project actions
- split view behavior
- right-click menu actions
- coordinating xterm instances

It should not hold unrelated UI markup if it can be moved into a component.

### 5. Frontend components

Current components:

- `ProjectSidebar.svelte`
- `TerminalPane.svelte`
- `ContextMenu.svelte`

Use components for:

- repeated UI sections
- view-only concerns
- markup that does not need to own the terminal session state machine

Avoid moving session orchestration into leaf components unless the change clearly improves the design.

## Styling and Layout Rules

This app is layout-sensitive.

Be careful with:

- `height: 100vh`
- `min-height: 0`
- `overflow: hidden`
- `overflow-y: auto`
- flex/grid shrink behavior

Past bugs were caused by:

- sidebar not having a real scroll container
- pane containers not shrinking on window resize
- xterm being attached to a dead DOM node after remount

If you change layout:

1. test single pane
2. test split pane
3. resize window larger
4. resize window smaller
5. verify cursor is still visible
6. verify sidebar scroll still works

## Terminal/Xterm Rules

The frontend terminal renderer uses `xterm.js`.

Rules:

- Do not replace xterm with a raw `<pre>` renderer.
- Always call fit/resize after major layout changes.
- If a pane host DOM node changes, rebuild or rebind the terminal correctly.
- A websocket close is not automatically equivalent to terminal death.
- Distinguish:
  - detach
  - attach
  - session exit

Protocol expectations:

- frontend sends `attach`
- frontend sends `input`
- frontend sends `resize`
- backend sends `snapshot`
- backend sends `output`
- backend sends `exit`

Do not casually change these message types without updating both sides.

## Persistence Rules

Workspace state is stored under the config directory:

- Linux: `~/.config/io.github.pinpointtools.protux/`

Current stored content includes:

- projects
- tabs
- active tab IDs
- split mode
- saved terminal history

Rules:

- Keep saved state JSON-compatible.
- Prefer additive, backward-compatible schema changes.
- If you add new state, provide sensible defaults.

## Naming Conventions

Preferred style in this repo:

- camelCase for local code we control

Exceptions:

- external library APIs that are snake_case or otherwise fixed
- Python standard library / framework APIs
- protocol keys only when intentionally preserved

Do not rename external APIs such as:

- `active_window()`
- `new_event_loop()`
- `set_event_loop()`
- `run_until_complete()`
- `to_thread()`
- `create_task()`
- `is_alive()`

## When Fixing Bugs

First classify the bug:

- frontend rendering bug
- layout bug
- xterm lifecycle bug
- websocket attach/detach bug
- PTY/session bug
- pywebview lifecycle bug
- dev-server process bug

Then fix the smallest correct layer.

Examples:

- Blank pane after toggling split:
  likely frontend runtime/DOM host lifecycle
- Tab dies after switching:
  likely backend session model or attach/detach logic
- App stays alive after closing window:
  likely `window.py` / `run.py` process lifecycle
- History missing after reattach:
  likely session buffer or config persistence mismatch

## Do Not Do These Without Strong Reason

- Do not remove the backend session registry.
- Do not move persistence logic fully into the frontend.
- Do not replace pywebview API calls with direct HTTP requests.
- Do not add unnecessary frameworks or state libraries.
- Do not introduce broad refactors unless the user asked for them.
- Do not silently change saved-state schema without preserving compatibility.

## Good Change Patterns

Preferred:

- small components for repeated UI
- small helper modules for shared types/state transforms
- backend changes paired with protocol updates in the frontend
- explicit verification after every meaningful edit

Avoid:

- giant monolithic Svelte files
- duplicated state logic
- mixing DOM lifecycle and persistence logic in the same helper
- hidden reconnection side effects during shutdown

## If You Touch Terminal Sessions

You must verify:

1. open app
2. create a new tab
3. type in old tab
4. switch to new tab
5. switch back
6. toggle split on
7. toggle split off
8. toggle split on again
9. close one tab
10. close the app window

If any of those fail, the task is not done.

## If You Touch Shutdown Behavior

You must verify:

1. `python run.py dev`
2. close the window with the window manager close button
3. confirm the Python process exits
4. confirm the Vite dev server process also exits in dev mode

## If You Touch Sidebar or Layout

You must verify:

1. enough projects exist to overflow the sidebar
2. sidebar scroll works
3. terminal remains visible after vertical shrink
4. terminal remains visible after horizontal shrink
5. split layout still renders both panes correctly

## Final Guidance

This codebase is sensitive to lifecycle interactions between:

- pywebview
- Vite dev server
- WebSocket sessions
- PTY processes
- xterm DOM hosts

When in doubt, prefer explicit lifecycle handling over “it should probably clean itself up”.
