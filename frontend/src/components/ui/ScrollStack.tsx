import {
  type ReactNode,
  useCallback,
  useLayoutEffect,
  useRef,
} from "react";
import Lenis from "lenis";

import { cn } from "@/components/ui/utils";

const prefersReducedMotion = () =>
  typeof window !== "undefined" &&
  window.matchMedia("(prefers-reduced-motion: reduce)").matches;

const isMobileViewport = () =>
  typeof window !== "undefined" && window.matchMedia("(max-width: 640px)").matches;

export interface ScrollStackItemProps {
  itemClassName?: string;
  children: ReactNode;
}

export function ScrollStackItem({ children, itemClassName = "" }: ScrollStackItemProps) {
  return (
    <div
      className={cn(
        "scroll-stack-card relative my-6 box-border flex h-[15rem] w-full origin-top flex-col justify-center rounded-[24px] border border-border bg-card p-7 text-left shadow-[0_24px_64px_-24px_rgba(15,23,42,0.32)] will-change-transform sm:my-8 sm:h-[19rem] sm:rounded-[32px] sm:p-12",
        itemClassName,
      )}
      style={{ backfaceVisibility: "hidden", transformStyle: "preserve-3d" }}
    >
      {children}
    </div>
  );
}

interface Transform {
  translateY: number;
  scale: number;
  rotation: number;
  blur: number;
}

interface ScrollStackProps {
  children: ReactNode;
  className?: string;
  itemDistance?: number;
  itemScale?: number;
  itemStackDistance?: number;
  stackPosition?: string;
  scaleEndPosition?: string;
  baseScale?: number;
  rotationAmount?: number;
  blurAmount?: number;
  useWindowScroll?: boolean;
  onStackComplete?: () => void;
}

export function ScrollStack({
  children,
  className = "",
  itemDistance = 100,
  itemScale = 0.03,
  itemStackDistance = 30,
  stackPosition = "20%",
  scaleEndPosition = "10%",
  baseScale = 0.85,
  rotationAmount = 0,
  blurAmount = 0,
  useWindowScroll = false,
  onStackComplete,
}: ScrollStackProps) {
  const reduce = prefersReducedMotion();
  const scrollerRef = useRef<HTMLDivElement>(null);
  const stackCompletedRef = useRef(false);
  const rafRef = useRef<number | null>(null);
  const lenisRef = useRef<Lenis | null>(null);
  const cardsRef = useRef<HTMLElement[]>([]);
  const lastTransformsRef = useRef(new Map<number, Transform>());
  const isUpdatingRef = useRef(false);

  const progress = useCallback((scroll: number, start: number, end: number) => {
    if (scroll < start) return 0;
    if (scroll > end) return 1;
    return (scroll - start) / (end - start);
  }, []);

  const toPx = useCallback((value: string, height: number) => {
    if (value.includes("%")) return (parseFloat(value) / 100) * height;
    return parseFloat(value);
  }, []);

  const getScroll = useCallback(() => {
    if (useWindowScroll) {
      return { scrollTop: window.scrollY, height: window.innerHeight };
    }
    const el = scrollerRef.current;
    return { scrollTop: el?.scrollTop ?? 0, height: el?.clientHeight ?? 0 };
  }, [useWindowScroll]);

  // offsetParent chain, not getBoundingClientRect: the card's own translateY must not feed back in.
  const offsetTop = useCallback(
    (el: HTMLElement) => {
      if (!useWindowScroll) return el.offsetTop;
      let y = 0;
      let node: HTMLElement | null = el;
      while (node) {
        y += node.offsetTop;
        node = node.offsetParent as HTMLElement | null;
      }
      return y;
    },
    [useWindowScroll],
  );

  const update = useCallback(() => {
    if (!cardsRef.current.length || isUpdatingRef.current) return;
    isUpdatingRef.current = true;

    const { scrollTop, height } = getScroll();
    const stackPx = toPx(stackPosition, height);
    const scaleEndPx = toPx(scaleEndPosition, height);
    const mobile = isMobileViewport();
    const stackDistance = mobile ? itemStackDistance * 0.6 : itemStackDistance;

    const endEl = (
      useWindowScroll ? document : (scrollerRef.current ?? document)
    ).querySelector(".scroll-stack-end") as HTMLElement | null;
    const endTop = endEl ? offsetTop(endEl) : 0;

    cardsRef.current.forEach((card, i) => {
      const cardTop = offsetTop(card);
      const triggerStart = cardTop - stackPx - stackDistance * i;
      const triggerEnd = cardTop - scaleEndPx;
      const pinStart = triggerStart;
      const pinEnd = endTop - height / 2;

      const scaleProgress = progress(scrollTop, triggerStart, triggerEnd);
      const targetScale = baseScale + i * itemScale;
      const scale = 1 - scaleProgress * (1 - targetScale);
      const rotation = rotationAmount ? i * rotationAmount * scaleProgress : 0;

      let blur = 0;
      if (blurAmount) {
        let topIndex = 0;
        for (let j = 0; j < cardsRef.current.length; j++) {
          const jStart = offsetTop(cardsRef.current[j]) - stackPx - stackDistance * j;
          if (scrollTop >= jStart) topIndex = j;
        }
        if (i < topIndex) blur = Math.max(0, (topIndex - i) * blurAmount);
      }

      let translateY = 0;
      const pinned = scrollTop >= pinStart && scrollTop <= pinEnd;
      if (pinned) {
        translateY = scrollTop - cardTop + stackPx + stackDistance * i;
      } else if (scrollTop > pinEnd) {
        translateY = pinEnd - cardTop + stackPx + stackDistance * i;
      }

      const next: Transform = {
        translateY: Math.round(translateY * 100) / 100,
        scale: Math.round(scale * 1000) / 1000,
        rotation: Math.round(rotation * 100) / 100,
        blur: Math.round(blur * 100) / 100,
      };
      const last = lastTransformsRef.current.get(i);
      const changed =
        !last ||
        Math.abs(last.translateY - next.translateY) > 0.1 ||
        Math.abs(last.scale - next.scale) > 0.001 ||
        Math.abs(last.rotation - next.rotation) > 0.1 ||
        Math.abs(last.blur - next.blur) > 0.1;

      if (changed) {
        card.style.transform = `translate3d(0, ${next.translateY}px, 0) scale(${next.scale}) rotate(${next.rotation}deg)`;
        card.style.filter = next.blur > 0 ? `blur(${next.blur}px)` : "";
        lastTransformsRef.current.set(i, next);
      }

      if (i === cardsRef.current.length - 1) {
        if (pinned && !stackCompletedRef.current) {
          stackCompletedRef.current = true;
          onStackComplete?.();
        } else if (!pinned && stackCompletedRef.current) {
          stackCompletedRef.current = false;
        }
      }
    });

    isUpdatingRef.current = false;
  }, [
    getScroll,
    offsetTop,
    toPx,
    progress,
    stackPosition,
    scaleEndPosition,
    itemStackDistance,
    itemScale,
    baseScale,
    rotationAmount,
    blurAmount,
    useWindowScroll,
    onStackComplete,
  ]);

  useLayoutEffect(() => {
    if (reduce) return;
    if (!useWindowScroll && !scrollerRef.current) return;

    const root = useWindowScroll ? document : scrollerRef.current!;
    const cards = Array.from(root.querySelectorAll(".scroll-stack-card")) as HTMLElement[];
    cardsRef.current = cards;
    const cache = lastTransformsRef.current;
    const mobile = isMobileViewport();
    const gap = mobile ? itemDistance * 0.55 : itemDistance;

    cards.forEach((card, i) => {
      if (i < cards.length - 1) card.style.marginBottom = `${gap}px`;
      card.style.willChange = "transform, filter";
      card.style.transformOrigin = "top center";
      card.style.backfaceVisibility = "hidden";
      card.style.transform = "translateZ(0)";
      card.style.perspective = "1000px";
    });

    const lenis = new Lenis({
      ...(useWindowScroll
        ? {}
        : {
            wrapper: scrollerRef.current!,
            content: scrollerRef.current!.querySelector(".scroll-stack-inner") as HTMLElement,
          }),
      duration: 1.2,
      easing: (t) => Math.min(1, 1.001 - Math.pow(2, -10 * t)),
      smoothWheel: true,
      touchMultiplier: 2,
      lerp: 0.1,
      syncTouch: true,
    });
    lenis.on("scroll", update);
    const raf = (time: number) => {
      lenis.raf(time);
      rafRef.current = requestAnimationFrame(raf);
    };
    rafRef.current = requestAnimationFrame(raf);
    lenisRef.current = lenis;
    update();

    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
      lenisRef.current?.destroy();
      stackCompletedRef.current = false;
      cardsRef.current = [];
      cache.clear();
      isUpdatingRef.current = false;
    };
  }, [reduce, useWindowScroll, itemDistance, update]);

  if (reduce) {
    return <div className={cn("flex flex-col gap-5", className)}>{children}</div>;
  }

  if (useWindowScroll) {
    return (
      <div className={cn("relative w-full", className)}>
        <div className="scroll-stack-inner pb-[9rem] pt-[6vh]">
          {children}
          <div className="scroll-stack-end h-px w-full" />
        </div>
      </div>
    );
  }

  return (
    <div
      ref={scrollerRef}
      className={cn("relative h-full w-full overflow-y-auto overflow-x-visible", className)}
      style={{ overscrollBehavior: "contain", willChange: "scroll-position" }}
    >
      <div className="scroll-stack-inner min-h-full px-4 pb-[20rem] pt-[14vh] sm:px-8">
        {children}
        <div className="scroll-stack-end h-px w-full" />
      </div>
    </div>
  );
}
