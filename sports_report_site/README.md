## Local NBA roster overrides

Player and team pages do not call balldontlie while rendering. Current roster
data is read from `data/nba_roster_overrides.json` first, then from the local
Sports Report video archive.

Create `data/nba_roster_overrides.json` using
`data/nba_roster_overrides.example.json` as the format:

```json
{
  "players": {
    "lebron-james": {
      "team": "Los Angeles Lakers",
      "source": "manual",
      "updated_at": "2026-09-18T00:00:00Z"
    }
  }
}
```

To rebuild the file without external APIs, use the YouTube-derived NBA tab data:

```bash
.venv/bin/flask --app app rebuild-roster-overrides-from-youtube
```

That command writes each player's latest team from the indexed NBA highlight
archive. It preserves entries marked `"source": "manual"` unless you pass
`--force`.

Preview smaller local rebuilds:

```bash
.venv/bin/flask --app app rebuild-roster-overrides-from-youtube --limit 25
.venv/bin/flask --app app rebuild-roster-overrides-from-youtube --team miami-heat
```

The balldontlie updater remains available for one-off testing, but it is not
scheduled:

```bash
.venv/bin/flask --app app refresh-roster-overrides --dry-run --limit 10 --delay 20 --force
```

To rebuild from public sources, try cached/Wikidata team data first, use the
Sports Report archive next, and supplement with balldontlie only when needed:

```bash
.venv/bin/flask --app app rebuild-roster-overrides-from-public-sources --limit 25 --dry-run --force
.venv/bin/flask --app app rebuild-roster-overrides-from-public-sources --force
```

Use `--skip-balldontlie` to avoid balldontlie entirely, or `--skip-wikidata` to
use cached public data plus the Sports Report archive only. Entries marked
`"source": "manual"` are preserved unless you pass `--force-manual`.
