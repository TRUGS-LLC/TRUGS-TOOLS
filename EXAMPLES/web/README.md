# Web Branch Examples

WEB branch examples for website structure representation using TRUGS v1.0.

## Files

| File | Complexity | Nodes | Description |
|------|-----------|-------|-------------|
| `minimal.json` | Minimal | 3 | Single site with one page |
| `medium.json` | Medium | 6 | Blog with two pages, hero banner, and content sections |
| `complex.json` | Complex | 9 | E-commerce store with navigation, product listings, and cart |
| `complete.json` | Complete | Many | Full-featured example with all node types |

## Node Types

- **SITE** — Top-level website
- **PAGE** — Individual page with path and template
- **SECTION** — Page section (hero, listing, nav, sidebar, grid, table)

## Dimensions

```
web_structure: SITE → PAGE → SECTION
```

## Usage

```bash
# Validate
trugs-validate web/medium.json

# Generate
trugs-generate --branch web --template minimal
```

## Specification

See [BRANCH_SPECS/REFERENCE_web.md](../../BRANCH_SPECS/REFERENCE_web.md) for the full Web branch specification.
