const base = require("./base.cjs");

module.exports = [
  ...base,
  {
    files: ["**/*.{ts,tsx}"],
    rules: {
      "no-undef": "off"
    }
  }
];
