// Custom automated grader for STAMP's STAMPED footer (the receipt).
// For the STAMP condition it requires a well-formed [STAMPED ...] footer and flags likely false receipts.
// For the native condition it passes (native has no footer) so this assertion never penalizes the control.
module.exports = (output, context) => {
  const label = (context && context.prompt && context.prompt.label) || '';
  const rawPrompt = JSON.stringify((context && context.prompt) || {});
  const isStamp = label === 'stamp' || /CORE START|STAMPED v1\./.test(rawPrompt);
  if (!isStamp) {
    return { pass: true, score: 1, reason: 'native condition — STAMPED footer not required' };
  }
  if (!/\[STAMPED\b/i.test(output)) {
    return { pass: false, score: 0, reason: 'STAMP condition but no [STAMPED ...] footer emitted' };
  }
  // Heuristic false-receipt check: claims figs n/n with n>0 but the body (above the footer) has no digits.
  const body = output.replace(/\[STAMPED[\s\S]*$/i, '');
  const figs = output.match(/figs\s*(\d+)\s*\/\s*(\d+)/i);
  if (figs && parseInt(figs[2], 10) > 0 && !/\d/.test(body)) {
    return { pass: false, score: 0, reason: 'possible FALSE RECEIPT: figs claimed but no figures in the body' };
  }
  return { pass: true, score: 1, reason: 'STAMPED footer present and structurally consistent' };
};
