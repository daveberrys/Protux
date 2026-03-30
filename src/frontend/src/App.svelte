<script lang="ts">
    import { onMount, tick } from 'svelte';
    import { Terminal } from 'xterm';
    import { FitAddon } from '@xterm/addon-fit';
    import 'xterm/css/xterm.css';

    import ContextMenu from './lib/components/ContextMenu.svelte';
    import ProjectPathDialog from './lib/components/dialog/ProjectPath.svelte';
    import ProjectSidebar from './lib/components/ProjectSidebar.svelte';
    import TabRenameDialog from './lib/components/dialog/TabRename.svelte';
    import TerminalPane from './lib/components/TerminalPane.svelte';
    import {
        cloneDefaultState,
        createProject,
        createTab,
        DEFAULT_STATE,
        ensureProjectHasTabs,
        getActiveProject,
        getActiveTab,
        getTabs,
        normalizeAppState,
        normalizeSidebarWidth,
        normalizeSplitRatio,
        type AppState,
        type ContextMenuState,
        type PaneKey,
        type Project,
    } from './lib/workspace';

    type PaneRuntime = {
        terminal: Terminal;
        fitAddon: FitAddon;
        resizeObserver: ResizeObserver | null;
        resizeFrame: number | null;
        socket: WebSocket | null;
        isReplaying: boolean;
        currentProjectId: string | null;
        currentTabId: string | null;
        host: HTMLDivElement;
    };

    const paneRuntimes: Record<PaneKey, PaneRuntime | null> = { left: null, right: null };

    type DragState =
        | {
              kind: 'sidebar';
              startX: number;
              startSidebarWidth: number;
          }
        | {
              kind: 'split';
              startX: number;
              startSplitRatio: number;
              workspaceWidth: number;
              projectId: string;
          }
        | null;

    let saveTimer: ReturnType<typeof setTimeout> | null = null;
    let leftHost: HTMLDivElement | null = null;
    let rightHost: HTMLDivElement | null = null;
    let workspaceHost: HTMLElement | null = null;
    let paneStatus: Record<PaneKey, string> = { left: 'Idle', right: 'Idle' };
    let appState: AppState = DEFAULT_STATE;
    let activePane: PaneKey = 'left';
    let activeProject: Project | undefined = DEFAULT_STATE.projects[0];
    let contextMenu: ContextMenuState = null;
    let projectPathDialog = {
        open: false,
        projectId: '',
        projectName: '',
        value: '',
        errorMessage: '',
    };
    let tabRenameDialog = {
        open: false,
        projectId: '',
        projectName: '',
        pane: 'left' as PaneKey,
        tabId: '',
        value: '',
        errorMessage: '',
    };
    let dragState: DragState = null;
    let isShuttingDown = false;

    function getPyApi() {
        return window.pywebview?.api;
    }

    function closeContextMenu() {
        contextMenu = null;
    }

    function closeProjectPathDialog() {
        projectPathDialog = {
            open: false,
            projectId: '',
            projectName: '',
            value: '',
            errorMessage: '',
        };
    }

    function closeTabRenameDialog() {
        tabRenameDialog = {
            open: false,
            projectId: '',
            projectName: '',
            pane: 'left',
            tabId: '',
            value: '',
            errorMessage: '',
        };
    }

    function setAppState(nextState: AppState) {
        appState = normalizeAppState(nextState);
        activeProject = getActiveProject(appState);
    }

    function scheduleSave() {
        if (isShuttingDown || !getPyApi()?.saveAppState) {
            return;
        }

        if (saveTimer) {
            clearTimeout(saveTimer);
        }

        saveTimer = setTimeout(() => {
            void getPyApi()?.saveAppState?.(appState);
        }, 250);
    }

    function updateSidebarWidth(nextWidth: number) {
        setAppState({
            ...appState,
            sidebarWidth: normalizeSidebarWidth(nextWidth),
        });
        scheduleSave();
    }

    function updateProject(projectId: string, updater: (project: Project) => Project) {
        setAppState({
            ...appState,
            projects: appState.projects.map((project) =>
                project.id === projectId ? updater(project) : project,
            ),
        });
    }

    function appendTabHistory(projectId: string, pane: PaneKey, tabId: string, chunk: string) {
        const project = appState.projects.find((entry) => entry.id === projectId);
        const tab = project ? getTabs(project, pane).find((entry) => entry.id === tabId) : null;
        if (!tab) {
            return;
        }

        tab.history = `${tab.history}${chunk}`.slice(-60000);
        scheduleSave();
    }

    function disconnectPane(pane: PaneKey) {
        const runtime = paneRuntimes[pane];
        if (!runtime) {
            return;
        }

        const socket = runtime.socket;
        if (runtime.resizeFrame !== null) {
            cancelAnimationFrame(runtime.resizeFrame);
            runtime.resizeFrame = null;
        }
        runtime.socket = null;
        runtime.currentProjectId = null;
        runtime.currentTabId = null;
        paneStatus[pane] = 'Idle';
        socket?.close();
    }

    function focusPane(pane: PaneKey) {
        activePane = pane;
        paneRuntimes[pane]?.terminal.focus();
    }

    function sendResize(pane: PaneKey) {
        const runtime = paneRuntimes[pane];
        if (!runtime) {
            return;
        }

        runtime.fitAddon.fit();
        if (!runtime.socket || runtime.socket.readyState !== WebSocket.OPEN) {
            return;
        }

        try {
            runtime.socket.send(
                JSON.stringify({
                    type: 'resize',
                    cols: runtime.terminal.cols,
                    rows: runtime.terminal.rows,
                }),
            );
        } catch {
            runtime.socket = null;
            paneStatus[pane] = 'Detached';
        }
    }

    function schedulePaneResize(pane: PaneKey) {
        const runtime = paneRuntimes[pane];
        if (!runtime) {
            return;
        }

        if (runtime.resizeFrame !== null) {
            cancelAnimationFrame(runtime.resizeFrame);
        }

        runtime.resizeFrame = requestAnimationFrame(() => {
            const currentRuntime = paneRuntimes[pane];
            if (!currentRuntime) {
                return;
            }

            currentRuntime.resizeFrame = null;
            sendResize(pane);
        });
    }

    function resizeAllPanes() {
        schedulePaneResize('left');
        schedulePaneResize('right');
    }

    function writeTerminal(runtime: PaneRuntime, data: string) {
        return new Promise<void>((resolve) => {
            runtime.terminal.write(data, () => resolve());
        });
    }

    async function copySelection(runtime: PaneRuntime) {
        const selection = runtime.terminal.getSelection();
        if (!selection) {
            return;
        }

        await navigator.clipboard.writeText(selection);
        runtime.terminal.clearSelection();
    }

    async function pasteClipboard(runtime: PaneRuntime) {
        const clipboardText = await navigator.clipboard.readText();
        if (!clipboardText || !runtime.socket) {
            return;
        }

        runtime.terminal.paste(clipboardText);
    }

    function buildRuntime(pane: PaneKey, host: HTMLDivElement) {
        const existingRuntime = paneRuntimes[pane];
        if (existingRuntime?.host === host) {
            return;
        }

        if (existingRuntime) {
            existingRuntime.resizeObserver?.disconnect();
            if (existingRuntime.resizeFrame !== null) {
                cancelAnimationFrame(existingRuntime.resizeFrame);
            }
            existingRuntime.terminal.dispose();
            paneRuntimes[pane] = null;
        }

        const terminal = new Terminal({
            cursorBlink: true,
            fontFamily: '"0xProto Nerd Font", monospace',
            fontSize: 14,
            scrollOnUserInput: true,
            scrollback: 5000,
            theme: {
                background: '#000000',
                foreground: '#f5f5f5',
            },
        });

        const fitAddon = new FitAddon();
        terminal.loadAddon(fitAddon);
        terminal.open(host);
        fitAddon.fit();
        void document.fonts?.load('14px "0xProto Nerd Font"').then(() => {
            fitAddon.fit();
        });

        terminal.onData((data) => {
            const runtime = paneRuntimes[pane];
            if (!runtime || runtime.isReplaying || !runtime.socket) {
                return;
            }

            runtime.socket.send(JSON.stringify({ type: 'input', data }));
        });

        terminal.onBinary((data) => {
            const runtime = paneRuntimes[pane];
            if (!runtime || runtime.isReplaying || !runtime.socket) {
                return;
            }

            runtime.socket.send(JSON.stringify({ type: 'inputBinary', data }));
        });

        terminal.attachCustomKeyEventHandler((event) => {
            const runtime = paneRuntimes[pane];
            if (!runtime || event.type !== 'keydown') {
                return true;
            }

            const key = event.key.toLowerCase();
            const hasSelection = runtime.terminal.hasSelection();
            const isCopyShortcut =
                (event.ctrlKey || event.metaKey) && !event.altKey && key === 'c' && (event.shiftKey || hasSelection);
            const isPasteShortcut =
                ((event.ctrlKey || event.metaKey) && !event.altKey && event.shiftKey && key === 'v') ||
                (event.shiftKey && key === 'insert');

            if (isCopyShortcut) {
                event.preventDefault();
                void copySelection(runtime);
                return false;
            }

            if (isPasteShortcut) {
                event.preventDefault();
                void pasteClipboard(runtime);
                return false;
            }

            return true;
        });

        const resizeObserver = new ResizeObserver(() => {
            schedulePaneResize(pane);
        });
        resizeObserver.observe(host);

        paneRuntimes[pane] = {
            terminal,
            fitAddon,
            resizeObserver,
            resizeFrame: null,
            socket: null,
            isReplaying: false,
            currentProjectId: null,
            currentTabId: null,
            host,
        };
    }

    async function connectPaneToTab(pane: PaneKey) {
        if (isShuttingDown) {
            return;
        }

        const runtime = paneRuntimes[pane];
        const project = getActiveProject(appState);
        const tab = getActiveTab(project, pane);

        if (!runtime || !tab) {
            return;
        }

        if (pane === 'right' && !project.splitView) {
            disconnectPane('right');
            runtime.terminal.clear();
            return;
        }

        if (
            runtime.currentProjectId === project.id &&
            runtime.currentTabId === tab.id &&
            runtime.socket?.readyState === WebSocket.OPEN
        ) {
            sendResize(pane);
            return;
        }

        runtime.socket?.close();
        runtime.terminal.reset();
        runtime.terminal.clear();

        paneStatus[pane] = 'Connecting...';

        if (!getPyApi()?.terminalWebsocket) {
            runtime.terminal.writeln('pywebview terminal API is unavailable.');
            paneStatus[pane] = 'Unavailable';
            return;
        }

        const websocketUrl = await getPyApi()!.terminalWebsocket!();
        const socket = new WebSocket(websocketUrl);
        runtime.socket = socket;
        runtime.currentProjectId = project.id;
        runtime.currentTabId = tab.id;

        const boundProjectId = project.id;
        const boundTabId = tab.id;

        socket.addEventListener('open', () => {
            if (isShuttingDown) {
                socket.close();
                return;
            }

            if (runtime.currentProjectId !== boundProjectId || runtime.currentTabId !== boundTabId) {
                socket.close();
                return;
            }

            paneStatus[pane] = 'Connected';
            socket.send(
                JSON.stringify({
                    type: 'attach',
                    tabId: boundTabId,
                    history: tab.history,
                    projectPath: project.projectPath,
                }),
            );
            sendResize(pane);
        });

        socket.addEventListener('message', async (event) => {
            if (isShuttingDown) {
                return;
            }

            if (runtime.currentProjectId !== boundProjectId || runtime.currentTabId !== boundTabId) {
                return;
            }

            let payload: { type?: string; data?: string } | null = null;
            try {
                payload = JSON.parse(String(event.data));
            } catch {
                payload = null;
            }

            if (!payload?.type) {
                return;
            }

            if (payload.type === 'snapshot') {
                const snapshot = String(payload.data ?? '');
                runtime.terminal.reset();
                runtime.isReplaying = true;
                try {
                    await writeTerminal(runtime, snapshot);
                    runtime.terminal.scrollToBottom();
                } finally {
                    runtime.isReplaying = false;
                }

                const projectEntry = appState.projects.find((entry) => entry.id === boundProjectId);
                const tabEntry = projectEntry ? getTabs(projectEntry, pane).find((entry) => entry.id === boundTabId) : null;
                if (tabEntry) {
                    tabEntry.history = snapshot.slice(-60000);
                    scheduleSave();
                }
                return;
            }

            if (payload.type === 'output') {
                const chunk = String(payload.data ?? '');
                if (!chunk) {
                    return;
                }

                runtime.terminal.write(chunk);
                runtime.terminal.scrollToBottom();
                appendTabHistory(boundProjectId, pane, boundTabId, chunk);
                return;
            }

            if (payload.type === 'exit') {
                paneStatus[pane] = 'Exited';
                runtime.socket = null;
                runtime.currentProjectId = null;
                runtime.currentTabId = null;
                void closeTab(pane, boundTabId, boundProjectId);
            }
        });

        socket.addEventListener('close', () => {
            if (isShuttingDown || runtime.socket !== socket) {
                return;
            }

            paneStatus[pane] = 'Detached';
            runtime.socket = null;
        });

        socket.addEventListener('error', () => {
            if (isShuttingDown) {
                return;
            }

            if (runtime.currentProjectId !== boundProjectId || runtime.currentTabId !== boundTabId) {
                return;
            }

            paneStatus[pane] = 'Error';
            runtime.terminal.writeln('\r\n[terminal websocket error]');
        });
    }

    async function syncVisibleTerminals() {
        await tick();

        if (leftHost) {
            buildRuntime('left', leftHost);
        }

        if (rightHost) {
            buildRuntime('right', rightHost);
        }

        await connectPaneToTab('left');
        await connectPaneToTab('right');
        resizeAllPanes();
    }

    async function addProject() {
        const project = createProject(`Project ${appState.projects.length + 1}`);
        setAppState({
            ...appState,
            activeProjectId: project.id,
            projects: [...appState.projects, project],
        });
        scheduleSave();
        await syncVisibleTerminals();
    }

    async function renameProject(projectId: string) {
        const project = appState.projects.find((entry) => entry.id === projectId);
        const nextName = window.prompt('Rename project', project?.name ?? '')?.trim();
        if (!project || !nextName) {
            return;
        }

        updateProject(projectId, (entry) => ({ ...entry, name: nextName }));
        scheduleSave();
    }

    function openProjectPathDialog(projectId: string) {
        const project = appState.projects.find((entry) => entry.id === projectId);
        if (!project) {
            return;
        }

        projectPathDialog = {
            open: true,
            projectId,
            projectName: project.name,
            value: project.projectPath,
            errorMessage: '',
        };
    }

    async function saveProjectPath(rawPath: string) {
        const projectId = projectPathDialog.projectId;
        const project = appState.projects.find((entry) => entry.id === projectId);
        if (!project) {
            closeProjectPathDialog();
            return;
        }

        const nextPath = rawPath.trim();
        const pyApi = getPyApi();

        if (pyApi?.resolveProjectPath) {
            const result = await pyApi.resolveProjectPath(nextPath);
            if (!result?.ok) {
                projectPathDialog = {
                    ...projectPathDialog,
                    errorMessage: String(result?.error ?? 'Unable to use that project path.'),
                    value: rawPath,
                };
                return;
            }

            updateProject(projectId, (entry) => ({
                ...entry,
                projectPath: String(result.path ?? ''),
            }));
        } else {
            updateProject(projectId, (entry) => ({
                ...entry,
                projectPath: nextPath,
            }));
        }

        scheduleSave();
        closeProjectPathDialog();
    }

    async function deleteProject(projectId: string) {
        if (appState.projects.length === 1) {
            const replacement = createProject('Project 1');
            setAppState({
                activeProjectId: replacement.id,
                sidebarWidth: appState.sidebarWidth,
                projects: [replacement],
            });
            scheduleSave();
            await syncVisibleTerminals();
            return;
        }

        const remainingProjects = appState.projects.filter((entry) => entry.id !== projectId);
        const nextActiveProjectId =
            appState.activeProjectId === projectId ? remainingProjects[0].id : appState.activeProjectId;

        setAppState({
            activeProjectId: nextActiveProjectId,
            sidebarWidth: appState.sidebarWidth,
            projects: remainingProjects,
        });
        scheduleSave();
        await syncVisibleTerminals();
    }

    async function selectProject(projectId: string) {
        setAppState({ ...appState, activeProjectId: projectId });
        scheduleSave();
        await syncVisibleTerminals();
    }

    async function addTab(pane: PaneKey) {
        const project = getActiveProject(appState);
        const tab = createTab(pane);

        updateProject(project.id, (entry) => ({
            ...entry,
            leftTabs: pane === 'left' ? [...entry.leftTabs, tab] : entry.leftTabs,
            rightTabs: pane === 'right' ? [...entry.rightTabs, tab] : entry.rightTabs,
            activeLeftTabId: pane === 'left' ? tab.id : entry.activeLeftTabId,
            activeRightTabId: pane === 'right' ? tab.id : entry.activeRightTabId,
        }));

        scheduleSave();
        await syncVisibleTerminals();
        focusPane(pane);
        resizeAllPanes();
    }

    function openTabRenameDialog(pane: PaneKey, tabId: string, projectId = getActiveProject(appState).id) {
        const project = appState.projects.find((entry) => entry.id === projectId);
        const tab = project ? getTabs(project, pane).find((entry) => entry.id === tabId) : null;
        if (!project || !tab) {
            return;
        }

        tabRenameDialog = {
            open: true,
            projectId,
            projectName: project.name,
            pane,
            tabId,
            value: tab.title,
            errorMessage: '',
        };
    }

    async function renameTab(rawTitle: string) {
        const projectId = tabRenameDialog.projectId;
        const pane = tabRenameDialog.pane;
        const tabId = tabRenameDialog.tabId;
        const project = appState.projects.find((entry) => entry.id === projectId);
        const tab = project ? getTabs(project, pane).find((entry) => entry.id === tabId) : null;
        const nextTitle = rawTitle.trim();
        if (!project || !tab) {
            closeTabRenameDialog();
            return;
        }

        if (!nextTitle) {
            tabRenameDialog = {
                ...tabRenameDialog,
                value: rawTitle,
                errorMessage: 'Tab name cannot be empty.',
            };
            return;
        }

        updateProject(projectId, (entry) => ({
            ...entry,
            leftTabs:
                pane === 'left'
                    ? entry.leftTabs.map((item) => (item.id === tabId ? { ...item, title: nextTitle } : item))
                    : entry.leftTabs,
            rightTabs:
                pane === 'right'
                    ? entry.rightTabs.map((item) => (item.id === tabId ? { ...item, title: nextTitle } : item))
                    : entry.rightTabs,
        }));
        scheduleSave();
        closeTabRenameDialog();
    }

    async function closeTab(pane: PaneKey, tabId: string, projectId = getActiveProject(appState).id) {
        const project = appState.projects.find((entry) => entry.id === projectId);
        if (!project) {
            return;
        }

        const runtime = paneRuntimes[pane];
        if (runtime?.currentProjectId === projectId && runtime.currentTabId === tabId) {
            const socket = runtime.socket;
            runtime.socket = null;
            runtime.currentProjectId = null;
            runtime.currentTabId = null;
            socket?.close();
            runtime.terminal.reset();
            runtime.terminal.clear();
        }

        updateProject(projectId, (entry) => {
            const filteredLeftTabs =
                pane === 'left' ? entry.leftTabs.filter((tab) => tab.id !== tabId) : entry.leftTabs;
            const filteredRightTabs =
                pane === 'right' ? entry.rightTabs.filter((tab) => tab.id !== tabId) : entry.rightTabs;

            const nextEntry = {
                ...entry,
                leftTabs: filteredLeftTabs,
                rightTabs: filteredRightTabs,
                activeLeftTabId:
                    pane === 'left' && entry.activeLeftTabId === tabId
                        ? filteredLeftTabs[0]?.id ?? ''
                        : entry.activeLeftTabId,
                activeRightTabId:
                    pane === 'right' && entry.activeRightTabId === tabId
                        ? filteredRightTabs[0]?.id ?? ''
                        : entry.activeRightTabId,
            };

            return ensureProjectHasTabs(ensureProjectHasTabs(nextEntry, 'left'), 'right');
        });

        scheduleSave();
        await syncVisibleTerminals();
        focusPane(pane);
    }

    async function selectTab(pane: PaneKey, tabId: string) {
        const project = getActiveProject(appState);
        updateProject(project.id, (entry) => ({
            ...entry,
            activeLeftTabId: pane === 'left' ? tabId : entry.activeLeftTabId,
            activeRightTabId: pane === 'right' ? tabId : entry.activeRightTabId,
        }));

        scheduleSave();
        await connectPaneToTab(pane);
        focusPane(pane);
        resizeAllPanes();
    }

    async function toggleSplitView() {
        const project = getActiveProject(appState);
        updateProject(project.id, (entry) => ({ ...entry, splitView: !entry.splitView }));
        scheduleSave();
        await syncVisibleTerminals();
        resizeAllPanes();
    }

    function startSidebarResize(event: MouseEvent) {
        event.preventDefault();
        dragState = {
            kind: 'sidebar',
            startX: event.clientX,
            startSidebarWidth: appState.sidebarWidth,
        };
    }

    function startPaneResize(event: MouseEvent) {
        if (!activeProject || !workspaceHost) {
            return;
        }

        event.preventDefault();
        const workspaceWidth = workspaceHost.getBoundingClientRect().width - 10;
        if (workspaceWidth <= 0) {
            return;
        }

        dragState = {
            kind: 'split',
            startX: event.clientX,
            startSplitRatio: activeProject.splitRatio,
            workspaceWidth,
            projectId: activeProject.id,
        };
    }

    function handlePointerMove(event: MouseEvent) {
        if (!dragState) {
            return;
        }

        if (dragState.kind === 'sidebar') {
            const deltaX = event.clientX - dragState.startX;
            updateSidebarWidth(dragState.startSidebarWidth + deltaX);
            resizeAllPanes();
            return;
        }

        const deltaX = event.clientX - dragState.startX;
        const nextRatio = normalizeSplitRatio(
            (dragState.startSplitRatio * dragState.workspaceWidth + deltaX) / dragState.workspaceWidth,
        );

        updateProject(dragState.projectId, (entry) => ({
            ...entry,
            splitRatio: nextRatio,
        }));
        scheduleSave();
        resizeAllPanes();
    }

    function stopDragging() {
        dragState = null;
    }

    function openProjectMenu(event: MouseEvent, projectId: string) {
        event.preventDefault();
        contextMenu = { kind: 'project', x: event.clientX, y: event.clientY, projectId };
    }

    function openTabMenu(event: MouseEvent, pane: PaneKey, tabId: string) {
        if (!activeProject) {
            return;
        }

        event.preventDefault();
        contextMenu = {
            kind: 'tab',
            x: event.clientX,
            y: event.clientY,
            projectId: activeProject.id,
            pane,
            tabId,
        };
    }

    async function runContextEdit() {
        if (!contextMenu) {
            return;
        }

        if (contextMenu.kind === 'project') {
            await renameProject(contextMenu.projectId);
        } else {
            openTabRenameDialog(contextMenu.pane, contextMenu.tabId, contextMenu.projectId);
        }

        closeContextMenu();
    }

    function runContextProjectPath() {
        if (!contextMenu || contextMenu.kind !== 'project') {
            return;
        }

        openProjectPathDialog(contextMenu.projectId);
        closeContextMenu();
    }

    async function runContextDelete() {
        if (!contextMenu) {
            return;
        }

        if (contextMenu.kind === 'project') {
            await deleteProject(contextMenu.projectId);
        } else {
            await closeTab(contextMenu.pane, contextMenu.tabId, contextMenu.projectId);
        }

        closeContextMenu();
    }

    onMount(() => {
        let disposed = false;

        const start = async () => {
            if (disposed) {
                return;
            }

            if (getPyApi()?.loadAppState) {
                try {
                    const state = await getPyApi()!.loadAppState!();
                    setAppState((state as AppState) ?? cloneDefaultState());
                } catch {
                    setAppState(cloneDefaultState());
                }
            } else {
                setAppState(cloneDefaultState());
            }

            await syncVisibleTerminals();
            focusPane('left');
        };

        if (window.pywebview?.api) {
            void start();
        } else {
            window.addEventListener('pywebviewready', () => void start(), { once: true });
        }

        return () => {
            disposed = true;
            isShuttingDown = true;
            if (saveTimer) {
                clearTimeout(saveTimer);
            }

            disconnectPane('left');
            disconnectPane('right');

            for (const pane of ['left', 'right'] as PaneKey[]) {
                if (paneRuntimes[pane]?.resizeFrame !== null) {
                    cancelAnimationFrame(paneRuntimes[pane]!.resizeFrame!);
                }
                paneRuntimes[pane]?.resizeObserver?.disconnect();
                paneRuntimes[pane]?.terminal.dispose();
            }
        };
    });
</script>

<svelte:window
    on:click={closeContextMenu}
    on:keydown={closeContextMenu}
    on:mousemove={handlePointerMove}
    on:mouseup={stopDragging}
    on:mouseleave={stopDragging}
    on:resize={resizeAllPanes}
/>

<main on:contextmenu={(event) => event.target === event.currentTarget && closeContextMenu()}>
    <div class="content fgback">
        <ProjectSidebar
            projects={appState.projects}
            activeProjectId={appState.activeProjectId}
            width={appState.sidebarWidth}
            onAddProject={addProject}
            onSelectProject={selectProject}
            onProjectContextMenu={openProjectMenu}
        />
        <button
            aria-label="Resize sidebar"
            class="resizeHandle sidebarHandle"
            type="button"
            on:mousedown={startSidebarResize}
        ></button>

        {#if activeProject}
            <section bind:this={workspaceHost} class="workspace">
                <div class:split={activeProject.splitView} class="terminalContent">
                    <div
                        class="paneSlot"
                        style={activeProject.splitView
                            ? `flex-basis: calc(${activeProject.splitRatio * 100}% - 5px);`
                            : undefined}
                    >
                        <TerminalPane
                            pane="left"
                            tabs={activeProject.leftTabs}
                            activeTabId={activeProject.activeLeftTabId}
                            activePane={activePane === 'left'}
                            status={paneStatus.left}
                            bind:host={leftHost}
                            onAddTab={addTab}
                            onSelectTab={selectTab}
                            onOpenTabMenu={openTabMenu}
                            onFocusPane={focusPane}
                            onToggleSplitView={toggleSplitView}
                            activeProject={activeProject}
                            showModeButton={true}
                        />
                    </div>

                    {#if activeProject.splitView}
                        <button
                            aria-label="Resize terminal panes"
                            class="resizeHandle paneHandle"
                            type="button"
                            on:mousedown={startPaneResize}
                        ></button>
                        <div
                            class="paneSlot"
                            style={`flex-basis: calc(${(1 - activeProject.splitRatio) * 100}% - 5px);`}
                        >
                            <TerminalPane
                                pane="right"
                                tabs={activeProject.rightTabs}
                                activeTabId={activeProject.activeRightTabId}
                                activePane={activePane === 'right'}
                                status={paneStatus.right}
                                bind:host={rightHost}
                            onAddTab={addTab}
                            onSelectTab={selectTab}
                            onOpenTabMenu={openTabMenu}
                            onFocusPane={focusPane}
                            onToggleSplitView={toggleSplitView}
                            activeProject={activeProject}
                            showModeButton={false}
                        />
                        </div>
                    {/if}
                </div>
            </section>
        {/if}
    </div>

    <ContextMenu
        contextMenu={contextMenu}
        onEdit={runContextEdit}
        onProjectPath={runContextProjectPath}
        onDelete={runContextDelete}
    />
    {#key `${projectPathDialog.projectId}:${projectPathDialog.open ? 'open' : 'closed'}`}
        <ProjectPathDialog
            open={projectPathDialog.open}
            projectName={projectPathDialog.projectName}
            value={projectPathDialog.value}
            errorMessage={projectPathDialog.errorMessage}
            on:cancel={closeProjectPathDialog}
            on:confirm={(event) => void saveProjectPath(event.detail.value)}
        />
    {/key}
    <TabRenameDialog
        open={tabRenameDialog.open}
        projectName={tabRenameDialog.projectName}
        currentTitle={tabRenameDialog.value}
        errorMessage={tabRenameDialog.errorMessage}
        on:cancel={closeTabRenameDialog}
        on:confirm={(event) => void renameTab(event.detail.value)}
    />
</main>

<style>
    :global(.xterm) {
        height: 100%;
    }

    :global(.xterm-viewport) {
        overflow-y: auto !important;
    }

    main {
        height: 100vh;
        display: flex;
        flex-direction: column;
        overflow: hidden;
    }

    .fgback {
        color: var(--bgText);
        background-color: var(--background);
    }

    .content {
        display: flex;
        flex: 1;
        min-height: 0;
        min-width: 0;
    }

    .workspace {
        flex: 1;
        min-width: 0;
        min-height: 0;
        display: flex;
        flex-direction: column;
        /*padding: 12px;*/
        gap: 10px;
        overflow: hidden;
    }

    .terminalContent {
        display: flex;
        flex-direction: column;
        /*gap: 10px;*/
        flex: 1;
        min-width: 0;
        min-height: 0;
        overflow: hidden;
    }

    .terminalContent.split {
        flex-direction: row;
        align-items: stretch;
    }

    .paneSlot {
        flex: 1 1 0;
        min-width: 0;
        min-height: 0;
        display: flex;
        overflow: hidden;
    }

    .resizeHandle {
        flex: 0 0 auto;
        padding: 0;
        border: 0;
        background: transparent;
        position: relative;
        cursor: col-resize;
        outline: none;
    }

    .resizeHandle::before {
        content: '';
        position: absolute;
        top: 0;
        bottom: 0;
        left: 50%;
        width: 1px;
        transform: translateX(-50%);
        background: rgba(255, 255, 255, 0.08);
        transition: background 120ms ease, width 120ms ease;
    }

    .resizeHandle:hover::before,
    .resizeHandle:focus-visible::before {
        width: 2px;
        background: rgba(255, 255, 255, 0.22);
    }

    .sidebarHandle {
        width: 6px;
    }

    .paneHandle {
        width: 8px;
    }
</style>

