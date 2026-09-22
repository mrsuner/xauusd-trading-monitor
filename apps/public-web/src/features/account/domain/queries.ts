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
      // Logout changes the identity boundary for every authenticated query.
      // Clearing the whole client prevents active digest/settings observers from
      // briefly rendering the previous account's cached data after sign-out.
      client.clear();
    }
  });
}
