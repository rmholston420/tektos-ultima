/**
 * API Client Unit Tests
 * Tests the API types and interface contracts
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
  RepographEdge,
  GitStatus,
  HookInfo,
  ConfigValue,
  KeyInfo,
  SearchResults,
} from '../api';

describe('API Types', () => {
  describe('SessionSnapshot', () => {
    test('valid snapshot has all required fields', () => {
      const session: SessionSnapshot = {
        id: '1',
        title: 'Test Session',
        model: 'gpt-4',
        status: 'ready',
        is_active: true,
        is_archived: false,
        is_failed: false,
        created_at: '2026-01-01',
        updated_at: '2026-01-01',
        current_seq: 0,
      };

      expect(session.id).toBe('1');
      expect(session.title).toBe('Test Session');
      expect(session.model).toBe('gpt-4');
      expect(session.status).toBe('ready');
      expect(session.is_active).toBe(true);
    });

    test('optional fields are optional', () => {
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
        cwd: '/home/user/project', status: 'ready',
        is_active: true, is_archived: false, is_failed: false,
        root_session_id: 'parent-1', tag: 'important',
        created_at: '2026-01-01', updated_at: '2026-01-01',
        current_seq: 42,
      };

      expect(session.cwd).toBe('/home/user/project');
      expect(session.root_session_id).toBe('parent-1');
      expect(session.tag).toBe('important');
      expect(session.current_seq).toBe(42);
    });

    test('supports all status values', () => {
      const statuses: SessionSnapshot['status'][] = [
        'created', 'ready', 'running', 'interrupted', 'failed'
      ];
      expect(statuses).toContain('created');
      expect(statuses).toContain('ready');
      expect(statuses).toContain('running');
      expect(statuses).toContain('interrupted');
      expect(statuses).toContain('failed');
    });

    test('supports interrupted and failed flags', () => {
      const failed: SessionSnapshot = {
        id: '1', title: 'Failed', model: 'gpt-4',
        status: 'failed', is_active: false, is_archived: false,
        is_failed: true, created_at: '2026-01-01',
        updated_at: '2026-01-01', current_seq: 0,
      };

      expect(failed.is_failed).toBe(true);
      expect(failed.is_active).toBe(false);
    });
  });

  describe('SessionEvent', () => {
    test('valid event has all required fields', () => {
      const event: SessionEvent = {
        id: 'e1', session_id: '1', type: 'user',
        payload: { message: 'Hello' },
        seq: 1, timestamp: '2026-01-01',
      };

      expect(event.id).toBe('e1');
      expect(event.session_id).toBe('1');
      expect(event.type).toBe('user');
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
      const telemetry: TelemetryData = {
        gpu_temp: 72, gpu_util: 85,
        cpu_temp: 65, cpu_util: 45,
        ram_used: 8192, ram_total: 32768, ram_util: 25,
        disk_used: 150, disk_total: 500, fan_speed: 1200,
        power_draw: 350, timestamp: '2026-01-01',
      };

      expect(telemetry.gpu_temp).toBe(72);
      expect(telemetry.gpu_util).toBe(85);
      expect(telemetry.cpu_temp).toBe(65);
      expect(telemetry.cpu_util).toBe(45);
      expect(telemetry.ram_util).toBe(25);
    });

    test('supports high values', () => {
      const telemetry: TelemetryData = {
        gpu_temp: 95, gpu_util: 100,
        cpu_temp: 90, cpu_util: 100,
        ram_used: 32000, ram_total: 32768, ram_util: 97.6,
        disk_used: 490, disk_total: 500, fan_speed: 5000,
        power_draw: 450, timestamp: '2026-01-01',
      };

      expect(telemetry.gpu_temp).toBe(95);
      expect(telemetry.gpu_util).toBe(100);
      expect(telemetry.power_draw).toBe(450);
    });
  });

  describe('ModelProfile', () => {
    test('valid model has all required fields', () => {
      const model: ModelProfile = {
        name: 'gpt-4',
        api_base: 'https://api.openai.com',
        model_name: 'gpt-4-turbo',
        tier: 'power',
        category: 'OpenAI',
        is_default: true,
        context_window: 128000,
        max_tokens: 4096,
      };

      expect(model.name).toBe('gpt-4');
      expect(model.tier).toBe('power');
      expect(model.context_window).toBe(128000);
    });

    test('supports all tiers', () => {
      const tiers: ModelProfile['tier'][] = ['power', 'fast', 'free'];
      expect(tiers).toContain('power');
      expect(tiers).toContain('fast');
      expect(tiers).toContain('free');
    });

    test('supports all categories', () => {
      const categories: ModelProfile['category'][] = ['OpenAI', 'Anthropic', 'Google', 'Custom'];
      expect(categories).toContain('OpenAI');
      expect(categories).toContain('Anthropic');
    });

    test('supports non-default models', () => {
      const model: ModelProfile = {
        name: 'claude-3',
        api_base: 'https://api.anthropic.com',
        model_name: 'claude-3-opus-20240229',
        tier: 'power',
        category: 'Anthropic',
        is_default: false,
        context_window: 200000,
        max_tokens: 8192,
      };

      expect(model.is_default).toBe(false);
    });
  });

  describe('RoutingDecision', () => {
    test('valid decision has all required fields', () => {
      const decision: RoutingDecision = {
        selected_model: 'gpt-4',
        tier: 'power',
        confidence: 0.95,
        reason: 'High complexity',
      };

      expect(decision.selected_model).toBe('gpt-4');
      expect(decision.confidence).toBe(0.95);
    });

    test('confidence is between 0 and 1', () => {
      const decision: RoutingDecision = {
        selected_model: 'gpt-4',
        tier: 'power',
        confidence: 1.0,
        reason: 'Certain',
      };

      expect(decision.confidence).toBe(1.0);
    });

    test('low confidence decision', () => {
      const decision: RoutingDecision = {
        selected_model: 'gpt-3.5',
        tier: 'fast',
        confidence: 0.3,
        reason: 'Low certainty',
      };

      expect(decision.confidence).toBe(0.3);
    });
  });

  describe('Axiom', () => {
    test('valid axiom has all required fields', () => {
      const axiom: Axiom = {
        id: 'a1',
        category: 'core',
        status: 'verified',
        description: 'Test axiom',
        prerequisites: [],
        verified_at: '2026-01-01',
      };

      expect(axiom.id).toBe('a1');
      expect(axiom.category).toBe('core');
      expect(axiom.status).toBe('verified');
    });

    test('supports axioms with prerequisites', () => {
      const axiom: Axiom = {
        id: 'a2',
        category: 'derived',
        status: 'pending',
        description: 'Depends on a1',
        prerequisites: ['a1', 'a3'],
        verified_at: null,
      };

      expect(axiom.prerequisites).toHaveLength(2);
      expect(axiom.status).toBe('pending');
    });

    test('supports all axiom statuses', () => {
      const statuses: Axiom['status'][] = ['verified', 'pending', 'invalidated', 'provisional'];
      expect(statuses).toContain('verified');
      expect(statuses).toContain('pending');
      expect(statuses).toContain('invalidated');
      expect(statuses).toContain('provisional');
    });

    test('supports all axiom categories', () => {
      const categories: Axiom['category'][] = ['core', 'derived', 'meta', 'operational'];
      expect(categories).toContain('core');
      expect(categories).toContain('derived');
      expect(categories).toContain('meta');
      expect(categories).toContain('operational');
    });
  });

  describe('LogEntry', () => {
    test('valid log has all required fields', () => {
      const log: LogEntry = {
        level: 'INFO',
        logger: 'test',
        message: 'Test log',
        timestamp: '2026-01-01',
      };

      expect(log.level).toBe('INFO');
      expect(log.logger).toBe('test');
    });

    test('supports all log levels', () => {
      const levels: LogEntry['level'][] = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'];
      expect(levels).toContain('DEBUG');
      expect(levels).toContain('INFO');
      expect(levels).toContain('WARNING');
      expect(levels).toContain('ERROR');
      expect(levels).toContain('CRITICAL');
    });

    test('supports optional fields', () => {
      const log: LogEntry = {
        level: 'ERROR',
        logger: 'api',
        message: 'Connection failed',
        timestamp: '2026-01-01',
        trace: 'stack trace here',
        extra: { endpoint: '/api/test', status: 500 },
      };

      expect(log.trace).toBe('stack trace here');
      expect(log.extra?.endpoint).toBe('/api/test');
    });
  });

  describe('PluginInfo', () => {
    test('valid plugin has all required fields', () => {
      const plugin: PluginInfo = {
        name: 'searxng',
        enabled: true,
        version: '1.0.0',
        description: 'Search plugin',
      };

      expect(plugin.name).toBe('searxng');
      expect(plugin.enabled).toBe(true);
      expect(plugin.version).toBe('1.0.0');
    });

    test('supports disabled plugins', () => {
      const plugin: PluginInfo = {
        name: 'tavily',
        enabled: false,
        version: '0.5.0',
        description: 'Search plugin',
      };

      expect(plugin.enabled).toBe(false);
    });
  });

  describe('MemorySystemStats', () => {
    test('has all memory sections', () => {
      const stats: MemorySystemStats = {
        sensory: { size: 100, capacity: 1000 },
        working: { size: 500, capacity: 5000 },
        longterm: { size: 10000, capacity: 100000 },
        procedural: { size: 500, capacity: 5000 },
      };

      expect(stats.sensory.size).toBe(100);
      expect(stats.working.size).toBe(500);
      expect(stats.longterm.size).toBe(10000);
      expect(stats.procedural.size).toBe(500);
    });

    test('utilization is size/capacity', () => {
      const stats: MemorySystemStats = {
        sensory: { size: 100, capacity: 1000 },
        working: { size: 500, capacity: 5000 },
        longterm: { size: 10000, capacity: 100000 },
        procedural: { size: 500, capacity: 5000 },
      };

      expect(stats.sensory.size / stats.sensory.capacity).toBe(0.1);
      expect(stats.longterm.size / stats.longterm.capacity).toBe(0.1);
    });

    test('supports high utilization', () => {
      const stats: MemorySystemStats = {
        sensory: { size: 950, capacity: 1000 },
        working: { size: 4900, capacity: 5000 },
        longterm: { size: 99000, capacity: 100000 },
        procedural: { size: 4900, capacity: 5000 },
      };

      expect(stats.sensory.size / stats.sensory.capacity).toBe(0.95);
    });
  });

  describe('RepographNode', () => {
    test('valid node has all required fields', () => {
      const node: RepographNode = {
        filepath: 'src/main.py',
        language: 'python',
        classes: ['MainClass'],
        functions: ['main', 'run'],
        imports: ['os', 'sys'],
        dependencies: ['utils.py'],
        pagerank: 0.85,
      };

      expect(node.filepath).toBe('src/main.py');
      expect(node.language).toBe('python');
      expect(node.pagerank).toBe(0.85);
    });

    test('supports empty arrays', () => {
      const node: RepographNode = {
        filepath: 'src/empty.py',
        language: 'python',
        classes: [],
        functions: [],
        imports: [],
        dependencies: [],
        pagerank: 0.0,
      };

      expect(node.classes).toHaveLength(0);
      expect(node.pagerank).toBe(0.0);
    });

    test('supports multiple classes and functions', () => {
      const node: RepographNode = {
        filepath: 'src/multi.py',
        language: 'python',
        classes: ['Class1', 'Class2', 'Class3'],
        functions: ['func1', 'func2', 'func3', 'func4'],
        imports: ['os', 'sys', 'json'],
        dependencies: ['utils.py', 'config.py'],
        pagerank: 0.5,
      };

      expect(node.classes).toHaveLength(3);
      expect(node.functions).toHaveLength(4);
    });
  });

  describe('RepographEdge', () => {
    test('valid edge has source and target', () => {
      const edge: RepographEdge = {
        source: 'src/main.py',
        target: 'src/utils.py',
        type: 'import',
      };

      expect(edge.source).toBe('src/main.py');
      expect(edge.target).toBe('src/utils.py');
      expect(edge.type).toBe('import');
    });

    test('supports call edges', () => {
      const edge: RepographEdge = {
        source: 'src/main.py',
        target: 'src/main.py',
        type: 'call',
      };

      expect(edge.type).toBe('call');
    });
  });

  describe('GitStatus', () => {
    test('valid status has all required fields', () => {
      const status: GitStatus = {
        is_repo: true,
        branch: 'main',
        is_dirty: false,
        staged_files: ['file1.py'],
        head_hash: 'abc123',
      };

      expect(status.is_repo).toBe(true);
      expect(status.branch).toBe('main');
      expect(status.head_hash).toBe('abc123');
    });

    test('supports non-repo', () => {
      const status: GitStatus = {
        is_repo: false,
        branch: '',
        is_dirty: false,
        staged_files: [],
        head_hash: '',
      };

      expect(status.is_repo).toBe(false);
    });

    test('supports dirty state', () => {
      const status: GitStatus = {
        is_repo: true,
        branch: 'feature',
        is_dirty: true,
        staged_files: ['file1.py', 'file2.py'],
        head_hash: 'def456',
      };

      expect(status.is_dirty).toBe(true);
      expect(status.staged_files).toHaveLength(2);
    });

    test('supports untracked files', () => {
      const status: GitStatus = {
        is_repo: true,
        branch: 'main',
        is_dirty: false,
        staged_files: [],
        untracked_files: ['new-file.py'],
        head_hash: 'abc123',
      };

      expect(status.untracked_files).toHaveLength(1);
    });
  });

  describe('HookInfo', () => {
    test('valid hook has name and enabled', () => {
      const hook: HookInfo = {
        name: 'on_message',
        enabled: true,
      };

      expect(hook.name).toBe('on_message');
      expect(hook.enabled).toBe(true);
    });
  });

  describe('ConfigValue', () => {
    test('valid config has key and value', () => {
      const config: ConfigValue = {
        key: 'temperature',
        value: 0.7,
      };

      expect(config.key).toBe('temperature');
      expect(config.value).toBe(0.7);
    });

    test('supports string values', () => {
      const config: ConfigValue = {
        key: 'model',
        value: 'gpt-4',
      };

      expect(config.value).toBe('gpt-4');
    });

    test('supports boolean values', () => {
      const config: ConfigValue = {
        key: 'debug',
        value: true,
      };

      expect(config.value).toBe(true);
    });

    test('supports numeric values', () => {
      const config: ConfigValue = {
        key: 'max_tokens',
        value: 4096,
      };

      expect(config.value).toBe(4096);
    });
  });

  describe('KeyInfo', () => {
    test('valid key has name and masked value', () => {
      const key: KeyInfo = {
        name: 'openai',
        masked: 'sk-****',
      };

      expect(key.name).toBe('openai');
      expect(key.masked).toBe('sk-****');
    });
  });

  describe('SearchResults', () => {
    test('has query and results', () => {
      const results: SearchResults = {
        query: 'test',
        results: [{ title: 'result', content: 'found' }],
      };

      expect(results.query).toBe('test');
      expect(results.results).toHaveLength(1);
    });

    test('supports empty results', () => {
      const results: SearchResults = {
        query: 'nonexistent',
        results: [],
      };

      expect(results.results).toHaveLength(0);
    });
  });
});
