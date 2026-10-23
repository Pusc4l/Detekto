const rawBase = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

export const API_BASE: string = rawBase.replace(/\/+$/, "");
export const WS_URL: string = `${API_BASE.replace(/^http/i, "ws")}/ws/interrogation`;
