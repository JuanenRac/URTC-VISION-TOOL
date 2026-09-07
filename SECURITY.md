# Security Policy 🔒 (URTC-VISION-TOOL)

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.x.x  | ✅ Yes             |

## Reporting a Vulnerability

**CRITICAL: Do not report safety-critical vulnerabilities through public GitHub issues.**

In a perception toolhead, a security flaw can lead to "blind spots" or spoofed thermal data, bypassing safety zones. If you discover a vulnerability affecting the **thermal sensor readout**, **USB stream hijacking**, or **CAN telemetry spoofing**:

1. **Email**: Send a detailed report to `electrohobby3d@gmail.com`.
2. **Impact**: Describe if the bug allows hiding hot-spots, injecting malicious RGB frames, or crashing the toolhead controller during critical motion.
3. **Response**: Initial acknowledgment within 48 hours.

We follow a coordinated disclosure policy to ensure hardware safety before public release.
