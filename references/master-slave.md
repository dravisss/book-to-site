# Master-Slave with `hermes chat`

## Why not delegate_task

`delegate_task` only lets you swap the model via global config
(`delegation.provider` / `delegation.model`), which affects all subagents.
`hermes chat` in background lets you choose the model per call with `-m` and
`--provider`.

## Recommended stack

| Role | Model tier | Notes |
|---|---|---|
| **Master** | flash-tier (e.g. `deepseek-v4-flash`) | Validated: cheap models orchestrate cheap workers fine |
| **Slave** | flash-tier (same) | Low cost (~50K tokens/task) |

The whole stack is configurable via env vars (see SKILL.md → Worker Contract):
`WORKER_MODEL`, `WORKER_PROVIDER`, `WORKER_MAX_TURNS`.

## Slave command

```bash
hermes chat -m "$WORKER_MODEL" --provider "$WORKER_PROVIDER" \
  --quiet --max-turns 4 --cli \
  -q "$(cat /tmp/prompt.txt)"
```

Critical flags:
- `--quiet`: suppress banner/spinner (script mode)
- `--max-turns N`: 3-4 for chapters, 4-5 for large chunks
- `--cli`: avoid interactive TUI

## Patterns

### 1. One-shot
Chapters < 20 pages:

```python
terminal(
    f"hermes chat -m '{model}' --provider '{provider}' "
    "--quiet --max-turns 3 --cli "
    f'-q "$(cat {prompt_file})"',
    background=True
)
```

### 2. Parallel chunking
Chapters > 40 pages: split into ~19-page chunks, N workers in parallel
(batches of 3).

### 3. write_file
Always instruct the worker to save via `write_file`:

```
8. AT THE END, use write_file to SAVE the markdown to: `{out_path}`
```

### 4. Merge
After all chunks finish:

```bash
cat parte1.md parte2.md parte3.md > capitulo.md
```

## Monitoring

```python
# Launch
terminal("hermes chat ...", background=True)
# → session_id: proc_abc123

# Progress
process(action='poll', session_id='proc_abc123')

# Wait
process(action='wait', session_id='proc_abc123', timeout=120)
```

A 183K-word book (43 chapters) processes in ~15 min with batches of 3 workers,
1-3 min per worker. Monitor progress with
`ls chapters/*_PT.md | wc -l`.
