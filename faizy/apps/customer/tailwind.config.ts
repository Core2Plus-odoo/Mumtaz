import type { Config } from "tailwindcss";
import { faizyPreset } from "@faizy/brand/tailwind";

export default {
  presets: [faizyPreset],
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    // Shared components live outside this app, so Tailwind must scan them too
    // or their classes get tree-shaken out of the build.
    "../../packages/ui/src/**/*.{ts,tsx}",
  ],
} satisfies Config;
