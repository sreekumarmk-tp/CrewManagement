"use client";
import useSWR from "swr";

import { crewApi } from "@/lib/api";
import type { CrewMember } from "@/types";

interface CrewData {
  signOn: CrewMember[];
  signOff: CrewMember[];
}

// Stable empty reference for the pre-load state. Returning a fresh `[]` each
// render would change identity every time and retrigger consumers' effects
// (e.g. the dashboard's store-sync effect) on every render.
const EMPTY: CrewMember[] = [];

// Both crew lists are fetched together (mirrors the old Promise.all) under one
// SWR key so they share a single cache entry and revalidation cycle.
const fetchCrew = async (): Promise<CrewData> => {
  const [signOn, signOff] = await Promise.all([
    crewApi.getSignOnCrew(),
    crewApi.getSignOffCrew(),
  ]);
  return { signOn, signOff };
};

/**
 * Step 4 — frontend data caching for the read-only crew lists.
 *
 * SWR gives us, for free, what the manual mount-time fetch did not:
 *  - request dedup: many mounts/components → a single network call,
 *  - a shared client-side cache that survives view navigation,
 *  - stale-while-revalidate (keepPreviousData) so the UI renders cached crew
 *    instantly and refreshes silently in the background,
 *  - revalidate-on-focus, plus `refresh()` for event-driven invalidation
 *    (e.g. a `crew_signed_on` WebSocket event).
 *
 * Mutations (POST /workflow/*) and the live WebSocket stream are intentionally
 * NOT routed through here — they are inherently dynamic.
 */
export function useCrew() {
  const { data, error, isLoading, isValidating, mutate } = useSWR<CrewData>("crew", fetchCrew, {
    revalidateOnFocus: true,
    // Collapse duplicate fetches within the window; pairs with the backend's
    // 30-minute Redis/HTTP cache so the crew list isn't re-pulled needlessly.
    dedupingInterval: 30_000,
    keepPreviousData: true,
  });

  return {
    signOnCrew: data?.signOn ?? EMPTY,
    signOffCrew: data?.signOff ?? EMPTY,
    // True only on the very first load (keepPreviousData keeps later
    // revalidations from flipping this back to true).
    isLoading: isLoading && !data,
    // True while a background revalidation is in flight over already-cached data
    // (drives the dashboard's "cached / revalidating" badge).
    isValidating: isValidating && !!data,
    error,
    // Revalidate on demand — used for WebSocket-driven crew refreshes.
    refresh: () => mutate(),
  };
}
