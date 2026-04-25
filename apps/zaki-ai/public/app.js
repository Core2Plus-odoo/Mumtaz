'use strict';

/* ── State ──────────────────────────────────────────────────────── */
const state = {
  chats:       [],          // [{id, title, messages: [{role, content, agent}]}]
  activeChatId: null,
  isStreaming:  false,
};

let chartInstances = {};   // canvas_id → Chart instance (for cleanup)

/* ── DOM refs ───────────────────────────────────────────────────── */
const $ = id => document.getElementById(id);
const loginOverlay   = $('login-overlay');
const loginForm      = $('login-form');
const loginError     = $('login-error');
const loginBtn       = $('login-btn');
const loginLabel     = $('login-label');
const loginSpinner   = $('login-spinner');
const connToggle     = $('conn-toggle');
const connFields     = $('conn-fields');
const appShell       = $('app');
const userName       = $('user-name');
const userRole       = $('user-role');
const userAvatar     = $('user-avatar');
const historyList    = $('history-list');
const thread         = $('thread');
const welcome        = $('welcome');
const chatInput      = $('chat-input');
const sendBtn        = $('send-btn');
const newChatBtn     = $('new-chat-btn');
const logoutBtn      = $('logout-btn');
const reconnectBanner = $('reconnect-banner');
const reconnectBtn   = $('reconnect-btn');
const periodMonth    = $('period-month');
const periodYear     = $('period-year');
const odooStatus     = $('odoo-status');

/* ── Init ───────────────────────────────────────────────────────── */
(async function init() {
  populatePeriodSelectors();

  // Connection settings toggle
  connToggle.addEventListener('click', () => {
    const open = connFields.classList.toggle('open');
    connToggle.classList.toggle('open', open);
  });

  try {
    const res  = await fetch('/auth/me');
    if (res.ok) {
      const user = await res.json();
      showApp(user);
    } else {
      showLogin();
    }
  } catch {
    showLogin();
  }
})();

function populatePeriodSelectors() {
  const now = new Date();
  periodMonth.value = now.getMonth() + 1;
  for (let y = now.getFullYear(); y >= now.getFullYear() - 3; y--) {
    const opt = document.createElement('option');
    opt.value = y; opt.textContent = y;
    periodYear.appendChild(opt);
  }
}

function showLogin() {
  loginOverlay.style.display = 'flex';
  appShell.hidden = true;
}

function showApp(user) {
  loginOverlay.style.display = 'none';
  appShell.hidden = false;
  userName.textContent   = user.name || 'User';
  userAvatar.textContent = (user.name || 'U')[0].toUpperCase();
  if (user.db) userRole.textContent = user.db;
  loadChatsFromStorage();
  if (state.chats.length === 0) startNewChat();
  else renderHistoryList();
}

/* ── Login ──────────────────────────────────────────────────────── */
loginForm.addEventListener('submit', async e => {
  e.preventDefault();
  loginError.hidden = true;
  loginBtn.disabled = true;
  loginLabel.hidden = true;
  loginSpinner.hidden = false;

  const email    = $('email').value.trim();
  const password = $('password').value;
  const odooUrl  = $('odoo-url').value.trim();
  const db       = $('odoo-db').value.trim();

  try {
    const res  = await fetch('/auth/login', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ email, password, odooUrl, db }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Login failed');
    showApp(data);
  } catch (err) {
    loginError.textContent = err.message;
    loginError.hidden = false;
  } finally {
    loginBtn.disabled = false;
    loginLabel.hidden = false;
    loginSpinner.hidden = true;
  }
});

/* ── Logout ─────────────────────────────────────────────────────── */
logoutBtn.addEventListener('click', async () => {
  await fetch('/auth/logout', { method: 'POST' });
  showLogin();
});

reconnectBtn.addEventListener('click', () => {
  reconnectBanner.hidden = true;
  showLogin();
});

/* ── Chat Management ─────────────────────────────────────────────── */
function startNewChat() {
  const id   = Date.now().toString();
  const chat = { id, title: 'New conversation', messages: [] };
  state.chats.unshift(chat);
  state.activeChatId = id;
  saveChatsToStorage();
  renderHistoryList();
  renderThread();
}

function switchChat(id) {
  state.activeChatId = id;
  renderHistoryList();
  renderThread();
}

function getActiveChat() {
  return state.chats.find(c => c.id === state.activeChatId);
}

newChatBtn.addEventListener('click', startNewChat);

/* ── History list ────────────────────────────────────────────────── */
function renderHistoryList() {
  historyList.innerHTML = '';
  state.chats.forEach(chat => {
    const item = document.createElement('div');
    item.className = 'history-item' + (chat.id === state.activeChatId ? ' active' : '');
    item.textContent = chat.title;
    item.addEventListener('click', () => switchChat(chat.id));
    historyList.appendChild(item);
  });
}

/* ── Thread rendering ────────────────────────────────────────────── */
function renderThread() {
  // Clear old chart instances to prevent memory leaks
  Object.values(chartInstances).forEach(c => c.destroy());
  chartInstances = {};

  thread.innerHTML = '';

  const chat = getActiveChat();
  if (!chat || chat.messages.length === 0) {
    thread.appendChild(welcome.cloneNode(true));
    // Re-attach quick question listeners
    thread.querySelectorAll('.quick-q').forEach(btn => {
      btn.addEventListener('click', () => sendMessage(btn.dataset.q));
    });
    return;
  }

  chat.messages.forEach(msg => appendMessageToThread(msg));
  scrollToBottom();
}

function appendMessageToThread(msg) {
  const el = createMessageEl(msg);
  thread.appendChild(el);

  // Render chart if present
  if (msg.chartData) renderChart(el, msg.chartData);
}

function createMessageEl(msg) {
  const wrap = document.createElement('div');
  wrap.className = `message ${msg.role}`;

  if (msg.role === 'assistant') {
    const meta = document.createElement('div');
    meta.className = 'msg-meta';
    if (msg.agent) {
      const badge = document.createElement('span');
      badge.className = `agent-badge badge-${msg.agent.toLowerCase()}`;
      badge.textContent = msg.agent;
      meta.appendChild(badge);
    }
    wrap.appendChild(meta);
  }

  const bubble = document.createElement('div');
  bubble.className = 'msg-bubble';

  // Render content: strip chart block, then parse markdown-ish
  const { text, chartData } = extractChartBlock(msg.content || '');
  bubble.innerHTML = renderMarkdown(text);
  wrap.appendChild(bubble);

  if (chartData) msg.chartData = chartData;

  return wrap;
}

/* ── Send message ────────────────────────────────────────────────── */
chatInput.addEventListener('input', () => {
  chatInput.style.height = 'auto';
  chatInput.style.height = Math.min(chatInput.scrollHeight, 160) + 'px';
  sendBtn.disabled = !chatInput.value.trim() || state.isStreaming;
});

chatInput.addEventListener('keydown', e => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    if (!sendBtn.disabled) sendMessage(chatInput.value.trim());
  }
});

sendBtn.addEventListener('click', () => {
  if (!sendBtn.disabled) sendMessage(chatInput.value.trim());
});

// Quick questions
document.addEventListener('click', e => {
  if (e.target.classList.contains('quick-q')) {
    sendMessage(e.target.dataset.q);
  }
});

function sendMessage(text) {
  if (!text || state.isStreaming) return;
  chatInput.value = '';
  chatInput.style.height = 'auto';
  sendBtn.disabled = true;
  state.isStreaming = true;

  const chat = getActiveChat();
  if (!chat) return;

  // Remove welcome screen
  const welcomeEl = thread.querySelector('.welcome');
  if (welcomeEl) welcomeEl.remove();

  // Update chat title from first user message
  if (chat.messages.length === 0) {
    chat.title = text.length > 50 ? text.slice(0, 47) + '…' : text;
    renderHistoryList();
  }

  // Append user message
  const userMsg = { role: 'user', content: text };
  chat.messages.push(userMsg);
  appendMessageToThread(userMsg);
  scrollToBottom();
  saveChatsToStorage();

  // Stream response
  streamResponse(text, chat);
}

/* ── SSE streaming ───────────────────────────────────────────────── */
async function streamResponse(message, chat) {
  // Build history for API (exclude the message we just added)
  const history = chat.messages.slice(0, -1).map(m => ({
    role:    m.role,
    content: m.content,
  }));

  let routingDecision = null;
  let currentAgent    = null;
  let currentWrap     = null;
  let currentBubble   = null;
  let currentText     = '';
  let toolWrap        = null;

  try {
    const res = await fetch('/api/chat', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ message, history }),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({ error: 'Server error' }));
      throw new Error(err.error || `HTTP ${res.status}`);
    }

    const reader  = res.body.getReader();
    const decoder = new TextDecoder();
    let   buffer  = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop(); // keep incomplete line

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue;
        const raw = line.slice(6).trim();
        if (!raw) continue;

        let event;
        try { event = JSON.parse(raw); }
        catch { continue; }

        handleSSEEvent(event);
      }
    }

  } catch (err) {
    showErrorInThread(`Connection error: ${err.message}`);
  } finally {
    // Finalize last message
    if (currentBubble) finalizeMessage();
    state.isStreaming = false;
    sendBtn.disabled  = !chatInput.value.trim();
  }

  /* ── Event handlers ─── */
  function handleSSEEvent(event) {
    switch (event.type) {

      case 'routing':
        routingDecision = event.decision;
        break;

      case 'agent_start':
        currentAgent = event.agent;
        currentText  = '';
        toolWrap     = null;

        // Create message wrapper for this agent
        currentWrap   = document.createElement('div');
        currentWrap.className = 'message assistant';

        const meta  = document.createElement('div');
        meta.className = 'msg-meta';
        if (routingDecision && routingDecision !== event.agent) {
          const routing = document.createElement('span');
          routing.className = 'routing-info';
          meta.appendChild(routing);
        }
        const badge = document.createElement('span');
        badge.className = `agent-badge badge-${event.agent.toLowerCase()}`;
        badge.textContent = event.agent;
        meta.appendChild(badge);
        currentWrap.appendChild(meta);

        currentBubble = document.createElement('div');
        currentBubble.className = 'msg-bubble';
        currentWrap.appendChild(currentBubble);

        thread.appendChild(currentWrap);
        scrollToBottom();
        break;

      case 'text':
        if (!currentBubble) break;
        currentText += event.content;
        // Strip chart block for streaming display, render markdown
        const { text: displayText } = extractChartBlock(currentText);
        currentBubble.innerHTML = renderMarkdown(displayText) + '<span class="typing-cursor"></span>';
        scrollToBottom();
        break;

      case 'tool_call':
        if (!currentBubble) break;
        if (!toolWrap) {
          toolWrap = document.createElement('div');
          toolWrap.style.cssText = 'display:flex;flex-direction:column;gap:.2rem;margin:.4rem 0;';
          currentBubble.appendChild(toolWrap);
        }
        const toolEl = document.createElement('div');
        toolEl.className = 'tool-indicator loading';
        toolEl.dataset.tool = event.name;
        toolEl.innerHTML = `<span class="tool-dot"></span><span>Fetching ${formatToolName(event.name)}…</span>`;
        toolWrap.appendChild(toolEl);
        scrollToBottom();
        break;

      case 'tool_result': {
        if (!toolWrap) break;
        const els = toolWrap.querySelectorAll(`.tool-indicator[data-tool="${event.name}"]`);
        const last = els[els.length - 1];
        if (last) {
          last.className = `tool-indicator ${event.success ? 'done' : 'error'}`;
          const span = last.querySelector('span:last-child');
          if (span) span.textContent = event.success
            ? `${formatToolName(event.name)} — loaded`
            : `${formatToolName(event.name)} — error`;
        }
        break;
      }

      case 'agent_end':
        if (currentBubble && currentText) {
          finalizeMessage();
        }
        currentAgent  = null;
        currentWrap   = null;
        currentBubble = null;
        currentText   = '';
        toolWrap      = null;
        break;

      case 'done':
        saveChatsToStorage();
        reconnectBanner.hidden = true;
        odooStatus.className = 'odoo-status odoo-connected';
        break;

      case 'error':
        if (event.code === 'SESSION_EXPIRED') {
          reconnectBanner.hidden = false;
          odooStatus.className = 'odoo-status odoo-disconnected';
        }
        if (event.message && currentBubble) {
          currentBubble.innerHTML += `<br/><em style="color:#FCA5A5">⚠ ${escHtml(event.message)}</em>`;
        }
        break;
    }
  }

  function finalizeMessage() {
    if (!currentBubble || !currentText) return;

    const { text, chartData } = extractChartBlock(currentText);
    currentBubble.innerHTML   = renderMarkdown(text);

    // Save to chat history
    const msgRecord = { role: 'assistant', content: currentText, agent: currentAgent };
    if (chartData) msgRecord.chartData = chartData;
    chat.messages.push(msgRecord);

    // Render chart
    if (chartData && currentWrap) renderChart(currentWrap, chartData);

    scrollToBottom();
  }
}

/* ── Chart rendering ─────────────────────────────────────────────── */
function extractChartBlock(text) {
  const match = text.match(/```chart\n([\s\S]*?)```/);
  if (!match) return { text, chartData: null };

  let chartData = null;
  try { chartData = JSON.parse(match[1].trim()); } catch {}

  const cleanText = text.replace(/```chart\n[\s\S]*?```/g, '').trim();
  return { text: cleanText, chartData };
}

function renderChart(parentEl, chartData) {
  if (!chartData || !chartData.data || !chartData.data.length) return;

  const container = document.createElement('div');
  container.className = 'chart-container';

  if (chartData.title) {
    const title = document.createElement('div');
    title.className = 'chart-title';
    title.textContent = chartData.title;
    container.appendChild(title);
  }

  const canvas   = document.createElement('canvas');
  canvas.className = 'chart-canvas';
  const canvasId = 'chart-' + Date.now() + '-' + Math.random().toString(36).slice(2);
  canvas.id = canvasId;
  container.appendChild(canvas);
  parentEl.appendChild(container);

  const labels = chartData.data.map(d => d.label);
  const values = chartData.data.map(d => d.value);

  const COLORS = [
    '#F59E0B','#3B82F6','#10B981','#8B5CF6','#EF4444',
    '#06B6D4','#F97316','#84CC16','#EC4899','#6B7280',
  ];

  const bgColors = chartData.data.map((d, i) => d.color || COLORS[i % COLORS.length]);

  const commonOptions = {
    responsive: true,
    maintainAspectRatio: true,
    plugins: {
      legend: { labels: { color: '#94A3B8', font: { size: 11 } } },
      tooltip: {
        callbacks: {
          label: ctx => ` ${Number(ctx.raw).toLocaleString()}`,
        },
      },
    },
  };

  let config;

  if (chartData.type === 'donut') {
    config = {
      type: 'doughnut',
      data: {
        labels,
        datasets: [{ data: values, backgroundColor: bgColors, borderColor: '#1C2534', borderWidth: 2 }],
      },
      options: {
        ...commonOptions,
        cutout: '65%',
      },
    };
  } else if (chartData.type === 'line') {
    config = {
      type: 'line',
      data: {
        labels,
        datasets: [{
          data: values,
          borderColor: '#F59E0B',
          backgroundColor: 'rgba(245,158,11,.1)',
          pointBackgroundColor: '#F59E0B',
          tension: 0.3, fill: true,
        }],
      },
      options: {
        ...commonOptions,
        scales: {
          x: { ticks: { color: '#64748B' }, grid: { color: 'rgba(255,255,255,.05)' } },
          y: { ticks: { color: '#64748B', callback: v => v.toLocaleString() }, grid: { color: 'rgba(255,255,255,.05)' } },
        },
        plugins: { ...commonOptions.plugins, legend: { display: false } },
      },
    };
  } else {
    // bar (default)
    config = {
      type: 'bar',
      data: {
        labels,
        datasets: [{
          data: values,
          backgroundColor: bgColors,
          borderRadius: 5,
        }],
      },
      options: {
        ...commonOptions,
        indexAxis: values.length > 6 ? 'y' : 'x',
        scales: {
          x: { ticks: { color: '#64748B' }, grid: { color: 'rgba(255,255,255,.05)' } },
          y: { ticks: { color: '#64748B', callback: v => typeof v === 'number' ? v.toLocaleString() : v }, grid: { color: 'rgba(255,255,255,.05)' } },
        },
        plugins: { ...commonOptions.plugins, legend: { display: false } },
      },
    };
  }

  try {
    const instance   = new Chart(canvas, config);
    chartInstances[canvasId] = instance;
  } catch (e) {
    container.remove();
  }
}

/* ── Markdown renderer ───────────────────────────────────────────── */
function renderMarkdown(text) {
  if (!text) return '';

  let html = escHtml(text);

  // Code blocks
  html = html.replace(/```[\w]*\n?([\s\S]*?)```/g, (_, code) =>
    `<pre><code>${code.trim()}</code></pre>`);

  // Inline code
  html = html.replace(/`([^`]+)`/g, '<code>$1</code>');

  // Bold
  html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');

  // Italic
  html = html.replace(/\*([^*]+)\*/g, '<em>$1</em>');

  // Tables (simple: | col | col |)
  html = html.replace(/((?:\|[^\n]+\|\n)+)/g, (table) => {
    const rows = table.trim().split('\n').filter(r => !/^[|\s-]+$/.test(r));
    if (rows.length < 1) return table;
    let out = '<table>';
    rows.forEach((row, i) => {
      const cells = row.split('|').filter((_, idx, arr) => idx > 0 && idx < arr.length - 1);
      const tag   = i === 0 ? 'th' : 'td';
      out += '<tr>' + cells.map(c => `<${tag}>${c.trim()}</${tag}>`).join('') + '</tr>';
    });
    out += '</table>';
    return out;
  });

  // Headings
  html = html.replace(/^### (.+)$/gm, '<h4>$1</h4>');
  html = html.replace(/^## (.+)$/gm,  '<h3>$1</h3>');

  // Unordered lists
  html = html.replace(/^[•\-\*] (.+)$/gm, '<li>$1</li>');
  html = html.replace(/(<li>[\s\S]*?<\/li>)(\n(?!<li>)|$)/g, '<ul>$1</ul>');

  // Ordered lists
  html = html.replace(/^\d+\. (.+)$/gm, '<li>$1</li>');

  // Paragraphs (double newlines)
  html = html.replace(/\n\n+/g, '</p><p>');
  html = html.replace(/\n/g, '<br/>');
  html = `<p>${html}</p>`;

  // Clean up empty tags
  html = html.replace(/<p><\/p>/g, '');
  html = html.replace(/<p>(<(?:table|ul|ol|pre|h[1-6])[^>]*>)/g, '$1');
  html = html.replace(/(<\/(?:table|ul|ol|pre|h[1-6])>)<\/p>/g, '$1');

  return html;
}

function escHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

/* ── Helpers ─────────────────────────────────────────────────────── */
function formatToolName(name) {
  return name.replace(/^get_/, '').replace(/_/g, ' ');
}

function showErrorInThread(msg) {
  const el = document.createElement('div');
  el.className = 'message assistant';
  el.innerHTML = `<div class="msg-bubble" style="border-color:rgba(239,68,68,.3);color:#FCA5A5">⚠️ ${escHtml(msg)}</div>`;
  thread.appendChild(el);
  scrollToBottom();
}

function scrollToBottom() {
  thread.scrollTop = thread.scrollHeight;
}

/* ── Persistence ─────────────────────────────────────────────────── */
function saveChatsToStorage() {
  try {
    // Only save last 30 chats, trim messages to last 50 per chat
    const toSave = state.chats.slice(0, 30).map(c => ({
      ...c,
      messages: c.messages.slice(-50),
    }));
    localStorage.setItem('zaki-chats', JSON.stringify(toSave));
    localStorage.setItem('zaki-active', state.activeChatId);
  } catch {}
}

function loadChatsFromStorage() {
  try {
    const raw    = localStorage.getItem('zaki-chats');
    const active = localStorage.getItem('zaki-active');
    if (raw) {
      state.chats = JSON.parse(raw);
      state.activeChatId = active || (state.chats[0] && state.chats[0].id);
    }
  } catch {}
}
