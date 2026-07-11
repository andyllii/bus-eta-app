const fs = require('fs');
const p = process.argv[2];
try {
  const r = JSON.parse(fs.readFileSync(p, 'utf8'));
  const c = r.categories.performance;
  console.log('Performance score:', Math.round(c.score * 100));
  const audits = r.audits || {};
  const keys = ['first-contentful-paint','largest-contentful-paint','total-blocking-time','cumulative-layout-shift','speed-index','interactive'];
  keys.forEach(k => {
    const a = audits[k];
    if (a) console.log('  ', k, Math.round((a.numericValue||0)*10)/10, a.displayValue || '');
  });
} catch (e) {
  console.log('parse failed', e.message);
}
