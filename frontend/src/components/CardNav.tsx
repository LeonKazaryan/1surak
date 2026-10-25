import { type ReactNode, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { gsap } from "gsap";

import { CardNavGoContext, type CardNavGo } from "./cardNavGo";
import { Logo } from "./Logo";

interface CardNavProps {
  /** The menu body. Each part marked `data-nav-card` rises in on open. */
  children: ReactNode;
  action?: ReactNode;
  ease?: string;
  baseColor?: string;
  menuColor?: string;
}

const TOP_BAR = 64;

export function CardNav({
  children,
  action,
  ease = "power3.out",
  baseColor = "#ffffff",
  menuColor = "#0f172a",
}: CardNavProps) {
  const navigate = useNavigate();
  const [isHamburgerOpen, setIsHamburgerOpen] = useState(false);
  const [isExpanded, setIsExpanded] = useState(false);
  const navRef = useRef<HTMLDivElement | null>(null);
  const contentRef = useRef<HTMLElement | null>(null);
  const tlRef = useRef<gsap.core.Timeline | null>(null);

  useEffect(() => () => void tlRef.current?.kill(), []);

  const contentHeight = () => {
    const el = contentRef.current;
    if (!el) return 0;
    const prev = { position: el.style.position, height: el.style.height };
    el.style.position = "static";
    el.style.height = "auto";
    const height = el.offsetHeight;
    el.style.position = prev.position;
    el.style.height = prev.height;
    return height;
  };

  // shortcut: the height is measured on open, so content that grows while open is clipped; observe it if that starts to matter.
  const openMenu = () => {
    const navEl = navRef.current;
    if (!navEl) return;
    tlRef.current?.kill();
    const cards = navEl.querySelectorAll("[data-nav-card]");
    gsap.set(cards, { y: 32, opacity: 0 });
    const tl = gsap.timeline();
    tl.to(navEl, { height: TOP_BAR + contentHeight(), duration: 0.4, ease });
    tl.to(cards, { y: 0, opacity: 1, duration: 0.4, ease, stagger: 0.08 }, "-=0.1");
    tlRef.current = tl;
    setIsHamburgerOpen(true);
    setIsExpanded(true);
  };

  const closeMenu = () => {
    setIsHamburgerOpen(false);
    const tl = tlRef.current;
    if (!tl) {
      setIsExpanded(false);
      return;
    }
    tl.eventCallback("onReverseComplete", () => setIsExpanded(false));
    tl.reverse();
  };

  const toggleMenu = () => {
    if (isExpanded) closeMenu();
    else openMenu();
  };

  useEffect(() => {
    if (!isExpanded) return;
    const onPointerDown = (e: PointerEvent) => {
      if (navRef.current && !navRef.current.contains(e.target as Node)) closeMenu();
    };
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") closeMenu();
    };
    document.addEventListener("pointerdown", onPointerDown, true);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("pointerdown", onPointerDown, true);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [isExpanded]);

  const go: CardNavGo = (href, state) => {
    closeMenu();
    if (href.startsWith("#")) {
      document
        .getElementById(href.slice(1))
        ?.scrollIntoView({ behavior: "smooth", block: "start" });
      return;
    }
    navigate(href, { state, viewTransition: true });
  };

  return (
    <div className="fixed left-1/2 top-3 z-50 w-[92%] max-w-3xl -translate-x-1/2 px-0">
      <div
        ref={navRef}
        className="relative block h-16 overflow-hidden rounded-3xl border border-border/70 p-0 shadow-md ring-1 ring-white/40 backdrop-blur-md will-change-[height]"
        style={{ backgroundColor: baseColor }}
      >
        <div className="absolute inset-x-0 top-0 z-[2] flex h-16 items-center justify-between gap-3 px-6 max-sm:gap-2 max-sm:px-4">
          <Logo />

          <div className="flex items-center gap-2">
            {action}
            <button
              type="button"
              onClick={toggleMenu}
              aria-label={isExpanded ? "Закрыть меню" : "Открыть меню"}
              aria-expanded={isExpanded}
              className="group -mr-1.5 flex h-9 w-9 cursor-pointer flex-col items-center justify-center gap-[6px] rounded-lg hover:bg-secondary"
              style={{ color: menuColor }}
            >
              <span
                className={`h-[2px] w-[22px] bg-current transition-transform duration-300 ${
                  isHamburgerOpen ? "translate-y-[4px] rotate-45" : ""
                }`}
              />
              <span
                className={`h-[2px] w-[22px] bg-current transition-transform duration-300 ${
                  isHamburgerOpen ? "-translate-y-[4px] -rotate-45" : ""
                }`}
              />
            </button>
          </div>
        </div>

        <nav
          ref={contentRef}
          aria-label="Разделы"
          aria-hidden={!isExpanded}
          className={`card-nav-content absolute inset-x-0 bottom-0 top-16 z-[1] px-2 pb-2 ${
            isExpanded ? "pointer-events-auto visible" : "pointer-events-none invisible"
          }`}
        >
          <CardNavGoContext value={go}>{children}</CardNavGoContext>
        </nav>
      </div>
    </div>
  );
}
