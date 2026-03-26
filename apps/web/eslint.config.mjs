import nextConfig from "@tenue/config-eslint/next";
import nextPlugin from "@next/eslint-plugin-next";

export default [
  ...nextConfig,
  {
    files: ["**/*.{js,jsx,ts,tsx}"],
    plugins: {
      "@next/next": nextPlugin
    },
    rules: {
      ...nextPlugin.configs.recommended.rules,
      ...nextPlugin.configs["core-web-vitals"].rules
    }
  }
];
