import { useEffect, useRef, type ReactNode } from "react";
import { createPortal } from "react-dom";

interface Props {
  label: string;
  onClose: () => void;
  children: ReactNode;
  className?: string;
}

export function Modal({ label, onClose, children, className = "" }: Props) {
  const ref = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const dialog = ref.current;
    const previousFocus = document.activeElement;
    if (!dialog) return;
    dialog.showModal();
    return () => {
      dialog.close();
      if (previousFocus instanceof HTMLElement && previousFocus.isConnected) {
        previousFocus.focus();
      }
    };
  }, []);

  return createPortal(
    <dialog
      ref={ref}
      aria-label={label}
      className={`app-dialog ${className}`}
      onCancel={(event) => {
        event.preventDefault();
        onClose();
      }}
      onClick={(event) => {
        if (
          event.target === event.currentTarget &&
          className.includes("app-dialog--drawer")
        ) {
          onClose();
        }
      }}
    >
      {children}
    </dialog>,
    document.body,
  );
}
