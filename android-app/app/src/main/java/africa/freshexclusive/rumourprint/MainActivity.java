package africa.freshexclusive.rumourprint;

import android.annotation.SuppressLint;
import android.app.Activity;
import android.app.DownloadManager;
import android.content.ActivityNotFoundException;
import android.content.Context;
import android.content.Intent;
import android.content.res.ColorStateList;
import android.graphics.Color;
import android.graphics.Insets;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Environment;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.view.WindowInsets;
import android.webkit.CookieManager;
import android.webkit.DownloadListener;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.webkit.URLUtil;
import android.widget.Button;
import android.widget.FrameLayout;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.TextView;
import android.widget.Toast;
import android.webkit.ValueCallback;

import android.content.SharedPreferences;
import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.net.URL;
import javax.net.ssl.HttpsURLConnection;
import java.nio.charset.StandardCharsets;
import org.json.JSONObject;
import org.json.JSONArray;

public class MainActivity extends Activity {
    private static final String HOME = "https://rumourprint-fem.streamlit.app/?embed=true";
    private static final String APP_HOST = "rumourprint-fem.streamlit.app";
    private static final String OFFLINE_BASE = "https://offline.rumourprint.invalid/";
    private static final String OFFLINE_FEED = "https://tools.freshexclusivemedia.com/offline-library.json";
    private static final String OFFLINE_PREFS = "rumourprint_offline";
    private boolean offlineLibraryVisible = false;

    private static final int FILE_PICKER_REQUEST = 4102;
    private static final int DARK = Color.rgb(21, 39, 38);
    private static final int PAGE = Color.rgb(243, 245, 244);
    private static final int LIGHT = Color.rgb(245, 248, 246);

    private WebView webView;
    private ProgressBar progress;
    private LinearLayout errorPanel;
    private ValueCallback<Uri[]> pendingFileCallback;

    private int dp(float value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }

    private GradientDrawable rounded(int color, int radius) {
        GradientDrawable shape = new GradientDrawable();
        shape.setColor(color);
        shape.setCornerRadius(dp(radius));
        return shape;
    }

    private TextView text(String value, int sp, int color, boolean bold) {
        TextView label = new TextView(this);
        label.setText(value);
        label.setTextSize(sp);
        label.setTextColor(color);
        if (bold) label.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        label.setGravity(Gravity.CENTER_VERTICAL);
        return label;
    }

    @SuppressLint("SetJavaScriptEnabled")
    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);

        getWindow().setStatusBarColor(DARK);
        getWindow().setNavigationBarColor(DARK);

        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(PAGE);
        if (Build.VERSION.SDK_INT >= 30) {
            root.setOnApplyWindowInsetsListener((view, windowInsets) -> {
                Insets safe = windowInsets.getInsets(
                    WindowInsets.Type.systemBars() | WindowInsets.Type.displayCutout()
                );
                view.setPadding(safe.left, safe.top, safe.right, safe.bottom);
                return windowInsets;
            });
        } else {
            root.setFitsSystemWindows(true);
        }

        LinearLayout header = new LinearLayout(this);
        header.setOrientation(LinearLayout.HORIZONTAL);
        header.setGravity(Gravity.CENTER_VERTICAL);
        header.setBackgroundColor(DARK);
        header.setPadding(dp(14), 0, dp(10), 0);
        root.addView(header, new LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT, dp(66)
        ));

        ImageView mark = new ImageView(this);
        mark.setImageResource(R.drawable.logo_mark);
        mark.setContentDescription("RUMOURPRINT AI logo");
        header.addView(mark, new LinearLayout.LayoutParams(dp(46), dp(46)));

        LinearLayout brand = new LinearLayout(this);
        brand.setOrientation(LinearLayout.VERTICAL);
        brand.setGravity(Gravity.CENTER_VERTICAL);
        brand.setPadding(dp(10), 0, 0, 0);
        header.addView(brand, new LinearLayout.LayoutParams(0, dp(56), 1f));

        TextView title = text("RUMOURPRINT AI", 17, Color.WHITE, true);
        title.setLetterSpacing(0.02f);
        brand.addView(title);

        TextView subtitle = text(getString(R.string.brand_subtitle), 8, Color.rgb(175, 207, 194), true);
        subtitle.setLetterSpacing(0.07f);
        brand.addView(subtitle);

        TextView reload = text("⟳", 26, LIGHT, false);
        reload.setGravity(Gravity.CENTER);
        reload.setContentDescription("Refresh application");
        reload.setOnClickListener(v -> webView.loadUrl(HOME));
        header.addView(reload, new LinearLayout.LayoutParams(dp(43), dp(49)));

        TextView open = text("↗", 25, LIGHT, false);
        open.setGravity(Gravity.CENTER);
        open.setContentDescription("Open RUMOURPRINT in browser to export reports");
        open.setOnClickListener(v -> openExternal(Uri.parse(HOME)));
        header.addView(open, new LinearLayout.LayoutParams(dp(43), dp(49)));

        TextView library = text("📚", 23, LIGHT, false);
        library.setGravity(Gravity.CENTER);
        library.setContentDescription("Read offline library without mobile data");
        library.setOnClickListener(v -> showOfflineLibrary());
        header.addView(library, new LinearLayout.LayoutParams(dp(46), dp(49)));

        progress = new ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal);
        progress.setMax(100);
        progress.setProgressTintList(ColorStateList.valueOf(Color.rgb(114, 188, 160)));
        progress.setProgressBackgroundTintList(ColorStateList.valueOf(DARK));
        progress.setVisibility(View.GONE);
        root.addView(progress, new LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT, dp(3)
        ));

        FrameLayout body = new FrameLayout(this);
        root.addView(body, new LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f
        ));

        webView = new WebView(this);
        webView.setBackgroundColor(PAGE);
        webView.setOverScrollMode(View.OVER_SCROLL_NEVER);
        body.addView(webView, new FrameLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT
        ));

        errorPanel = createOfflinePanel();
        errorPanel.setVisibility(View.GONE);
        body.addView(errorPanel, new FrameLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT
        ));

        configureWebView();
        setContentView(root);
        if (state == null) {
            webView.loadUrl(HOME);
        } else if (webView.restoreState(state) == null) {
            webView.loadUrl(HOME);
        }
    }

    private LinearLayout createOfflinePanel() {
        LinearLayout panel = new LinearLayout(this);
        panel.setOrientation(LinearLayout.VERTICAL);
        panel.setGravity(Gravity.CENTER);
        panel.setPadding(dp(30), dp(20), dp(30), dp(20));
        panel.setBackgroundColor(PAGE);

        TextView heading = text(getString(R.string.offline_title), 24, DARK, true);
        heading.setGravity(Gravity.CENTER);
        panel.addView(heading);

        TextView explanation = text(getString(R.string.offline_description), 15, Color.rgb(90, 110, 101), false);
        explanation.setGravity(Gravity.CENTER);
        explanation.setPadding(0, dp(16), 0, dp(20));
        panel.addView(explanation);

        Button retry = new Button(this);
        retry.setText(R.string.retry);
        retry.setTextColor(Color.WHITE);
        retry.setAllCaps(false);
        retry.setBackground(rounded(Color.rgb(33, 99, 87), 10));
        retry.setOnClickListener(v -> {
            panel.setVisibility(View.GONE);
            webView.loadUrl(HOME);
        });
        panel.addView(retry, new LinearLayout.LayoutParams(dp(150), dp(50)));
        return panel;
    }

    @SuppressLint("SetJavaScriptEnabled")
    private void configureWebView() {
        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setAllowFileAccess(false);
        settings.setAllowContentAccess(true);
        settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        settings.setJavaScriptCanOpenWindowsAutomatically(false);
        settings.setSupportMultipleWindows(false);
        settings.setMediaPlaybackRequiresUserGesture(true);
        settings.setCacheMode(WebSettings.LOAD_DEFAULT);
        CookieManager.getInstance().setAcceptCookie(true);
        if (Build.VERSION.SDK_INT >= 26) settings.setSafeBrowsingEnabled(true);

        webView.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                Uri url = request.getUrl();
                if ("https".equalsIgnoreCase(url.getScheme()) &&
                    APP_HOST.equalsIgnoreCase(url.getHost())) {
                    return false;
                }
                if ("https".equalsIgnoreCase(url.getScheme()) ||
                    "http".equalsIgnoreCase(url.getScheme())) {
                    openExternal(url);
                }
                return true;
            }

            @Override
            public void onPageStarted(WebView view, String url, android.graphics.Bitmap favicon) {
                if (url != null && url.startsWith("https://" + APP_HOST)) {
                    offlineLibraryVisible = false;
                }
                progress.setVisibility(View.VISIBLE);
                errorPanel.setVisibility(View.GONE);
            }

            @Override
            public void onPageFinished(WebView view, String url) {
                progress.setVisibility(View.GONE);
            }

            @Override
            public void onReceivedError(WebView view, WebResourceRequest request, WebResourceError error) {
                if (request.isForMainFrame()) {
                    progress.setVisibility(View.GONE);
                    if (!offlineLibraryVisible) {
                        showOfflineLibrary();
                    } else {
                        errorPanel.setVisibility(View.VISIBLE);
                    }
                }
            }
        });

        webView.setWebChromeClient(new WebChromeClient() {
            @Override
            public void onProgressChanged(WebView view, int newProgress) {
                progress.setProgress(newProgress);
                if (newProgress >= 100) progress.setVisibility(View.GONE);
            }

            @Override
            public boolean onShowFileChooser(WebView view, ValueCallback<Uri[]> callback,
                                              FileChooserParams params) {
                if (pendingFileCallback != null) {
                    pendingFileCallback.onReceiveValue(null);
                }
                pendingFileCallback = callback;
                Intent select = new Intent(Intent.ACTION_GET_CONTENT);
                select.setType("*/*");
                select.addCategory(Intent.CATEGORY_OPENABLE);
                try {
                    startActivityForResult(Intent.createChooser(select, "Choose investigation file"), FILE_PICKER_REQUEST);
                    return true;
                } catch (ActivityNotFoundException ex) {
                    pendingFileCallback = null;
                    return false;
                }
            }
        });

        webView.setDownloadListener((url, agent, disposition, mime, size) -> {
            if (url == null || !url.startsWith("https://")) {
                Toast.makeText(this, "To export a report, tap ↗ and download in your browser.", Toast.LENGTH_LONG).show();
                return;
            }
            try {
                DownloadManager.Request request = new DownloadManager.Request(Uri.parse(url));
                request.setMimeType(mime);
                request.setTitle(URLUtil.guessFileName(url, disposition, mime));
                request.setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED);
                request.setDestinationInExternalPublicDir(
                    Environment.DIRECTORY_DOWNLOADS,
                    URLUtil.guessFileName(url, disposition, mime)
                );
                String cookie = CookieManager.getInstance().getCookie(url);
                if (cookie != null) request.addRequestHeader("Cookie", cookie);
                DownloadManager downloader = (DownloadManager) getSystemService(Context.DOWNLOAD_SERVICE);
                downloader.enqueue(request);
                Toast.makeText(this, "Download started", Toast.LENGTH_SHORT).show();
            } catch (Exception ex) {
                openExternal(Uri.parse(url));
            }
        });
    }


    private static String readSmall(InputStream input, int limit) throws java.io.IOException {
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        byte[] buffer = new byte[8192];
        int length;
        while ((length = input.read(buffer)) != -1) {
            if (out.size() + length > limit) {
                throw new java.io.IOException("Library file is unexpectedly large.");
            }
            out.write(buffer, 0, length);
        }
        return new String(out.toByteArray(), StandardCharsets.UTF_8);
    }

    private String bundledLibrary() throws java.io.IOException {
        try (InputStream input = getAssets().open("offline-library.json")) {
            return readSmall(input, 240_000);
        }
    }

    private boolean validLibrary(String text) {
        try {
            JSONObject doc = new JSONObject(text);
            JSONArray entries = doc.getJSONArray("articles");
            if (entries.length() < 10 || entries.length() > 250) return false;
            for (int i = 0; i < entries.length(); i++) {
                JSONObject entry = entries.getJSONObject(i);
                if (entry.getString("title").length() < 4 || entry.getJSONArray("body").length() < 1) {
                    return false;
                }
            }
            return true;
        } catch (Exception ex) {
            return false;
        }
    }

    private void showOfflineLibrary() {
        try {
            String library = getSharedPreferences(OFFLINE_PREFS, MODE_PRIVATE).getString("library", "");
            if (!validLibrary(library)) library = bundledLibrary();
            if (!validLibrary(library)) throw new java.io.IOException("No readable library found.");
            String template;
            try (InputStream input = getAssets().open("offline.html")) {
                template = readSmall(input, 120_000);
            }
            // An embedded JSON script must not contain literal '<' characters.
            String protectedJson = library.replace("<", "\\u003c").replace(">", "\\u003e");
            String page = template.replace("__RUMOURPRINT_LIBRARY_JSON__", protectedJson);
            offlineLibraryVisible = true;
            progress.setVisibility(View.GONE);
            errorPanel.setVisibility(View.GONE);
            webView.loadDataWithBaseURL(OFFLINE_BASE, page, "text/html", "UTF-8", OFFLINE_BASE);
        } catch (Exception ex) {
            errorPanel.setVisibility(View.VISIBLE);
            Toast.makeText(this, "The offline library could not be opened.", Toast.LENGTH_LONG).show();
        }
    }

    private void refreshOfflineLibraryWhenConnected() {
        SharedPreferences preferences = getSharedPreferences(OFFLINE_PREFS, MODE_PRIVATE);
        long now = System.currentTimeMillis();
        long lastAttempt = preferences.getLong("last_attempt", 0L);
        if (lastAttempt > 0 && now - lastAttempt < 20L * 60L * 1000L) return;
        preferences.edit().putLong("last_attempt", now).apply();

        new Thread(() -> {
            HttpsURLConnection connection = null;
            try {
                connection = (HttpsURLConnection) new URL(OFFLINE_FEED).openConnection();
                connection.setConnectTimeout(6000);
                connection.setReadTimeout(6500);
                connection.setInstanceFollowRedirects(false);
                if (connection.getResponseCode() != 200) return;
                String received;
                try (InputStream input = connection.getInputStream()) {
                    received = readSmall(input, 240_000);
                }
                if (validLibrary(received)) {
                    preferences.edit().putString("library", received).apply();
                }
            } catch (Exception ignored) {
                // A failed refresh must never block access to the bundled offline library.
            } finally {
                if (connection != null) connection.disconnect();
            }
        }).start();
    }

    @Override
    protected void onResume() {
        super.onResume();
        refreshOfflineLibraryWhenConnected();
    }

    private void openExternal(Uri uri) {
        try {
            startActivity(new Intent(Intent.ACTION_VIEW, uri));
        } catch (ActivityNotFoundException ex) {
            Toast.makeText(this, "No browser is available.", Toast.LENGTH_SHORT).show();
        }
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode == FILE_PICKER_REQUEST && pendingFileCallback != null) {
            Uri[] selected = null;
            if (resultCode == RESULT_OK && data != null) {
                selected = WebChromeClient.FileChooserParams.parseResult(resultCode, data);
            }
            pendingFileCallback.onReceiveValue(selected);
            pendingFileCallback = null;
        }
    }

    @Override
    public void onBackPressed() {
        if (offlineLibraryVisible) {
            offlineLibraryVisible = false;
            webView.loadUrl(HOME);
        } else if (webView != null && webView.canGoBack()) {
            webView.goBack();
        } else {
            super.onBackPressed();
        }
    }

    @Override
    protected void onSaveInstanceState(Bundle state) {
        if (webView != null) webView.saveState(state);
        super.onSaveInstanceState(state);
    }

    @Override
    protected void onDestroy() {
        if (pendingFileCallback != null) {
            pendingFileCallback.onReceiveValue(null);
            pendingFileCallback = null;
        }
        if (webView != null) {
            webView.destroy();
            webView = null;
        }
        super.onDestroy();
    }
}
