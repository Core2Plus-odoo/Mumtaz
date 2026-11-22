'use strict';

const Anthropic = require('@anthropic-ai/sdk');
const farid     = require('./farid');
const ayaz      = require('./ayaz');

const MODEL = 'claude-sonnet-4-5';

const ROUTER_PROMPT = `You are Zaki, the executive intelligence platform for AJ Arabia Enterprise.
You route questions to two specialised agents:

FARID (CFO) handles: cash, bank balances, receivables, payables, Five Fine Fragrance (FFF) position,
P&L, gross margin, OPEX, VAT, salaries, FX rates, journal entries, outstanding invoices, aging.

AYAZ (Commercial Director) handles: sales performance, customers, SKUs/products, regions (MENA/Europe/CIS/Americas/Asia),
orders, rankings, growth vs prior period, pipeline, dormant accounts, tester vs FP units.

BOTH agents are needed for: questions combining financial and commercial data
(e.g. "which customers drive the most revenue AND are overdue?")

Respond with EXACTLY one word: FARID, AYAZ, or BOTH.
If the question is completely ambiguous, respond: ASK`;

const ZAKI_INTRO_PROMPT = `You are Zaki, executive intelligence platform for AJ Arabia Enterprise.
You coordinate Farid (CFO) and Ayaz (Commercial Director).
You are serving the CEO and Directors with live data from Odoo ERP.

When a question needs clarification, ask one concise question.
Keep your routing notes brief — the agents' answers are what matters.`;

/**
 * Quick non-streaming routing call.
 * Returns: 'FARID' | 'AYAZ' | 'BOTH' | 'ASK'
 */
async function routeQuestion(question, history = []) {
  const client  = new Anthropic({ apiKey: process.env.ANTHROPIC_API_KEY });

  // Include recent history context for routing accuracy
  const recentHistory = history.slice(-6);

  const response = await client.messages.create({
    model:      MODEL,
    max_tokens: 10,
    system:     ROUTER_PROMPT,
    messages:   [
      ...recentHistory,
      { role: 'user', content: question },
    ],
  });

  const decision = (response.content[0]?.text || 'BOTH').trim().toUpperCase();
  if (['FARID', 'AYAZ', 'BOTH', 'ASK'].includes(decision)) return decision;
  return 'BOTH'; // safe fallback
}

/**
 * Stream a single agent's response via SSE.
 * writeSSE(object) sends a Server-Sent Event to the client.
 */
async function streamAgent(agentName, systemPrompt, tools, executeTool, messages, conn, writeSSE) {
  const client = new Anthropic({ apiKey: process.env.ANTHROPIC_API_KEY });

  writeSSE({ type: 'agent_start', agent: agentName });

  let currentMessages = [...messages];
  let iterations      = 0;
  const MAX_ITER      = 8; // prevent infinite tool loops

  while (iterations < MAX_ITER) {
    iterations++;

    const stream = client.messages.stream({
      model:      MODEL,
      max_tokens: 8192,
      system:     systemPrompt,
      tools,
      messages:   currentMessages,
    });

    const assistantBlocks = [];
    let   currentBlock    = null;
    let   hasText         = false;

    for await (const event of stream) {
      switch (event.type) {

        case 'content_block_start':
          currentBlock = { ...event.content_block };
          if (currentBlock.type === 'tool_use') currentBlock._json = '';
          break;

        case 'content_block_delta':
          if (!currentBlock) break;
          if (event.delta.type === 'text_delta') {
            const chunk = event.delta.text;
            currentBlock.text = (currentBlock.text || '') + chunk;
            hasText = true;
            writeSSE({ type: 'text', content: chunk, agent: agentName });
          } else if (event.delta.type === 'input_json_delta') {
            currentBlock._json += event.delta.partial_json;
          }
          break;

        case 'content_block_stop':
          if (currentBlock) {
            if (currentBlock.type === 'tool_use') {
              try {
                currentBlock.input = JSON.parse(currentBlock._json || '{}');
              } catch {
                currentBlock.input = {};
              }
              delete currentBlock._json;
            }
            assistantBlocks.push({ ...currentBlock });
          }
          currentBlock = null;
          break;
      }
    }

    // Check stop reason from final message
    const finalMsg  = await stream.finalMessage();
    const stopReason = finalMsg.stop_reason;

    if (stopReason === 'tool_use') {
      const toolUseBlocks = assistantBlocks.filter(b => b.type === 'tool_use');
      const toolResults   = [];

      for (const block of toolUseBlocks) {
        writeSSE({ type: 'tool_call', name: block.name, agent: agentName });
        try {
          const result = await executeTool(block.name, block.input || {}, conn);
          toolResults.push({
            type:        'tool_result',
            tool_use_id: block.id,
            content:     JSON.stringify(result),
          });
          writeSSE({ type: 'tool_result', name: block.name, success: true, agent: agentName });
        } catch (err) {
          const errMsg = err.code === 'SESSION_EXPIRED' ? err.message : `Odoo error: ${err.message}`;
          toolResults.push({
            type:        'tool_result',
            tool_use_id: block.id,
            content:     `Error fetching data: ${errMsg}`,
            is_error:    true,
          });
          writeSSE({ type: 'tool_result', name: block.name, success: false, error: errMsg, agent: agentName });

          if (err.code === 'SESSION_EXPIRED') {
            writeSSE({ type: 'error', code: 'SESSION_EXPIRED', message: err.message });
            writeSSE({ type: 'agent_end', agent: agentName });
            return;
          }
        }
      }

      currentMessages = [
        ...currentMessages,
        { role: 'assistant', content: assistantBlocks },
        { role: 'user',      content: toolResults      },
      ];
      continue;
    }

    // end_turn — we're done
    break;
  }

  writeSSE({ type: 'agent_end', agent: agentName });
}

/**
 * Main entry point — routes and streams the full response.
 */
async function chat({ message, history = [], conn, writeSSE }) {
  // 1. Route
  const routing = await routeQuestion(message, history);

  writeSSE({ type: 'routing', decision: routing });

  // 2. If needs clarification
  if (routing === 'ASK') {
    const client   = new Anthropic({ apiKey: process.env.ANTHROPIC_API_KEY });
    const stream   = client.messages.stream({
      model:     MODEL,
      max_tokens: 200,
      system:    ZAKI_INTRO_PROMPT,
      messages:  [...history, { role: 'user', content: message }],
    });
    writeSSE({ type: 'agent_start', agent: 'ZAKI' });
    stream.on('text', text => writeSSE({ type: 'text', content: text, agent: 'ZAKI' }));
    await stream.finalMessage();
    writeSSE({ type: 'agent_end', agent: 'ZAKI' });
    writeSSE({ type: 'done' });
    return;
  }

  // 3. Build message list for agents (combine history + new user message)
  const agentMessages = [
    ...history,
    { role: 'user', content: message },
  ];

  // 4. Stream from appropriate agent(s)
  if (routing === 'FARID' || routing === 'BOTH') {
    await streamAgent(
      'FARID',
      farid.SYSTEM_PROMPT,
      farid.TOOLS,
      farid.executeTool,
      agentMessages,
      conn,
      writeSSE,
    );
  }

  if (routing === 'AYAZ' || routing === 'BOTH') {
    await streamAgent(
      'AYAZ',
      ayaz.SYSTEM_PROMPT,
      ayaz.TOOLS,
      ayaz.executeTool,
      agentMessages,
      conn,
      writeSSE,
    );
  }

  writeSSE({ type: 'done' });
}

module.exports = { chat, routeQuestion };
