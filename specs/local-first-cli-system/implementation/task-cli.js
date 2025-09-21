#!/usr/bin/env node

/**
 * Task CLI - Command Line Interface for Local-First Development
 * 
 * Provides command-line access to the local task management system.
 * Used by slash commands for local-first development workflow.
 * 
 * Usage:
 * - node task-cli.js create "description" --type=bug --scope=backend/
 * - node task-cli.js list --status=pending
 * - node task-cli.js start local-001
 * - node task-cli.js complete local-001
 * - node task-cli.js status
 */

const TaskUtils = require('./task-utils');
const TaskParser = require('./task-parser');
const SpecFolderManager = require('./spec-folder-manager');

class TaskCLI {
    constructor() {
        this.taskUtils = new TaskUtils();
        this.taskParser = new TaskParser();
        this.specFolderManager = new SpecFolderManager();
    }

    async run(args) {
        const command = args[0];
        const subArgs = args.slice(1);

        try {
            switch (command) {
                case 'create':
                    return await this.handleCreate(subArgs);
                case 'list':
                    return await this.handleList(subArgs);
                case 'start':
                    return await this.handleStart(subArgs);
                case 'complete':
                    return await this.handleComplete(subArgs);
                case 'status':
                    return await this.handleStatus(subArgs);
                case 'resume':
                    return await this.handleResume(subArgs);
                case 'init':
                    return await this.handleInit(subArgs);
                case 'sync':
                    return await this.handleSync(subArgs);
                case 'validate':
                    return await this.handleValidate(subArgs);
                case 'create-feature':
                    return await this.handleCreateFeature(subArgs);
                case 'list-features':
                    return await this.handleListFeatures(subArgs);
                case 'help':
                    return this.showHelp();
                default:
                    throw new Error(`Unknown command: ${command}`);
            }
        } catch (error) {
            return {
                success: false,
                error: error.message,
                command: command
            };
        }
    }

    /**
     * Handle task creation
     */
    async handleCreate(args) {
        const description = args[0];
        if (!description) {
            throw new Error('Description is required for task creation');
        }

        const options = this.parseOptions(args.slice(1));
        const task = this.taskUtils.createTask(description, options);

        return {
            success: true,
            action: 'create',
            task: task,
            message: `Created task ${task.id}: ${task.description}`
        };
    }

    /**
     * Handle task listing
     */
    async handleList(args) {
        const options = this.parseOptions(args);
        const tasks = this.taskUtils.listTasks(options);

        return {
            success: true,
            action: 'list',
            tasks: tasks,
            count: tasks.length,
            filters: options
        };
    }

    /**
     * Handle starting work on a task
     */
    async handleStart(args) {
        const taskId = args[0];
        if (!taskId) {
            throw new Error('Task ID is required');
        }

        const result = this.taskUtils.startWork(taskId);

        return {
            success: true,
            action: 'start',
            ...result
        };
    }

    /**
     * Handle completing a task
     */
    async handleComplete(args) {
        const taskId = args[0];
        if (!taskId) {
            throw new Error('Task ID is required');
        }

        const options = this.parseOptions(args.slice(1));
        const result = await this.taskUtils.completeTask(taskId, options);

        return {
            success: true,
            action: 'complete',
            ...result
        };
    }

    /**
     * Handle status overview
     */
    async handleStatus(args) {
        const status = this.taskUtils.getWorkStatus();
        const sessions = this.taskUtils.getActiveWorkSessions();

        return {
            success: true,
            action: 'status',
            status: status,
            activeSessions: sessions,
            message: this.formatStatusMessage(status)
        };
    }

    /**
     * Handle resuming work
     */
    async handleResume(args) {
        const result = this.taskUtils.resumeWork();
        
        if (!result) {
            return {
                success: true,
                action: 'resume',
                message: 'No work to resume. Use "list --status=pending" to see available tasks.'
            };
        }

        return {
            success: true,
            action: 'resume',
            ...result
        };
    }

    /**
     * Handle system initialization
     */
    async handleInit(args) {
        const result = this.taskUtils.initializeLocalSystem();

        return {
            success: true,
            action: 'init',
            ...result
        };
    }

    /**
     * Handle GitHub sync
     */
    async handleSync(args) {
        const taskId = args[0];
        if (!taskId) {
            throw new Error('Task ID is required for sync');
        }

        const result = await this.taskUtils.syncToGitHub(taskId);

        return {
            success: true,
            action: 'sync',
            ...result
        };
    }

    /**
     * Handle system validation
     */
    async handleValidate(args) {
        const result = this.taskUtils.validateSystem();

        return {
            success: true,
            action: 'validate',
            ...result
        };
    }

    /**
     * Handle feature spec creation
     */
    async handleCreateFeature(args) {
        const featureName = args[0];
        if (!featureName) {
            throw new Error('Feature name is required');
        }

        const options = this.parseOptions(args.slice(1));
        
        // Set intelligent defaults based on options
        const featureOptions = {
            description: options.description || '',
            type: options.type || 'feature',
            priority: options.priority || 'normal',
            complexity: parseInt(options.complexity) || 3,
            assignedAgents: options.agents ? options.agents.split(',') : ['claude'],
            requiresDatabase: options.database || false,
            requiresAPI: options.api || false,
            requiresFrontend: options.frontend || false,
            dependencies: options.dependencies ? options.dependencies.split(',') : []
        };

        const result = this.specFolderManager.createFeatureSpec(featureName, featureOptions);

        return {
            success: true,
            action: 'create-feature',
            ...result
        };
    }

    /**
     * Handle listing feature specs
     */
    async handleListFeatures(args) {
        const features = this.specFolderManager.listFeatureSpecs();

        return {
            success: true,
            action: 'list-features',
            features: features,
            count: features.length
        };
    }

    /**
     * Parse command line options
     */
    parseOptions(args) {
        const options = {};
        
        for (const arg of args) {
            if (arg.startsWith('--')) {
                const [key, value] = arg.substring(2).split('=');
                if (value !== undefined) {
                    options[key] = value;
                } else {
                    options[key] = true;
                }
            }
        }

        // Parse specific option formats
        if (options.scope && typeof options.scope === 'string') {
            options.scope = options.scope.split(',');
        }

        if (options.dependencies && typeof options.dependencies === 'string') {
            options.dependencies = options.dependencies.split(',');
        }

        return options;
    }

    /**
     * Format status message for display
     */
    formatStatusMessage(status) {
        const parts = [
            `Total: ${status.total} tasks`,
            `Pending: ${status.pending}`,
            `In Progress: ${status.inProgress}`,
            `Completed: ${status.completed}`
        ];

        if (status.blocked > 0) {
            parts.push(`Blocked: ${status.blocked}`);
        }

        if (status.activeSessions > 0) {
            parts.push(`Active Sessions: ${status.activeSessions}`);
        }

        if (status.nextTask) {
            parts.push(`Next: ${status.nextTask.id}`);
        }

        return parts.join(', ');
    }

    /**
     * Show help information
     */
    showHelp() {
        return {
            success: true,
            action: 'help',
            help: `
Local-First Task Management CLI

COMMANDS:
  create <description>     Create new local task
    --type=<type>         Task type (bug, feature, refactor, etc.)
    --scope=<paths>       Scope paths (comma-separated)
    --agent=<agent>       Assigned agent (default: claude)
    --github             Enable GitHub sync
    --dependencies=<ids>  Task dependencies (comma-separated)

  list                    List tasks
    --status=<status>     Filter by status (pending, in_progress, completed)
    --agent=<agent>       Filter by agent
    --type=<type>         Filter by type
    --local              Show only local tasks

  start <task-id>         Start work on task (creates branch)
  complete <task-id>      Complete task (runs QA)
    --skip-qa            Skip QA validation
    --sync-to-github     Sync completion to GitHub

  status                  Show work overview
  resume                  Resume most recent work
  init                    Initialize local-first system
  sync <task-id>          Sync task to GitHub
  validate                Check system integrity

  create-feature <name>   Create spec-driven feature folder
    --description=<desc>  Feature description
    --type=<type>         Feature type (feature, enhancement, integration)
    --priority=<level>    Priority (low, normal, high, critical)
    --complexity=<1-5>    Complexity rating
    --agents=<list>       Assigned agents (comma-separated)
    --database           Requires database changes
    --api                Requires API development
    --frontend           Requires frontend development
    --dependencies=<list> Dependencies (comma-separated)

  list-features          List all feature specs
  help                   Show this help

EXAMPLES:
  # Local task management
  node task-cli.js create "Fix authentication bug" --type=bug --scope=backend/auth
  node task-cli.js list --status=pending --agent=claude
  node task-cli.js start local-001
  node task-cli.js complete local-001 --sync-to-github
  node task-cli.js status
  node task-cli.js resume

  # Feature spec creation (follows spec-kit patterns)
  node task-cli.js create-feature "user dashboard" --description="Admin user dashboard" --api --frontend --database
  node task-cli.js create-feature "payment integration" --type=integration --complexity=4 --agents=claude,qwen
  node task-cli.js list-features

LOCAL-FIRST FEATURES:
  - Works offline without GitHub connection
  - Integrates with .specify/ for Spec-Kit compliance
  - Automatic QA command integration
  - Branch and work session tracking
  - Optional GitHub synchronization
  - Post-deployment iterative development focus
`
        };
    }
}

// CLI execution when run directly
if (require.main === module) {
    const cli = new TaskCLI();
    const args = process.argv.slice(2);
    
    if (args.length === 0) {
        args.push('help');
    }

    cli.run(args)
        .then(result => {
            if (result.success) {
                console.log(JSON.stringify(result, null, 2));
            } else {
                console.error(JSON.stringify(result, null, 2));
                process.exit(1);
            }
        })
        .catch(error => {
            console.error(JSON.stringify({
                success: false,
                error: error.message,
                stack: error.stack
            }, null, 2));
            process.exit(1);
        });
}

module.exports = TaskCLI;