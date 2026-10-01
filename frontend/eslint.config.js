import js from "@eslint/js";
import globals from "globals";
import reactHooks from "eslint-plugin-react-hooks";
import tseslint from "typescript-eslint";

export default tseslint.config(
  { ignores: ["dist", "node_modules"] },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    files: ["**/*.{ts,tsx}"],
    languageOptions: {
      globals: { ...globals.browser, ...globals.es2020 },
    },
    plugins: { "react-hooks": reactHooks },
    // The two classic rules only. eslint-plugin-react-hooks' `recommended` now
    // also carries the compiler-based rules, whose `set-state-in-effect` check
    // rejects the ordinary `setLoading(true)` at the top of a fetch effect --
    // which is how every data-loading effect in this app is written. Enabling
    // rules that fire on correct code teaches people to ignore the linter.
    rules: {
      "react-hooks/rules-of-hooks": "error",
      "react-hooks/exhaustive-deps": "warn",
    },
  },
);
