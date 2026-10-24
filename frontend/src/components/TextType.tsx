import {
  type ElementType,
  type ReactNode,
  createElement,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { gsap } from "gsap";

const prefersReducedMotion = () =>
  typeof window !== "undefined" &&
  window.matchMedia("(prefers-reduced-motion: reduce)").matches;

interface TextTypeProps {
  text: string | string[];
  as?: ElementType;
  typingSpeed?: number;
  initialDelay?: number;
  pauseDuration?: number;
  deletingSpeed?: number;
  loop?: boolean;
  className?: string;
  showCursor?: boolean;
  cursorCharacter?: ReactNode;
  cursorClassName?: string;
  cursorBlinkDuration?: number;
  highlightWords?: string[];
  highlightClassName?: string;
}

function withHighlight(
  shown: string,
  phrase: string,
  word: string | undefined,
  cls: string,
): ReactNode {
  if (!word) return shown;
  const start = phrase.indexOf(word);
  if (start < 0 || shown.length <= start) return shown;
  const end = Math.min(shown.length, start + word.length);
  return (
    <>
      {shown.slice(0, start)}
      <span className={cls}>{shown.slice(start, end)}</span>
      {shown.slice(end)}
    </>
  );
}

export function TextType({
  text,
  as: Component = "span",
  typingSpeed = 55,
  initialDelay = 0,
  pauseDuration = 1800,
  deletingSpeed = 35,
  loop = true,
  className = "",
  showCursor = true,
  cursorCharacter = "|",
  cursorClassName = "",
  cursorBlinkDuration = 0.5,
  highlightWords,
  highlightClassName = "",
}: TextTypeProps) {
  const textArray = useMemo(() => (Array.isArray(text) ? text : [text]), [text]);
  const reduce = prefersReducedMotion();
  const [displayed, setDisplayed] = useState("");
  const [charIndex, setCharIndex] = useState(0);
  const [isDeleting, setIsDeleting] = useState(false);
  const [textIndex, setTextIndex] = useState(0);
  const cursorRef = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    if (reduce || !showCursor || !cursorRef.current) return;
    gsap.set(cursorRef.current, { opacity: 1 });
    const tween = gsap.to(cursorRef.current, {
      opacity: 0,
      duration: cursorBlinkDuration,
      repeat: -1,
      yoyo: true,
      ease: "power2.inOut",
    });
    return () => {
      tween.kill();
    };
  }, [reduce, showCursor, cursorBlinkDuration]);

  useEffect(() => {
    if (reduce) return;
    const current = textArray[textIndex];
    let timeout: ReturnType<typeof setTimeout>;

    const tick = () => {
      if (isDeleting) {
        if (displayed === "") {
          setIsDeleting(false);
          if (textIndex === textArray.length - 1 && !loop) return;
          setTextIndex((p) => (p + 1) % textArray.length);
          setCharIndex(0);
        } else {
          timeout = setTimeout(() => setDisplayed((p) => p.slice(0, -1)), deletingSpeed);
        }
      } else if (charIndex < current.length) {
        timeout = setTimeout(() => {
          setDisplayed((p) => p + current[charIndex]);
          setCharIndex((p) => p + 1);
        }, typingSpeed);
      } else if (loop || textIndex !== textArray.length - 1) {
        timeout = setTimeout(() => setIsDeleting(true), pauseDuration);
      }
    };

    if (charIndex === 0 && !isDeleting && displayed === "") {
      timeout = setTimeout(tick, initialDelay);
    } else {
      tick();
    }
    return () => clearTimeout(timeout);
  }, [
    reduce,
    charIndex,
    displayed,
    isDeleting,
    textIndex,
    textArray,
    typingSpeed,
    deletingSpeed,
    pauseDuration,
    loop,
    initialDelay,
  ]);

  if (reduce) {
    return createElement(
      Component,
      { className },
      withHighlight(textArray[0], textArray[0], highlightWords?.[0], highlightClassName),
    );
  }

  return createElement(
    Component,
    { className: `inline whitespace-pre-wrap ${className}` },
    <span>
      {withHighlight(
        displayed,
        textArray[textIndex] ?? "",
        highlightWords?.[textIndex],
        highlightClassName,
      )}
    </span>,
    showCursor && (
      <span ref={cursorRef} className={`ml-0.5 inline-block ${cursorClassName}`}>
        {cursorCharacter}
      </span>
    ),
  );
}
