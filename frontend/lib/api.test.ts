import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api, clearTokens, isAuthed, setTokens } from "./api";

function res(status: number, body: unknown): Promise<Response> {
  return Promise.resolve({
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(body),
  } as Response);
}

beforeEach(() => {
  localStorage.clear();
  vi.restoreAllMocks();
});
afterEach(() => {
  vi.unstubAllGlobals();
});

describe("token helpers", () => {
  it("stores, reports, and clears tokens", () => {
    expect(isAuthed()).toBe(false);
    setTokens("access1", "refresh1");
    expect(isAuthed()).toBe(true);
    expect(localStorage.getItem("flowcare_access")).toBe("access1");
    expect(localStorage.getItem("flowcare_refresh")).toBe("refresh1");
    clearTokens();
    expect(isAuthed()).toBe(false);
  });
});

describe("request auto-refresh", () => {
  it("refreshes the access token on a 401 and retries the original request", async () => {
    setTokens("oldA", "oldR");
    const fetchMock = vi
      .fn()
      .mockImplementationOnce(() => res(401, { detail: "expired" })) // first /dashboard
      .mockImplementationOnce(() => res(200, { access_token: "newA", refresh_token: "newR" })) // /auth/refresh
      .mockImplementationOnce(() => res(200, { referrals_total: 5 })); // retried /dashboard
    vi.stubGlobal("fetch", fetchMock);

    const data = await api.dashboard();

    expect(data.referrals_total).toBe(5);
    expect(localStorage.getItem("flowcare_access")).toBe("newA");
    expect(fetchMock).toHaveBeenCalledTimes(3);
    expect(String(fetchMock.mock.calls[1][0])).toContain("/auth/refresh");
  });

  it("uses a single-flight refresh for concurrent 401s", async () => {
    setTokens("oldA", "oldR");
    let refreshCalls = 0;
    const fetchMock = vi.fn((url: string, init: RequestInit) => {
      if (String(url).includes("/auth/refresh")) {
        refreshCalls += 1;
        return res(200, { access_token: "newA", refresh_token: "newR" });
      }
      const auth = (init.headers as Headers).get("Authorization");
      return auth === "Bearer newA" ? res(200, []) : res(401, { detail: "expired" });
    });
    vi.stubGlobal("fetch", fetchMock);

    await Promise.all([api.dashboard(), api.listTasks()]);

    expect(refreshCalls).toBe(1); // both 401s share one refresh
  });

  it("clears tokens and surfaces the error when refresh fails", async () => {
    setTokens("oldA", "oldR");
    const fetchMock = vi
      .fn()
      .mockImplementationOnce(() => res(401, { detail: "expired" }))
      .mockImplementationOnce(() => res(401, { detail: "invalid refresh" })); // refresh fails
    vi.stubGlobal("fetch", fetchMock);

    await expect(api.dashboard()).rejects.toThrow();
    expect(isAuthed()).toBe(false); // tokens cleared
  });

  it("propagates a non-401 error message", async () => {
    setTokens("a", "r");
    vi.stubGlobal("fetch", vi.fn(() => res(400, { detail: "bad request" })));
    await expect(api.dashboard()).rejects.toThrow("bad request");
  });
});
