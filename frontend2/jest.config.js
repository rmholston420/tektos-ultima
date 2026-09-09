/** @type {import('jest').Config} */
module.exports = {
  testEnvironment: "jsdom",
  setupFilesAfterEach: ["<rootDir>/jest.setup.ts"],
  moduleNameMapper: {
    "^@/(.*)$": "<rootDir>/src/$1",
    "\\.(css|less|scss)$": "identity-obj-proxy",
  },
  transform: { "^.+\\.(ts|tsx)$": ["ts-jest", { tsconfig: "tsconfig.json" }] },
  testMatch: ["<rootDir>/tests/unit/**/*.test.(ts|tsx)", "<rootDir>/src/**/*.test.(ts|tsx)"],
  moduleFileExtensions: ["ts", "tsx", "js", "jsx", "json"],
};
