import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { getSubscriptionCatalog } from "../../../api/client";
import {
  createTelegramLink,
  getDigest,
  getDigestPreferences,
  getDigests,
  getChannels,
  getPreferences,
  saveDigestPreferences,
  savePreferences,
  setTelegramEnabled,
  unlinkTelegram
} from "./api";
import type { DeliveryLanguage, DigestPreferences } from "./models";

const keys = {
  preferences: ["news-notifications", "preferences"] as const,
  channels: ["news-notifications", "channels"] as const,
  catalog: ["subscription-catalog"] as const,
  digestPreferences: ["news-digests", "preferences"] as const
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

export function useDigestPreferences() {
  return useQuery({ queryKey: keys.digestPreferences, queryFn: getDigestPreferences, retry: false, staleTime: 30_000 });
}

export function useSaveDigestPreferences() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (input: Pick<DigestPreferences, "enabled" | "topics">) => saveDigestPreferences(input),
    onSuccess: () => client.invalidateQueries({ queryKey: keys.digestPreferences })
  });
}

export function useDigests(language: DeliveryLanguage, enabled = true) {
  return useQuery({ queryKey: ["news-digests", "list", language], queryFn: () => getDigests(language), enabled, retry: false });
}

export function useDigest(id: string | undefined, language: DeliveryLanguage) {
  return useQuery({ queryKey: ["news-digests", "detail", id, language], queryFn: () => getDigest(id!, language), enabled: Boolean(id), retry: false });
}
