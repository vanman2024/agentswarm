/**
 * Task Management Utilities for Local-First Development
 * 
 * Provides utility functions for working with local tasks:
 * - Task creation helpers
 * - Status management
 * - Branch association
 * - QA integration
 * - Spec-Kit integration
 */

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');
const TaskParser = require('./task-parser');

class TaskUtils {
    constructor(workingDir = process.cwd()) {
        this.workingDir = workingDir;
        this.parser = new TaskParser(workingDir);
        this.localStateDir = path.join(workingDir, '.local-state');
    }

    /**
     * Create a new local task with intelligent defaults
     */
    createTask(description, options = {}) {
        const taskOptions = {
            description: description,
            type: this.inferTaskType(description),
            scope: this.inferScope(description),
            qaCommands: options.qaCommands || [],
            agent: options.agent || 'claude',
            githubSync: options.github || false,
            dependencies: options.dependencies || [],
            ...options
        };

        const task = this.parser.createLocalTask(taskOptions);
        return this.parser.addTaskToFile(task);
    }

    /**
     * Start work on a task (creates branch, updates status)
     */
    startWork(taskId) {
        const task = this.getTask(taskId);
        if (!task) {
            throw new Error(`Task ${taskId} not found`);
        }

        // Check dependencies
        const deps = this.parser.checkTaskDependencies(taskId);
        if (!deps.resolved) {
            throw new Error(`Task ${taskId} is blocked by: ${deps.blocked.join(', ')}`);
        }

        // Create branch
        const branchName = this.parser.getBranchName(task);
        this.createBranch(branchName);

        // Update status
        this.parser.updateTaskStatus(taskId, 'in_progress', `Started work on branch ${branchName}`);

        // Track work session
        this.startWorkSession(taskId, branchName);

        return {
            task: task,
            branch: branchName,
            message: `Started work on ${taskId} in branch ${branchName}`
        };
    }

    /**
     * Complete a task (runs QA, updates status)
     */
    async completeTask(taskId, options = {}) {
        const task = this.getTask(taskId);
        if (!task) {
            throw new Error(`Task ${taskId} not found`);
        }

        // Run QA commands if not skipped
        if (!options.skipQA) {
            const qaResults = await this.runQACommands(task);
            if (!qaResults.success) {
                throw new Error(`QA failed: ${qaResults.errors.join(', ')}`);
            }
        }

        // Update status
        this.parser.updateTaskStatus(taskId, 'completed', 'QA passed, work completed');

        // End work session
        this.endWorkSession(taskId);

        // Sync to GitHub if enabled
        if (task.githubSync.enabled && options.syncToGitHub) {
            await this.syncToGitHub(taskId);
        }

        return {
            task: task,
            message: `Task ${taskId} completed successfully`
        };
    }

    /**
     * Get task by ID
     */
    getTask(taskId) {
        const parsed = this.parser.parseTasks();
        return parsed.tasks.find(t => t.id === taskId);
    }

    /**
     * List tasks with filtering options
     */
    listTasks(filter = {}) {
        const parsed = this.parser.parseTasks();
        let tasks = parsed.tasks;

        if (filter.status) {
            tasks = tasks.filter(t => t.status === filter.status);
        }

        if (filter.agent) {
            tasks = tasks.filter(t => t.agent === filter.agent);
        }

        if (filter.type) {
            tasks = tasks.filter(t => t.type === filter.type);
        }

        if (filter.local) {
            tasks = tasks.filter(t => t.id.startsWith('local-'));
        }

        return tasks;
    }

    /**
     * Get work status overview
     */
    getWorkStatus() {
        const tasks = this.listTasks({ local: true });
        const workSessions = this.getActiveWorkSessions();
        
        return {
            total: tasks.length,
            pending: tasks.filter(t => t.status === 'pending').length,
            inProgress: tasks.filter(t => t.status === 'in_progress').length,
            completed: tasks.filter(t => t.status === 'completed').length,
            blocked: tasks.filter(t => {
                const deps = this.parser.checkTaskDependencies(t.id);
                return !deps.resolved;
            }).length,
            activeSessions: workSessions.length,
            nextTask: this.parser.getNextTask()
        };
    }

    /**
     * Resume work on most recent task
     */
    resumeWork() {
        const sessions = this.getActiveWorkSessions();
        if (sessions.length === 0) {
            const nextTask = this.parser.getNextTask();
            if (nextTask) {
                return this.startWork(nextTask.id);
            }
            return null;
        }

        const mostRecent = sessions.sort((a, b) => 
            new Date(b.started) - new Date(a.started)
        )[0];

        return {
            task: this.getTask(mostRecent.taskId),
            branch: mostRecent.branch,
            message: `Resume work on ${mostRecent.taskId} in branch ${mostRecent.branch}`
        };
    }

    /**
     * Infer task type from description
     */
    inferTaskType(description) {
        const lower = description.toLowerCase();
        
        if (lower.includes('fix') || lower.includes('bug') || lower.includes('error')) {
            return 'bug';
        }
        if (lower.includes('refactor') || lower.includes('cleanup') || lower.includes('reorganize')) {
            return 'refactor';
        }
        if (lower.includes('update') || lower.includes('upgrade') || lower.includes('modify')) {
            return 'update';
        }
        if (lower.includes('add') || lower.includes('create') || lower.includes('implement')) {
            return 'feature';
        }
        if (lower.includes('security') || lower.includes('auth') || lower.includes('vulnerability')) {
            return 'security';
        }
        if (lower.includes('performance') || lower.includes('optimize') || lower.includes('speed')) {
            return 'optimization';
        }
        if (lower.includes('test') || lower.includes('testing')) {
            return 'testing';
        }
        if (lower.includes('doc') || lower.includes('readme') || lower.includes('guide')) {
            return 'documentation';
        }
        
        return 'update'; // Default for post-deployment work
    }

    /**
     * Infer scope from description
     */
    inferScope(description) {
        const lower = description.toLowerCase();
        const scope = [];
        
        if (lower.includes('backend') || lower.includes('api') || lower.includes('server')) {
            scope.push('backend/');
        }
        if (lower.includes('frontend') || lower.includes('ui') || lower.includes('component')) {
            scope.push('frontend/');
        }
        if (lower.includes('database') || lower.includes('db') || lower.includes('migration')) {
            scope.push('database/');
        }
        if (lower.includes('auth') || lower.includes('login') || lower.includes('user')) {
            scope.push('auth/');
        }
        if (lower.includes('test') || lower.includes('spec')) {
            scope.push('tests/');
        }
        if (lower.includes('doc') || lower.includes('readme')) {
            scope.push('docs/');
        }
        if (lower.includes('config') || lower.includes('settings')) {
            scope.push('config/');
        }
        if (lower.includes('deploy') || lower.includes('ci') || lower.includes('workflow')) {
            scope.push('.github/');
        }
        
        return scope.length > 0 ? scope : ['src/'];
    }

    /**
     * Create git branch for task
     */
    createBranch(branchName) {
        try {
            // Ensure we're on main and up to date
            execSync('git checkout main', { cwd: this.workingDir });
            execSync('git pull origin main', { cwd: this.workingDir });
            
            // Create and checkout new branch
            execSync(`git checkout -b ${branchName}`, { cwd: this.workingDir });
            
            return branchName;
        } catch (error) {
            throw new Error(`Failed to create branch ${branchName}: ${error.message}`);
        }
    }

    /**
     * Run QA commands for a task
     */
    async runQACommands(task) {
        const results = {
            success: true,
            errors: [],
            outputs: []
        };

        for (const command of task.qaCommands) {
            try {
                const output = execSync(command, { 
                    cwd: this.workingDir,
                    encoding: 'utf8'
                });
                results.outputs.push({ command, output, success: true });
            } catch (error) {
                results.success = false;
                results.errors.push(`${command}: ${error.message}`);
                results.outputs.push({ 
                    command, 
                    output: error.stdout || error.message, 
                    success: false 
                });
            }
        }

        return results;
    }

    /**
     * Start work session tracking
     */
    startWorkSession(taskId, branch) {
        const session = {
            taskId: taskId,
            branch: branch,
            started: new Date().toISOString(),
            commits: [],
            status: 'active'
        };

        this.updateWorkSession(session);
        return session;
    }

    /**
     * End work session
     */
    endWorkSession(taskId) {
        const sessions = this.getWorkSessions();
        const session = sessions.find(s => s.taskId === taskId && s.status === 'active');
        
        if (session) {
            session.status = 'completed';
            session.ended = new Date().toISOString();
            this.updateWorkSession(session);
        }

        return session;
    }

    /**
     * Get active work sessions
     */
    getActiveWorkSessions() {
        const sessions = this.getWorkSessions();
        return sessions.filter(s => s.status === 'active');
    }

    /**
     * Get all work sessions
     */
    getWorkSessions() {
        const sessionsFile = path.join(this.localStateDir, 'work-sessions.json');
        
        if (!fs.existsSync(sessionsFile)) {
            return [];
        }

        try {
            return JSON.parse(fs.readFileSync(sessionsFile, 'utf8'));
        } catch (error) {
            console.warn('Warning: Could not parse work sessions file');
            return [];
        }
    }

    /**
     * Update work session
     */
    updateWorkSession(session) {
        // Ensure .local-state directory exists
        if (!fs.existsSync(this.localStateDir)) {
            fs.mkdirSync(this.localStateDir, { recursive: true });
        }

        let sessions = this.getWorkSessions();
        const index = sessions.findIndex(s => 
            s.taskId === session.taskId && s.started === session.started
        );

        if (index >= 0) {
            sessions[index] = session;
        } else {
            sessions.push(session);
        }

        const sessionsFile = path.join(this.localStateDir, 'work-sessions.json');
        fs.writeFileSync(sessionsFile, JSON.stringify(sessions, null, 2));
    }

    /**
     * Sync task to GitHub (create issue)
     */
    async syncToGitHub(taskId) {
        const task = this.getTask(taskId);
        if (!task) {
            throw new Error(`Task ${taskId} not found`);
        }

        const githubData = this.parser.exportForGitHub(taskId);
        
        // This would use MCP GitHub functions in the actual command
        return {
            task: task,
            githubData: githubData,
            message: `Task ${taskId} ready for GitHub sync`
        };
    }

    /**
     * Initialize local-first system in current directory
     */
    initializeLocalSystem() {
        // Create .local-state directory
        if (!fs.existsSync(this.localStateDir)) {
            fs.mkdirSync(this.localStateDir, { recursive: true });
        }

        // Create README for .local-state
        const readmePath = path.join(this.localStateDir, 'README.md');
        if (!fs.existsSync(readmePath)) {
            fs.writeFileSync(readmePath, `# Local Development State

This directory tracks local-first development state for this project.

## Files:
- \`active-work.json\` - Current task states and metadata
- \`work-sessions.json\` - Work session history and tracking  
- \`task-history.json\` - Complete task change history

## Integration:
- Syncs with tasks.md for task definitions
- Integrates with .specify/ for Spec-Kit compliance
- Supports optional GitHub synchronization

## Usage:
This directory is managed automatically by the local-first command system.
Manual editing is not recommended.
`);
        }

        // Initialize empty state files
        const stateFile = path.join(this.localStateDir, 'active-work.json');
        if (!fs.existsSync(stateFile)) {
            fs.writeFileSync(stateFile, JSON.stringify({
                tasks: {},
                history: [],
                sessions: []
            }, null, 2));
        } else {
            // Migrate old format if needed
            try {
                const existing = JSON.parse(fs.readFileSync(stateFile, 'utf8'));
                if (!existing.tasks) {
                    existing.tasks = {};
                    existing.history = existing.history || [];
                    existing.sessions = existing.sessions || [];
                    fs.writeFileSync(stateFile, JSON.stringify(existing, null, 2));
                }
            } catch (e) {
                // If corrupted, reinitialize
                fs.writeFileSync(stateFile, JSON.stringify({
                    tasks: {},
                    history: [],
                    sessions: []
                }, null, 2));
            }
        }

        const sessionsFile = path.join(this.localStateDir, 'work-sessions.json');
        if (!fs.existsSync(sessionsFile)) {
            fs.writeFileSync(sessionsFile, JSON.stringify([], null, 2));
        }

        return {
            message: 'Local-first development system initialized',
            stateDir: this.localStateDir,
            features: [
                'Task creation and tracking',
                'Work session management',
                'Branch association',
                'QA integration',
                'Optional GitHub sync'
            ]
        };
    }

    /**
     * Get task dependency graph
     */
    getDependencyGraph() {
        const parsed = this.parser.parseTasks();
        const graph = {
            nodes: [],
            edges: [],
            cycles: []
        };

        // Create nodes
        for (const task of parsed.tasks) {
            graph.nodes.push({
                id: task.id,
                description: task.description,
                status: task.status,
                agent: task.agent
            });
        }

        // Create edges
        for (const task of parsed.tasks) {
            for (const depId of task.dependencies) {
                graph.edges.push({
                    from: depId,
                    to: task.id
                });
            }
        }

        return graph;
    }

    /**
     * Validate task system integrity
     */
    validateSystem() {
        const issues = [];
        const parsed = this.parser.parseTasks();

        // Check for missing dependencies
        for (const task of parsed.tasks) {
            for (const depId of task.dependencies) {
                const dep = parsed.tasks.find(t => t.id === depId);
                if (!dep) {
                    issues.push(`Task ${task.id} depends on missing task ${depId}`);
                }
            }
        }

        // Check for circular dependencies
        const graph = this.getDependencyGraph();
        // TODO: Implement cycle detection

        // Check file system consistency
        if (!fs.existsSync(this.parser.tasksFile)) {
            issues.push('tasks.md file not found');
        }

        if (!fs.existsSync(this.localStateDir)) {
            issues.push('.local-state directory not initialized');
        }

        return {
            valid: issues.length === 0,
            issues: issues,
            suggestions: this.generateSuggestions(issues)
        };
    }

    /**
     * Generate suggestions for fixing issues
     */
    generateSuggestions(issues) {
        const suggestions = [];

        if (issues.some(i => i.includes('missing task'))) {
            suggestions.push('Run task dependency check and update references');
        }

        if (issues.some(i => i.includes('tasks.md'))) {
            suggestions.push('Create tasks.md using /create-issue command');
        }

        if (issues.some(i => i.includes('.local-state'))) {
            suggestions.push('Initialize local system with initializeLocalSystem()');
        }

        return suggestions;
    }
}

module.exports = TaskUtils;