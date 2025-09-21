/**
 * Spec Folder Manager - Creates and manages spec-driven feature folders
 * 
 * Provides consistent folder structure for both spec-kit and local-first systems.
 * Maintains spec-driven development patterns while enabling agent swarm speed.
 * 
 * Usage:
 * - Create new feature specs following spec-kit patterns
 * - Generate spec.md, plan.md, tasks.md with proper structure
 * - Enable agent swarm to build features rapidly
 * - Maintain consistency across all development approaches
 */

const fs = require('fs');
const path = require('path');

class SpecFolderManager {
    constructor(workingDir = process.cwd()) {
        this.workingDir = workingDir;
        this.specsDir = path.join(workingDir, 'specs');
        this.specifyDir = path.join(workingDir, '.specify');
        this.constitutionPath = path.join(this.specifyDir, 'memory', 'constitution.md');
    }

    /**
     * Create a new feature spec folder with full spec-kit structure
     */
    createFeatureSpec(featureName, options = {}) {
        const {
            description = '',
            type = 'feature', // feature, enhancement, integration
            priority = 'normal', // low, normal, high, critical
            complexity = 3, // 1-5 scale
            assignedAgents = ['claude'], // default to claude coordination
            requiresDatabase = false,
            requiresAPI = false,
            requiresFrontend = false,
            dependencies = []
        } = options;

        // Generate folder name
        const folderName = this.generateFeatureFolderName(featureName);
        const featureDir = path.join(this.specsDir, folderName);

        // Create directory structure
        this.createDirectoryStructure(featureDir);

        // Generate all spec files
        const specData = {
            name: featureName,
            folderName: folderName,
            description: description,
            type: type,
            priority: priority,
            complexity: complexity,
            assignedAgents: assignedAgents,
            requiresDatabase: requiresDatabase,
            requiresAPI: requiresAPI,
            requiresFrontend: requiresFrontend,
            dependencies: dependencies,
            created: new Date().toISOString()
        };

        this.generateSpecFile(featureDir, specData);
        this.generatePlanFile(featureDir, specData);
        this.generateTasksFile(featureDir, specData);
        this.createImplementationStructure(featureDir, specData);

        return {
            featureDir: featureDir,
            folderName: folderName,
            structure: this.getFeatureStructure(featureDir),
            readyForAgentSwarm: true,
            message: `Created feature spec: ${folderName}`
        };
    }

    /**
     * Generate clean folder name from feature description
     */
    generateFeatureFolderName(featureName) {
        return featureName
            .toLowerCase()
            .replace(/[^a-z0-9\s-]/g, '')
            .replace(/\s+/g, '-')
            .replace(/-+/g, '-')
            .replace(/^-|-$/g, '');
    }

    /**
     * Create directory structure for feature
     */
    createDirectoryStructure(featureDir) {
        // Main feature directory
        fs.mkdirSync(featureDir, { recursive: true });

        // Implementation subdirectories
        const implDir = path.join(featureDir, 'implementation');
        fs.mkdirSync(implDir, { recursive: true });

        // Component-specific directories
        fs.mkdirSync(path.join(implDir, 'backend'), { recursive: true });
        fs.mkdirSync(path.join(implDir, 'frontend'), { recursive: true });
        fs.mkdirSync(path.join(implDir, 'database'), { recursive: true });
        fs.mkdirSync(path.join(implDir, 'tests'), { recursive: true });
        fs.mkdirSync(path.join(implDir, 'docs'), { recursive: true });
    }

    /**
     * Generate spec.md file (equivalent to /specify output)
     */
    generateSpecFile(featureDir, specData) {
        const constitution = this.getConstitutionContext();
        
        const specContent = `# Feature Specification: ${specData.name}

## Overview
**Feature**: ${specData.name}
**Type**: ${specData.type}
**Priority**: ${specData.priority}
**Complexity**: ${specData.complexity}/5
**Created**: ${specData.created}

## Description
${specData.description || 'Feature description to be defined.'}

## Constitutional Compliance
${constitution ? `Following project constitution: ${this.constitutionPath}` : 'No constitution found - consider creating one'}

### Key Principles
- Maintain architectural consistency
- Follow existing code patterns
- Ensure test coverage
- Document all changes

## Requirements

### Functional Requirements
- [ ] Core functionality defined
- [ ] User interaction patterns specified
- [ ] Data flow requirements documented
- [ ] Integration points identified

### Technical Requirements
- [ ] Database schema defined ${specData.requiresDatabase ? '(Required)' : '(Optional)'}
- [ ] API endpoints specified ${specData.requiresAPI ? '(Required)' : '(Optional)'}
- [ ] Frontend components planned ${specData.requiresFrontend ? '(Required)' : '(Optional)'}
- [ ] Performance requirements set
- [ ] Security considerations addressed

### Quality Requirements
- [ ] Unit test strategy defined
- [ ] Integration test approach planned
- [ ] Error handling specified
- [ ] Logging requirements set

## Dependencies
${specData.dependencies.length > 0 ? 
    specData.dependencies.map(dep => `- ${dep}`).join('\n') : 
    'No dependencies identified'}

## Acceptance Criteria
- [ ] Feature works as specified
- [ ] All tests pass
- [ ] Performance meets requirements
- [ ] Security validated
- [ ] Documentation complete

## Success Metrics
- [ ] User can complete core workflows
- [ ] Performance benchmarks met
- [ ] Error rates below threshold
- [ ] User satisfaction criteria achieved

---
*Generated by Local-First Spec System*
*Ready for agent swarm implementation*
`;

        fs.writeFileSync(path.join(featureDir, 'spec.md'), specContent);
    }

    /**
     * Generate plan.md file (equivalent to /plan output)
     */
    generatePlanFile(featureDir, specData) {
        const planContent = `# Implementation Plan: ${specData.name}

## Architecture Overview

### Component Strategy
- **Backend**: ${specData.requiresAPI ? 'API endpoints, business logic, data layer' : 'Minimal backend changes'}
- **Frontend**: ${specData.requiresFrontend ? 'UI components, state management, user workflows' : 'No frontend changes'}
- **Database**: ${specData.requiresDatabase ? 'Schema changes, migrations, queries' : 'No database changes'}
- **Testing**: Unit tests, integration tests, E2E validation

### Technology Stack
Following existing project patterns:
- Backend: [Detect from project - Node.js/Python/etc]
- Frontend: [Detect from project - React/Vue/etc]
- Database: [Detect from project - PostgreSQL/MySQL/etc]
- Testing: [Detect from project - Jest/pytest/etc]

## Implementation Phases

### Phase 1: Foundation
- [ ] Database schema design and migration
- [ ] Core data models
- [ ] Basic API structure
- [ ] Test framework setup

### Phase 2: Core Logic
- [ ] Business logic implementation
- [ ] API endpoint development
- [ ] Data validation and processing
- [ ] Error handling

### Phase 3: User Interface
- [ ] Frontend component development
- [ ] State management integration
- [ ] User workflow implementation
- [ ] UI/UX polish

### Phase 4: Integration & Testing
- [ ] Integration testing
- [ ] End-to-end testing
- [ ] Performance optimization
- [ ] Security validation

### Phase 5: Documentation & Deployment
- [ ] API documentation
- [ ] User documentation
- [ ] Deployment preparation
- [ ] Monitoring setup

## Technical Decisions

### Database Design
${specData.requiresDatabase ? `
- Schema changes required
- Consider migration strategy
- Index optimization
- Data validation rules
` : 'No database changes required'}

### API Design
${specData.requiresAPI ? `
- RESTful endpoint structure
- Request/response formats
- Authentication/authorization
- Rate limiting strategy
` : 'No new API endpoints required'}

### Frontend Architecture
${specData.requiresFrontend ? `
- Component hierarchy
- State management approach
- Routing requirements
- Performance considerations
` : 'No frontend changes required'}

## Risk Assessment
- **Complexity**: ${specData.complexity}/5
- **Dependencies**: ${specData.dependencies.length} external dependencies
- **Integration Points**: Review existing system touchpoints
- **Performance Impact**: Assess system resource requirements

## Quality Gates
- [ ] Code review completion
- [ ] Test coverage > 80%
- [ ] Performance benchmarks met
- [ ] Security scan passed
- [ ] Documentation complete

---
*Generated by Local-First Spec System*
*Ready for task generation and agent assignment*
`;

        fs.writeFileSync(path.join(featureDir, 'plan.md'), planContent);
    }

    /**
     * Generate tasks.md file with agent assignments
     */
    generateTasksFile(featureDir, specData) {
        const tasksContent = `# Feature Implementation Tasks: ${specData.name}

## Project: ${specData.name}
## Swarm Deployment: \`swarm ${featureDir} "Implement ${specData.name}"\`

### Architecture & Analysis
- [ ] T001 @gemini Analyze existing system integration points for ${specData.name}
- [ ] T002 @gemini Review specification requirements and technical constraints
- [ ] T003 @gemini Document architectural decisions and design patterns

${specData.requiresDatabase ? `
### Database Development
- [ ] T010 @claude Design database schema for ${specData.name}
- [ ] T011 @claude Create migration scripts
- [ ] T012 @claude Implement data models and relationships
- [ ] T013 @claude Add database indexes and constraints
` : ''}

${specData.requiresAPI ? `
### Backend Development
- [ ] T020 @claude Implement core business logic
- [ ] T021 @claude Create API endpoints and routing
- [ ] T022 @claude Add request validation and error handling
- [ ] T023 @claude Implement authentication and authorization
` : ''}

${specData.requiresFrontend ? `
### Frontend Development
- [ ] T030 @codex Create UI components for ${specData.name}
- [ ] T031 @codex Implement user workflows and navigation
- [ ] T032 @codex Add state management and data fetching
- [ ] T033 @codex Implement responsive design and accessibility
` : ''}

### Testing & Quality
- [ ] T040 @claude Write unit tests for core functionality
- [ ] T041 @claude Create integration tests
- [ ] T042 @claude Implement end-to-end test scenarios
- [ ] T043 @claude Performance testing and optimization

### Performance & Optimization
- [ ] T050 @qwen Profile performance bottlenecks
- [ ] T051 @qwen Optimize database queries and caching
- [ ] T052 @qwen Frontend performance optimization
- [ ] T053 @qwen Load testing and scalability validation

### Documentation & Deployment
- [ ] T060 @gemini Create API documentation
- [ ] T061 @gemini Write user documentation and guides
- [ ] T062 @claude Prepare deployment configuration
- [ ] T063 @claude Set up monitoring and logging

## Task Assignment Protocol

### How Agents Find Their Tasks
1. **Swarm deployment** extracts tasks for each agent using @symbol
2. **Each agent** focuses on their specialty area
3. **Claude coordinates** integration and quality gates
4. **Mark complete** by changing \`[ ]\` to \`[x]\` with implementation notes

### Agent Responsibilities
- **@gemini**: Analysis, documentation, architecture review
- **@qwen**: Performance optimization, caching, scalability
- **@codex**: Frontend components, UI/UX, user experience
- **@claude**: Backend logic, coordination, integration, testing

## Task Dependencies

### Sequential Dependencies
- [ ] T001-T003 @gemini Analysis (must complete first)
${specData.requiresDatabase ? '- [ ] T010-T013 @claude Database foundation (depends on analysis)' : ''}
${specData.requiresAPI ? '- [ ] T020-T023 @claude Backend implementation (depends on database)' : ''}
${specData.requiresFrontend ? '- [ ] T030-T033 @codex Frontend implementation (depends on backend)' : ''}
- [ ] T040-T043 @claude Testing (depends on implementation)
- [ ] T050-T053 @qwen Optimization (after core implementation)
- [ ] T060-T063 Documentation and deployment (depends on completion)

### Parallel Tasks (can run simultaneously)
- [ ] T002 @gemini Requirements review
- [ ] T003 @gemini Architecture documentation
- [ ] T041 @claude Integration tests
- [ ] T051 @qwen Performance optimization
- [ ] T061 @gemini User documentation

## Success Criteria
- [ ] All functional requirements implemented
- [ ] Test coverage > 80%
- [ ] Performance benchmarks met
- [ ] Security validation passed
- [ ] Documentation complete
- [ ] Ready for production deployment

## Agent Swarm Execution
\`\`\`bash
# Deploy agent swarm to build this feature
swarm ${featureDir} "Implement ${specData.name}"

# Monitor progress
tail -f /tmp/agent-swarm-logs/*.log

# Validate completion
./ops qa --all
\`\`\`

---
*Generated by Local-First Spec System*
*Compatible with spec-kit patterns*
*Optimized for agent swarm execution*
`;

        fs.writeFileSync(path.join(featureDir, 'tasks.md'), tasksContent);
    }

    /**
     * Create implementation directory structure
     */
    createImplementationStructure(featureDir, specData) {
        const implDir = path.join(featureDir, 'implementation');
        
        // Create README for implementation
        const readmeContent = `# Implementation: ${specData.name}

This directory contains all implementation artifacts for the ${specData.name} feature.

## Structure
- \`backend/\` - Server-side code, APIs, business logic
- \`frontend/\` - User interface components and workflows
- \`database/\` - Schema migrations and database-related code
- \`tests/\` - Unit, integration, and E2E tests
- \`docs/\` - Technical documentation and API specs

## Development Workflow
1. Agents implement according to tasks.md assignments
2. Code is organized by component type
3. Tests are written alongside implementation
4. Documentation is updated as features are built

## Quality Gates
- All code must pass linting and type checking
- Test coverage must exceed 80%
- Security scans must pass
- Performance benchmarks must be met

---
*Generated by agent swarm from spec-driven tasks*
`;

        fs.writeFileSync(path.join(implDir, 'README.md'), readmeContent);

        // Create component-specific README files
        this.createComponentReadme(path.join(implDir, 'backend'), 'Backend Implementation');
        this.createComponentReadme(path.join(implDir, 'frontend'), 'Frontend Implementation');
        this.createComponentReadme(path.join(implDir, 'database'), 'Database Implementation');
        this.createComponentReadme(path.join(implDir, 'tests'), 'Test Implementation');
        this.createComponentReadme(path.join(implDir, 'docs'), 'Documentation');
    }

    /**
     * Create component-specific README
     */
    createComponentReadme(componentDir, title) {
        const readmeContent = `# ${title}

This directory contains ${title.toLowerCase()} for the feature.

## Guidelines
- Follow existing project patterns and conventions
- Maintain consistency with current codebase
- Document all public interfaces
- Include appropriate error handling
- Write tests for all functionality

## Agent Responsibilities
Code in this directory is implemented by specialized agents based on their expertise areas.
`;

        fs.writeFileSync(path.join(componentDir, 'README.md'), readmeContent);
    }

    /**
     * Get constitutional context if available
     */
    getConstitutionContext() {
        if (fs.existsSync(this.constitutionPath)) {
            try {
                return fs.readFileSync(this.constitutionPath, 'utf8');
            } catch (error) {
                return null;
            }
        }
        return null;
    }

    /**
     * Get feature structure for validation
     */
    getFeatureStructure(featureDir) {
        const structure = {
            spec: fs.existsSync(path.join(featureDir, 'spec.md')),
            plan: fs.existsSync(path.join(featureDir, 'plan.md')),
            tasks: fs.existsSync(path.join(featureDir, 'tasks.md')),
            implementation: {
                backend: fs.existsSync(path.join(featureDir, 'implementation', 'backend')),
                frontend: fs.existsSync(path.join(featureDir, 'implementation', 'frontend')),
                database: fs.existsSync(path.join(featureDir, 'implementation', 'database')),
                tests: fs.existsSync(path.join(featureDir, 'implementation', 'tests')),
                docs: fs.existsSync(path.join(featureDir, 'implementation', 'docs'))
            }
        };

        return structure;
    }

    /**
     * List all feature specs
     */
    listFeatureSpecs() {
        if (!fs.existsSync(this.specsDir)) {
            return [];
        }

        const specs = [];
        const entries = fs.readdirSync(this.specsDir, { withFileTypes: true });

        for (const entry of entries) {
            if (entry.isDirectory()) {
                const featureDir = path.join(this.specsDir, entry.name);
                const structure = this.getFeatureStructure(featureDir);
                
                // Only include directories that look like feature specs
                if (structure.spec && structure.plan && structure.tasks) {
                    specs.push({
                        name: entry.name,
                        path: featureDir,
                        structure: structure,
                        isComplete: structure.spec && structure.plan && structure.tasks
                    });
                }
            }
        }

        return specs;
    }

    /**
     * Validate feature spec completeness
     */
    validateFeatureSpec(featureName) {
        const featureDir = path.join(this.specsDir, featureName);
        
        if (!fs.existsSync(featureDir)) {
            return {
                valid: false,
                error: `Feature directory not found: ${featureName}`
            };
        }

        const structure = this.getFeatureStructure(featureDir);
        const issues = [];

        if (!structure.spec) issues.push('Missing spec.md');
        if (!structure.plan) issues.push('Missing plan.md');
        if (!structure.tasks) issues.push('Missing tasks.md');

        return {
            valid: issues.length === 0,
            issues: issues,
            structure: structure
        };
    }
}

module.exports = SpecFolderManager;