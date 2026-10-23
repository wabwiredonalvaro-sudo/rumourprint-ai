# RUMOURPRINT AI — Android application

**Powered by Fresh Exclusive Media**

This is an Android application source project that opens the existing RUMOURPRINT AI investigation service in a native Android WebView. It features an Android launcher icon, branded header, reload control, network failure screen, and a button to open the website in a browser for downloads.

## Requirements
- Android Studio with Android SDK Platform 35 / Build Tools 35
- JDK 17 (Android Studio can supply it)
- Android 8.0 or newer phone
- Internet connection

## Method 1 — Get a test APK automatically from GitHub

1. Open your GitHub repository and select **Actions**.
2. Open the workflow **Build RUMOURPRINT Android APK**.
3. Select its latest successful run or choose **Run workflow**.
4. Under **Artifacts**, download `RUMOURPRINT-AI-Android-debug-APK`.
5. Unzip it to get `app-debug.apk`.
6. Transfer the APK to an Android phone and install it, approving the relevant Android security prompt only if you trust the source.

The debug APK is for testing, **not a release-signed production installer**. Never distribute debug APKs as an official Play Store release.

## Method 2 — Build using Android Studio

1. In Android Studio, choose **Open** and select the `android-app` folder.
2. Let Gradle sync and install any prompted Android SDK components.
3. Select **Build > Build Bundle(s) / APK(s) > Build APK(s)**.
4. Find the output at `app/build/outputs/apk/debug/app-debug.apk`.

## Important limitations

- The AI model runs on the existing Streamlit-hosted server; the app **requires internet**.
- Claim data is currently temporary and session-based.
- For exporting reports through Streamlit's blob downloads, tap the ↗ native action to open the full site in the phone's browser.
- The wrapper does **not** add user accounts, encrypted permanent storage, offline AI or native push notifications.
- Before publishing on Google Play, create a **release-signed APK/AAB**, privacy policy, support/contact page, store listing, and verify Play policy compliance.

## Website
https://rumourprint-fem.streamlit.app/

© Fresh Exclusive Media — RUMOURPRINT AI.
