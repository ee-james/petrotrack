# petrotrack

A small dashboard for tracking oil, gas, coal and related commodity data. It
polls [OilPriceAPI](https://oilpriceapi.com), keeps the history in SQLite, and
shows prices, 24h/30d ranges, sparklines and change alerts. It also tracks
"count" series - rig counts, well permits, DUC wells, frac spreads - which move
slowly, so those get polled on an adaptive schedule instead of every cycle.

There's a built-in browser pane (a server-side fetch-and-restyle proxy) so you
can pull up a Wikipedia page or a news article next to the numbers without
leaving the app.

Runs as a web app or wrapped in Electron as a desktop client.

## Layout

```
app/        fastapi backend - polling loop, sqlite, metrics
proxy/      html fetch/restyle service for the browser pane
frontend/   svelte dashboard (vite build, served by nginx)
electron/   desktop wrapper
config/     config.toml - which commodities, refresh timing, theme colors
```

## Running it

You need an OilPriceAPI token.

```
cp .env.example .env      # put your token in it
docker compose up --build
```

- dashboard: http://localhost:8010
- backend api: http://localhost:8000

### Desktop

```
cd electron
npm install
npm run build-frontend
npm start
```

`electron/config.json` points at the backend (defaults to localhost:8000).

## Config

`config/config.toml` is hot-reloaded - the backend watches its mtime. Set the
commodity list under `[commodities]`, refresh intervals and alert threshold
under `[behavior]`, and the dashboard colors under `[theme]`. The config panel
in the UI writes back to this file.

## Notes

- `available` is the full catalog you can pick from; `enabled` is what's
  actually being polled. Not every code is on every API plan - run the
  plan-check from the config panel to see what your key can actually pull.
- Backfill grabs 30 days of history the first time a commodity is added so the
  sparkline isn't empty.
- Alert beep uses the Web Audio API, no sound files.

## License

MIT - see [LICENSE](LICENSE).
