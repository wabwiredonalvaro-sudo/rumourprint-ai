# FEM Tools portal: RUMOURPRINT AI

This is an independent static landing page. It does not overwrite, edit or assume access to the existing ChatGPT Sites website at **freshexclusivemedia.com**.

## Current verified destinations

- Web app: https://rumourprint-fem.streamlit.app/?embed=true
- Android testing APK: https://github.com/wabwiredonalvaro-sudo/rumourprint-ai/releases/download/android-v0.1.0-beta.1/RUMOURPRINT-AI-Android-Beta.apk
- Android beta release notes: https://github.com/wabwiredonalvaro-sudo/rumourprint-ai/releases/tag/android-v0.1.0-beta.1

## Deploy on Cloudflare Pages from this GitHub repo

In Cloudflare: Workers & Pages > Create > Pages > Connect to Git > select `wabwiredonalvaro-sudo/rumourprint-ai`.

Production branch: `main`
Project name suggestion: `fem-tools` (must be available)
Framework preset: `None`
Root directory (advanced): `fem-tools-site`
Build command: `exit 0`
Build output directory: `.`

Click Save and Deploy. Cloudflare will show your actual project `*.pages.dev` URL.

In the new Pages project's **Custom domains**, add `tools.freshexclusivemedia.com` if that subdomain is available in the Cloudflare zone. Complete Cloudflare's prompted DNS steps. Do not replace `@`, `www`, the current ChatGPT Sites CNAME or the live root domain.

This creates **an independent FEM tools portal** that can be linked/shared right away. It does not add a navigation link to the original ChatGPT Sites homepage; that still requires the original editor or a separate authorised update to the existing site.

## Limitations

The linked APK is a DEBUG-SIGNED beta, not a production-signed app-store installer. Both the web and Android clients require internet. Data is stored per session without guaranteed persistence. Do not submit confidential information.
