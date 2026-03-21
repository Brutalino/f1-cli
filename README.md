# f1-cli

Formula 1 live timing in your terminal.

```
 ● FORMULA 1 GRAN PREMIO D'ITALIA 2025  Race  12/53  28°C T:42°C
   P     DRV        GAP       INT       LAST      BEST
 ──────────────────────────────────────────────────────
   1  ●  VER                           1:18.523  1:18.123
   2  ●  NOR     +1.204    +1.204      1:18.731  1:18.410
   3  ●  LEC     +3.892    +2.688      1:19.002  1:18.876
  ...
 ──────────────────────────────────────────────────────
  ● PB ● Best ● Pit ● Out  │ s:sectors t:tyres c:RC q:quit
```

## Install

```bash
pip install .
```

Requires Python 3.10+.

## Usage

```bash
# live timing (requires F1TV subscription)
f1-cli
f1-cli live

# simulated race for testing
f1-cli demo

# view presets
f1-cli -t              # times only: GAP, INT, LAST, BEST
f1-cli -s              # simple: positions + GAP
f1-cli demo -t         # works with any mode
```

### Authentication

Live timing requires an F1TV Access, Pro, or Premium subscription. On first run a browser window opens for login. The token is saved locally by FastF1.

```bash
f1-cli login           # authenticate with F1TV
f1-cli logout          # clear saved token
f1-cli status          # check auth status
```

### Keybindings

While running, press:

| Key | Action |
|-----|--------|
| `s` | toggle sector times |
| `t` | toggle tyres + pit stops |
| `c` | toggle race control messages |
| `q` | quit |

Active toggles are shown in bold in the footer. Start with `-t` or `-s` for a minimal view and add columns as needed.

## How it works

Connects to the F1 live timing SignalR stream (the same feed that powers the official F1 app) via a custom client built on top of [FastF1](https://github.com/theOehrly/Fast-F1). Data is processed in real-time and rendered directly to the terminal using [Rich](https://github.com/Textualize/rich).

The display adapts to your terminal size — columns expand horizontally, and rows are spaced vertically to fill the screen. Colors follow your terminal theme.

### Architecture

```
f1cli/
├── __main__.py      # CLI entry point & argument parsing
├── app.py           # Rich Live display, Layout, keybindings
├── auth.py          # F1TV authentication (browser flow via FastF1)
├── data_store.py    # Thread-safe state from live timing messages
├── demo_data.py     # Simulated race data for testing
└── live_client.py   # Custom SignalR client for real-time processing
```

## Dependencies

- [FastF1](https://github.com/theOehrly/Fast-F1) — F1 data access + SignalR live timing
- [Rich](https://github.com/Textualize/rich) — terminal rendering
- [signalrcore](https://pypi.org/project/signalrcore/) — SignalR protocol

## License

MIT