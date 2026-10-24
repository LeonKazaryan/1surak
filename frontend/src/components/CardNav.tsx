import { type ReactNode, useEffect, useLayoutEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowUpRight } from "lucide-react";
import { gsap } from "gsap";

import { Logo } from "./Logo";

interface CardNavLink {
  label: string;
  href: string;
}

export interface CardNavItem {
  label: string;
  bgColor: string;
  textColor: string;
  links: CardNavLink[];
  dark?: boolean;
}

interface CardNavProps {
  items: CardNavItem[];
  action?: ReactNode;
  ease?: string;
  baseColor?: string;
  menuColor?: string;
}

const TOP_BAR = 64;

export function CardNav({
  items,
  action,
  ease = "power3.out",
  baseColor = "#ffffff",
  menuColor = "#0f172a",
}: CardNavProps) {
  const navigate = useNavigate();
  const [isHamburgerOpen, setIsHamburgerOpen] = useState(false);
  const [isExpanded, setIsExpanded] = useState(false);
  const navRef = useRef<HTMLDivElement | null>(null);
  const cardsRef = useRef<HTMLDivElement[]>([]);
  const tlRef = useRef<gsap.core.Timeline | null>(null);

  const calculateHeight = () => {
    const navEl = navRef.current;
    if (!navEl) return 280;
    const isMobile = window.matchMedia("(max-width: 768px)").matches;
    if (isMobile) {
      const contentEl = navEl.querySelector(".card-nav-content") as HTMLElement | null;
      if (contentEl) {
        const prev = {
          v: contentEl.style.visibility,
          p: contentEl.style.pointerEvents,
          pos: contentEl.style.position,
          h: contentEl.style.height,
        };
        contentEl.style.visibility = "visible";
        contentEl.style.pointerEvents = "auto";
        contentEl.style.position = "static";
        contentEl.style.height = "auto";
        void contentEl.offsetHeight;
        const height = TOP_BAR + contentEl.scrollHeight + 16;
        contentEl.style.visibility = prev.v;
        contentEl.style.pointerEvents = prev.p;
        contentEl.style.position = prev.pos;
        contentEl.style.height = prev.h;
        return height;
      }
    }
    return 280;
  };

  const createTimeline = () => {
    const navEl = navRef.current;
    if (!navEl) return null;
    gsap.set(navEl, { height: TOP_BAR, overflow: "hidden" });
    gsap.set(cardsRef.current, { y: 40, opacity: 0 });
    const tl = gsap.timeline({ paused: true });
    tl.to(navEl, { height: calculateHeight, duration: 0.4, ease });
    tl.to(
      cardsRef.current,
      { y: 0, opacity: 1, duration: 0.4, ease, stagger: 0.08 },
      "-=0.1",
    );
    return tl;
  };

  useLayoutEffect(() => {
    const tl = createTimeline();
    tlRef.current = tl;
    return () => {
      tl?.kill();
      tlRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ease, items]);

  const openMenu = () => {
    const tl = tlRef.current;
    if (!tl) return;
    setIsHamburgerOpen(true);
    setIsExpanded(true);
    tl.play(0);
  };

  const closeMenu = () => {
    const tl = tlRef.current;
    if (!tl) return;
    setIsHamburgerOpen(false);
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

  const go = (href: string) => {
    toggleMenu();
    if (href.startsWith("#")) {
      document
        .getElementById(href.slice(1))
        ?.scrollIntoView({ behavior: "smooth", block: "start" });
      return;
    }
    navigate(href);
  };

  const setCardRef = (i: number) => (el: HTMLDivElement | null) => {
    if (el) cardsRef.current[i] = el;
  };

  return (
    <div className="fixed left-1/2 top-3 z-50 w-[92%] max-w-3xl -translate-x-1/2 px-0">
      <div
        ref={navRef}
        className="relative block h-16 overflow-hidden rounded-2xl border border-border/70 p-0 shadow-md ring-1 ring-white/40 backdrop-blur-md will-change-[height]"
        style={{ backgroundColor: baseColor }}
      >
        <div className="absolute inset-x-0 top-0 z-[2] flex h-16 items-center justify-between gap-3 px-4">
          <Logo />

          <div className="flex items-center gap-2">
            {action}
            <button
              type="button"
              onClick={toggleMenu}
              aria-label={isExpanded ? "Закрыть меню" : "Открыть меню"}
              aria-expanded={isExpanded}
              className="group flex h-9 w-9 cursor-pointer flex-col items-center justify-center gap-[6px] rounded-lg hover:bg-secondary"
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

        <div
          className={`card-nav-content absolute inset-x-0 bottom-0 top-16 z-[1] flex flex-col items-stretch justify-start gap-2 p-2 md:flex-row md:items-end md:gap-3 ${
            isExpanded ? "pointer-events-auto visible" : "pointer-events-none invisible"
          }`}
          aria-hidden={!isExpanded}
        >
          {items.slice(0, 3).map((item, idx) => (
            <div
              key={`${item.label}-${idx}`}
              ref={setCardRef(idx)}
              className="relative flex h-auto min-h-[80px] min-w-0 flex-[1_1_auto] select-none flex-col gap-2 rounded-xl px-4 py-3 md:h-full md:min-h-0 md:flex-[1_1_0%]"
              style={{ backgroundColor: item.bgColor, color: item.textColor }}
            >
              <div className="text-[17px] font-medium tracking-tight md:text-lg">
                {item.label}
              </div>
              <div className="mt-auto flex flex-col gap-1.5">
                {item.links.map((lnk, i) => (
                  <button
                    key={`${lnk.label}-${i}`}
                    type="button"
                    onClick={() => go(lnk.href)}
                    className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-2 text-left text-[14px] font-medium transition-colors ${
                      item.dark
                        ? "bg-white/15 hover:bg-white/25"
                        : "bg-white/70 shadow-sm hover:bg-white"
                    }`}
                  >
                    <ArrowUpRight className="h-4 w-4 shrink-0" aria-hidden />
                    {lnk.label}
                  </button>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
