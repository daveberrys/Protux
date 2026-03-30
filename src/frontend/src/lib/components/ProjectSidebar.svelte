<script lang="ts">
    import type { Project } from '../workspace';

    export let projects: Project[] = [];
    export let activeProjectId = '';
    export let width = 260;
    export let onAddProject: () => void;
    export let onSelectProject: (projectId: string) => void;
    export let onProjectContextMenu: (event: MouseEvent, projectId: string) => void;
</script>

<aside class="sidebar" style={`width:${width}px;flex-basis:${width}px;`}>
    <div class="projectList">
        {#each projects as project}
            <button
                class:selected={project.id === activeProjectId}
                class="projectCard"
                on:click={() => onSelectProject(project.id)}
                on:contextmenu={(event) => onProjectContextMenu(event, project.id)}
            >
                <span class="projectName">{project.name}</span>
                <span>{project.leftTabs.length + project.rightTabs.length} tabs saved</span>
            </button>
        {/each}
    </div>

    <div class="sidebarFooter">
        <button class="iconButton" on:click={onAddProject}>+</button>
    </div>
</aside>

<style>
    .sidebar {
        flex: 0 0 260px;
        width: 260px;
        min-width: 220px;
        height: 100%;
        min-height: 0;
        display: flex;
        flex-direction: column;
        gap: 10px;
        overflow: hidden;
    }

    .sidebarFooter {
        flex: 0 0 auto;
        display: flex;
        align-items: center;
        gap: 10px;
        
        justify-content: space-between;
    }

    .projectList {
        flex: 1;
        min-height: 0;
        overflow-y: auto;
        display: flex;
        flex-direction: column;
        gap: 10px;
    }

    .iconButton,
    .projectCard {
        border: 0;
        color: inherit;
        background: var(--frameFG);
        width: 100%;
    }

    .iconButton {
        padding: 8px 10px;
        cursor: pointer;
    }

    .projectCard {
        text-align: left;
        padding: 14px;
        display: flex;
        flex-direction: column;
        gap: 8px;
        cursor: pointer;
    }

    .projectCard.selected {
        background: var(--frameSelected);
    }

    .projectName {
        font-size: 1.3rem;
    }
</style>
