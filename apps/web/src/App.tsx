import { useEffect, useState } from "react";
import { getHealth } from "./lib/api";
import Upload from "./components/Upload";
import Chat from "./components/Chat";

export default function App() {
  const [status, setStatus] = useState<"loading" | "ok" | "error">("loading");
  const [msg, setMsg] = useState("");

  useEffect(() => {
    getHealth()
      .then((d) => {
        if (d?.ok) {
          setStatus("ok");
          setMsg("API OK");
        } else {
          setStatus("error");
          setMsg("Unexpected response");
        }
      })
      .catch((e) => {
        setStatus("error");
        setMsg(e?.message || "Failed to reach API");
      });
  }, []);

  return (
    <div style={{ maxWidth: 900, margin: "48px auto", fontFamily: "system-ui, Segoe UI, Roboto", color: "white" }}>
      <h1>RAG Chatbot</h1>
      <p>Backend URL: {import.meta.env.VITE_API_URL || "(same origin)"} </p>
      {status === "loading" && <p>Checking API...</p>}
      {status === "ok" && <p>✅ {msg}</p>}
      {status === "error" && <p>❌ {msg}</p>}

      <hr style={{ margin: "24px 0" }} />
      <h2>Upload a PDF or TXT</h2>
      <Upload />

      <h2 style={{ marginTop: 24 }}>Chat</h2>
      <Chat />
    </div>
  );
}
