import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { X } from "lucide-react";
import { apiDownload } from "../api/apiConfig";
import { FeedbackContext, type DialogRequest } from "./feedbackContext";
import { Modal } from "./Modal";

export function FeedbackProvider({ children }: { children: ReactNode }) {
  const [notice, setNotice] = useState<{
    message: string;
    kind: "success" | "error";
  } | null>(null);
  const [dialog, setDialog] = useState<DialogRequest | null>(null);

  const notify = useCallback(
    (message: string, kind: "success" | "error" = "error") => {
      setNotice({ message, kind });
    },
    [],
  );

  useEffect(() => {
    if (!notice) return;
    const delay = notice.kind === "success" ? 5000 : 8000;
    const timer = window.setTimeout(() => setNotice(null), delay);
    return () => window.clearTimeout(timer);
  }, [notice]);

  const download = useCallback(
    async (url: string, filename: string) => {
      try {
        await apiDownload(url, filename);
      } catch (error) {
        notify(
          error instanceof Error ? error.message : "Не удалось скачать файл",
        );
      }
    },
    [notify],
  );

  const feedback = useMemo(
    () => ({ notify, showDialog: setDialog, download }),
    [notify, download],
  );

  return (
    <FeedbackContext.Provider value={feedback}>
      {children}
      {notice && (
        <div
          className={`app-toast notice notice--${notice.kind === "error" ? "danger" : "success"}`}
        >
          <span role={notice.kind === "error" ? "alert" : "status"}>
            {notice.message}
          </span>
          <button
            type="button"
            className="button-icon"
            aria-label="Закрыть уведомление"
            onClick={() => setNotice(null)}
          >
            <X size={16} />
          </button>
        </div>
      )}
      {dialog && (
        <Modal label={dialog.title} onClose={() => setDialog(null)}>
          <div className="app-dialog__body">
            <h2>{dialog.title}</h2>
            {dialog.message && (
              <p className="app-dialog__message">{dialog.message}</p>
            )}
            {dialog.copyValue && (
              <input
                className="app-field"
                readOnly
                value={dialog.copyValue}
                aria-label="Ссылка на расчёт"
                onFocus={(event) => event.currentTarget.select()}
              />
            )}
            <div className="app-dialog__actions">
              <button
                type="button"
                className="btn-secondary"
                onClick={() => setDialog(null)}
              >
                {dialog.onConfirm ? "Отмена" : "Закрыть"}
              </button>
              {dialog.onConfirm && (
                <button
                  type="button"
                  className="btn-primary"
                  onClick={() => {
                    setDialog(null);
                    dialog.onConfirm?.();
                  }}
                >
                  {dialog.confirmLabel || "Подтвердить"}
                </button>
              )}
            </div>
          </div>
        </Modal>
      )}
    </FeedbackContext.Provider>
  );
}
