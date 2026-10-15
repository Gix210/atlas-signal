"""Checks that the command's in-page script and backtest.py compute the same levels.

Pulls the JavaScript out of .claude/commands/atlas.md, runs it in Node against a
stand-in for TradingView's chart API, and compares every value with what
backtest.py computes from the same bars. It also checks that the script's
constants are the variant backtest.py picked, then repeats the comparison with
the confluence filter switched on so that branch is covered too.

Usage:
    python3 check_parity.py spy_15m.json

Needs Node.js. Only the Python standard library is used.
"""

import json
import re
import subprocess
import sys
from pathlib import Path

import backtest as bt

COMMAND = Path(__file__).resolve().parent.parent / ".claude" / "commands" / "atlas.md"
WINDOW = 300        # bars the stand-in chart has loaded, like a freshly opened chart
TOLERANCE = 0.005   # to the cent
FIELDS = ("price", "vwap", "ema9", "ema20", "atr",
          "recent_high", "recent_low", "prior_high", "prior_low")

HARNESS = r"""
const fs = require('fs');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const evaluate = new Function('window', 'return (' + input.script + ');');
const out = input.ends.map(function (end) {
  const loaded = input.bars.slice(Math.max(0, end - input.window + 1), end + 1);
  const series = {
    firstIndex: function () { return 0; },
    lastIndex: function () { return loaded.length - 1; },
    valueAt: function (i) { return loaded[i]; },
  };
  const mainSeries = { bars: function () { return series; } };
  const chart = { _chartWidget: { model: function () { return { mainSeries: function () { return mainSeries; } }; } } };
  return evaluate({ TradingViewApi: { activeChart: function () { return chart; } } });
});
process.stdout.write(JSON.stringify(out));
"""


def extract_script(markdown):
    m = re.search(r"```javascript\n(.*?)```", markdown, re.S)
    if not m:
        sys.exit(f"No javascript block found in {COMMAND}")
    return m.group(1).strip().rstrip(";")


def constant(script, name):
    m = re.search(rf"\bvar {name} = ([^;]+);", script)
    if not m:
        sys.exit(f"Constant {name} not found in the script")
    return m.group(1).strip()


def set_constant(script, name, value):
    return re.sub(rf"(\bvar {name} = )[^;]+;", rf"\g<1>{value};", script, count=1)


def compare(bars, script):
    """Run the script on every bar and diff it against backtest.py."""
    params = {
        "buffer_pct": float(constant(script, "BUFFER_PCT")),
        "stop_atr": float(constant(script, "STOP_ATR")),
        "rr": float(constant(script, "RR")),
        "confluence": constant(script, "CONFLUENCE") == "true",
    }
    ends = list(range(WINDOW - 1, len(bars)))
    payload = json.dumps({"script": script, "bars": bars, "ends": ends, "window": WINDOW})
    proc = subprocess.run(["node", "-e", HARNESS], input=payload, capture_output=True, text=True)
    if proc.returncode != 0:
        sys.exit("Node failed:\n" + proc.stderr)
    results = json.loads(proc.stdout)

    starts = bt.session_starts(bars)
    max_diff, problems, rejected = 0.0, [], 0
    for i, js in zip(ends, results):
        ind = bt.indicators(bars, i, starts[i])
        lv = bt.levels_v2(ind, params["buffer_pct"], params["stop_atr"], params["rr"])
        pairs = [(f, ind[f], js[f]) for f in FIELDS]
        for side in ("long", "short"):
            code = bt.reject(side, lv[side], ind, params["confluence"])
            rejected += code is not None
            if (code is None) != js[side]["valid"] or (code and code != js[side]["code"]):
                problems.append(f"bar {i} {side}: backtest says {code or 'valid'}, "
                                f"script says {js[side]['code'] or 'valid'}")
            pairs += [(f"{side}.{f}", lv[side][f], js[side][f]) for f in ("entry", "tp1", "tp2", "sl")]
            if code is None:
                pairs.append((f"{side}.rr", bt.reward_risk(lv[side]), js[side]["rr"]))
        for name, py, j in pairs:
            diff = abs(py - j)
            max_diff = max(max_diff, diff)
            if diff > TOLERANCE:
                problems.append(f"bar {i} {name}: backtest {py:.4f}, script {j:.4f}")
    return params, len(ends), rejected, max_diff, problems


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    with open(sys.argv[1]) as f:
        bars = json.load(f)
    bars.sort(key=lambda b: b[0])
    script = extract_script(COMMAND.read_text())
    failed = False

    params, n, rejected, max_diff, problems = compare(bars, script)
    picked = {k: params[k] for k in ("stop_atr", "rr", "confluence")}
    if picked != bt.SELECTED:
        failed = True
        print(f"FAIL: the script uses {bt.label(picked)}, "
              f"but backtest.py picked {bt.label(bt.SELECTED)}")
    else:
        print(f"OK: the script uses the picked variant ({bt.label(picked)})")

    runs = [("as shipped", params, n, rejected, max_diff, problems)]
    flipped = set_constant(script, "CONFLUENCE", "true")
    runs.append(("with confluence on", *compare(bars, flipped)))
    for name, _, n, rejected, max_diff, problems in runs:
        if problems:
            failed = True
            print(f"FAIL ({name}): {len(problems)} mismatches out of {n:,} bars")
            for p in problems[:10]:
                print("  " + p)
        else:
            print(f"OK ({name}): {n:,} bars, every value matches to the cent "
                  f"(largest difference {max_diff:.1e}, {rejected:,} rejected setups agree)")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
