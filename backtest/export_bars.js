// Dumps every bar loaded on the active TradingView Desktop chart to a JSON file.
// TradingView must be running with remote debugging on port 9222 (the
// TradingView MCP's tv_launch does this). Scroll the chart back first, or call
// mainSeries().requestMoreData(n), to load more history.
//
// Usage: node export_bars.js out.json
// Needs chrome-remote-interface (npm i chrome-remote-interface).

const CDP = require('chrome-remote-interface');
const fs = require('fs');

(async () => {
  const targets = await CDP.List({ port: 9222 });
  const target = targets.find(t => t.type === 'page' && /tradingview\.com\/chart/.test(t.url));
  if (!target) throw new Error('No TradingView chart found on port 9222');
  const client = await CDP({ port: 9222, target });
  const { result } = await client.Runtime.evaluate({
    returnByValue: true,
    expression: `(function () {
      var b = window.TradingViewApi.activeChart()._chartWidget.model().mainSeries().bars();
      var out = [];
      for (var i = b.firstIndex(); i <= b.lastIndex(); i++) {
        var v = b.valueAt(i);
        if (v) out.push([v[0], v[1], v[2], v[3], v[4], v[5]]);
      }
      return JSON.stringify(out);
    })()`,
  });
  fs.writeFileSync(process.argv[2], result.value);
  await client.close();
  console.log(`${JSON.parse(result.value).length} bars written to ${process.argv[2]}`);
})();
