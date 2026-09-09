/**
 * API Types Unit Tests
 * Tests the API type contracts (ApiClient is not exported, only singleton instance)
 */

import {
  SessionSnapshot,
  SessionEvent,
  TelemetryData,
  ModelProfile,
  RoutingDecision,
  Axiom,
  LogEntry,
  PluginInfo,
  MemorySystemStats,
  RepographNode,
  GitStatus,
} from '../api';

describe('API Types', () => {
  describe('SessionSnapshot', () => {
    test('valid snapshot has all required fields', () => {
      const session: SessionSnapshot = {
        id: '1', title: 'Test Session', model: 'gpt-4',
        status: 'ready', is_active: true, is_archived: false,
        is_failed: false, created_at: '2026-01-01',
        updated_at: '2026-01-01', current_seq: 0,
      };
      expect(session.id).toBe('1');
      expect(session.title).toBe('Test Session');
    });

    test('optional fields are truly optional', () => {
      const session: SessionSnapshot = {
        id: '1', title: 'Test', model: 'gpt-4',
        status: 'ready', is_active: true, is_archived: false,
        is_failed: false, created_at: '2026-01-01',
        updated_at: '2026-01-01', current_seq: 0,
      };
      expect(session.cwd).toBeUndefined();
      expect(session.root_session_id).toBeUndefined();
      expect(session.tag).toBeUndefined();
    });

    test('supports all optional fields', () => {
      const session: SessionSnapshot = {
        id: '1', title: 'Test', model: 'gpt-4',
        cwd: '/home/project', status: 'ready',
        is_active: true, is_archived: false, is_failed: false,
        root_session_id: 'parent-1', tag: 'important',
        created_at: '2026-01-01', updated_at: '2026-01-01',
        current_seq: 42,
      };
      expect(session.cwd).toBe('/home/project');
      expect(session.root_session_id).toBe('parent-1');
      expect(session.tag).toBe('important');
      expect(session.current_seq).toBe(42);
    });

    test('supports all status values', () => {
      const statuses: SessionSnapshot['status'][] = [
        'created', 'ready', 'running', 'interrupted', 'failed'
      ];
      statuses.forEach(s => expect(['created','ready','running','interrupted','failed']).toContain(s));
    });

    test('supports failed state', () => {
      const session: SessionSnapshot = {
        id: '1', title: 'Failed', model: 'gpt-4',
        status: 'failed', is_active: false, is_archived: false,
        is_failed: true, created_at: '2026-01-01',
        updated_at: '2026-01-01', current_seq: 0,
      };
      expect(session.is_failed).toBe(true);
      expect(session.is_active).toBe(false);
    });
  });

  describe('SessionEvent', () => {
    test('valid event has all required fields', () => {
      const event: SessionEvent = {
        id: 'e1', session_id: '1', type: 'user',
        payload: { message: 'Hello' }, seq: 1, timestamp: '2026-01-01',
      };
      expect(event.id).toBe('e1');
      expect(event.session_id).toBe('1');
      expect(event.seq).toBe(1);
    });

    test('payload can be empty', () => {
      const event: SessionEvent = {
        id: 'e1', session_id: '1', type: 'system',
        payload: {}, seq: 1, timestamp: '2026-01-01',
      };
      expect(event.payload).toEqual({});
    });
  });

  describe('TelemetryData', () => {
    test('has all sensor fields', () => {
      const t: TelemetryData = {
        gpu_temp: 72, gpu_util: 85, cpu_temp: 65, cpu_util: 45,
        ram_used: 8192, ram_total: 32768, ram_util: 25,
        disk_used: 150, disk_total: 500, fan_speed: 1200,
        power_draw: 350, timestamp: '2026-01-01',
      };
      expect(t.gpu_temp).toBe(72);
      expect(t.gpu_util).toBe(85);
      expect(t.power_draw).toBe(350);
    });

    test('supports high values', () => {
      const t: TelemetryData = {
        gpu_temp: 95, gpu_util: 100, cpu_temp: 90, cpu_util: 100,
        ram_used: 32000, ram_total: 32768, ram_util: 97.6,
        disk_used: 490, disk_total: 500, fan_speed: 5000,
        power_draw: 450, timestamp: '2026-01-01',
      };
      expect(t.gpu_temp).toBe(95);
      expect(t.power_draw).toBe(450);
    });
  });

  describe('ModelProfile', () => {
    test('valid model has all required fields', () => {
      const m: ModelProfile = {
        name: 'gpt-4', api_base: 'https://api.openai.com',
        model_name: 'gpt-4-turbo', tier: 'power', category: 'OpenAI',
        is_default: true, context_window: 128000, max_tokens: 4096,
      };
      expect(m.name).toBe('gpt-4');
      expect(m.tier).toBe('power');
      expect(m.context_window).toBe(128000);
    });

    test('supports all tiers', () => {
      const tiers: ModelProfile['tier'][] = ['fast', 'balanced', 'power', 'expert'];
      tiers.forEach(t => expect(['fast','balanced','power','expert']).toContain(t));
    });

    test('supports non-default models', () => {
      const m: ModelProfile = {
        name: 'claude-3', api_base: 'https://api.anthropic.com',
        model_name: 'claude-3-opus', tier: 'expert', category: 'Anthropic',
        is_default: false, context_window: 200000, max_tokens: 8192,
      };
      expect(m.is_default).toBe(false);
    });
  });

  describe('RoutingDecision', () => {
    test('valid decision has all required fields', () => {
      const d: RoutingDecision = {
        selected_model: 'gpt-4', tier: 'power',
        confidence: 0.95, reason: 'High complexity',
      };
      expect(d.selected_model).toBe('gpt-4');
      expect(d.confidence).toBe(0.95);
    });

    test('supports fallback_model', () => {
      const d: RoutingDecision = {
        selected_model: 'gpt-4', tier: 'power',
        confidence: 0.5, reason: 'Uncertain',
        fallback_model: 'claude-3',
      };
      expect(d.fallback_model).toBe('claude-3');
    });
  });

  describe('Axiom', () => {
    test('valid axiom has all required fields', () => {
      const a: Axiom = {
        id: 'a1', category: 'core', status: 'verified',
        description: 'Test axiom', prerequisites: [],
        verified_at: '2026-01-01',
      };
      expect(a.id).toBe('a1');
      expect(a.category).toBe('core');
      expect(a.status).toBe('verified');
    });

    test('supports axioms with prerequisites', () => {
      const a: Axiom = {
        id: 'a2', category: 'derived', status: 'in_progress',
        description: 'Depends on a1', prerequisites: ['a1', 'a3'],
        verified_at: undefined,
      };
      expect(a.prerequisites).toHaveLength(2);
      expect(a.status).toBe('in_progress');
    });

    test('supports all axiom statuses', () => {
      const statuses: Axiom['status'][] = ['in_progress', 'verified', 'blocked'];
      statuses.forEach(s => expect(['in_progress','verified','blocked']).toContain(s));
    });

    test('verified_at is optional', () => {
      const a: Axiom = {
        id: 'a1', category: 'core', status: 'in_progress',
        description: 'Pending', prerequisites: [],
      };
      expect(a.verified_at).toBeUndefined();
    });
  });

  describe('LogEntry', () => {
    test('valid log has all required fields', () => {
      const l: LogEntry = {
        level: 'INFO', logger: 'test',
        message: 'Test log', timestamp: '2026-01-01',
      };
      expect(l.level).toBe('INFO');
      expect(l.logger).toBe('test');
    });

    test('supports all log levels', () => {
      const levels: LogEntry['level'][] = ['DEBUG', 'INFO', 'WARNING', 'ERROR'];
      levels.forEach(l => expect(['DEBUG','INFO','WARNING','ERROR']).toContain(l));
    });
  });

  describe('PluginInfo', () => {
    test('valid plugin has all required fields', () => {
      const p: PluginInfo = {
        name: 'searxng', enabled: true,
        version: '1.0.0', description: 'Search plugin',
      };
      expect(p.name).toBe('searxng');
      expect(p.enabled).toBe(true);
    });

    test('supports disabled plugins', () => {
      const p: PluginInfo = {
        name: 'tavily', enabled: false,
        version: '0.5.0', description: 'Search plugin',
      };
      expect(p.enabled).toBe(false);
    });
  });

  describe('MemorySystemStats', () => {
    test('has all memory sections', () => {
      const s: MemorySystemStats = {
        sensory: { size: 100, capacity: 1000 },
        working: { size: 500, capacity: 5000 },
        longterm: { size: 10000, capacity: 100000 },
        procedural: { size: 500, capacity: 5000 },
      };
      expect(s.sensory.size).toBe(100);
      expect(s.working.size).toBe(500);
      expect(s.longterm.size).toBe(10000);
    });

    test('utilization is size/capacity', () => {
      const s: MemorySystemStats = {
        sensory: { size: 100, capacity: 1000 },
        working: { size: 500, capacity: 5000 },
        longterm: { size: 10000, capacity: 100000 },
        procedural: { size: 500, capacity: 5000 },
      };
      expect(s.sensory.size / s.sensory.capacity).toBe(0.1);
      expect(s.longterm.size / s.longterm.capacity).toBe(0.1);
    });
  });

  describe('RepographNode', () => {
    test('valid node has all required fields', () => {
      const n: RepographNode = {
        filepath: 'src/main.py', language: 'python',
        classes: ['MainClass'], functions: ['main', 'run'],
        imports: ['os', 'sys'], dependencies: ['utils.py'],
        pagerank: 0.85,
      };
      expect(n.filepath).toBe('src/main.py');
      expect(n.language).toBe('python');
      expect(n.pagerank).toBe(0.85);
    });

    test('supports empty arrays', () => {
      const n: RepographNode = {
        filepath: 'src/empty.py', language: 'python',
        classes: [], functions: [], imports: [],
        dependencies: [], pagerank: 0.0,
      };
      expect(n.classes).toHaveLength(0);
      expect(n.pagerank).toBe(0.0);
    });
  });

  describe('GitStatus', () => {
    test('valid status has all required fields', () => {
      const s: GitStatus = {
        is_repo: true, branch: 'main', is_dirty: false,
        staged_files: ['file1.py'], head_hash: 'abc123',
      };
      expect(s.is_repo).toBe(true);
      expect(s.branch).toBe('main');
      expect(s.head_hash).toBe('abc123');
    });

    test('supports non-repo', () => {
      const s: GitStatus = {
        is_repo: false, branch: '', is_dirty: false,
        staged_files: [], head_hash: '',
      };
      expect(s.is_repo).toBe(false);
    });

    test('supports dirty state', () => {
      const s: GitStatus = {
        is_repo: true, branch: 'feature', is_dirty: true,
        staged_files: ['file1.py', 'file2.py'], head_hash: 'def456',
      };
      expect(s.is_dirty).toBe(true);
      expect(s.staged_files).toHaveLength(2);
    });
  });
});
