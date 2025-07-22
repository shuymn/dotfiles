---
allowed-tools: Bash(mkdir:*), Bash(find:*), Bash(ls:*), Read, Write, Edit, MultiEdit, TodoWrite
description: Perform spec-driven development by creating requirements, design, and implementation plan documents
---

We will perform spec-driven development using Claude Code.

## What is spec-driven development

Spec-driven development is a development methodology consisting of the following 5 phases.  
When writing documentation, prioritize using Mermaid notation over ASCII art.  
Think carefully and work hard on everything you do at ULTRATHINK.

### 1. Preparation Phase

- The user communicates an overview of the task they want to execute to Claude Code
- In this phase, execute !`mkdir -p ./specs`
- Create a directory with an appropriate spec name based on the task overview within `./specs`
    - For example, if the task is "create an article component", create a directory named `./specs/create-article-component`
- When creating the following files, create them inside this directory

### 2. Requirements Phase

- Claude Code creates a "requirements file" that describes what the task should satisfy, based on the task overview communicated by the user
- Claude Code presents the "requirements file" to the user and asks if there are any issues
- The user reviews the "requirements file" and provides feedback to Claude Code if there are any problems
- Repeat modifications to the "requirements file" until the user confirms there are no problems

### 3. Design Phase

- Claude Code creates a "design file" that describes a design satisfying the requirements listed in the "requirements file"
- Claude Code presents the "design file" to the user and asks if there are any issues
- The user reviews the "design file" and provides feedback to Claude Code if there are any problems
- Repeat modifications to the "requirements file" until the user confirms there are no problems with the "design file"

### 4. Implementation Planning Phase

- Claude Code creates an "implementation plan file" for implementing the design described in the "design file"
- Claude Code presents the "implementation plan file" to the user and asks if there are any issues
- The user reviews the "implementation plan file" and provides feedback to Claude Code if there are any problems
- Repeat modifications to the "requirements file" until the user confirms there are no problems with the "implementation plan file"

### 5. Implementation Phase

- Claude Code begins implementation based on the "implementation plan file"
- When implementing, please implement while adhering to the content described in the "requirements file" and "design file"
