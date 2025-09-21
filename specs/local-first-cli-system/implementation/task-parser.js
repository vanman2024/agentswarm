/**
 * Local Task Parser for Local-First Development
 * 
 * Handles reading, writing, and parsing tasks.md files for local development workflow.
 * Integrates with Specification-Driven Development (SDD) principles and QA CLI.
 * 
 * Usage:
 * - Parse existing tasks.md files (both monolithic and spec-folder structure)
 * - Create new local tasks with proper metadata
 * - Track task status and dependencies
 * - Integrate with .specify/ folder for SDD compliance
 * - Support both GitHub sync and local-only workflows
 */

const fs = require('fs');
const path = require('path');

class TaskParser {
    constructor(workingDir = process.cwd()) {
        this.workingDir = workingDir;
        this.tasksFile = path.join(workingDir, 'tasks.md');
        this.localFirstTasksFile = path.join(workingDir, 'specs', 'local-first-slash-commands', 'tasks.md');
        this.localStateDir = path.join(workingDir, '.local-state');
        this.specifyDir = path.join(workingDir, '.specify');
        this.specsDir = path.join(workingDir, 'specs');
    }

    /**
     * Parse tasks.md file and extract all tasks with metadata
     * Supports both monolithic and spec-folder organization
     */
    parseTasks() {
        let tasks = [];
        let metadata = {};
        
        // Parse root tasks.md if it exists
        if (fs.existsSync(this.tasksFile)) {
            const rootResult = this.parseTaskFile(this.tasksFile);
            tasks = tasks.concat(rootResult.tasks);
            metadata = { ...metadata, ...rootResult.metadata };
        }

        // Parse local-first spec tasks if it exists
        if (fs.existsSync(this.localFirstTasksFile)) {
            const localResult = this.parseTaskFile(this.localFirstTasksFile);
            tasks = tasks.concat(localResult.tasks);
        }

        return {
            metadata: {
                ...metadata,
                structure: fs.existsSync(this.specsDir) ? 'spec-folder' : 'monolithic',
                hasSpecs: fs.existsSync(this.specsDir),
                hasSpecify: fs.existsSync(this.specifyDir)
            },
            tasks: tasks,
            structure: fs.existsSync(this.specsDir) ? 'spec-folder' : 'monolithic'
        };
    }

    /**
     * Parse a specific tasks file
     */
    parseTaskFile(filePath) {
        if (!fs.existsSync(filePath)) {
            return {
                metadata: {},
                tasks: []
            };
        }

        const content = fs.readFileSync(filePath, 'utf8');
        const lines = content.split('\n');
        
        let metadata = {};
        let tasks = [];
        let currentSection = null;
        let structure = 'monolithic'; // vs 'spec-folder'

        for (let i = 0; i < lines.length; i++) {
            const line = lines[i].trim();
            
            // Parse metadata from header
            if (line.startsWith('# ') && !metadata.title) {
                metadata.title = line.substring(2);
            }
            
            // Detect spec-folder structure
            if (line.includes('→ Extract:') || line.includes('specs/')) {
                structure = 'spec-folder';
            }
            
            // Parse sections
            if (line.startsWith('### ') || line.startsWith('## ')) {
                currentSection = line.replace(/^#+\s*/, '').replace(/🔧|🏗️|📚|🚀|⚡/, '').trim();
            }
            
            // Parse task items - handle T001, L001, local-001 formats
            const taskMatch = line.match(/^- \[([ x])\]\s*((?:[TL]\d+|local-\d+))\s+(@\w+)?\s*(.+?)$/);
            if (taskMatch) {
                const [, status, taskId, agent, description] = taskMatch;
                
                // Extract additional metadata from description
                let priority = null;
                let parallel = false;
                let scope = [];
                let qaCommands = [];
                let dependencies = [];
                
                // Check for [P] parallel marker
                if (description.includes('[P]')) {
                    parallel = true;
                }
                
                // Extract priority markers
                const priorityMatch = description.match(/\(PRIORITY\s+(\d+)\)/);
                if (priorityMatch) {
                    priority = parseInt(priorityMatch[1]);
                }
                
                tasks.push({
                    id: taskId || `auto-${tasks.length + 1}`,
                    status: status === 'x' ? 'completed' : 'pending',
                    description: description.replace(/\[P\]|\(PRIORITY\s+\d+\)/g, '').trim(),
                    agent: agent ? agent.substring(1) : 'claude',
                    section: currentSection,
                    parallel: parallel,
                    priority: priority,
                    scope: scope,
                    qaCommands: qaCommands,
                    dependencies: dependencies,
                    line: i + 1
                });
            }
        }

        return {
            metadata: {
                ...metadata,
                structure: structure,
                hasSpecs: fs.existsSync(this.specsDir),
                hasSpecify: fs.existsSync(this.specifyDir)
            },
            tasks: tasks,
            structure: structure
        };
    }

    /**
     * Create a new local task with proper metadata
     * Follows local-first patterns with optional GitHub sync
     */
    createLocalTask(options) {
        const {
            description,
            type = 'update', // refactor|update|patch|feature|bug|enhancement
            scope = [],
            qaCommands = [],
            dependencies = [],
            agent = 'claude',
            githubSync = false,
            specRequirements = []
        } = options;

        // Generate local task ID
        const existingTasks = this.parseTasks();
        const maxLocalId = Math.max(
            ...existingTasks.tasks
                .filter(t => t.id.startsWith('local-'))
                .map(t => parseInt(t.id.split('-')[1]) || 0),
            0
        );
        const taskId = `local-${String(maxLocalId + 1).padStart(3, '0')}`;

        // Create task metadata
        const task = {
            id: taskId,
            status: 'pending',
            description: description,
            type: type,
            agent: agent,
            scope: scope,
            qaCommands: qaCommands || this.generateQACommands(type, scope),
            dependencies: dependencies,
            githubSync: {
                enabled: githubSync,
                issueNumber: null,
                prNumber: null
            },
            specKit: this.getSpecKitContext(),
            specRequirements: specRequirements,
            created: new Date().toISOString(),
            updated: new Date().toISOString()
        };

        return task;
    }

    /**
     * Add task to local-first tasks.md file in proper format
     */
    addTaskToFile(task) {
        const taskLine = this.formatTaskLine(task);
        
        // Use local-first spec folder for local tasks
        const targetFile = task.id.startsWith('local-') ? this.localFirstTasksFile : this.tasksFile;
        
        // Read current file
        let content = '';
        if (fs.existsSync(targetFile)) {
            content = fs.readFileSync(targetFile, 'utf8');
        } else {
            // Create new tasks.md with proper header
            content = this.createTasksFileHeader(task.id.startsWith('local-'));
        }

        // Find insertion point
        const lines = content.split('\n');
        let insertIndex = -1;
        let hasLocalSection = false;

        if (task.id.startsWith('local-')) {
            // For local-first spec folder, find appropriate section
            for (let i = 0; i < lines.length; i++) {
                if (lines[i].includes('### Local Task Management System') && 
                    task.type === 'system') {
                    hasLocalSection = true;
                    insertIndex = i + 1;
                    break;
                } else if (lines[i].includes('### Post-Deployment Tasks')) {
                    hasLocalSection = true;
                    insertIndex = i + 1;
                    break;
                }
            }

            if (!hasLocalSection) {
                // Add post-deployment section to spec file
                lines.push('');
                lines.push('### Post-Deployment Tasks');
                lines.push('');
                insertIndex = lines.length;
            }
        } else {
            // For root tasks.md, find local development section
            for (let i = 0; i < lines.length; i++) {
                if (lines[i].includes('### Local Development') || 
                    lines[i].includes('### Active Development')) {
                    hasLocalSection = true;
                    insertIndex = i + 1;
                    break;
                }
            }

            if (!hasLocalSection) {
                // Add local development section
                lines.push('');
                lines.push('### Local Development (Post-Deployment)');
                lines.push('');
                insertIndex = lines.length;
            }
        }

        // Insert task with metadata
        lines.splice(insertIndex, 0, taskLine);
        lines.splice(insertIndex + 1, 0, this.formatTaskMetadata(task));
        lines.splice(insertIndex + 2, 0, '');

        // Write back to file
        fs.writeFileSync(targetFile, lines.join('\n'));
        
        // Update local state
        this.updateLocalState(task);

        return task;
    }

    /**
     * Update task status and sync to file
     */
    updateTaskStatus(taskId, status, notes = null) {
        const parsed = this.parseTasks();
        const task = parsed.tasks.find(t => t.id === taskId);
        
        if (!task) {
            throw new Error(`Task ${taskId} not found`);
        }

        // Update in memory
        task.status = status;
        task.updated = new Date().toISOString();
        if (notes) {
            task.notes = notes;
        }

        // Update file
        this.syncTaskToFile(task);
        
        // Update local state
        this.updateLocalState(task);

        return task;
    }

    /**
     * Format task line for tasks.md
     */
    formatTaskLine(task) {
        const checkbox = task.status === 'completed' ? '[x]' : '[ ]';
        const completedMark = task.status === 'completed' ? ' ✅' : '';
        
        return `- ${checkbox} ${task.id} @${task.agent} ${task.description}${completedMark}`;
    }

    /**
     * Format task metadata for tasks.md
     */
    formatTaskMetadata(task) {
        const metadata = [
            `  - **Type**: ${task.type}`,
            `  - **Scope**: ${task.scope.join(', ') || 'General'}`,
            `  - **QA**: \`${task.qaCommands.join(', ') || './ops qa --all'}\` required before completion`
        ];

        if (task.dependencies.length > 0) {
            metadata.push(`  - **Dependencies**: ${task.dependencies.join(', ')}`);
        }

        if (task.specRequirements.length > 0) {
            metadata.push(`  - **Spec**: References ${task.specRequirements.join(', ')}`);
        }

        if (task.githubSync.enabled) {
            const issueRef = task.githubSync.issueNumber ? `#${task.githubSync.issueNumber}` : 'TBD';
            metadata.push(`  - **GitHub**: Will sync to issue ${issueRef}`);
        }

        return metadata.join('\n');
    }

    /**
     * Create header for new tasks.md file
     */
    createTasksFileHeader(isLocalFirst = false) {
        if (isLocalFirst) {
            // Header for local-first spec folder
            return `# Local-First Slash Commands Tasks

## Project: Local-First Development Workflow
## Swarm Deployment: \`swarm /home/vanman2025/multi-agent-claude-code "Implement local-first command system"\`

### Architecture & Analysis
- [x] T001 @claude Analyze current GitHub-dependent slash commands ✅ 
- [x] T002 @claude Design local task format for tasks.md integration ✅
- [x] T003 @claude Document local-first workflow patterns vs GitHub automation ✅

### Local Task Management System
- [x] T010 @claude Create local task parser for reading/writing tasks.md ✅
- [ ] T011 @claude Implement local task creation and status tracking
- [ ] T012 @claude Build local work state management (.local-state/ directory)
- [ ] T013 @claude Create task-to-branch association system

### Command Refactoring  
- [ ] T020 @claude Refactor /create-issue for local task creation (no GitHub required)
- [ ] T021 @claude Update /work command for local task management
- [ ] T022 @claude Add --github flags for optional GitHub integration
- [ ] T023 @claude Ensure backward compatibility with existing command usage

### Performance & Optimization
- [ ] T030 @claude Optimize local file parsing and task operations
- [ ] T031 @claude Create efficient task search and filtering
- [ ] T032 @claude Design fast task status updates and work resumption

### Integration & Quality
- [ ] T040 @claude Test all commands work offline without GitHub
- [ ] T041 @claude Validate GitHub sync mechanisms when --github used  
- [ ] T042 @claude Ensure template repository compatibility
- [ ] T043 @claude Create comprehensive workflow documentation

`;
        } else {
            const projectName = path.basename(this.workingDir);
            
            return `# Local-First Development Tasks - ${projectName}

## Spec-Kit Integration
- **Constitution**: ${fs.existsSync(this.specifyDir) ? '@.specify/memory/constitution.md' : 'Not configured'}
- **Current Spec**: ${fs.existsSync(this.specifyDir) ? '@.specify/memory/current-spec.md' : 'Not configured'}
- **QA Config**: @qa-config.json

## Post-Deployment Workflow
Following Specification-Driven Development (SDD) principles for brownfield iterative development.
All tasks support local-first development with optional GitHub synchronization.

`;
        }
    }

    /**
     * Generate appropriate QA commands based on task type and scope
     */
    generateQACommands(type, scope = []) {
        const commands = [];
        
        // Ensure scope is an array
        const scopeArray = Array.isArray(scope) ? scope : [scope];
        
        // Base QA command
        commands.push('./ops qa');
        
        // Type-specific commands
        if (type === 'security' || scopeArray.some(s => s && s.includes('auth'))) {
            commands.push('./ops qa --security');
        }
        
        if (scopeArray.some(s => s && (s.includes('backend') || s.includes('api')))) {
            commands.push('./ops qa --backend');
        }
        
        if (scopeArray.some(s => s && (s.includes('frontend') || s.includes('ui')))) {
            commands.push('./ops qa --frontend');
        }
        
        return commands;
    }

    /**
     * Get Spec-Kit context for task creation
     */
    getSpecKitContext() {
        const specKit = {
            constitution: null,
            spec: null,
            requirements: []
        };

        if (fs.existsSync(this.specifyDir)) {
            const constitutionPath = path.join(this.specifyDir, 'memory', 'constitution.md');
            const specPath = path.join(this.specifyDir, 'memory', 'current-spec.md');
            
            if (fs.existsSync(constitutionPath)) {
                specKit.constitution = '.specify/memory/constitution.md';
            }
            
            if (fs.existsSync(specPath)) {
                specKit.spec = '.specify/memory/current-spec.md';
            }
        }

        return specKit;
    }

    /**
     * Update local state tracking
     */
    updateLocalState(task) {
        // Ensure .local-state directory exists
        if (!fs.existsSync(this.localStateDir)) {
            fs.mkdirSync(this.localStateDir, { recursive: true });
        }

        // Load existing state
        const stateFile = path.join(this.localStateDir, 'active-work.json');
        let state = { tasks: {}, history: [], sessions: [] };
        
        if (fs.existsSync(stateFile)) {
            try {
                state = JSON.parse(fs.readFileSync(stateFile, 'utf8'));
            } catch (e) {
                console.warn('Warning: Could not parse existing state file');
            }
        }

        // Ensure tasks object exists
        if (!state.tasks) {
            state.tasks = {};
        }

        // Update task in state
        state.tasks[task.id] = {
            ...task,
            lastModified: new Date().toISOString()
        };

        // Add to history if status changed
        if (task.status) {
            state.history.push({
                taskId: task.id,
                status: task.status,
                timestamp: new Date().toISOString(),
                notes: task.notes || null
            });
        }

        // Write state back
        fs.writeFileSync(stateFile, JSON.stringify(state, null, 2));
    }

    /**
     * Sync task changes back to tasks.md file
     */
    syncTaskToFile(task) {
        if (!fs.existsSync(this.tasksFile)) {
            return this.addTaskToFile(task);
        }

        const content = fs.readFileSync(this.tasksFile, 'utf8');
        const lines = content.split('\n');
        
        // Find the task line and update it
        for (let i = 0; i < lines.length; i++) {
            if (lines[i].includes(task.id)) {
                lines[i] = this.formatTaskLine(task);
                break;
            }
        }

        fs.writeFileSync(this.tasksFile, lines.join('\n'));
    }

    /**
     * Get all local tasks (those starting with 'local-')
     */
    getLocalTasks() {
        const parsed = this.parseTasks();
        return parsed.tasks.filter(t => t.id.startsWith('local-'));
    }

    /**
     * Find tasks by status
     */
    getTasksByStatus(status) {
        const parsed = this.parseTasks();
        return parsed.tasks.filter(t => t.status === status);
    }

    /**
     * Get task dependencies and check if they're resolved
     */
    checkTaskDependencies(taskId) {
        const parsed = this.parseTasks();
        const task = parsed.tasks.find(t => t.id === taskId);
        
        if (!task || !task.dependencies.length) {
            return { resolved: true, blocked: [] };
        }

        const blocked = [];
        for (const depId of task.dependencies) {
            const dep = parsed.tasks.find(t => t.id === depId);
            if (!dep || dep.status !== 'completed') {
                blocked.push(depId);
            }
        }

        return {
            resolved: blocked.length === 0,
            blocked: blocked
        };
    }

    /**
     * Get next available task (prioritized by dependencies and priority)
     */
    getNextTask() {
        const parsed = this.parseTasks();
        const pendingTasks = parsed.tasks.filter(t => t.status === 'pending');
        
        // Filter out blocked tasks
        const availableTasks = pendingTasks.filter(task => {
            const deps = this.checkTaskDependencies(task.id);
            return deps.resolved;
        });

        if (availableTasks.length === 0) {
            return null;
        }

        // Sort by priority (lower number = higher priority)
        availableTasks.sort((a, b) => {
            if (a.priority && b.priority) {
                return a.priority - b.priority;
            }
            if (a.priority) return -1;
            if (b.priority) return 1;
            return 0;
        });

        return availableTasks[0];
    }

    /**
     * Create branch name from task
     */
    getBranchName(task) {
        const cleanDesc = task.description
            .toLowerCase()
            .replace(/[^a-z0-9\s-]/g, '')
            .replace(/\s+/g, '-')
            .substring(0, 50);
        
        return `${task.id}-${cleanDesc}`;
    }

    /**
     * Export task data for GitHub sync
     */
    exportForGitHub(taskId) {
        const parsed = this.parseTasks();
        const task = parsed.tasks.find(t => t.id === taskId);
        
        if (!task) {
            throw new Error(`Task ${taskId} not found`);
        }

        return {
            title: `[${task.type.toUpperCase()}] ${task.description}`,
            body: this.generateGitHubIssueBody(task),
            labels: [task.type, 'local-first'],
            assignees: [],
            milestone: null
        };
    }

    /**
     * Generate GitHub issue body from task
     */
    generateGitHubIssueBody(task) {
        let body = `## Local Task: ${task.id}

### Description
${task.description}

### Technical Details
- **Type**: ${task.type}
- **Scope**: ${task.scope.join(', ') || 'General'}
- **Agent**: @${task.agent}

### Quality Assurance
Required QA commands before completion:
${task.qaCommands.map(cmd => `- \`${cmd}\``).join('\n')}

### Specification Context
${task.specKit.constitution ? `- **Constitution**: ${task.specKit.constitution}` : ''}
${task.specKit.spec ? `- **Current Spec**: ${task.specKit.spec}` : ''}
${task.specRequirements.length > 0 ? `- **Requirements**: ${task.specRequirements.join(', ')}` : ''}

### Dependencies
${task.dependencies.length > 0 ? task.dependencies.map(dep => `- Depends on ${dep}`).join('\n') : 'None'}

### Implementation Checklist
- [ ] Analysis and planning
- [ ] Implementation
- [ ] QA commands pass
- [ ] Documentation updated
- [ ] Ready for review

---
*Created from local task management system*
*Local Task ID: ${task.id}*
`;

        return body;
    }
}

module.exports = TaskParser;