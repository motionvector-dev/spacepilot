import { useQueries, useQuery } from '@tanstack/react-query';
import { fleet } from '../lib/fleet';

/** How often each thing is worth re-reading.
 *
 * The dock is the only fast poll, because it is the only thing that can start
 * costing money between two glances. Hardware does not change while you look
 * at it, and probing runtimes shells out to the interpreter. */
const DOCK_MS = 10_000;
const SLOW_MS = 60_000;

export function useProfile() {
  return useQuery({
    queryKey: ['profile'],
    queryFn: fleet.profile,
    refetchInterval: SLOW_MS,
  });
}

export function useDock() {
  return useQuery({
    queryKey: ['dock'],
    queryFn: fleet.dock,
    refetchInterval: DOCK_MS,
  });
}

export function useRuntimes() {
  return useQuery({
    queryKey: ['runtimes'],
    queryFn: fleet.runtimes,
    refetchInterval: SLOW_MS,
  });
}

export function useSystems() {
  return useQuery({ queryKey: ['systems'], queryFn: fleet.systems });
}

export function useCompatibility() {
  return useQuery({
    queryKey: ['compatibility'],
    queryFn: fleet.compatibility,
    refetchInterval: SLOW_MS,
  });
}

export function useFlown() {
  return useQuery({ queryKey: ['summary'], queryFn: fleet.summary });
}

/** Everything the glance view needs, in one call, so the page has a single
 *  place to ask "is any of this stale" and "did any of it fail". */
export function useGlance() {
  const results = useQueries({
    queries: [
      { queryKey: ['profile'], queryFn: fleet.profile, refetchInterval: SLOW_MS },
      { queryKey: ['dock'], queryFn: fleet.dock, refetchInterval: DOCK_MS },
      { queryKey: ['runtimes'], queryFn: fleet.runtimes, refetchInterval: SLOW_MS },
      { queryKey: ['systems'], queryFn: fleet.systems },
      { queryKey: ['summary'], queryFn: fleet.summary },
      {
        queryKey: ['compatibility'],
        queryFn: fleet.compatibility,
        refetchInterval: SLOW_MS,
      },
    ],
  });
  const [profile, dock, runtimes, systems, flown, compat] = results;
  return {
    profile,
    dock,
    runtimes,
    systems,
    flown,
    compat,
    /** The oldest successful read on the page. The header quotes this, because
     *  a header that quoted the newest one would age slower than the screen. */
    oldestUpdate: Math.min(
      ...results.filter((r) => r.dataUpdatedAt > 0).map((r) => r.dataUpdatedAt),
      Date.now(),
    ),
    /** True only when nothing at all answered — the daemon is down, rather
     *  than one route being unhappy. */
    allFailed: results.every((r) => r.isError),
  };
}
