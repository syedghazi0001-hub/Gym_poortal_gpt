/**
 * Vanguard Gym OS - QR Attendance Scanner Engine
 * Supports HTML5 Camera stream, BarcodeDetector API, Audio feedback, and Manual fallback.
 */

class GymScanner {
  constructor(options = {}) {
    this.videoElement = document.getElementById(options.videoId || "scanner-video");
    this.resultContainer = document.getElementById(options.resultId || "scan-result");
    this.facingMode = "environment"; // default to rear camera
    this.stream = null;
    this.isScanning = false;
    this.scanInterval = null;
    this.lastScannedToken = null;
    this.cooldownTimeout = null;

    // Web Audio Synthesizer for instant feedback (zero external audio dependency)
    this.audioCtx = null;

    this.initAudio();
  }

  initAudio() {
    try {
      const AudioContext = window.AudioContext || window.webkitAudioContext;
      if (AudioContext) {
        this.audioCtx = new AudioContext();
      }
    } catch (e) {
      console.warn("AudioContext not supported:", e);
    }
  }

  playBeep(success = true) {
    if (!this.audioCtx) return;
    try {
      if (this.audioCtx.state === "suspended") {
        this.audioCtx.resume();
      }
      const osc = this.audioCtx.createOscillator();
      const gain = this.audioCtx.createGain();
      osc.connect(gain);
      gain.connect(this.audioCtx.destination);

      if (success) {
        // High upbeat dual chime
        osc.frequency.setValueAtTime(880, this.audioCtx.currentTime); // A5
        osc.frequency.setValueAtTime(1320, this.audioCtx.currentTime + 0.08); // E6
        gain.gain.setValueAtTime(0.2, this.audioCtx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.01, this.audioCtx.currentTime + 0.25);
        osc.start();
        osc.stop(this.audioCtx.currentTime + 0.25);
      } else {
        // Low error buzz
        osc.type = "sawtooth";
        osc.frequency.setValueAtTime(220, this.audioCtx.currentTime);
        gain.gain.setValueAtTime(0.2, this.audioCtx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.01, this.audioCtx.currentTime + 0.3);
        osc.start();
        osc.stop(this.audioCtx.currentTime + 0.3);
      }
    } catch (e) {
      console.warn("Error playing audio feedback:", e);
    }
  }

  async startCamera() {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      this.showStatus("Camera API not supported in this browser. Please use manual entry.", "danger");
      return;
    }

    try {
      if (this.stream) {
        this.stopCamera();
      }

      this.stream = await navigator.mediaDevices.getUserMedia({
        video: {
          facingMode: this.facingMode,
          width: { ideal: 1280 },
          height: { ideal: 720 }
        },
        audio: false
      });

      if (this.videoElement) {
        this.videoElement.srcObject = this.stream;
        await this.videoElement.play();
        this.isScanning = true;
        this.startDetectionLoop();
        this.showStatus("Camera ready. Position member QR code in frame.", "info");
      }
    } catch (err) {
      console.error("Camera access error:", err);
      let msg = "Camera access denied. Please allow camera permissions or use manual check-in.";
      if (err.name === "NotFoundError" || err.name === "DevicesNotFoundError") {
        msg = "No camera device detected on this system. Use manual check-in below.";
      }
      this.showStatus(msg, "warning");
    }
  }

  stopCamera() {
    this.isScanning = false;
    if (this.scanInterval) {
      clearInterval(this.scanInterval);
      this.scanInterval = null;
    }
    if (this.stream) {
      this.stream.getTracks().forEach((track) => track.stop());
      this.stream = null;
    }
  }

  toggleCamera() {
    this.facingMode = this.facingMode === "environment" ? "user" : "environment";
    this.startCamera();
  }

  startDetectionLoop() {
    // Check if browser native BarcodeDetector is supported
    if ("BarcodeDetector" in window) {
      const barcodeDetector = new window.BarcodeDetector({ formats: ["qr_code"] });
      this.scanInterval = setInterval(async () => {
        if (!this.isScanning || !this.videoElement || this.videoElement.readyState < 2) return;
        try {
          const barcodes = await barcodeDetector.detect(this.videoElement);
          if (barcodes.length > 0) {
            const rawValue = barcodes[0].rawValue;
            this.handleDetectedToken(rawValue);
          }
        } catch (e) {
          // ignore frame decode hiccups
        }
      }, 300);
    } else {
      // Fallback message for older browsers
      console.log("BarcodeDetector not native. Ready for camera canvas / manual input.");
    }
  }

  async handleDetectedToken(token) {
    if (!token || token === this.lastScannedToken) return;

    // Cooldown lock to prevent hammering server on continuous frames
    this.lastScannedToken = token;
    clearTimeout(this.cooldownTimeout);
    this.cooldownTimeout = setTimeout(() => {
      this.lastScannedToken = null;
    }, 4000);

    await this.submitToken(token);
  }

  async submitToken(token) {
    const viewport = document.querySelector(".scanner-viewport");
    this.showStatus("Verifying token...", "info");

    try {
      const resp = await fetch("/api/attendance/scan", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRF-Token": document.querySelector('meta[name="csrf-token"]')?.content || ""
        },
        body: JSON.stringify({ qr_token: token })
      });

      const data = await resp.json();

      if (resp.ok && data.success) {
        this.playBeep(true);
        if (viewport) {
          viewport.classList.remove("shake-error");
          viewport.classList.add("scan-success-pulse");
          setTimeout(() => viewport.classList.remove("scan-success-pulse"), 800);
        }
        this.renderSuccess(data);
        // Reload today's attendance table if present
        setTimeout(() => {
          window.location.reload();
        }, 1800);
      } else {
        this.playBeep(false);
        if (viewport) {
          viewport.classList.add("shake-error");
          setTimeout(() => viewport.classList.remove("shake-error"), 500);
        }
        this.renderError(data.message || "Attendance check-in rejected.");
      }
    } catch (err) {
      this.playBeep(false);
      this.renderError("Network error contacting gym server.");
    }
  }

  escapeHtml(value) {
    return String(value ?? "").replace(/[&<>"']/g, (char) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
    }[char]));
  }

  renderSuccess(data) {
    if (!this.resultContainer) return;
    const memberName = this.escapeHtml(data.member_name);
    const memberCode = this.escapeHtml(data.member_code);
    const checkInTime = this.escapeHtml(data.check_in_time);
    const message = this.escapeHtml(data.message);
    this.resultContainer.innerHTML = `
      <div class="alert alert-success animate-slide-up" style="display:flex; gap:14px; align-items:center;">
        <div style="font-size:2rem; line-height:1;">✓</div>
        <div>
          <div style="font-weight:700; font-size:1.05rem;">${memberName}</div>
          <div style="font-size:0.85rem; opacity:0.9;">Member ID: <strong>${memberCode}</strong> • Checked In at <strong>${checkInTime}</strong></div>
          <div style="font-size:0.82rem; margin-top:2px;">${message}</div>
        </div>
      </div>
    `;
  }

  renderError(msg) {
    if (!this.resultContainer) return;
    const safeMessage = this.escapeHtml(msg);
    this.resultContainer.innerHTML = `
      <div class="alert alert-danger animate-slide-up" style="display:flex; gap:14px; align-items:center;">
        <div style="font-size:2rem; line-height:1;">✕</div>
        <div>
          <div style="font-weight:700; font-size:1rem;">Check-in Denied</div>
          <div style="font-size:0.85rem;">${safeMessage}</div>
        </div>
      </div>
    `;
  }

  showStatus(msg, type = "info") {
    if (!this.resultContainer) return;
    this.resultContainer.innerHTML = `
      <div class="alert alert-${type} animate-fade-in" style="font-size:0.88rem; padding:10px 14px;">
        ${msg}
      </div>
    `;
  }
}

// Global Manual Member Check-in
async function submitManualAttendance(memberId) {
  try {
    const resp = await fetch("/api/attendance/manual", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRF-Token": document.querySelector('meta[name="csrf-token"]')?.content || ""
      },
      body: JSON.stringify({ member_id: memberId })
    });
    const data = await resp.json();
    if (resp.ok && data.success) {
      showToast(data.message, "success");
      setTimeout(() => window.location.reload(), 1200);
    } else {
      showToast(data.message || "Manual check-in failed", "danger");
    }
  } catch (err) {
    showToast("Network error during manual check-in", "danger");
  }
}
