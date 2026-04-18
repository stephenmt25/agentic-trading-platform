"use client";

import { useState, useRef, useEffect } from "react";
import { createPortal } from "react-dom";
import { Info } from "lucide-react";

interface InfoTooltipProps {
  text: string;
  className?: string;
}

export function InfoTooltip({ text, className = "" }: InfoTooltipProps) {
  const [visible, setVisible] = useState(false);
  const [coords, setCoords] = useState({ top: 0, left: 0 });
  const triggerRef = useRef<HTMLButtonElement>(null);
  const showTimeout = useRef<ReturnType<typeof setTimeout>>(undefined);
  const hideTimeout = useRef<ReturnType<typeof setTimeout>>(undefined);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    return () => setMounted(false);
  }, []);

  const show = () => {
    clearTimeout(hideTimeout.current);
    showTimeout.current = setTimeout(() => {
      if (triggerRef.current) {
        const rect = triggerRef.current.getBoundingClientRect();
        const tooltipWidth = 360;

        // Vertical: prefer above, fall back to below
        const above = rect.top > 120;
        const top = above ? rect.top - 8 : rect.bottom + 8;

        // Horizontal: center on icon, but clamp to viewport
        let left = rect.left + rect.width / 2 - tooltipWidth / 2;
        left = Math.max(8, Math.min(left, window.innerWidth - tooltipWidth - 8));

        setCoords({ top, left });
      }
      setVisible(true);
    }, 200);
  };

  const hide = () => {
    clearTimeout(showTimeout.current);
    hideTimeout.current = setTimeout(() => setVisible(false), 100);
  };

  useEffect(() => {
    return () => {
      clearTimeout(showTimeout.current);
      clearTimeout(hideTimeout.current);
    };
  }, []);

  const above = triggerRef.current
    ? triggerRef.current.getBoundingClientRect().top > 120
    : true;

  return (
    <span className={`relative inline-flex ${className}`}>
      <button
        ref={triggerRef}
        onMouseEnter={show}
        onMouseLeave={hide}
        onFocus={show}
        onBlur={hide}
        aria-describedby={visible ? "info-tooltip" : undefined}
        className="text-muted-foreground hover:text-foreground transition-colors p-0.5 rounded focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
        type="button"
        tabIndex={0}
      >
        <Info className="w-3.5 h-3.5" aria-hidden="true" />
        <span className="sr-only">More info</span>
      </button>
      {visible &&
        mounted &&
        createPortal(
          <div
            id="info-tooltip"
            role="tooltip"
            onMouseEnter={() => clearTimeout(hideTimeout.current)}
            onMouseLeave={hide}
            style={{
              position: "fixed",
              top: above ? undefined : coords.top,
              bottom: above ? window.innerHeight - coords.top : undefined,
              left: coords.left,
              width: 360,
              maxWidth: "90vw",
              zIndex: 9999,
            }}
            className="bg-popover text-foreground text-xs leading-relaxed rounded-md p-3 shadow-lg border border-border"
          >
            {text}
          </div>,
          document.body
        )}
    </span>
  );
}
