---
name: code_reviewer
description: Performs a comprehensive code review of code changes (diffs or file sets), grading them on DRY, clean coding, maintainability, stability, and performance. Adaptable to any provided diff, file set, or git changes.
---

# Code Reviewer Skill

This skill allows the Antigravity agent to perform a high-quality code review of code changes from various sources: direct diffs, specific files, git ranges, or staged changes.

## Capabilities
- Analyzes code changes from various sources: direct diff strings, specific files/directories, git ranges, or staged changes.
- Grades code across five key dimensions: DRY, Clean Code, Maintainability, Stability, and Performance.
- Provides actionable feedback and refactoring suggestions tailored to the provided changes.

## Instructions for the Agent

When this skill is activated, follow this adaptable workflow to review code changes:

### 1. Determine the Code to Review

First, identify what code changes to analyze. Check the user's request for any of the following:

**A. Direct Diff Provided:**
- If the user provides a diff string (typically starting with `diff --git` or containing `---`/`+++` markers), use that directly.

**B. Specific Files or Directories:**
- If the user mentions specific file paths or directories, obtain the diff for those files:
  - For staged changes: `git diff --cached -- <file paths>`
  - For unstaged changes: `git diff -- <file paths>`
  - If unsure, ask the user whether to review staged or unstaged changes.

**C. Git Range or Commit Comparison:**
- If the user specifies a commit range, branch, or commit hash (e.g., "main..feature", "HEAD~2"), use:
  - `git diff <range>` (e.g., `git diff main..feature-branch`)
  - `git diff <commit>` (e.g., `git diff HEAD~2`)
  - `git diff <commit1> <commit2>`

**D. Default: Staged Changes:**
- If no specific input is provided, run `git diff --cached` to review staged changes.
- If nothing is staged, check `git diff` for unstaged changes and ask the user if they'd like those reviewed.
- If there are too many changes, focus on the most critical files or ask the user for guidance.

### 2. Conduct Analysis

Review the code changes specifically for:
- **DRY (Don't Repeat Yourself)**: Are there patterns being repeated? Can logic be moved to a helper or a shared component?
- **Clean Coding**: Are names descriptive? Is the logic easy to follow? Are there any "magic numbers" or confusing constructs?
- **Maintainability**: Is the code modular? How hard will it be to change this in 6 months? Are there proper comments for complex logic?
- **Stability**: Are there potential null pointer exceptions? Missing error boundaries? Unhandled promise rejections? Edge cases in logic?
- **Performance**: Are there expensive operations inside loops? Unnecessary re-renders? Suboptimal data structures?

### 3. Structure the Response

Your response should be formatted as follows:

### 📝 Code Review Summary
[A brief 2-3 sentence overview of what the changes accomplish.]

### 📊 Quality Grades
| Dimension | Grade | Rationale |
| :--- | :--- | :--- |
| **DRY** | [Grade] | [Brief explanation] |
| **Clean Code** | [Grade] | [Brief explanation] |
| **Maintainability** | [Grade] | [Brief explanation] |
| **Stability** | [Grade] | [Brief explanation] |
| **Performance** | [Grade] | [Brief explanation] |

### 🔍 Detailed Feedback
- **[File Name]**:
    - [Line Number]: [Specific comment or suggestion]
    - [General]: [High-level feedback for this file]

### 💡 Recommendations
[Specific code snippets or architectural suggestions for improvement.]

## Example Usage
- "Review my staged changes."
- "Perform a code review on the latest features."
- "How does my code look regarding performance and stability?"
- "Review these changes: [paste diff here]"
- "Review the files: src/components/Button.jsx and src/utils/helpers.js"
- "Compare the changes between main and feature-branch."
- "Review the changes in commit abc123."
- "Check the diff between HEAD~3 and HEAD."
