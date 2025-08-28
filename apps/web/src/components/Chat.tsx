import { useState } from "react";
import { api } from "../lib/api";

type Msg = { role: "user" | "assistant"; text: string; citations?: Array<{ document_id: string; chunk_id: string; snippet: string; score: number }> };

export default function Chat() {
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function send() {
    const question = q.trim();
    if (!question || busy) return;
    setMsgs((m) => [...m, { role: "user", text: question }]);
    setQ("");
    setBusy(true);
    setError("");
    try {
      const { data } = await api.post("/ask", { question, top_k: 5 });
      setMsgs((m) => [...m, { role: "assistant", text: data.answer, citations: data.citations }]);
    } catch (e: any) {
      setError(e?.message || "Ask failed");
    } finally {
      setBusy(false);
    }
  }

  function onKey(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter") send();
  }

  return (
    <div style={{ marginTop: 24 }}>
      <div style={{ border: "1px solid #333", borderRadius: 8, padding: 12, minHeight: 120 }}>
        {msgs.length === 0 && <p style={{ opacity: 0.7 }}>Ask something about your uploaded document.</p>}
        {msgs.map((m, i) => (
          <div key={i} style={{ margin: "8px 0" }}>
            <b>{m.role === "user" ? "You" : "Assistant"}</b>
            <div style={{ whiteSpace: "pre-wrap", marginTop: 4 }}>{m.text}</div>
            {m.role === "assistant" && m.citations && m.citations.length > 0 && (
              <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginTop: 8 }}>
                {m.citations.map((c, idx) => (
                  <span key={idx} style={{ fontSize: 12, border: "1px solid #555", borderRadius: 6, padding: "2px 6px" }}>
                    [{idx + 1}] {c.document_id} • {c.chunk_id.split(":")[1]} • {(c.score || 0).toFixed(2)}
                  </span>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>

      <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={onKey}
          disabled={busy}
          placeholder="Type your question…"
          style={{ flex: 1, padding: 10, borderRadius: 6, border: "1px solid #444", background: "#111", color: "white" }}
        />
        <button onClick={send} disabled={busy || !q.trim()} style={{ padding: "10px 16px", borderRadius: 6 }}>
          {busy ? "Thinking…" : "Ask"}
        </button>
      </div>
      {error && <p style={{ color: "tomato", marginTop: 8 }}>{error}</p>}
    </div>
  );
}
