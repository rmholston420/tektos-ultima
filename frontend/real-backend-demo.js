/**
 * Tektos Frontend — Real Backend Live Demo (REST + SSE)
 * 
 * Uses the actual backend API to drive a real coding task.
 * Prompt submission via /api/prompt/sse (SSE streaming).
 */

const http = require('http');

function apiCall(method, path, body = null) {
  return new Promise((resolve, reject) => {
    const url = `http://localhost:8020${path}`;
    const options = {
      method,
      headers: { 'Content-Type': 'application/json' },
      timeout: 10000
    };
    const req = http.request(url, options, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        try { resolve(JSON.parse(data)); }
        catch (e) { resolve(data); }
      });
    });
    req.on('error', reject);
    req.on('timeout', () => { req.destroy(); reject(new Error('Timeout')); });
    if (body) req.write(JSON.stringify(body));
    req.end();
  });
}

function submitPromptSSE(sessionId, promptText) {
  return new Promise((resolve, reject) => {
    const url = 'http://localhost:8020/api/prompt/sse';
    const options = {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'text/event-stream'
      },
      timeout: 120000
    };
    const req = http.request(url, options, (res) => {
      if (res.statusCode !== 200) {
        reject(new Error(`SSE failed: ${res.statusCode}`));
        return;
      }
      const events = [];
      res.on('data', (chunk) => {
        const text = chunk.toString();
        const lines = text.split('\n');
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = line.substring(6);
            if (data === '[DONE]') {
              resolve(events);
              return;
            }
            try {
              const parsed = JSON.parse(data);
              events.push(parsed);
              const type = parsed.type || parsed.event || 'unknown';
              const summary = JSON.stringify(parsed).substring(0, 150);
              console.log(`  ← SSE: ${type} — ${summary}`);
            } catch (e) {
              // Skip non-JSON
            }
          }
        }
      });
      res.on('end', () => resolve(events));
      res.on('error', reject);
    });
    req.on('error', reject);
    req.on('timeout', () => { req.destroy(); reject(new Error('SSE timeout')); });
    req.write(JSON.stringify({
      session_id: sessionId,
      prompt: promptText
    }));
    req.end();
  });
}

async function main() {
  console.log('\n═══════════════════════════════════════════');
  console.log('  TEKTOS-ULTIMA REAL BACKEND LIVE DEMO');
  console.log('═══════════════════════════════════════════\n');
  
  // Step 1: Health
  console.log('▶ Step 1: Backend health...');
  const health = await apiCall('GET', '/health');
  console.log(`  ✓ Health: ok=${health.ok}`);
  console.log(`    LLM URL: ${health.llm_url}`);
  console.log(`    LLM Model: ${health.llm_model}`);
  console.log(`    Active sessions: ${health.active_sessions}`);
  console.log(`    Protocol: ${health.protocol_version}`);
  console.log(`    Event bus: published=${health.event_bus.published}, dropped=${health.event_bus.dropped}`);
  console.log(`    State machine: total=${health.state_machine.total_sessions}, transitions=${health.state_machine.transitions_completed}`);
  
  // Step 2: Models
  console.log('\n▶ Step 2: Available models...');
  const models = await apiCall('GET', '/api/models');
  models.forEach(m => console.log(`    • ${m.name} (${m.role}) — ${m.params} params`));
  
  // Step 3: Create session
  console.log('\n▶ Step 3: Creating session...');
  const session = await apiCall('POST', '/api/sessions', { title: 'Live Demo — Fibonacci' });
  console.log(`  ✓ Session: ${session.id}`);
  console.log(`    Model: ${session.model}`);
  console.log(`    Status: ${session.status}`);
  
  // Step 4: Submit prompt via SSE
  console.log('\n▶ Step 4: Submitting prompt via SSE...');
  const prompt = 'Write a Python function called fibonacci(n) that returns the nth Fibonacci number using memoization. Include type hints and docstring.';
  console.log(`  → Prompt: "${prompt}"`);
  
  const events = await submitPromptSSE(session.id, prompt);
  console.log(`\n  ✓ Received ${events.length} SSE events`);
  
  // Step 5: Check session state
  console.log('\n▶ Step 5: Session state...');
  const state = await apiCall('GET', `/api/state/${session.id}`);
  console.log(`  ✓ Status: ${state.status || state.state || 'unknown'}`);
  console.log(`    Seq: ${state.current_seq || state.seq || 'N/A'}`);
  
  // Step 6: Check messages
  console.log('\n▶ Step 6: Session messages...');
  const messages = await apiCall('GET', `/api/archive/sessions/${session.id}/messages`);
  console.log(`  ✓ ${messages.length} messages`);
  messages.forEach((m, i) => {
    const role = m.role || m.type || 'unknown';
    const content = (m.content || m.text || '').substring(0, 200);
    console.log(`    [${i}] ${role}: ${content}`);
  });
  
  // Step 7: Check all sessions
  console.log('\n▶ Step 7: All sessions...');
  const allSessions = await apiCall('GET', '/api/sessions');
  console.log(`  ✓ Total sessions: ${allSessions.length}`);
  const statusCounts = {};
  allSessions.forEach(s => {
    const st = s.status || 'unknown';
    statusCounts[st] = (statusCounts[st] || 0) + 1;
  });
  Object.entries(statusCounts).forEach(([st, count]) => console.log(`    ${st}: ${count}`));
  
  // Step 8: Frontend API proxy
  console.log('\n▶ Step 8: Frontend API proxy (localhost:3000)...');
  const proxyModels = await apiCall('GET', '/api/models');
  console.log(`  ✓ Proxy models: ${proxyModels.length}`);
  
  // Step 9: Telemetry
  console.log('\n▶ Step 9: Telemetry...');
  const telemetry = await apiCall('GET', '/api/telemetry');
  if (telemetry.gpu) {
    console.log(`  ✓ GPU: temp=${telemetry.gpu.temperature}°C, util=${telemetry.gpu.utilization}%`);
    console.log(`    VRAM: ${telemetry.gpu.memory_used}/${telemetry.gpu.memory_total} MB`);
    console.log(`    Power: ${telemetry.gpu.power_draw}W / ${telemetry.gpu.power_limit}W`);
  }
  if (telemetry.cpu) console.log(`  ✓ CPU: ${telemetry.cpu.utilization}%`);
  if (telemetry.ram) console.log(`  ✓ RAM: ${telemetry.ram.used}/${telemetry.ram.total} GB`);
  
  console.log('\n═══════════════════════════════════════════');
  console.log('  ✅ REAL BACKEND DEMO COMPLETE');
  console.log('═══════════════════════════════════════════\n');
}

main().catch(err => {
  console.error('ERROR:', err.message);
  process.exit(1);
});
