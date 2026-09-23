import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { getReaderPreferences, saveReaderPreferences } from "./api";
import type { ReaderPreferences } from "./models";

export const readerPreferenceKeys = {
  detail: ["reader-preferences"] as const
};

export function useReaderPreferences(enabled = true) {
  return useQuery({
    queryKey: readerPreferenceKeys.detail,
    queryFn: getReaderPreferences,
    enabled,
    retry: false,
    staleTime: 0,
    refetchOnMount: "always"
  });
}

export function useSaveReaderPreferences() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: saveReaderPreferences,
    onSuccess: (preferences: ReaderPreferences) => {
      client.setQueryData(readerPreferenceKeys.detail, preferences);
    }
  });
}
