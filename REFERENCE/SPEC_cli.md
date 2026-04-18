# TRUGS_TOOLS: CLI Specification

**Version:** 1.1.0 (AAA_AARDVARK)
**Component:** TRUGS_TOOLS Command-Line Interface
**Status:** ✅ Specification Complete (Sprint 2 Filesystem Commands Added)
**Last Updated:** 2026-02-17
**Parent:** [AAA.md](AAA.md)

---

## Purpose

The TRUGS_TOOLS CLI provides a unified command-line interface for all TRUGS tools: validator, generator, renderer, and filesystem commands. It offers intuitive commands, consistent options, and helpful output for working with TRUG files.

**Core Commands:**
- `trugs-validate` - Validate TRUG files
- `trugs-generate` - Generate example TRUGs
- `trugs-info` - Analyze and display TRUG information
- `trugs-render` - Render folder.trug.json into markdown

**Filesystem Commands (Sprint 2):**
- `trugs tinit` - Initialize folder.trug.json
- `trugs tadd` - Add files to graph
- `trugs tls` - List with graph enrichment
- `trugs tcd` - Graph-based navigation
- `trugs tfind` - Graph query engine
- `trugs tmove` - Atomic file move + graph update
- `trugs tlink` - Create/remove typed edges
- `trugs tdim` - Dimension management
- `trugs twatch` - Monitor + auto-regenerate docs
- `trugs tsync` - Discover files + infer edges

**Design Goals:**
1. **Intuitive** - Commands follow Unix conventions
2. **Consistent** - Similar options across all commands
3. **Helpful** - Clear error messages and hints
4. **Scriptable** - JSON output for automation
5. **Fast** - Quick startup and execution

---

## Architecture

### Design Principles

1. **Single Entry Point** - One main CLI script with subcommands
2. **Composable** - Tools can be chained via pipes
3. **Standard I/O** - Reads from stdin, writes to stdout
4. **Exit Codes** - Proper exit codes for scripting
5. **Colors** - Optional colored output for terminals

### Module Structure

```
trugs_tools/
├── cli.py                # Main CLI entry point (all commands)
├── validator.py          # Validation engine
├── generator.py          # TRUG generation
├── renderer.py           # Folder TRUG → markdown rendering
├── errors.py             # Error types
├── rules.py              # Validation rules
├── templates/            # Branch templates
└── filesystem/           # Filesystem commands (Sprint 2)
    ├── __init__.py       # Package exports
    ├── utils.py          # Shared utilities (load_graph, save_graph, etc.)
    ├── tinit.py          # Initialize folder.trug.json
    ├── tadd.py           # Add files to graph
    ├── tls.py            # List with graph enrichment
    ├── tcd.py            # Graph-based navigation
    ├── tfind.py          # Graph query engine
    ├── tmove.py          # Atomic file move + graph update
    ├── tlink.py          # Create/remove typed edges
    ├── tdim.py           # Dimension management
    ├── twatch.py         # Monitor + auto-regenerate
    └── tsync.py          # Discover files + infer edges
```

### CLI Architecture

```
trugs [global options] <command> [command options] [arguments]

Global Options:
  --version              Show version
  --help                 Show help
  --no-color             Disable colored output

Commands:
  validate               Validate TRUG files
  generate               Generate example TRUGs
  info                   Show TRUG information
  render                 Render folder.trug.json into markdown
  tinit                  Initialize folder.trug.json
  tadd                   Add files to graph
  tls                    List with graph enrichment
  tcd                    Navigate TRUG graph
  tfind                  Query TRUG graph nodes
  tmove                  Move/rename graph node
  tlink                  Create/remove typed edges
  tdim                   Manage dimensions
  twatch                 Watch and auto-regenerate docs
  tsync                  Sync graph with directory
```

---

## Command Specifications

### 1. trugs validate

**Purpose:** Validate TRUG files against TRUGS v1.0 specification

**Usage:**
```bash
trugs validate [options] <file>...
trugs validate [options] -      # Read from stdin
```

**Options:**

| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--format FORMAT` | `-f` | Output format (text, json, compact) | text |
| `--quiet` | `-q` | Only show summary | false |
| `--verbose` | `-v` | Show all details | false |
| `--no-color` | | Disable colored output | false |
| `--output FILE` | `-o` | Write output to file | stdout |

**Examples:**

```bash
# Validate single file
trugs validate example.json

# Validate multiple files
trugs validate file1.json file2.json file3.json

# Validate from stdin
cat example.json | trugs validate -

# JSON output for scripting
trugs validate --format json example.json

# Quiet mode (exit code only)
trugs validate --quiet example.json && echo "Valid"

# Verbose output
trugs validate --verbose example.json
```

**Output Examples:**

**Success (text):**
```
✓ example.json: Valid TRUG (42 nodes, 38 edges)
```

**Failure (text):**
```
✗ example.json: 2 errors found

[DUPLICATE_NODE_ID] nodes[1].id
  Duplicate node ID: 'func_main'
  Hint: Each node must have a unique ID

[INCONSISTENT_HIERARCHY] nodes[func_2].parent_id
  Node 'func_2' claims parent 'module_1', but parent doesn't list it in contains[]
  Hint: Add 'func_2' to nodes[module_1].contains[] array
```

**Success (JSON):**
```json
{
  "file": "example.json",
  "valid": true,
  "errors": [],
  "warnings": [],
  "stats": {
    "nodes": 42,
    "edges": 38
  }
}
```

**Failure (JSON):**
```json
{
  "file": "example.json",
  "valid": false,
  "errors": [
    {
      "code": "DUPLICATE_NODE_ID",
      "message": "Duplicate node ID: 'func_main'",
      "location": "nodes[1].id",
      "hint": "Each node must have a unique ID"
    }
  ],
  "warnings": []
}
```

**Exit Codes:**

| Code | Meaning |
|------|---------|
| 0 | All files valid |
| 1 | Validation errors found |
| 2 | File not found or read error |
| 3 | Invalid JSON syntax |
| 4 | Invalid command-line arguments |

---

### 2. trugs generate

**Purpose:** Generate example TRUG files for all branches and extensions

**Usage:**
```bash
trugs generate [options]
trugs generate --branch BRANCH [options]
```

**Options:**

| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--branch BRANCH` | `-b` | Branch name (python, rust, llvm, web, writer, semantic) | required |
| `--template TYPE` | `-t` | Template type (minimal, complete) | minimal |
| `--extension EXT` | `-e` | Add extension (repeatable) | [] |
| `--name NAME` | `-n` | Custom TRUG name | auto |
| `--output FILE` | `-o` | Output file path | stdout |
| `--output-dir DIR` | | Output directory (with --all) | . |
| `--all` | `-a` | Generate all branches | false |
| `--validate` | | Validate before output | true |
| `--no-validate` | | Skip validation | false |
| `--pretty` | | Pretty-print JSON | true |

**Examples:**

```bash
# Generate minimal Python TRUG
trugs generate --branch python

# Generate complete Python TRUG
trugs generate --branch python --template complete

# Add extensions
trugs generate --branch python --extension typed --extension scoped

# Save to file
trugs generate --branch python --output example.json

# Generate all branches (minimal)
trugs generate --all --output-dir examples/

# Generate with custom name
trugs generate --branch rust --name "My Rust Example"

# Skip validation (faster)
trugs generate --branch llvm --no-validate
```

**Output Examples:**

**Success:**
```
✓ Generated Python minimal TRUG (3 nodes, 0 edges)
{
  "name": "Python Minimal Example",
  "version": "1.0.0",
  ...
}
```

**With File Output:**
```
✓ Generated example.json (3 nodes, 0 edges)
```

**Generate All:**
```
✓ Generated python_minimal.json (3 nodes, 0 edges)
✓ Generated rust_minimal.json (3 nodes, 0 edges)
✓ Generated llvm_minimal.json (4 nodes, 0 edges)
✓ Generated web_minimal.json (3 nodes, 0 edges)
✓ Generated writer_minimal.json (3 nodes, 0 edges)
✓ Generated semantic_minimal.json (3 nodes, 0 edges)
```

**Exit Codes:**

| Code | Meaning |
|------|---------|
| 0 | Generation successful |
| 1 | Generation failed |
| 2 | Invalid branch or template |
| 3 | Validation failed (if --validate) |
| 4 | Invalid command-line arguments |

---

### 3. trugs info

**Purpose:** Analyze and display TRUG information and statistics

**Usage:**
```bash
trugs info [options] <file>...
trugs info [options] -      # Read from stdin
```

**Options:**

| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--format FORMAT` | `-f` | Output format (text, json, compact) | text |
| `--section SECTION` | `-s` | Show only specific section | all |
| `--output FILE` | `-o` | Write output to file | stdout |
| `--no-color` | | Disable colored output | false |

**Sections:**
- `metadata` - TRUG metadata only
- `statistics` - Graph statistics only
- `hierarchy` - Hierarchy analysis only
- `dimensions` - Dimension analysis only
- `distributions` - Type and relation distributions only
- `all` - Show all sections (default)

**Examples:**

```bash
# Show full analysis
trugs info example.json

# Compact summary
trugs info --format compact example.json

# JSON output
trugs info --format json example.json

# Show only metadata
trugs info --section metadata example.json

# Analyze multiple files
trugs info file1.json file2.json file3.json

# From stdin
cat example.json | trugs info -
```

**Output Examples:**

**Text Output:**
```
TRUG Analysis: Python Fibonacci Example
================================================================================

METADATA
  Name: Python Fibonacci Example
  Version: 1.0.0
  Type: CODE
  Extensions: typed, scoped
  Vocabularies: python_3.12

STATISTICS
  Nodes: 42
  Edges: 38
  Roots: 1
  Leaves: 20
  Avg Degree: 1.81
  Density: 0.0220

HIERARCHY
  Max Depth: 4
  Avg Depth: 2.30
  Branching Factor: 2.10
  Max Children: 5

DIMENSIONS
  code_structure: 42 nodes, depth 4
    Levels: BASE(15), CENTI(17), DECI(10)

NODE TYPES
  STATEMENT: 20 (47.6%)
  FUNCTION: 15 (35.7%)
  MODULE: 5 (11.9%)
  CLASS: 2 (4.8%)

EDGE RELATIONS
  CONTAINS: 20 (52.6%)
  CALLS: 15 (39.5%)
  IMPORTS: 3 (7.9%)
```

**Compact Output:**
```
Python Fibonacci Example (CODE): 42 nodes, 38 edges, depth 4
```

**Exit Codes:**

| Code | Meaning |
|------|---------|
| 0 | Analysis successful |
| 1 | Analysis failed |
| 2 | File not found or read error |
| 3 | Invalid JSON syntax |
| 4 | Invalid command-line arguments |

---

## Global Options

### --version

Shows version information and exits.

```bash
trugs --version
# Output: trugs-tools 1.0.0 (AAA_AARDVARK)
```

### --help

Shows help message and exits.

```bash
trugs --help
trugs validate --help
trugs generate --help
trugs info --help
```

**Help Output:**
```
trugs-tools 1.0.0 - TRUGS Protocol Tools

Usage: trugs [options] <command> [args]

Commands:
  validate    Validate TRUG files
  generate    Generate example TRUGs
  info        Show TRUG information

Options:
  --version   Show version and exit
  --help      Show this help message
  --no-color  Disable colored output

Run 'trugs <command> --help' for command-specific help.

Examples:
  trugs validate example.json
  trugs generate --branch python
  trugs info example.json
```

---

## Color Scheme

When color is enabled (terminal and not disabled):

**Validation:**
- ✅ Green - Valid
- ❌ Red - Invalid
- ⚠️  Yellow - Warning
- 🔵 Blue - Info

**Code Highlights:**
- Error codes: Red
- Locations: Yellow
- Hints: Cyan

**Statistics:**
- Section headers: Bold
- Values: Default
- High values: Green
- Low values: Red (when relevant)

**Auto-Detection:**
Colors are automatically disabled when:
- Output is not a TTY (piped/redirected)
- `NO_COLOR` environment variable is set
- `--no-color` flag is used
- Running on Windows without ANSI support

---

## Implementation

### Main CLI Entry Point

```python
# cli.py
import sys
from .cli_validate import validate_command
from .cli_generate import generate_command
from .cli_info import info_command

def main():
    """Main CLI entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        prog='trugs',
        description='TRUGS Protocol Tools',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument('--version', action='version', version='trugs-tools 1.0.0')
    parser.add_argument('--no-color', action='store_true', help='Disable colored output')
    
    subparsers = parser.add_subparsers(dest='command', help='Command to run')
    
    # Validate command
    validate_parser = subparsers.add_parser('validate', help='Validate TRUG files')
    validate_parser.add_argument('files', nargs='+', help='TRUG files to validate')
    validate_parser.add_argument('-f', '--format', choices=['text', 'json', 'compact'], default='text')
    validate_parser.add_argument('-q', '--quiet', action='store_true')
    validate_parser.add_argument('-v', '--verbose', action='store_true')
    validate_parser.add_argument('-o', '--output', help='Output file')
    
    # Generate command
    generate_parser = subparsers.add_parser('generate', help='Generate example TRUGs')
    generate_parser.add_argument('-b', '--branch', help='Branch name')
    generate_parser.add_argument('-t', '--template', choices=['minimal', 'complete'], default='minimal')
    generate_parser.add_argument('-e', '--extension', action='append', default=[], help='Add extension')
    generate_parser.add_argument('-n', '--name', help='Custom TRUG name')
    generate_parser.add_argument('-o', '--output', help='Output file')
    generate_parser.add_argument('-a', '--all', action='store_true', help='Generate all branches')
    generate_parser.add_argument('--no-validate', action='store_true', help='Skip validation')
    
    # Info command
    info_parser = subparsers.add_parser('info', help='Show TRUG information')
    info_parser.add_argument('files', nargs='+', help='TRUG files to analyze')
    info_parser.add_argument('-f', '--format', choices=['text', 'json', 'compact'], default='text')
    info_parser.add_argument('-s', '--section', help='Show only specific section')
    info_parser.add_argument('-o', '--output', help='Output file')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(0)
    
    # Dispatch to command
    try:
        if args.command == 'validate':
            sys.exit(validate_command(args))
        elif args.command == 'generate':
            sys.exit(generate_command(args))
        elif args.command == 'info':
            sys.exit(info_command(args))
    except KeyboardInterrupt:
        print("\nInterrupted", file=sys.stderr)
        sys.exit(130)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()
```

### CLI Utilities

```python
# cli_utils.py
import sys
import os

def is_terminal() -> bool:
    """Check if stdout is a terminal."""
    return sys.stdout.isatty()

def should_use_color(args) -> bool:
    """Determine if colored output should be used."""
    if getattr(args, 'no_color', False):
        return False
    if os.environ.get('NO_COLOR'):
        return False
    if not is_terminal():
        return False
    return True

class Colors:
    """ANSI color codes."""
    RESET = '\033[0m'
    BOLD = '\033[1m'
    RED = '\033[31m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    BLUE = '\033[34m'
    CYAN = '\033[36m'

def colorize(text: str, color: str, use_color: bool = True) -> str:
    """Colorize text if color is enabled."""
    if not use_color:
        return text
    return f"{color}{text}{Colors.RESET}"

def print_success(message: str, use_color: bool = True):
    """Print success message."""
    symbol = colorize("✓", Colors.GREEN, use_color)
    print(f"{symbol} {message}")

def print_error(message: str, use_color: bool = True):
    """Print error message."""
    symbol = colorize("✗", Colors.RED, use_color)
    print(f"{symbol} {message}", file=sys.stderr)

def print_warning(message: str, use_color: bool = True):
    """Print warning message."""
    symbol = colorize("⚠", Colors.YELLOW, use_color)
    print(f"{symbol} {message}")

def read_from_stdin_or_file(filename: str) -> str:
    """Read from stdin if filename is '-', otherwise read file."""
    if filename == '-':
        return sys.stdin.read()
    else:
        with open(filename) as f:
            return f.read()

def write_to_stdout_or_file(content: str, filename: str = None):
    """Write to stdout if filename is None, otherwise write to file."""
    if filename:
        with open(filename, 'w') as f:
            f.write(content)
    else:
        print(content)
```

---

## Testing Strategy

### Unit Tests

Test each command:

```python
# tests/test_cli.py
def test_validate_command():
    """Test validate command."""
    result = subprocess.run(
        ['trugs', 'validate', 'tests/fixtures/valid.json'],
        capture_output=True,
        text=True
    )
    assert result.returncode == 0
    assert "Valid TRUG" in result.stdout

def test_generate_command():
    """Test generate command."""
    result = subprocess.run(
        ['trugs', 'generate', '--branch', 'python'],
        capture_output=True,
        text=True
    )
    assert result.returncode == 0
    assert "Python Minimal Example" in result.stdout

def test_info_command():
    """Test info command."""
    result = subprocess.run(
        ['trugs', 'info', 'tests/fixtures/valid.json'],
        capture_output=True,
        text=True
    )
    assert result.returncode == 0
    assert "TRUG Analysis" in result.stdout
```

### Integration Tests

Test complete workflows:

```python
# tests/test_cli_integration.py
def test_generate_and_validate():
    """Test generating and validating in pipeline."""
    # Generate
    gen_result = subprocess.run(
        ['trugs', 'generate', '--branch', 'python', '--output', '/tmp/test.json'],
        capture_output=True
    )
    assert gen_result.returncode == 0
    
    # Validate
    val_result = subprocess.run(
        ['trugs', 'validate', '/tmp/test.json'],
        capture_output=True
    )
    assert val_result.returncode == 0

def test_stdin_pipe():
    """Test reading from stdin."""
    # Generate to stdout, pipe to validate
    result = subprocess.run(
        'trugs generate --branch python | trugs validate -',
        shell=True,
        capture_output=True
    )
    assert result.returncode == 0
```

---

## Implementation Checklist

### Phase 1: Core Infrastructure
- [ ] Create `cli.py` with main entry point
- [ ] Create `cli_utils.py` with helper functions
- [ ] Implement argument parsing
- [ ] Add color support with auto-detection

### Phase 2: Commands
- [ ] Implement `cli_validate.py`
- [ ] Implement `cli_generate.py`
- [ ] Implement `cli_info.py`
- [ ] Wire up commands to main CLI

### Phase 3: Features
- [ ] Add stdin/stdout support
- [ ] Add file output support
- [ ] Add JSON output format
- [ ] Add compact output format
- [ ] Implement --help for all commands

### Phase 4: Polish
- [ ] Add colored output
- [ ] Improve error messages
- [ ] Add progress indicators (for --all)
- [ ] Add bash completion script

### Phase 5: Testing
- [ ] Write unit tests for each command
- [ ] Write integration tests
- [ ] Test on Linux, macOS, Windows
- [ ] Test with pipes and redirects

### Phase 6: Documentation
- [ ] Write man pages
- [ ] Create usage examples
- [ ] Add troubleshooting guide

---

## Dependencies

### Required
- Python 3.8+
- argparse (stdlib)
- sys, os (stdlib)

### Optional
- colorama (for Windows color support)

---

## Installation

The CLI will be installed via:

```bash
pip install trugs-tools
```

Which will register the `trugs` command in the user's PATH.

**Entry point in setup.py/pyproject.toml:**
```toml
[project.scripts]
trugs = "trugs_tools.cli:main"
```

---

## Future Enhancements

**Not in v1.0, but valuable for future versions:**

1. **Shell Completion** - Bash/Zsh/Fish completion scripts
2. **Watch Mode** - `trugs validate --watch` for continuous validation
3. **Batch Mode** - Process entire directories
4. **Config Files** - `.trugsrc` for default options
5. **Plugins** - User-defined commands
6. **Interactive Mode** - Guided TRUG creation
7. **LSP Server** - Language Server Protocol for editors

---

## Specification Status

✅ **Complete** - Ready for implementation

**Next Steps:**
1. Review this specification
2. Implement Phase 1: Core Infrastructure
3. Implement Phase 2: Commands
4. Test and polish

---

## References

- [SPEC_validator.md](SPEC_validator.md) - Validator specification
- [SPEC_generator.md](SPEC_generator.md) - Generator specification
- [SPEC_analyzer.md](SPEC_analyzer.md) - Analyzer specification
- [SPEC_filesystem.md](SPEC_filesystem.md) - Filesystem commands tutorial and reference
- [AAA.md](AAA.md) - TRUGS_TOOLS project overview
