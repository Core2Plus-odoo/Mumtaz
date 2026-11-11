import { afterEach, describe, expect, it, vi } from 'vitest';
import { api, ApiError } from './api';

const reply = (status: number, body: unknown) =>
  vi.fn().mockResolvedValue({ ok: status < 400, status, json: async () => body } as Response);

afterEach(() => vi.unstubAllGlobals());

describe('api client', () => {
  it('unwraps the data envelope', async () => {
    vi.stubGlobal('fetch', reply(200, { ok: true, data: { service: 'jawhar-api', version: '1.0' } }));
    expect((await api.health()).service).toBe('jawhar-api');
  });
  it('turns an error envelope into ApiError with the server code', async () => {
    vi.stubGlobal('fetch', reply(401, { ok: false, error: { code: 'unauthenticated', message: 'Sign in first.' } }));
    await expect(api.me()).rejects.toMatchObject({ status: 401, code: 'unauthenticated' } satisfies Partial<ApiError>);
  });
  it('sends login as JSON with the session cookie', async () => {
    const f = reply(200, { ok: true, data: { id: 2 } });
    vi.stubGlobal('fetch', f);
    await api.login('admin', 'x');
    const [url, init] = f.mock.calls[0];
    expect(url).toBe('/jawhar/v1/auth/login');
    expect(init.method).toBe('POST');
    expect(init.credentials).toBe('same-origin');
    expect(JSON.parse(init.body)).toEqual({ login: 'admin', password: 'x' });
  });
  it('drops empty query parameters', async () => {
    const f = reply(200, { ok: true, data: { items: [] } });
    vi.stubGlobal('fetch', f);
    await api.pieces({ q: '', karat: undefined, on_hand: true, limit: 50 });
    expect(f.mock.calls[0][0]).toBe('/jawhar/v1/pieces?on_hand=true&limit=50');
  });
});
