package com.gnani.glow;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.Service;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.graphics.PixelFormat;
import android.os.IBinder;
import android.view.WindowManager;

/** Overlay window driven by: adb shell am broadcast -a com.gnani.glow.STATE --es s <state> */
public class GlowService extends Service {
    static final String ACTION = "com.gnani.glow.STATE";
    private GlowView view;
    private WindowManager wm;

    private BroadcastReceiver rx;

    @Override public void onCreate() {
        super.onCreate();
        NotificationManager nm = getSystemService(NotificationManager.class);
        nm.createNotificationChannel(new NotificationChannel("g", "Glow", NotificationManager.IMPORTANCE_MIN));
        startForeground(1, new Notification.Builder(this, "g")
                .setSmallIcon(android.R.drawable.presence_online).setContentTitle("Glow overlay").build());

        wm = getSystemService(WindowManager.class);
        view = new GlowView(this);
        WindowManager.LayoutParams p = new WindowManager.LayoutParams(
                WindowManager.LayoutParams.MATCH_PARENT, WindowManager.LayoutParams.MATCH_PARENT,
                WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY,
                WindowManager.LayoutParams.FLAG_NOT_TOUCHABLE | WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE
                        | WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN | WindowManager.LayoutParams.FLAG_LAYOUT_NO_LIMITS,
                PixelFormat.TRANSLUCENT);
        p.layoutInDisplayCutoutMode = WindowManager.LayoutParams.LAYOUT_IN_DISPLAY_CUTOUT_MODE_SHORT_EDGES;
        wm.addView(view, p);
        rx = new Rx(this, view);
        registerReceiver(rx, new IntentFilter(ACTION));
    }

    @Override public void onDestroy() {
        unregisterReceiver(rx);
        if (view != null) wm.removeView(view);
        super.onDestroy();
    }

    @Override public IBinder onBind(Intent i) { return null; }

    static class Rx extends BroadcastReceiver {
        final Service svc; final GlowView v;
        Rx(Service svc, GlowView v) { this.svc = svc; this.v = v; }
        @Override public void onReceive(Context c, Intent i) {
            String s = i.getStringExtra("s");
            if (s == null) return;
            if (s.equals("quit")) svc.stopSelf(); else v.setState(s);
        }
    }
}
