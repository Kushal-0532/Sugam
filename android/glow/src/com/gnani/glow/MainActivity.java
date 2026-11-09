package com.gnani.glow;

import android.app.Activity;
import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import android.provider.Settings;

/** Launch once: opens the overlay-permission page if missing, else starts the service. */
public class MainActivity extends Activity {
    @Override protected void onCreate(Bundle b) {
        super.onCreate(b);
        if (Settings.canDrawOverlays(this)) {
            startForegroundService(new Intent(this, GlowService.class));
        } else {
            startActivity(new Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION,
                    Uri.parse("package:" + getPackageName())));
        }
        finish();
    }
}
