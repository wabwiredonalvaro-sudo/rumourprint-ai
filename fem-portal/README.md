# RUMOURPRINT AI — FEM branded page (without old ChatGPT Work account)

This folder is a standalone static site for Cloudflare Pages. It does NOT edit the original ChatGPT Sites project or main FEM homepage.

## Publish under ai.freshexclusivemedia.com

1. Sign in to the Cloudflare account managing freshexclusivemedia.com.
2. Workers & Pages → Create application → Pages → Import an existing Git repository.
3. Connect GitHub repository: `wabwiredonalvaro-sudo/rumourprint-ai` (authorize if necessary).
4. Project name: `fem-rumourprint-ai` (or an available alternative).
5. Branch: `main`.
6. Framework preset: None.
7. Build command: `exit 0` (or leave blank).
8. Build output directory: `fem-portal`.
9. Root directory: repository root (leave default).
10. Deploy. Check the generated `*.pages.dev` URL before changing the domain.
11. On this new Pages project: Custom domains → Add custom domain → `ai.freshexclusivemedia.com`.
12. Follow Cloudflare's DNS prompts. If Cloudflare manages the domain in the same account, it may add the needed CNAME automatically. Confirm no existing record at `ai` needs preservation.

This DOES NOT edit the ChatGPT Sites-hosted main site or add a homepage menu entry. Adding a visible link to the original FEM homepage requires recovering edit access to that site.

## Links on the page

Launch: https://rumourprint-fem.streamlit.app/?embed=true

Download APK: https://github.com/wabwiredonalvaro-sudo/rumourprint-ai/releases/download/android-v0.1.0-beta.1/RUMOURPRINT-AI-Android-Beta.apk

NOTE: APK is an Android 8.0+ debug-signed beta for testing. It is not a Play Store production build.

Reference: https://developers.cloudflare.com/pages/framework-guides/deploy-anything/
