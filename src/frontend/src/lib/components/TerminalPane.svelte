<script lang="ts">
    import type { PaneKey, TerminalTab } from '../workspace';

    export let pane: PaneKey;
    export let tabs: TerminalTab[] = [];
    export let activeTabId = '';
    export let activePane = false;
    export let status = 'Idle';
    export let host: HTMLDivElement | null = null;
    export let onAddTab: (pane: PaneKey) => void;
    export let onSelectTab: (pane: PaneKey, tabId: string) => void;
    export let onOpenTabMenu: (event: MouseEvent, pane: PaneKey, tabId: string) => void;
    export let onFocusPane: (pane: PaneKey) => void;
    export let onToggleSplitView: (() => void) | undefined = undefined;
    export let activeProject: { splitView: boolean };
    export let showModeButton = false;
</script>

<div class="pane">
    <div class="topbar">
        <div class="tabs">
            {#each tabs as tab}
                <button
                    class:selected={tab.id === activeTabId}
                    class="tabButton"
                    on:click={() => onSelectTab(pane, tab.id)}
                    on:contextmenu={(event) => onOpenTabMenu(event, pane, tab.id)}
                >
                    {tab.title}
                </button>
            {/each}
        </div>

        <button class="iconButton" on:click={() => onAddTab(pane)}>+</button>
        {#if showModeButton && onToggleSplitView}
            <button class="modeButton" on:click={onToggleSplitView}>
                {activeProject.splitView ? 'Single Terminal' : 'Horizontal Split'}
            </button>
        {/if}
        <div class="status">{status}</div>
    </div>

    <div
        bind:this={host}
        class:active={activePane}
        class="terminal"
        role="textbox"
        tabindex="0"
        on:mousedown={() => onFocusPane(pane)}
        on:focus={() => onFocusPane(pane)}
    ></div>
</div>

<style>
    .pane {
        flex: 1 1 auto;
        width: 100%;
        min-width: 0;
        min-height: 0;
        display: flex;
        flex-direction: column;
        overflow: hidden;
    }

    .topbar {
        flex: 0 0 auto;
        min-width: 0;
        display: flex;
        align-items: center;
        gap: 10px;
    }

    .tabs {
        flex: 1 1 auto;
        display: flex;
        gap: 8px;
        min-width: 0;
        overflow-x: auto;
    }

    .iconButton,
    .tabButton {
        border: 0;
        color: inherit;
        background: var(--frameFG);
        padding: 8px 10px;
        cursor: pointer;
    }

    .tabButton.selected {
        background: var(--frameSelected);
    }

    .status {
        margin-left: auto;
        color: #a3a3a3;
        font-size: 0.85rem;
        margin-right: 1rem;
    }

    .terminal {
        background-color: var(--terminalBackground);
        /*border: 1px solid rgba(255, 255, 255, 0.08);*/
        border: 0;
        flex: 1;
        min-height: 0;
        min-width: 0;
        overflow: hidden;
        outline: none;
    }

    .terminal :global(.xterm) {
        width: 100%;
        height: 100%;
    }

    .terminal :global(.xterm-screen),
    .terminal :global(.xterm-viewport),
    .terminal :global(.xterm-scroll-area) {
        width: 100% !important;
    }

    .terminal.active {
        box-shadow: inset 0 0 0 1px var(--frameSelected);
    }
    
    .modeButton {
        border: 0;
        color: inherit;
        background: var(--frameFG);
        padding: 8px 10px;
        cursor: pointer;
    }
</style>
