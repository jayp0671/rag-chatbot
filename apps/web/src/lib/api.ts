import axios from "axios";

const baseURL =
  (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/+$/, "") || "";

export const api = axios.create({
  baseURL,
  timeout: 30000,
  headers: { "Content-Type": "application/json" },
});

export async function getHealth() {
  const { data } = await api.get("/health");
  return data;
}
