import {
  Children,
  cloneElement,
  isValidElement,
  type CSSProperties,
  type ReactElement,
  type ReactNode,
} from "react";

type Revealable = ReactElement<{ className?: string; style?: CSSProperties }>;

/**
 * The only entrance motion in the app: fade plus a 14px rise, 420ms ease-out,
 * 70ms between siblings.
 *
 * It clones its children rather than wrapping them in an element, so it can be
 * dropped inside a grid or a flex row without becoming an extra layout box —
 * `.candidate-grid > *` and `.need-cards > *` still address the real children.
 *
 * Honouring prefers-reduced-motion is the stylesheet's job (see `.reveal`),
 * not this component's, so there is no media query to keep in sync here.
 */
export function Reveal({
  children,
  delay = 0,
  step = 70,
}: {
  children: ReactNode;
  /** Milliseconds before the first child starts. */
  delay?: number;
  /** Milliseconds between siblings. */
  step?: number;
}) {
  let index = 0;
  return (
    <>
      {Children.map(children, (child) => {
        if (!isValidElement(child)) return child;
        const element = child as Revealable;
        const at = delay + index * step;
        index += 1;
        return cloneElement(element, {
          className: `${element.props.className ?? ""} reveal`.trim(),
          style: { ...element.props.style, animationDelay: `${at}ms` },
        });
      })}
    </>
  );
}
