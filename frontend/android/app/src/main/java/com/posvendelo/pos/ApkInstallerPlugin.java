package com.posvendelo.pos;

import android.content.Intent;
import android.net.Uri;

import androidx.core.content.FileProvider;

import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;

import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.Arrays;
import java.util.HashSet;
import java.util.Set;

@CapacitorPlugin(name = "ApkInstaller")
public class ApkInstallerPlugin extends Plugin {

    private static final Set<String> TRUSTED_DOMAINS = new HashSet<>(Arrays.asList(
        "github.com", "objects.githubusercontent.com", "ghcr.io",
        "pkg-containers.githubusercontent.com"
    ));

    @PluginMethod
    public void downloadAndInstall(PluginCall call) {
        String url = call.getString("url");
        String rawFileName = call.getString("fileName", "update.apk");

        if (url == null || url.isEmpty()) {
            call.reject("URL is required");
            return;
        }

        // Validate download URL against trusted domains
        try {
            String host = new URL(url).getHost().toLowerCase();
            if (!TRUSTED_DOMAINS.contains(host)) {
                call.reject("Dominio no confiable: " + host);
                return;
            }
        } catch (Exception e) {
            call.reject("URL invalida: " + url);
            return;
        }

        // Sanitize fileName — strip path separators to prevent path traversal
        String fileName = new File(rawFileName).getName();
        if (fileName.isEmpty() || fileName.equals(".") || fileName.equals("..")) {
            fileName = "update.apk";
        }
        final String safeFileName = fileName;

        // Run download in background thread to avoid blocking the main thread
        new Thread(() -> {
            try {
                // Prefer external cache dir; fall back to internal cache
                File cacheDir = getContext().getExternalCacheDir();
                if (cacheDir == null) {
                    cacheDir = getContext().getCacheDir();
                }
                File apkFile = new File(cacheDir, safeFileName);

                // Download APK
                HttpURLConnection conn = (HttpURLConnection) new URL(url).openConnection();
                conn.setConnectTimeout(30_000);
                conn.setReadTimeout(60_000);
                conn.setRequestProperty("Accept", "application/vnd.android.package-archive");
                try (InputStream in = conn.getInputStream();
                     FileOutputStream out = new FileOutputStream(apkFile)) {
                    byte[] buf = new byte[8192];
                    int len;
                    while ((len = in.read(buf)) != -1) {
                        out.write(buf, 0, len);
                    }
                } finally {
                    conn.disconnect();
                }

                // Build content URI via FileProvider (required on Android 7+)
                Uri apkUri = FileProvider.getUriForFile(
                    getContext(),
                    getContext().getPackageName() + ".fileprovider",
                    apkFile
                );

                Intent intent = new Intent(Intent.ACTION_VIEW);
                intent.setDataAndType(apkUri, "application/vnd.android.package-archive");
                intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
                getContext().startActivity(intent);

                call.resolve();
            } catch (Exception e) {
                call.reject("No se pudo descargar o instalar la actualizacion: " + e.getMessage(), e);
            }
        }).start();
    }
}
