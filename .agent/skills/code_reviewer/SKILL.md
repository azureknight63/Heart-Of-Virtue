---
name: code_reviewer
description: Performs a comprehensive code review of staged changes in the current git branch, grading them on DRY, clean coding, maintainability, stability, and performance.
---

# Code Reviewer Skill

This skill allows the Antigravity agent to perform a high-quality code review of changes staged in the current repository.

## Capabilities
- Analyzes git diffs for code quality.
- Grades code across five key dimensions: DRY, Clean Code, Maintainability, Stability, and Performance.
- Provides actionable feedback and refactoring suggestions.

## Instructions for the Agent

When this skill is activated:

1.  **Retrieve Staged Changes**:
    - Run `git diff --cached` to see what is currently staged for commit.
    - If nothing is staged, check `git diff` for unstaged changes and ask the user if they'd like those reviewed instead.
    - If there are too many changes, focus on the most critical files or ask the user for guidance.

2.  **Conduct Analysis**:
    Review the code changes specifically for:
    - **DRY (Don't Repeat Yourself)**: Are there patterns being repeated? Can logic be moved to a helper or a shared component?
    - **Clean Coding**: Are names descriptive? Is the logic easy to follow? Are there any "magic numbers" or confusing constructs?
    - **Maintainability**: Is the code modular? How hard will it be to change this in 6 months? Are there proper comments for complex logic?
    - **Stability**: Are there potential null pointer exceptions? Missing error boundaries? Unhandled promise rejections? Edge cases in logic?
    - **Performance**: Are there expensive operations inside loops? Unnecessary re-renders? Suboptimal data structures?

3.  **Structure the Response**:
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
