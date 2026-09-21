import { Eye, EyeOff } from "lucide-react";
import { FormEvent, useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useI18n, useLanguage, useLocalizedPath } from "../../../i18n";
import { AccountApiError } from "../domain/api";
import { useAccountSession, useLogin, useRegister } from "../domain/queries";

export function AuthPage({ mode }: { mode: "login" | "register" }) {
  const t = useI18n().auth;
  const lang = useLanguage();
  const to = useLocalizedPath();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const session = useAccountSession();
  const login = useLogin();
  const register = useRegister();
  const mutation = mode === "login" ? login : register;
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [passwordConfirmation, setPasswordConfirmation] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);
  const returnTo = safeReturnTo(searchParams.get("returnTo"), lang, to("/events"));

  useEffect(() => {
    if (session.data) navigate(returnTo, { replace: true });
  }, [navigate, returnTo, session.data]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLocalError(null);

    if (mode === "register" && password !== passwordConfirmation) {
      setLocalError(t.passwordMismatch);
      return;
    }

    try {
      if (mode === "login") {
        await login.mutateAsync({ email: email.trim(), password });
      } else {
        await register.mutateAsync({
          name: name.trim(),
          email: email.trim(),
          password,
          passwordConfirmation
        });
      }
      navigate(returnTo, { replace: true });
    } catch {
      // The mutation error is rendered below with field-level API details.
    }
  }

  const error = localError ?? messageFor(mutation.error, t.genericError);
  const switchSearch = `?returnTo=${encodeURIComponent(returnTo)}`;

  return (
    <div className="mx-auto grid min-h-[calc(100dvh-4rem)] max-w-7xl place-items-center px-4 py-10 sm:px-6 lg:px-8">
      <section className="w-full max-w-md rounded-box border border-base-300 bg-base-200/55 p-6 shadow-sm sm:p-8">
        <p className="font-mono text-xs uppercase tracking-[0.16em] text-primary">TickBase News</p>
        <h1 className="mt-3 text-3xl font-semibold tracking-tight">
          {mode === "login" ? t.signInTitle : t.registerTitle}
        </h1>
        <p className="mt-3 text-sm leading-6 text-base-content/65">
          {mode === "login" ? t.signInBody : t.registerBody}
        </p>

        <form className="mt-7 grid gap-5" onSubmit={submit}>
          {mode === "register" && (
            <label className="grid gap-2">
              <span className="text-sm font-medium">{t.name}</span>
              <input
                className="input input-bordered w-full bg-base-100"
                name="name"
                autoComplete="name"
                required
                value={name}
                onChange={(event) => setName(event.target.value)}
              />
              <FieldError error={fieldError(mutation.error, "name")} />
            </label>
          )}

          <label className="grid gap-2">
            <span className="text-sm font-medium">{t.email}</span>
            <input
              className="input input-bordered w-full bg-base-100"
              name="email"
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(event) => setEmail(event.target.value)}
            />
            <FieldError error={fieldError(mutation.error, "email")} />
          </label>

          <label className="grid gap-2">
            <span className="text-sm font-medium">{t.password}</span>
            <span className="input input-bordered flex w-full items-center gap-2 bg-base-100">
              <input
                className="min-w-0 grow"
                name="password"
                type={showPassword ? "text" : "password"}
                autoComplete={mode === "login" ? "current-password" : "new-password"}
                minLength={8}
                required
                value={password}
                onChange={(event) => setPassword(event.target.value)}
              />
              <button
                className="btn btn-ghost btn-circle btn-xs"
                type="button"
                aria-label={showPassword ? t.hidePassword : t.showPassword}
                onClick={() => setShowPassword((visible) => !visible)}
              >
                {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            </span>
            <FieldError error={fieldError(mutation.error, "password")} />
          </label>

          {mode === "register" && (
            <label className="grid gap-2">
              <span className="text-sm font-medium">{t.passwordConfirmation}</span>
              <input
                className="input input-bordered w-full bg-base-100"
                name="password_confirmation"
                type={showPassword ? "text" : "password"}
                autoComplete="new-password"
                minLength={8}
                required
                value={passwordConfirmation}
                onChange={(event) => setPasswordConfirmation(event.target.value)}
              />
            </label>
          )}

          {error && <div className="alert alert-error py-3 text-sm"><span>{error}</span></div>}

          <button className="btn btn-primary w-full" type="submit" disabled={mutation.isPending}>
            {mutation.isPending
              ? mode === "login" ? t.signingIn : t.creatingAccount
              : mode === "login" ? t.signIn : t.createAccount}
          </button>
        </form>

        <p className="mt-6 text-center text-sm text-base-content/60">
          {mode === "login" ? t.noAccount : t.haveAccount}{" "}
          <Link
            className="font-medium text-primary hover:underline"
            to={to(mode === "login" ? "/register" : "/sign-in", switchSearch)}
          >
            {mode === "login" ? t.createAccount : t.signIn}
          </Link>
        </p>
      </section>
    </div>
  );
}

function safeReturnTo(value: string | null, lang: string, fallback: string): string {
  if (!value || !value.startsWith(`/${lang}/`) || value.startsWith("//")) return fallback;
  return value;
}

function fieldError(error: unknown, field: string): string | null {
  return error instanceof AccountApiError ? error.fields?.[field]?.[0] ?? null : null;
}

function messageFor(error: unknown, fallback: string): string | null {
  if (!error) return null;
  if (error instanceof AccountApiError && error.fields && Object.keys(error.fields).length > 0) return null;
  return error instanceof Error ? error.message : fallback;
}

function FieldError({ error }: { error: string | null }) {
  return error ? <span className="text-sm text-error">{error}</span> : null;
}
