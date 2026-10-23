"use client";

import { motion, type HTMLMotionProps, type Variants } from "framer-motion";

export type ButtonTone = "acid" | "hazard" | "radar" | "magenta" | "crimson" | "canvas";
export type ButtonSize = "md" | "sm";

const TONES: Record<ButtonTone, string> = {
  acid: "bg-acid text-ink",
  hazard: "bg-hazard text-ink",
  radar: "bg-radar text-ink",
  magenta: "bg-magenta text-ink",
  crimson: "bg-crimson text-canvas",
  canvas: "bg-canvas text-ink",
};

/** Tombol fisik: hover menekan setengah jalan, tap menekan penuh sampai bayangan hitam tertutup. */
const PRESS: Record<ButtonSize, Variants> = {
  md: {
    rest: { x: 0, y: 0, boxShadow: "8px 8px 0px 0px #000000" },
    hover: { x: 4, y: 4, boxShadow: "4px 4px 0px 0px #000000" },
    tap: { x: 8, y: 8, boxShadow: "0px 0px 0px 0px #000000" },
  },
  sm: {
    rest: { x: 0, y: 0, boxShadow: "4px 4px 0px 0px #000000" },
    hover: { x: 2, y: 2, boxShadow: "2px 2px 0px 0px #000000" },
    tap: { x: 4, y: 4, boxShadow: "0px 0px 0px 0px #000000" },
  },
};

const SIZES: Record<ButtonSize, string> = {
  md: "px-6 py-3 text-lg",
  sm: "px-3 py-1 text-sm",
};

type BrutalButtonProps = Omit<
  HTMLMotionProps<"button">,
  "variants" | "initial" | "animate" | "whileHover" | "whileTap" | "transition"
> & { tone?: ButtonTone; size?: ButtonSize };

export function BrutalButton({
  tone = "acid",
  size = "md",
  className = "",
  disabled,
  children,
  ...rest
}: BrutalButtonProps) {
  return (
    <motion.button
      type="button"
      variants={PRESS[size]}
      initial="rest"
      animate="rest"
      whileHover={disabled ? undefined : "hover"}
      whileTap={disabled ? undefined : "tap"}
      transition={{ type: "spring", stiffness: 900, damping: 40, mass: 0.6 }}
      disabled={disabled}
      className={`rounded-none border-4 border-ink font-display font-bold uppercase tracking-tight disabled:cursor-not-allowed disabled:bg-concrete disabled:text-ink ${SIZES[size]} ${TONES[tone]} ${className}`}
      {...rest}
    >
      {children}
    </motion.button>
  );
}
