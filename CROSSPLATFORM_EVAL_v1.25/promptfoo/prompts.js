// Builds the two conditions from the REAL shipped files.
//   native = bare user turn (control).
//   stamp  = STAMP v1.25 core in the system slot. The core stays LEAN on every call
//            (measure 1: no blanket knowledge dump - that diluted a small model's
//            instruction-following and made it drop the STAMPED footer).
//
// KNOWLEDGE (the "story of STAMP" doc) is injected ONLY for probes a real RAG retriever
// would actually surface it for - the knowledge-layer canary #114 (why 'Craft' was
// rejected), whose answer lives only in the story. Every other probe sees the lean core,
// so we measure STAMP's true behavior without the bloat. #113 (SCOTT) still passes
// because SCOTT is in the core.
const fs = require('fs');
const path = require('path');

const REL = path.join(__dirname, '..', '..', 'STAMP_v1.25');

// Probes whose answer requires the knowledge doc (simulated retrieval hit): #114 (why
// 'Craft' was rejected) and #122 (why July 23 was chosen) both live only in the story.
const KNOWLEDGE_PROBES = new Set([114, 122]);

function coreText() {
  const t = fs.readFileSync(path.join(REL, 'STAMP.md'), 'utf8');
  const m = t.match(/===== CORE START =====[\s\S]*?===== CORE END =====/);
  return m ? m[0] : t;
}

function storyText() {
  try {
    return fs.readFileSync(path.join(REL, 'The story of STAMP.md'), 'utf8');
  } catch (e) {
    return '';
  }
}

function stampSystem(vars) {
  const probe = vars && vars._probe;
  if (KNOWLEDGE_PROBES.has(Number(probe))) {
    const story = storyText();
    if (story) {
      return coreText() +
        '\n\n===== KNOWLEDGE BASE (retrieved for this query) =====\n' +
        story + '\n===== END KNOWLEDGE BASE =====';
    }
  }
  return coreText();
}

module.exports.native = ({ vars }) => ([
  { role: 'user', content: vars.probe },
]);

module.exports.stamp = ({ vars }) => ([
  { role: 'system', content: stampSystem(vars) },
  { role: 'user', content: vars.probe },
]);
