"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { Ruler, Camera, X, Check, Loader2, RotateCcw } from "lucide-react";
import { pickGarmentFor, type Garment } from "@/lib/fitcheck/garments";
import { detectPose, preloadPose, PoseError, type PoseResult } from "@/lib/fitcheck/pose";
import { computeMeasurements, MeasurementError, type BodyMeasurements } from "@/lib/fitcheck/measure";
import { fitConfidence, type FitResult } from "@/lib/fitcheck/size";
import { tryOn, dataUrlToBlob, TryOnError } from "@/lib/fitcheck/tryon";

/** Accepts 183, 183cm, 1.83m, 6ft, 5'11, 5'11". Returns cm or null. */
function parseHeightCm(raw: string): number | null {
  const s = raw.trim().toLowerCase();
  if (!s) return null;
  let m = s.match(/^(\d+(?:\.\d+)?)\s*m$/);
  if (m) return Math.round(parseFloat(m[1]) * 100);
  m = s.match(/^(\d+(?:\.\d+)?)\s*cm$/);
  if (m) return Math.round(parseFloat(m[1]));
  m = s.match(/^(\d+)\s*(?:'|ft|feet)\s*(\d+(?:\.\d+)?)?\s*(?:"|in|inch|inches)?$/);
  if (m) {
    const ft = parseInt(m[1], 10);
    const inch = m[2] ? parseFloat(m[2]) : 0;
    return Math.round((ft * 12 + inch) * 2.54);
  }
  m = s.match(/^(\d+(?:\.\d+)?)$/);
  if (m) {
    const n = parseFloat(m[1]);
    if (n > 0 && n < 3) return Math.round(n * 100);
    return Math.round(n);
  }
  return null;
}

/** Accepts 70, 70kg, 154lb. Returns kg or null. */
function parseWeightKg(raw: string): number | null {
  const s = raw.trim().toLowerCase();
  if (!s) return null;
  let m = s.match(/^(\d+(?:\.\d+)?)\s*(?:lb|lbs|pounds?)$/);
  if (m) return Math.round(parseFloat(m[1]) * 0.453592);
  m = s.match(/^(\d+(?:\.\d+)?)\s*(?:kg|kgs)?$/);
  if (m) return Math.round(parseFloat(m[1]));
  return null;
}

// Skeleton connections, by the keypoint names pose.ts returns.
const CONNECTIONS: [string, string][] = [
  ["left_shoulder", "right_shoulder"],
  ["left_shoulder", "left_elbow"],
  ["left_elbow", "left_wrist"],
  ["right_shoulder", "right_elbow"],
  ["right_elbow", "right_wrist"],
  ["left_shoulder", "left_hip"],
  ["right_shoulder", "right_hip"],
  ["left_hip", "right_hip"],
  ["left_hip", "left_knee"],
  ["left_knee", "left_ankle"],
  ["right_hip", "right_knee"],
  ["right_knee", "right_ankle"],
];

function drawSkeleton(ctx: CanvasRenderingContext2D, pose: PoseResult) {
  const kp = pose.keypoints;
  ctx.lineWidth = Math.max(2, pose.width / 300);
  ctx.strokeStyle = "rgba(122,162,255,0.95)";
  ctx.fillStyle = "#ffffff";
  for (const [a, b] of CONNECTIONS) {
    if (!kp[a] || !kp[b]) continue;
    ctx.beginPath();
    ctx.moveTo(kp[a][0], kp[a][1]);
    ctx.lineTo(kp[b][0], kp[b][1]);
    ctx.stroke();
  }
  const r = Math.max(3, pose.width / 200);
  for (const name of Object.keys(kp)) {
    ctx.beginPath();
    ctx.arc(kp[name][0], kp[name][1], r, 0, Math.PI * 2);
    ctx.fill();
  }
  // Highlight the shoulder line — the width that drives the chest estimate.
  if (kp.left_shoulder && kp.right_shoulder) {
    ctx.strokeStyle = "#ffd166";
    ctx.lineWidth = Math.max(3, pose.width / 220);
    ctx.beginPath();
    ctx.moveTo(kp.left_shoulder[0], kp.left_shoulder[1]);
    ctx.lineTo(kp.right_shoulder[0], kp.right_shoulder[1]);
    ctx.stroke();
  }
}

type Step = "intro" | "camera" | "result";

export function FitCheck({ item }: { item: { name?: string; category?: string } }) {
  const [open, setOpen] = useState(false);
  const [step, setStep] = useState<Step>("intro");
  const [heightStr, setHeightStr] = useState("");
  const [weightStr, setWeightStr] = useState("");
  const [busy, setBusy] = useState(false);
  const [countdown, setCountdown] = useState<number | null>(null);
  const [error, setError] = useState("");
  const [measurements, setMeasurements] = useState<BodyMeasurements | null>(null);
  const [fit, setFit] = useState<FitResult | null>(null);
  const [captured, setCaptured] = useState<string | null>(null);
  const [tryonUrl, setTryonUrl] = useState<string | null>(null);
  const [tryonBusy, setTryonBusy] = useState(false);
  const [tryonErr, setTryonErr] = useState("");

  const garment: Garment = pickGarmentFor(item);
  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const clearTimer = useCallback(() => {
    if (timerRef.current) clearInterval(timerRef.current);
    timerRef.current = null;
    setCountdown(null);
  }, []);

  const stopCamera = useCallback(() => {
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
  }, []);

  const close = useCallback(() => {
    clearTimer();
    stopCamera();
    setOpen(false);
    setStep("intro");
    setError("");
    setBusy(false);
    setMeasurements(null);
    setFit(null);
    setCaptured(null);
    setTryonUrl(null);
    setTryonBusy(false);
    setTryonErr("");
  }, [stopCamera, clearTimer]);

  useEffect(() => () => { clearTimer(); stopCamera(); }, [clearTimer, stopCamera]);

  async function startCamera() {
    const cm = parseHeightCm(heightStr);
    if (!cm) {
      setError("Enter your height, e.g. 183, 183cm, or 5'11\".");
      return;
    }
    setError("");
    void preloadPose();
    setStep("camera");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: "user", width: { ideal: 1280 }, height: { ideal: 720 } },
        audio: false,
      });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
      }
    } catch {
      setError("Camera access is needed for the fit check. Allow it and try again.");
      setStep("intro");
    }
  }

  function startCountdown() {
    if (busy || countdown !== null) return;
    setError("");
    setCountdown(10);
    timerRef.current = setInterval(() => {
      setCountdown((c) => {
        if (c === null) return null;
        if (c <= 1) {
          clearTimer();
          void doCapture();
          return null;
        }
        return c - 1;
      });
    }, 1000);
  }

  async function doCapture() {
    const video = videoRef.current;
    if (!video || !video.videoWidth) {
      setError("Camera isn't ready yet. Try again.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const canvas = document.createElement("canvas");
      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;
      const ctx = canvas.getContext("2d");
      if (!ctx) throw new Error("Canvas unavailable.");
      ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

      const pose = await detectPose(canvas, canvas.width, canvas.height);
      const cm = parseHeightCm(heightStr)!;
      const kg = parseWeightKg(weightStr);
      const m = computeMeasurements(pose.keypoints, cm, kg);
      const result = fitConfidence(m.photoChestCircumferenceCm, m.shoulderWidthCm, garment.sizeChart);

      // Draw the detected skeleton over the captured frame — the visualization.
      drawSkeleton(ctx, pose);
      setCaptured(canvas.toDataURL("image/jpeg", 0.85));

      setMeasurements(m);
      setFit(result);
      stopCamera();
      setStep("result");
    } catch (e) {
      // Required: surface a clear, actionable message and let them retry.
      setError(
        e instanceof PoseError || e instanceof MeasurementError
          ? e.message
          : "Couldn't read a pose from that frame. Make sure your whole body is visible and try again.",
      );
    } finally {
      setBusy(false);
    }
  }

  function retake() {
    setMeasurements(null);
    setFit(null);
    setCaptured(null);
    setTryonUrl(null);
    setTryonErr("");
    setError("");
    void startCamera();
  }

  async function runTryOn() {
    if (!captured) return;
    setTryonBusy(true);
    setTryonErr("");
    try {
      const personBlob = await dataUrlToBlob(captured);
      const url = await tryOn(personBlob, garment.imageUrl, `${garment.fit} ${garment.name}`);
      setTryonUrl(url);
    } catch (e) {
      setTryonErr(e instanceof TryOnError ? e.message : "Try-on failed. Please try again.");
    } finally {
      setTryonBusy(false);
    }
  }

  const bandColor = (b: string) => (b === "HIGH" ? "#2f8f4e" : b === "MEDIUM" ? "#b8860b" : "#b0562a");

  return (
    <>
      <button
        type="button"
        className="product-link"
        onClick={() => setOpen(true)}
        style={{ display: "inline-flex", alignItems: "center", gap: "0.35rem", marginTop: "0.35rem" }}
      >
        <Ruler size={13} /> Fit check
      </button>

      {open && (
        <div
          role="dialog"
          aria-modal="true"
          onClick={close}
          style={{
            position: "fixed", inset: 0, background: "rgba(0,0,0,0.6)",
            display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000, padding: "1rem",
          }}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            style={{
              background: "var(--surface, #14171f)", color: "inherit", borderRadius: 18,
              width: "min(560px, 100%)", maxHeight: "90vh", overflow: "auto",
              padding: "1.25rem 1.5rem", boxShadow: "0 20px 60px rgba(0,0,0,0.4)",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.5rem" }}>
              <strong style={{ fontSize: "1.05rem" }}>Fit check</strong>
              <button type="button" aria-label="Close" onClick={close} className="text-button">
                <X size={18} />
              </button>
            </div>
            <p style={{ opacity: 0.7, fontSize: "0.85rem", marginTop: 0 }}>
              Sizing you for <strong>{garment.name}</strong> ({garment.fit} fit).
            </p>

            {error && (
              <p className="notice-banner" role="alert" style={{ margin: "0.5rem 0" }}>{error}</p>
            )}

            {step === "intro" && (
              <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem", marginTop: "0.5rem" }}>
                <label style={{ display: "flex", flexDirection: "column", gap: "0.25rem", fontSize: "0.85rem" }}>
                  Your height
                  <input value={heightStr} onChange={(e) => setHeightStr(e.target.value)} placeholder={`e.g. 183, 183cm, 5'11"`}
                    style={{ padding: "0.5rem 0.6rem", borderRadius: 10, border: "1px solid rgba(128,128,128,0.4)", background: "transparent", color: "inherit" }} />
                </label>
                <label style={{ display: "flex", flexDirection: "column", gap: "0.25rem", fontSize: "0.85rem" }}>
                  Weight <span style={{ opacity: 0.6 }}>(optional, improves hip estimate)</span>
                  <input value={weightStr} onChange={(e) => setWeightStr(e.target.value)} placeholder="e.g. 70kg, 154lb"
                    style={{ padding: "0.5rem 0.6rem", borderRadius: 10, border: "1px solid rgba(128,128,128,0.4)", background: "transparent", color: "inherit" }} />
                </label>
                <p style={{ fontSize: "0.78rem", opacity: 0.6, margin: 0 }}>
                  On the next screen you get a 10-second timer to step back so your whole body is in frame, facing the camera. Nothing is uploaded, the sizing runs on your device.
                </p>
                <button type="button" className="button primary" onClick={startCamera}
                  style={{ display: "inline-flex", alignItems: "center", gap: "0.4rem", justifyContent: "center" }}>
                  <Camera size={16} /> Open camera
                </button>
              </div>
            )}

            {step === "camera" && (
              <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem", marginTop: "0.5rem" }}>
                <div style={{ position: "relative", borderRadius: 12, overflow: "hidden", background: "#000" }}>
                  <video ref={videoRef} playsInline muted style={{ width: "100%", display: "block", transform: "scaleX(-1)" }} />
                  <div aria-hidden style={{
                    position: "absolute", inset: "6% 28%", border: "2px dashed rgba(255,255,255,0.6)", borderRadius: 60, pointerEvents: "none",
                  }} />
                  {countdown !== null && (
                    <div aria-live="assertive" style={{
                      position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center",
                      background: "rgba(0,0,0,0.35)", color: "#fff", fontSize: "6rem", fontWeight: 700,
                    }}>
                      {countdown}
                    </div>
                  )}
                  {busy && countdown === null && (
                    <div style={{
                      position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center",
                      background: "rgba(0,0,0,0.45)", color: "#fff", gap: "0.5rem",
                    }}>
                      <Loader2 size={20} className="spin" /> Reading pose…
                    </div>
                  )}
                </div>
                <p style={{ fontSize: "0.78rem", opacity: 0.7, margin: 0 }}>
                  Fit your whole body head-to-feet inside the outline, face the camera. Press start and you have 10 seconds to get in position.
                </p>
                <button type="button" className="button primary" onClick={startCountdown} disabled={busy || countdown !== null}
                  style={{ display: "inline-flex", alignItems: "center", gap: "0.4rem", justifyContent: "center" }}>
                  <Camera size={16} /> {countdown !== null ? `Capturing in ${countdown}…` : busy ? "Reading pose…" : "Start 10s timer"}
                </button>
              </div>
            )}

            {step === "result" && fit && measurements && (
              <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem", marginTop: "0.5rem" }}>
                <div style={{ display: "flex", gap: "0.9rem", flexWrap: "wrap" }}>
                  {captured && (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img src={captured} alt="Your captured pose with detected skeleton"
                      style={{ width: 180, borderRadius: 12, border: "1px solid rgba(128,128,128,0.25)" }} />
                  )}
                  <div style={{ flex: 1, minWidth: 180, display: "flex", flexDirection: "column", gap: "0.4rem" }}>
                    <div style={{ display: "flex", alignItems: "baseline", gap: "0.6rem" }}>
                      <span style={{ fontSize: "2.4rem", fontWeight: 700 }}>{fit.recommendedSize}</span>
                      <span style={{ color: bandColor(fit.band), fontWeight: 600, fontSize: "0.8rem" }}>
                        {fit.band} ({Math.round(fit.confidence * 100)}%)
                      </span>
                    </div>
                    <p style={{ margin: 0, fontSize: "0.88rem" }}>
                      <Check size={14} style={{ verticalAlign: "-2px" }} /> Size <strong>{fit.recommendedSize}</strong> for the {garment.name}
                      {fit.alternateSize ? <>, or <strong>{fit.alternateSize}</strong>.</> : "."}
                    </p>
                    <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img src={garment.imageUrl} alt={garment.name}
                        style={{ width: 40, height: 52, objectFit: "cover", borderRadius: 6 }} />
                      <span style={{ fontSize: "0.78rem", opacity: 0.7 }}>{garment.name}</span>
                    </div>
                  </div>
                </div>
                {fit.note && <p style={{ margin: 0, fontSize: "0.82rem", opacity: 0.75 }}>{fit.note}</p>}
                <div style={{ fontSize: "0.8rem", opacity: 0.7, borderTop: "1px solid rgba(128,128,128,0.2)", paddingTop: "0.5rem" }}>
                  Estimated chest ~{Math.round(measurements.photoChestCircumferenceCm)}cm · shoulder ~{measurements.shoulderWidthCm}cm · height {measurements.heightCm}cm
                </div>
                {measurements.warnings.length > 0 && (
                  <ul style={{ margin: 0, paddingLeft: "1.1rem", fontSize: "0.78rem", opacity: 0.7 }}>
                    {measurements.warnings.map((w, i) => <li key={i}>{w}</li>)}
                  </ul>
                )}

                <div style={{ borderTop: "1px solid rgba(128,128,128,0.2)", paddingTop: "0.6rem", display: "flex", flexDirection: "column", gap: "0.5rem" }}>
                  <span style={{ fontSize: "0.8rem", fontWeight: 600 }}>Virtual try-on</span>
                  {tryonUrl ? (
                    <>
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img src={tryonUrl} alt={`You wearing the ${garment.name}`}
                        style={{ width: "100%", borderRadius: 12, border: "1px solid rgba(128,128,128,0.25)" }} />
                      <button type="button" className="text-button" onClick={() => setTryonUrl(null)}>
                        Regenerate
                      </button>
                    </>
                  ) : (
                    <button type="button" className="button primary" onClick={runTryOn} disabled={tryonBusy}
                      style={{ display: "inline-flex", alignItems: "center", gap: "0.4rem", justifyContent: "center" }}>
                      {tryonBusy ? <Loader2 size={16} className="spin" /> : <Camera size={16} />}
                      {tryonBusy ? "Generating try-on (~30-60s)…" : "See it on you"}
                    </button>
                  )}
                  {tryonErr && <p className="notice-banner" role="alert" style={{ margin: 0 }}>{tryonErr}</p>}
                </div>

                <button type="button" className="button" onClick={retake}
                  style={{ display: "inline-flex", alignItems: "center", gap: "0.4rem", justifyContent: "center" }}>
                  <RotateCcw size={15} /> Retake
                </button>
              </div>
            )}
          </div>
        </div>
      )}
    </>
  );
}
