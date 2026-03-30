export type PaneKey = 'left' | 'right';

export type TerminalTab = {
    id: string;
    title: string;
    history: string;
};

export type Project = {
    id: string;
    name: string;
    projectPath: string;
    splitRatio: number;
    leftTabs: TerminalTab[];
    rightTabs: TerminalTab[];
    activeLeftTabId: string;
    activeRightTabId: string;
    splitView: boolean;
};

export type AppState = {
    activeProjectId: string;
    sidebarWidth: number;
    projects: Project[];
};

export type ProjectMenuState = {
    kind: 'project';
    x: number;
    y: number;
    projectId: string;
};

export type TabMenuState = {
    kind: 'tab';
    x: number;
    y: number;
    projectId: string;
    pane: PaneKey;
    tabId: string;
};

export type ContextMenuState = ProjectMenuState | TabMenuState | null;

export const DEFAULT_STATE: AppState = {
    activeProjectId: 'project-1',
    sidebarWidth: 260,
    projects: [
        {
            id: 'project-1',
            name: 'Project 1',
            projectPath: '',
            splitRatio: 0.5,
            leftTabs: [{ id: 'tab-left-1', title: '~', history: '' }],
            rightTabs: [{ id: 'tab-right-1', title: '~', history: '' }],
            activeLeftTabId: 'tab-left-1',
            activeRightTabId: 'tab-right-1',
            splitView: true,
        },
    ],
};

export function makeId(prefix: string) {
    return `${prefix}-${crypto.randomUUID().slice(0, 8)}`;
}

export function cloneDefaultState() {
    return JSON.parse(JSON.stringify(DEFAULT_STATE)) as AppState;
}

export function createTab(pane: PaneKey): TerminalTab {
    return {
        id: makeId(`tab-${pane}`),
        title: '~',
        history: '',
    };
}

export function createProject(name: string): Project {
    const leftTab = createTab('left');
    const rightTab = createTab('right');

    return {
        id: makeId('project'),
        name,
        projectPath: '',
        splitRatio: 0.5,
        leftTabs: [leftTab],
        rightTabs: [rightTab],
        activeLeftTabId: leftTab.id,
        activeRightTabId: rightTab.id,
        splitView: true,
    };
}

export function getTabs(project: Project, pane: PaneKey) {
    return pane === 'left' ? project.leftTabs : project.rightTabs;
}

export function getActiveProject(appState: AppState) {
    return appState.projects.find((project) => project.id === appState.activeProjectId) ?? appState.projects[0];
}

export function getActiveTab(project: Project, pane: PaneKey) {
    const tabs = getTabs(project, pane);
    const activeId = pane === 'left' ? project.activeLeftTabId : project.activeRightTabId;
    return tabs.find((tab) => tab.id === activeId) ?? tabs[0];
}

export function ensureProjectHasTabs(project: Project, pane: PaneKey) {
    const tabs = getTabs(project, pane);
    if (tabs.length > 0) {
        return project;
    }

    const replacement = createTab(pane);
    return {
        ...project,
        leftTabs: pane === 'left' ? [replacement] : project.leftTabs,
        rightTabs: pane === 'right' ? [replacement] : project.rightTabs,
        activeLeftTabId: pane === 'left' ? replacement.id : project.activeLeftTabId,
        activeRightTabId: pane === 'right' ? replacement.id : project.activeRightTabId,
    };
}

export function normalizeProject(project: Project): Project {
    const normalizedProject = {
        ...project,
        projectPath: typeof project.projectPath === 'string' ? project.projectPath : '',
        splitRatio: normalizeSplitRatio(project.splitRatio),
    };

    return {
        ...ensureProjectHasTabs(ensureProjectHasTabs(normalizedProject, 'left'), 'right'),
        projectPath: normalizedProject.projectPath,
    };
}

export function normalizeAppState(state: AppState): AppState {
    const fallbackState = cloneDefaultState();
    const projects = Array.isArray(state?.projects) && state.projects.length > 0 ? state.projects : fallbackState.projects;
    const normalizedProjects = projects.map((project) => normalizeProject(project));
    const hasActiveProject = normalizedProjects.some((project) => project.id === state?.activeProjectId);

    return {
        activeProjectId: hasActiveProject ? state.activeProjectId : normalizedProjects[0].id,
        sidebarWidth: normalizeSidebarWidth(state?.sidebarWidth),
        projects: normalizedProjects,
    };
}

export function normalizeSidebarWidth(sidebarWidth: unknown) {
    if (typeof sidebarWidth !== 'number' || Number.isNaN(sidebarWidth)) {
        return 260;
    }

    return Math.min(420, Math.max(220, Math.round(sidebarWidth)));
}

export function normalizeSplitRatio(splitRatio: unknown) {
    if (typeof splitRatio !== 'number' || Number.isNaN(splitRatio)) {
        return 0.5;
    }

    return Math.min(0.75, Math.max(0.25, splitRatio));
}
