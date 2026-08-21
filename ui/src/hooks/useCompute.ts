import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import type { ComputeProfile, RecommendedModel, EngineItem } from '../types/api';

async function fetchToken(): Promise<string> {
  try {
    const res = await fetch('/api/token');
    if (res.ok) {
      const data = await res.json();
      return data.token || '';
    }
  } catch {
    // fallback
  }
  return '';
}

export function useComputeProfile() {
  return useQuery<ComputeProfile>({
    queryKey: ['compute-profile'],
    queryFn: async () => {
      const res = await fetch('/api/compute/local-profile');
      if (!res.ok) throw new Error('Failed to fetch local compute profile');
      return res.json();
    },
    staleTime: 60000,
  });
}

export function useRecommendedModels() {
  return useQuery<RecommendedModel[]>({
    queryKey: ['recommended-models'],
    queryFn: async () => {
      const res = await fetch('/api/compute/models/recommended');
      if (!res.ok) throw new Error('Failed to fetch recommended models');
      const data = await res.json();
      return data.models || data;
    },
    staleTime: 30000,
  });
}

export function useDownloadModel() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (modelId: string) => {
      const token = await fetchToken();
      const res = await fetch('/api/compute/models/download', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { 'X-Pluto-Token': token } : {}),
        },
        body: JSON.stringify({ model_id: modelId }),
      });
      if (!res.ok) throw new Error('Failed to initiate model download');
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['recommended-models'] });
    },
  });
}

export function useEngines() {
  return useQuery<EngineItem[]>({
    queryKey: ['engines'],
    queryFn: async () => {
      const res = await fetch('/api/engines');
      if (!res.ok) throw new Error('Failed to fetch engine catalogue');
      const data = await res.json();
      return data.engines || data;
    },
    staleTime: 60000,
  });
}
