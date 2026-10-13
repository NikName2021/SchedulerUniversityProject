import { useEffect, useId, useRef, useState, type ButtonHTMLAttributes } from "react";
import { createPortal } from "react-dom";

type ActionButtonProps = Omit<
  ButtonHTMLAttributes<HTMLButtonElement>,
  "title"
> & {
  label: string;
};

/** Immediate, keyboard-accessible hints outside the registry's overflow area. */
export const ActionButton = ({
  label,
  children,
  ...props
}: ActionButtonProps) => {
  const id = useId();
  const buttonRef = useRef<HTMLButtonElement>(null);
  const [anchor, setAnchor] = useState<DOMRect | null>(null);

  const isOpen = anchor !== null;

  useEffect(() => {
    if (!isOpen) return;
    const close = () => setAnchor(null);
    const reposition = () => {
      const rect = buttonRef.current?.getBoundingClientRect();
      setAnchor(rect && rect.bottom > 0 && rect.top < window.innerHeight ? rect : null);
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") close();
    };
    window.addEventListener("scroll", reposition, true);
    window.addEventListener("resize", reposition);
    window.addEventListener("keydown", onKeyDown);
    return () => {
      window.removeEventListener("scroll", reposition, true);
      window.removeEventListener("resize", reposition);
      window.removeEventListener("keydown", onKeyDown);
    };
  }, [isOpen]);

  const width = Math.min(260, window.innerWidth - 16);
  const below = anchor !== null && anchor.top < 80;

  return (
    <>
      <button
        {...props}
        ref={buttonRef}
        aria-label={label}
        aria-describedby={anchor ? id : undefined}
        onMouseEnter={(event) =>
          setAnchor(event.currentTarget.getBoundingClientRect())
        }
        onMouseLeave={() => setAnchor(null)}
        onFocus={(event) =>
          setAnchor(event.currentTarget.getBoundingClientRect())
        }
        onBlur={() => setAnchor(null)}
      >
        {children}
      </button>
      {anchor &&
        createPortal(
          <span
            id={id}
            role="tooltip"
            className="action-tooltip"
            style={{
              width,
              left: Math.max(
                8,
                Math.min(
                  anchor.left + anchor.width / 2 - width / 2,
                  window.innerWidth - width - 8,
                ),
              ),
              top: below ? anchor.bottom + 8 : anchor.top - 8,
              transform: below ? undefined : "translateY(-100%)",
            }}
          >
            {label}
          </span>,
          document.body,
        )}
    </>
  );
};
