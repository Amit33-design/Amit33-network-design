/// <reference types="vite/client" />

// react-plotly.js pulls in the prebuilt dist bundle, which ships no types.
declare module "plotly.js-dist-min";
