import { secondsToSMPTE, smpteToSeconds } from './smpte';

// Simple unit assertion test runner
function assert(condition: boolean, msg: string) {
  if (!condition) throw new Error(`Assertion Failed: ${msg}`);
}

console.log('Running SMPTE unit tests...');

// 0 seconds -> 00:00:00:00
assert(secondsToSMPTE(0) === '00:00:00:00', '0s formatting');

// 1 second @ 24fps -> 00:00:01:00
assert(secondsToSMPTE(1) === '00:00:01:00', '1s formatting');

// 4.5 seconds @ 24fps -> 00:00:04:12
assert(secondsToSMPTE(4.5) === '00:00:04:12', '4.5s formatting (12 frames)');

// Round trip conversion
assert(smpteToSeconds('00:00:04:12') === 4.5, 'SMPTE parse 4.5s');

console.log('✓ All SMPTE unit tests passed (100% Green)');
