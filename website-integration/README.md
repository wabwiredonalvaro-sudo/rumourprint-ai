# Add RUMOURPRINT AI to the Fresh Exclusive Media website

Official target website: https://freshexclusivemedia.com/

**Purpose:** Let FEM visitors open the investigative web tool or download the Android beta directly from the FEM website.

## URLs

Web app: https://rumourprint-fem.streamlit.app/?embed=true

Android beta APK: https://github.com/wabwiredonalvaro-sudo/rumourprint-ai/releases/download/android-v0.1.0-beta.1/RUMOURPRINT-AI-Android-Beta.apk

GitHub beta release: https://github.com/wabwiredonalvaro-sudo/rumourprint-ai/releases/tag/android-v0.1.0-beta.1

## Website steps

1. Create a page titled **RUMOURPRINT AI** on freshexclusivemedia.com (suggested path `/rumourprint-ai`; not currently live).
2. Add it to your website's primary menu or a Tools submenu.
3. Insert the companion responsive HTML section `rumourprint-section.html`, or recreate its two buttons in your page builder.
4. Optionally embed the live investigation tool using the officially supported Streamlit iframe:
   `<iframe src="https://rumourprint-fem.streamlit.app/?embed=true" title="RUMOURPRINT AI" style="width:100%;height:900px;border:0"></iframe>`
5. Test on Android and desktop. Do not collect sensitive submissions in the current session-only prototype.

**Release warning:** The downloadable Android APK is a debug-signed **beta test build** for Android 8.0+ and requires internet. It is NOT production signed and not listed on Google Play. Future APK updates may require uninstall/reinstall because the debug signing key can change.

## Publishing

This repository hosts RUMOURPRINT AI, not the official Fresh Exclusive Media website's source. Editing the official domain requires the FEM website editor, connected CMS app, or its own code repository.
