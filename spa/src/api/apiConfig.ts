import { downloadResponse, openDownload } from "../utils/openDownload";

export const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL as string) || "";

export { downloadResponse, openDownload };
