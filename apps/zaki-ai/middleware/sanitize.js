'use strict';

// Patterns that indicate prompt injection attempts
const INJECTION_PATTERNS = [
  /ignore\s+(all\s+)?(previous|prior|above|earlier)\s+(instructions|prompts|context)/i,
  /disregard\s+(your|the)\s+(previous|prior|system|above)\s+(instructions|prompts)/i,
  /you\s+are\s+now\s+(a|an)\s+/i,
  /act\s+as\s+(a|an)\s+/i,
  /pretend\s+(you\s+are|to\s+be)\s+/i,
  /new\s+persona\s*:/i,
  /system\s*prompt\s*:/i,
  /jailbreak/i,
  /<\|im_start\|>/i,
  /\[INST\]/i,
  /\[\[HUMAN\]\]/i,
  /###\s*(instruction|system)/i,
];

const MAX_MESSAGE_LENGTH = 8192;

/**
 * Sanitize a user message for prompt injection attempts.
 * Throws an error with code INJECTION_ATTEMPT if suspicious content is detected.
 * Returns the trimmed message on success.
 */
function sanitizeMessage(msg) {
  if (typeof msg !== 'string') {
    throw Object.assign(new Error('Message must be a string'), { code: 'INVALID_INPUT' });
  }
  const trimmed = msg.trim().slice(0, MAX_MESSAGE_LENGTH);
  for (const pattern of INJECTION_PATTERNS) {
    if (pattern.test(trimmed)) {
      // Log for security monitoring (don't include the actual content in prod logs)
      console.warn(`[security] prompt injection attempt detected from pattern: ${pattern}`);
      throw Object.assign(
        new Error('Message contains disallowed content'),
        { code: 'INJECTION_ATTEMPT', status: 400 }
      );
    }
  }
  return trimmed;
}

/**
 * Validate that assistant output doesn't leak system internals.
 * Returns false if the output looks suspicious.
 */
function validateOutput(text) {
  if (typeof text !== 'string') return true;
  const LEAK_PATTERNS = [
    /my\s+system\s+prompt\s+is/i,
    /i\s+was\s+instructed\s+to/i,
    /anthropic\s+told\s+me/i,
  ];
  return !LEAK_PATTERNS.some(p => p.test(text));
}

/**
 * Express middleware — validates req.body.message before it reaches the AI.
 */
function sanitizeMiddleware(req, res, next) {
  const msg = req.body && req.body.message;
  if (!msg) return next();
  try {
    req.body.message = sanitizeMessage(msg);
    next();
  } catch (err) {
    if (err.code === 'INJECTION_ATTEMPT') {
      return res.status(400).json({ error: 'Invalid message content', code: err.code });
    }
    next(err);
  }
}

module.exports = { sanitizeMessage, validateOutput, sanitizeMiddleware };
