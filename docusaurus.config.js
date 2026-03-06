// @ts-check
const { themes: prismThemes } = require("prism-react-renderer");

/** @type {import('@docusaurus/types').Config} */
const config = {
  title: "Agentest",
  tagline: "Universal testing and evaluation toolkit for AI agents",
  favicon: "img/favicon.ico",

  url: "https://ColinHarker.github.io",
  baseUrl: "/agentest/",

  organizationName: "ColinHarker",
  projectName: "agentest",

  onBrokenLinks: "throw",
  onBrokenMarkdownLinks: "warn",

  i18n: {
    defaultLocale: "en",
    locales: ["en"],
  },

  presets: [
    [
      "classic",
      /** @type {import('@docusaurus/preset-classic').Options} */
      ({
        docs: {
          sidebarPath: "./sidebars.js",
          editUrl: "https://github.com/ColinHarker/agentest/tree/main/",
          routeBasePath: "docs",
        },
        blog: false,
        theme: {
          customCss: "./src/css/custom.css",
        },
      }),
    ],
  ],

  themeConfig:
    /** @type {import('@docusaurus/preset-classic').ThemeConfig} */
    ({
      navbar: {
        title: "Agentest",
        items: [
          {
            type: "docSidebar",
            sidebarId: "docsSidebar",
            position: "left",
            label: "Docs",
          },
          {
            href: "https://github.com/ColinHarker/agentest",
            label: "GitHub",
            position: "right",
          },
        ],
      },
      footer: {
        style: "dark",
        links: [
          {
            title: "Docs",
            items: [
              { label: "Getting Started", to: "/docs/getting-started/installation" },
              { label: "User Guide", to: "/docs/guide/recording" },
              { label: "API Reference", to: "/docs/api/core" },
            ],
          },
          {
            title: "Community",
            items: [
              { label: "GitHub", href: "https://github.com/ColinHarker/agentest" },
              { label: "Issues", href: "https://github.com/ColinHarker/agentest/issues" },
            ],
          },
        ],
        copyright: `Copyright © ${new Date().getFullYear()} Agentest Contributors. Built with Docusaurus.`,
      },
      prism: {
        theme: prismThemes.github,
        darkTheme: prismThemes.dracula,
        additionalLanguages: ["bash", "python", "yaml"],
      },
      colorMode: {
        defaultMode: "light",
        respectPrefersColorScheme: true,
      },
    }),
};

module.exports = config;
