# Contributing

Thanks for your interest in the TRUGS commons.

## How changes land

This public repository is the **release surface** of a private staging
mirror. Issues and pull requests are welcome here — maintainers triage them
and shepherd accepted changes through the staging mirror into the next
coordinated release, so a merged contribution may appear in `main` as part
of a release batch rather than as your individual commit.

- **Bugs / proposals:** open an issue with a minimal reproduction (the input
  graph or TRL and the command run).
- **Pull requests:** keep them small and focused; include a test where the
  change is testable.

## Development

```bash
make dev      # editable installs: the trug CLI + the bundled trugs-folder suite
make check    # the Tier-1 gate — the bundled trugs-folder tests + self-validation
```

The canonical language spec lives in [TRUGS-LLC/TRUGS](https://github.com/TRUGS-LLC/TRUGS) —
spec questions belong there, tooling questions here.

## Licensing of contributions

This project is licensed under **Apache-2.0** (see `LICENSE` and `NOTICE`).
By submitting a contribution you agree it is provided under the same license
(inbound = outbound). Note the patent carve-out in `NOTICE`: self-developing
graph systems are out of scope for this commons and are licensed separately
by Xepayac LLC.
