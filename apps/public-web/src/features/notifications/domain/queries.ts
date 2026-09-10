import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { getSubscriptionCatalog } from "../../../api/client";
import {
  createTelegramLink,
  getChannels,
  getPreferences,
  savePreferences,
  setTelegramEnabled,
  unlinkTelegram
} from "./api";

const keys = {
  preferences: ["news-notifications", "preferences"] as const,
  channels: ["news-notifications", "channels"] as const,
  catalog: ["subscription-catalog"] as const
};

export function useNotificationSettings() {
  return useQuery({ queryKey: keys.preferences, queryFn: getPreferences, retry: false, staleTime: 30_000 });
}

export function useNotificationChannels(enabled: boolean) {
  return useQuery({ queryKey: keys.channels, queryFn: getChannels, enabled, retry: false, staleTime: 10_000 });
}

export function useSubscriptionCatalog() {
  return useQuery({ queryKey: keys.catalog, queryFn: getSubscriptionCatalog, staleTime: 300_000 });
}

export function useSavePreferences() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: savePreferences,
    onSuccess: (preferences) => client.setQueryData(keys.preferences, (current: { access: string } | undefined) => ({
      access: current?.access ?? "active",
      preferences
    }))
  });
}

export function useCreateTelegramLink() {
  return useMutation({ mutationFn: createTelegramLink });
}

export function useSetTelegramEnabled() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: setTelegramEnabled,
    onSuccess: () => client.invalidateQueries({ queryKey: keys.channels })
  });
}

export function useUnlinkTelegram() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: unlinkTelegram,
    onSuccess: async () => {
      await client.invalidateQueries({ queryKey: keys.channels });
      await client.invalidateQueries({ queryKey: keys.preferences });
    }
  });
}
