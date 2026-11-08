"use client";
import * as React from "react";
import { cn } from "@/lib/utils";

export interface SliderProps {
  value: number;
  min: number;
  max: number;
  step: number;
  onChange: (v: number) => void;
  className?: string;
  "aria-label"?: string;
}

/** Native range input styled via .rl-range in globals.css. */
export function Slider({ value, min, max, step, onChange, className, ...rest }: SliderProps) {
  return (
    <input
      type="range"
      className={cn("rl-range", className)}
      value={value}
      min={min}
      max={max}
      step={step}
      onChange={(e) => onChange(Number(e.target.value))}
      {...rest}
    />
  );
}
