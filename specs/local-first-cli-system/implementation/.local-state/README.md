# Local Development State

This directory tracks local development state for the local-first workflow.

## Files

- `active-work.json` - Currently active tasks and branches
- `task-history.json` - Completed task history
- `work-sessions.json` - Work session tracking
- `local-config.json` - Local development preferences

## Structure

### Active Work Format
```json
{
  "currentTask": "local-123",
  "currentBranch": "feature/local-task-123",
  "workingSince": "2025-01-20T10:30:00Z",
  "activeTasks": [
    {
      "id": "local-123", 
      "title": "Implement local task system",
      "status": "in-progress",
      "branch": "feature/local-task-123",
      "startedAt": "2025-01-20T10:30:00Z"
    }
  ]
}
```

### Task History Format
```json
{
  "completed": [
    {
      "id": "local-122",
      "title": "Design local task format", 
      "completedAt": "2025-01-20T09:45:00Z",
      "duration": "2h 15m",
      "commits": ["abc123", "def456"]
    }
  ]
}
```