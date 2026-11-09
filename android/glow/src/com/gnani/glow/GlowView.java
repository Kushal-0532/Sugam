package com.gnani.glow;

import android.animation.ValueAnimator;
import android.content.Context;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Matrix;
import android.graphics.Paint;
import android.graphics.RectF;
import android.graphics.SweepGradient;
import android.view.View;

/** Soft rotating-gradient border. State = colour pair + pulse speed + target intensity. */
public class GlowView extends View {
    private static final int LAYERS = 16;
    private final Paint paint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Matrix rot = new Matrix();
    private final RectF rect = new RectF();
    private int cA = Color.TRANSPARENT, cB = Color.TRANSPARENT, tA, tB;
    private float level = 0f, target = 0f, pulse = 0f, angle = 0f, spin = 60f;
    private long last = System.nanoTime();
    private SweepGradient grad;

    public GlowView(Context c) {
        super(c);
        paint.setStyle(Paint.Style.STROKE);
        ValueAnimator a = ValueAnimator.ofFloat(0, 1);
        a.setRepeatCount(ValueAnimator.INFINITE);
        a.setDuration(1000);
        a.addUpdateListener(x -> tick());
        a.start();
        setState("off");
    }

    // ponytail: colours/speeds hardcoded; add a config only if the look needs per-take tuning
    public void setState(String s) {
        switch (s) {
            case "listening": set(0xFF3B82F6, 0xFF22D3EE, 1f, 70f, 1.6f); break;  // blue pulse
            case "thinking":  set(0xFFA855F7, 0xFFEC4899, 1f, 220f, 0f); break;   // purple fast sweep
            case "acting":    set(0xFF06B6D4, 0xFF3B82F6, 1f, 120f, 0f); break;   // cyan
            case "done":      set(0xFF22C55E, 0xFFA3E635, 1f, 40f, 0f); break;    // green
            case "blocked":   set(0xFFEF4444, 0xFFF97316, 1f, 40f, 2.4f); break;  // red pulse
            case "idle":      set(0xFF64748B, 0xFF94A3B8, 0.25f, 20f, 0f); break; // dim
            default:          target = 0f;                                         // off/hidden
        }
    }

    private void set(int a, int b, float lvl, float spd, float pls) {
        tA = a; tB = b; target = lvl; spin = spd; pulse = pls;
        if (cA == Color.TRANSPARENT) { cA = a; cB = b; }
    }

    private void tick() {
        long now = System.nanoTime();
        float dt = (now - last) / 1e9f;
        last = now;
        angle = (angle + spin * dt) % 360f;
        level += (target - level) * Math.min(1f, dt * 8f);      // ease intensity
        cA = mix(cA, tA, Math.min(1f, dt * 8f));                // ease colour
        cB = mix(cB, tB, Math.min(1f, dt * 8f));
        setVisibility(level < 0.01f && target == 0f ? INVISIBLE : VISIBLE);
        invalidate();
    }

    private static int mix(int x, int y, float t) {
        return Color.argb(255, (int) (Color.red(x) + (Color.red(y) - Color.red(x)) * t),
                (int) (Color.green(x) + (Color.green(y) - Color.green(x)) * t),
                (int) (Color.blue(x) + (Color.blue(y) - Color.blue(x)) * t));
    }

    @Override protected void onDraw(Canvas c) {
        if (level < 0.01f) return;
        float w = getWidth(), h = getHeight();
        grad = new SweepGradient(w / 2, h / 2, new int[]{cA, cB, cA}, null);
        rot.setRotate(angle, w / 2, h / 2);
        grad.setLocalMatrix(rot);
        paint.setShader(grad);
        float breathe = pulse == 0 ? 1f : 0.65f + 0.35f * (float) Math.sin(System.nanoTime() / 1e9 * pulse * Math.PI);
        float radius = 70f, maxW = 64f * getResources().getDisplayMetrics().density / 3f;
        for (int i = 0; i < LAYERS; i++) {                      // wide faint stroke first, tight bright last
            float f = (float) (LAYERS - i) / LAYERS;
            float sw = maxW * f;
            paint.setStrokeWidth(sw);
            paint.setAlpha((int) (255 * level * breathe * (1f - f) * (1f - f) * 0.9f + 8 * level));
            rect.set(sw / 2 - maxW / 2 + 0f, sw / 2 - maxW / 2 + 0f, w - sw / 2 + maxW / 2, h - sw / 2 + maxW / 2);
            rect.inset(maxW / 2, maxW / 2);
            c.drawRoundRect(rect, radius, radius, paint);
        }
    }
}
