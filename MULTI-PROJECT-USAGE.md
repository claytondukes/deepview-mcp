# Multi-Project Usage Guide

DeepView MCP supports analyzing different codebases in a single server instance. You can access projects via URL paths or specify codebase files in MCP tool calls, allowing you to work with multiple projects simultaneously.

## Quick Start with Repomix

For the easiest setup with repomix-generated codebases:

1. **Generate your codebase:**

   ```bash
   repomix --output codebase.xml
   ```

2. **Create project directory:**

   ```bash
   mkdir -p codebase/my-project
   mv codebase.xml codebase/my-project/
   ```

3. **Access via URL:**

   ```bash
   curl "http://localhost:8019/my-project?question=What%20does%20this%20code%20do?"
   ```

## Setup

1. **Organize your codebase files:**

   ```text
   codebase/
   ├── sample/
   │   └── codebase.xml         # Sample web app project
   ├── my-project/
   │   └── codebase.xml         # Your project
   └── another-project/
       └── codebase.xml         # Another project
   ```

2. **Start the server:**

   ```bash
   docker compose up
   ```

## Access Methods

### 1. URL-Based Access (Recommended for Repomix)

Access projects directly via HTTP GET requests:

```bash
# Direct project access
http://localhost:8019/{project-name}?question=Your%20question

# Alternative with /codebase/ prefix
http://localhost:8019/codebase/{project-name}?question=Your%20question
```

**Automatic File Detection:**
The system automatically looks for these files in order:

- `codebase.xml` (repomix default)
- `codebase.txt`
- `codebase.md`
- `codebase.json`

**Optional Filename Override:**

```bash
http://localhost:8019/va?question=Your%20question&filename=custom-file.xml
```

### 2. MCP Tools (For Programmatic Access)

#### `list_codebase_files`

Lists all available codebase files in mounted directories.

**Example Response:**

```json
{
  "available_files": [
    {
      "filename": "product-docs.md",
      "relative_path": "product-docs.md",
      "size_kb": 3.2,
      "directory": "/app/codebase"
    },
    {
      "filename": "backend-code.py",
      "relative_path": "backend-code.py", 
      "size_kb": 5.1,
      "directory": "/app/codebase"
    }
  ],
  "total_files": 2,
  "usage": "Use the 'relative_path' value as the codebase_file parameter in deepview queries"
}
```

### 2. `get_codebase_info`

Get information about a specific codebase file without loading its full content.

**Parameters:**

- `codebase_file`: The filename or relative path

**Example:**

```json
{
  "filename": "backend-code.py",
  "size_kb": 5.1,
  "total_lines": 145,
  "preview": [
    "# Backend Code Sample",
    "# This is a sample backend codebase for demonstrating multi-project support",
    "",
    "from flask import Flask, request, jsonify",
    "..."
  ],
  "ready_for_analysis": true
}
```

### 3. `deepview`

Analyze a codebase with Gemini AI, optionally specifying which codebase file to use.

**Parameters:**

- `question`: Your question about the code
- `codebase_file`: (Optional) Specific codebase file to analyze

## Usage Examples

### Example 1: URL-Based Access (Repomix Workflow)

```bash
# Analyze sample project via URL
curl "http://localhost:8019/sample?question=What%20are%20the%20main%20components%20of%20this%20system?"

# Alternative with /codebase/ prefix
curl "http://localhost:8019/codebase/sample?question=How%20is%20authentication%20handled?"

# Override default filename
curl "http://localhost:8019/sample?question=Explain%20the%20API&filename=custom-codebase.json"
```

**Response Format:**

```json
{
  "project": "sample",
  "codebase_file": "/app/codebase/sample/codebase.xml",
  "question": "What are the main components?",
  "answer": "Based on the codebase analysis...",
  "model": "gemini-2.5-flash"
}
```

### Example 2: MCP Tool Access

```python
# First, see what files are available
list_codebase_files()

# Analyze the sample project
deepview(
    question="What are the main components of this web application?",
    codebase_file="sample/codebase.xml"
)

# Get info about a project first
get_codebase_info(codebase_file="sample/codebase.xml")

# Ask specific questions about the sample project
deepview(
    question="How is authentication implemented in this system?",
    codebase_file="sample/codebase.xml"
)
```

### Example 3: Comparing Different Projects

```python
# Analyze documentation
docs_analysis = deepview(
    question="What API endpoints are documented?",
    codebase_file="product-docs.md"
)

# Analyze actual implementation
code_analysis = deepview(
    question="What API endpoints are implemented?", 
    codebase_file="backend-code.py"
)

# Compare results to find discrepancies
```

### Example 4: Default Codebase

```python
# If no codebase_file is specified, uses the default loaded codebase
deepview(question="What does this code do?")
```

## File Path Resolution

The system searches for codebase files in multiple locations:

1. Exact path as provided
2. `/app/codebase/{filename}` (Docker mounted directory)
3. `./codebase/{filename}` (Local codebase directory)
4. `/app/{filename}` (App root directory)

This means you can use simple filenames like `"backend-code.py"` and the system will find them automatically.

## Best Practices

### 1. **Organize by Project Type**

```text
codebase/
├── project-a-docs.md
├── project-a-backend.py
├── project-a-frontend.js
├── project-b-docs.md
├── project-b-api.py
└── shared-utils.py
```

### 2. **Use Descriptive Filenames**

- `user-service-api.py` instead of `api.py`
- `payment-docs.md` instead of `docs.md`
- `frontend-components.js` instead of `components.js`

### 3. **Check Available Files First**

Always use `list_codebase_files()` to see what's available before making queries.

### 4. **Preview Before Analysis**

Use `get_codebase_info()` to preview files and understand their content before running expensive analysis queries.

### 5. **Specific Questions**

Ask specific questions about each codebase rather than generic ones for better results.

## Workflow Example

```python
# 1. See what projects are available
files = list_codebase_files()

# 2. Get info about a specific project
info = get_codebase_info("backend-code.py")

# 3. Analyze the project
analysis = deepview(
    question="Explain the authentication flow and identify any security concerns",
    codebase_file="backend-code.py"
)

# 4. Switch to documentation analysis
docs_analysis = deepview(
    question="What deployment options are documented?",
    codebase_file="product-docs.md"
)
```

This approach allows you to maintain a single DeepView MCP server while analyzing multiple projects efficiently.
