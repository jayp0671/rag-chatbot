import { useState } from "react";
import { api } from "../lib/api";

export default function Upload() {
  const [doc, setDoc] = useState<{ document_id: string; title: string } | null>(null);
  const [error, setError] = useState("");

  async function handleFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    const form = new FormData();
    form.append("file", file);
    try {
      const { data } = await api.post("/upload", form, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      setDoc(data);
      setError("");
    } catch (err: any) {
      setError(err.message || "Upload failed");
    }
  }

  return (
    <div>
      <input type="file" accept=".pdf,.txt" onChange={handleFile} />
      {doc && (
        <p>
          ✅ Uploaded {doc.title} with id {doc.document_id}
        </p>
      )}
      {error && <p style={{ color: "red" }}>{error}</p>}
    </div>
  );
}
