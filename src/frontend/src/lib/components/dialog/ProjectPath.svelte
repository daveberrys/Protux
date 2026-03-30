<script lang="ts">
    import { createEventDispatcher } from 'svelte';

    export let open = false;
    export let projectName = '';
    export let value = '';
    export let errorMessage = '';

    const dispatch = createEventDispatcher<{
        cancel: void;
        confirm: { value: string };
    }>();

    let inputValue = '';
    let wasOpen = false;
    let lastProjectName = '';
    let lastValue = '';

    $: if (open && !wasOpen) {
        inputValue = value;
    }

    $: if (open && (projectName !== lastProjectName || value !== lastValue)) {
        inputValue = value;
    }

    $: wasOpen = open;
    $: if (open) {
        lastProjectName = projectName;
        lastValue = value;
    }

    function submit() {
        dispatch('confirm', { value: inputValue });
    }
</script>

{#if open}
    <button
        aria-label="Close project path dialog"
        class="backdrop"
        type="button"
        on:click={() => dispatch('cancel')}
    ></button>
    <div
        aria-labelledby="project-path-title"
        aria-modal="true"
        class="dialog"
        role="dialog"
        tabindex="-1"
    >
        <h2 id="project-path-title">Project Path</h2>
        <p class="subtitle">{projectName}</p>
        <label class="fieldLabel" for="project-path-input">Open terminals in this folder</label>
        <input
            id="project-path-input"
            class="pathInput"
            bind:value={inputValue}
            placeholder="~/Documents/protux"
            spellcheck="false"
            on:keydown={(event) => {
                if (event.key === 'Escape') {
                    dispatch('cancel');
                }

                if (event.key === 'Enter') {
                    submit();
                }
            }}
        />
        {#if errorMessage}
            <p class="error">{errorMessage}</p>
        {/if}
        <div class="actions">
            <button class="secondaryButton" on:click={() => dispatch('cancel')}>Cancel</button>
            <button class="primaryButton" on:click={submit}>Confirm</button>
        </div>
    </div>
{/if}

<style>
    .backdrop {
        position: fixed;
        inset: 0;
        z-index: 1090;
        background: rgba(4, 6, 8, 0.56);
        border: 0;
        padding: 0;
        cursor: default;
    }

    .dialog {
        position: fixed;
        top: 50%;
        left: 50%;
        z-index: 1100;
        width: min(520px, calc(100vw - 32px));
        transform: translate(-50%, -50%);
        background: var(--background);
        box-shadow: 0 24px 80px rgba(0, 0, 0, 0.45);
        padding: 24px;
        display: flex;
        flex-direction: column;
        gap: 14px;
    }

    h2 {
        margin: 0;
        font-size: 1.2rem;
    }

    .subtitle {
        margin: 0;
        color: rgba(255, 255, 255, 0.66);
    }

    .fieldLabel {
        font-size: 0.92rem;
        color: rgba(255, 255, 255, 0.82);
    }

    .pathInput {
        border: none;
        background: var(--frameFG);
        color: #f5f5f5;
        padding: 12px 14px;
        font: inherit;
    }

    .error {
        margin: 0;
        color: #ff9d9d;
        font-size: 0.92rem;
    }

    .actions {
        display: flex;
        justify-content: flex-end;
        gap: 10px;
    }

    .secondaryButton,
    .primaryButton {
        border: 0;
        padding: 10px 14px;
        font: inherit;
        cursor: pointer;
    }

    .secondaryButton {
        background: rgba(255, 255, 255, 0.08);
        color: #f5f5f5;
    }

    .primaryButton {
        background: #f0f0f0;
        color: #111111;
    }
    
    #project-path-title {
        color: white;
    }
</style>
