/**
 * SMPTE Timecode Formatter and Parser
 * Standard 24fps Drop/Non-Drop SMPTE utility
 */

export function secondsToSMPTE(seconds: number, fps = 24): string {
  const totalFrames = Math.floor(seconds * fps);
  const hrs = Math.floor(totalFrames / (fps * 3600));
  const mins = Math.floor((totalFrames % (fps * 3600)) / (fps * 60));
  const secs = Math.floor((totalFrames % (fps * 60)) / fps);
  const frames = Math.floor(totalFrames % fps);

  return [
    String(hrs).padStart(2, '0'),
    String(mins).padStart(2, '0'),
    String(secs).padStart(2, '0'),
    String(frames).padStart(2, '0')
  ].join(':');
}

export function smpteToSeconds(smpte: string, fps = 24): number {
  const parts = smpte.split(':').map(Number);
  if (parts.length !== 4) return 0;
  const [hrs, mins, secs, frames] = parts;
  return hrs * 3600 + mins * 60 + secs + frames / fps;
}
