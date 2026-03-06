/** @type {import('@docusaurus/plugin-content-docs').SidebarsConfig} */
const sidebars = {
  docsSidebar: [
    "index",
    {
      type: "category",
      label: "Getting Started",
      items: [
        "getting-started/installation",
        "getting-started/quickstart",
      ],
    },
    {
      type: "category",
      label: "User Guide",
      items: [
        "guide/recording",
        "guide/replaying",
        "guide/mocking",
        "guide/evaluators",
        "guide/benchmarking",
        "guide/mcp-testing",
        "guide/integrations",
        "guide/pytest",
        "guide/cli",
        "guide/web-ui",
      ],
    },
    {
      type: "category",
      label: "API Reference",
      items: [
        "api/core",
        "api/recorder",
        "api/replayer",
        "api/mocking",
        "api/evaluators",
        "api/benchmark",
        "api/mcp",
        "api/integrations",
        "api/reporters",
      ],
    },
    "contributing",
    "changelog",
  ],
};

module.exports = sidebars;
