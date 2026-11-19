import { createContext, useContext } from "react";

export interface DialogRequest {
  title: string;
  message?: string;
  confirmLabel?: string;
  copyValue?: string;
  onConfirm?: () => void;
}

export interface PageFeedback {
  notify: (message: string, kind?: "success" | "error") => void;
  showDialog: (request: DialogRequest) => void;
  download: (url: string, filename: string) => Promise<void>;
}

export const FeedbackContext = createContext<PageFeedback | null>(null);

export function useFeedback() {
  const feedback = useContext(FeedbackContext);
  if (!feedback) throw new Error("Missing feedback provider");
  return feedback;
}
