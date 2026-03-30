<script lang="ts">
    import type { ContextMenuState } from '../workspace';

    export let contextMenu: ContextMenuState = null;
    export let onEdit: () => void;
    export let onProjectPath: () => void;
    export let onDelete: () => void;
</script>

{#if contextMenu}
    <div class="contextMenu" style={`left:${contextMenu.x}px;top:${contextMenu.y}px;`}>
        <button class="menuItem" on:click={onEdit}>
            Edit
        </button>
        {#if contextMenu.kind === 'project'}
            <button class="menuItem" on:click={onProjectPath}>
                Project Path
            </button>
        {/if}
        <button class="menuItem danger" on:click={onDelete}>
            {contextMenu.kind === 'project' ? 'Delete' : 'Exit'}
        </button>
    </div>
{/if}

<style>
    .contextMenu {
        position: fixed;
        z-index: 1000;
        min-width: 160px;
        background: #181818;
        box-shadow: 0 20px 50px rgba(0, 0, 0, 0.45);
        display: flex;
        flex-direction: column;
        padding: 6px;
        gap: 4px;
    }

    .menuItem {
        border: 0;
        text-align: left;
        background: transparent;
        color: white;
        padding: 10px 12px;
        cursor: pointer;
    }

    .menuItem:hover {
        background: rgba(255, 255, 255, 0.08);
    }

    .menuItem.danger {
        color: #ff9d9d;
    }
</style>
