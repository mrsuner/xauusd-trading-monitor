import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { getAccountSession, login, logout, register } from "./api";

export const accountKeys = {
  session: ["account", "session"] as const
};

export function useAccountSession() {
  return useQuery({
    queryKey: accountKeys.session,
    queryFn: getAccountSession,
    retry: false,
    staleTime: 60_000
  });
}

export function useLogin() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: login,
    onSuccess: (session) => {
      client.setQueryData(accountKeys.session, session);
    }
  });
}

export function useRegister() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: register,
    onSuccess: (session) => {
      client.setQueryData(accountKeys.session, session);
    }
  });
}

export function useLogout() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: logout,
    onSuccess: () => {
      client.removeQueries({ queryKey: accountKeys.session });
      client.removeQueries({ queryKey: ["news-notifications"] });
      client.removeQueries({ queryKey: ["news-digests"] });
    }
  });
}
