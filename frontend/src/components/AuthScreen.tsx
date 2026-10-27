import { useEffect, useRef, useState, type FormEvent } from "react";
import { ArrowRight, Heart, ShieldCheck, Sparkles } from "lucide-react";
import { useAuth } from "../contexts/AuthContext";
import { api } from "../services/api";

declare global {
  interface Window {
    google?: {
      accounts: {
        id: {
          initialize: (options: {
            client_id: string;
            callback: (response: { credential: string }) => void;
          }) => void;
          renderButton: (
            element: HTMLElement,
            options: { theme: string; size: string; text: string; shape: string; width: number },
          ) => void;
        };
      };
    };
  }
}

export default function AuthScreen() {
  const initialParams = new URLSearchParams(window.location.search);
  const initialResetToken = initialParams.get("reset");
  const verificationToken = initialParams.get("verify");
  const [mode, setMode] = useState<"signin" | "register" | "forgot" | "reset">(initialResetToken ? "reset" : "signin");
  const [resetToken] = useState(initialResetToken);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [notice, setNotice] = useState("");
  const [localError, setLocalError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [googleClientId, setGoogleClientId] = useState<string | null | undefined>();
  const [googleConfigError, setGoogleConfigError] = useState("");
  const googleButton = useRef<HTMLDivElement>(null);
  const googleCredentialHandler = useRef<(credential: string) => void>(() => undefined);
  const { signIn, signInWithGoogle, signUp, error, clearError } = useAuth();
  const registering = mode === "register";

  useEffect(() => {
    api.googleAuthConfig().then(({ client_id }) => {
      setGoogleClientId(client_id);
    }).catch((reason: unknown) => {
      setGoogleConfigError(reason instanceof Error ? reason.message : "Google sign-in configuration is unavailable.");
    });
  }, []);

  useEffect(() => {
    googleCredentialHandler.current = (credential) => {
      setSubmitting(true);
      setLocalError("");
      clearError();
      signInWithGoogle(credential).catch((reason: unknown) => {
        setLocalError(reason instanceof Error ? reason.message : "Unable to sign in with Google.");
      }).finally(() => setSubmitting(false));
    };
  }, [clearError, signInWithGoogle]);

  useEffect(() => {
    if (!googleClientId || !googleButton.current || (mode !== "signin" && mode !== "register")) return;
    let active = true;
    const renderGoogleButton = () => {
      if (!active || !googleButton.current || !window.google) return;
      window.google.accounts.id.initialize({
        client_id: googleClientId,
        callback: ({ credential }) => googleCredentialHandler.current(credential),
      });
      googleButton.current.replaceChildren();
      window.google.accounts.id.renderButton(googleButton.current, {
        theme: "outline",
        size: "large",
        text: "continue_with",
        shape: "rect",
        width: Math.min(360, googleButton.current.clientWidth || 360),
      });
    };

    let script = document.querySelector<HTMLScriptElement>('script[src="https://accounts.google.com/gsi/client"]');
    if (!script) {
      script = document.createElement("script");
      script.src = "https://accounts.google.com/gsi/client";
      script.async = true;
      script.defer = true;
      document.head.appendChild(script);
    }
    if (window.google) {
      renderGoogleButton();
    } else {
      script.addEventListener("load", renderGoogleButton);
      script.addEventListener("error", () => {
        if (active) setLocalError("Google sign-in could not load. Please try again later.");
      }, { once: true });
    }
    return () => {
      active = false;
      script?.removeEventListener("load", renderGoogleButton);
    };
  }, [googleClientId, mode]);

  useEffect(() => {
    if (!verificationToken) return;
    setSubmitting(true);
    api.verifyEmail(verificationToken).then((result) => {
      setLocalError("");
      setNotice(result.message);
      window.history.replaceState({}, "", window.location.pathname);
    }).catch((reason: unknown) => {
      setLocalError(reason instanceof Error ? reason.message : "Unable to verify this email link.");
      window.history.replaceState({}, "", window.location.pathname);
    }).finally(() => setSubmitting(false));
  }, [verificationToken]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setNotice("");
    setLocalError("");
    try {
      if (registering) {
        setNotice(await signUp(name, email, password));
        setMode("signin");
      } else if (mode === "forgot") {
        setNotice((await api.requestPasswordReset(email)).message);
      } else if (mode === "reset") {
        if (!resetToken) throw new Error("This password-reset link is invalid or expired.");
        setNotice((await api.confirmPasswordReset(resetToken, password)).message);
        setMode("signin");
        window.history.replaceState({}, "", window.location.pathname);
      } else {
        await signIn(email, password);
      }
    } catch (reason) {
      setLocalError(reason instanceof Error ? reason.message : "Unable to complete this request.");
    } finally {
      setSubmitting(false);
    }
  }

  function toggleMode(nextMode: "signin" | "register" | "forgot") {
    setMode(nextMode);
    setNotice("");
    setLocalError("");
    setPassword("");
    clearError();
  }

  return (
    <main className="auth-page">
      <section className="auth-story">
        <a className="brand brand-light" href="/" aria-label="PetVerse home">
          <span className="brand-mark"><Heart size={19} fill="currentColor" /></span>
          <span>petverse<span className="brand-dot">.</span></span>
        </a>
        <div className="story-copy">
          <span className="eyebrow"><Sparkles size={14} /> A little more care, every day</span>
          <h1>All the love.<br /><em>All the care.</em></h1>
          <p>Keep the little things that make a big difference in one happy place.</p>
          <div className="story-note">
            <div className="avatar-stack"><span>🐶</span><span>🐱</span><span>🐰</span></div>
            <span>Made for every kind of <strong>pet family</strong></span>
          </div>
        </div>
        <div className="story-photo" role="img" aria-label="Dog enjoying time outdoors" />
        <div className="photo-caption"><span className="caption-pulse" /> A happier routine starts here</div>
      </section>

      <section className="auth-panel">
        <div className="auth-topline"><span>YOUR PET'S NEW FAVORITE PLACE</span><span className="secure-label"><ShieldCheck size={15} /> Private by design</span></div>
        <div className="auth-form-wrap">
          <div className="form-heading">
            <span className="form-kicker">{registering ? "LET'S GET STARTED" : mode === "reset" ? "ACCOUNT RECOVERY" : mode === "forgot" ? "ACCOUNT RECOVERY" : "WELCOME BACK"}</span>
            <h2>{registering ? "Create your account" : mode === "reset" ? "Choose a new password" : mode === "forgot" ? "Forgot your password?" : "Good to see you."}</h2>
            <p>{registering ? "A calmer care routine is just a few details away." : mode === "reset" ? "Choose a new password for your PetVerse account." : mode === "forgot" ? "We'll email you a secure link if an account matches." : "Your care corner is right where you left it."}</p>
          </div>
          <form onSubmit={submit} className="auth-form">
            {registering && <label>Your name<input value={name} onChange={(event) => setName(event.target.value)} autoComplete="name" minLength={2} required placeholder="Jamie Parker" /></label>}
            {mode !== "reset" && <label>Email address<input type="email" value={email} onChange={(event) => setEmail(event.target.value)} autoComplete="email" required placeholder="you@example.com" /></label>}
            {(registering || mode === "signin" || mode === "reset") && <label>{mode === "reset" ? "New password" : "Password"}<input type="password" value={password} onChange={(event) => setPassword(event.target.value)} autoComplete={registering || mode === "reset" ? "new-password" : "current-password"} minLength={registering || mode === "reset" ? 12 : 1} required placeholder={registering || mode === "reset" ? "At least 12 characters" : "Enter your password"} /></label>}
            {(localError || error) && <div role="alert" className="form-error">{localError || error}</div>}
            {notice && <div role="status" className="form-success">{notice}</div>}
            <button className="button button-primary button-full" type="submit" disabled={submitting}>
              {submitting ? "One moment…" : registering ? "Create account" : mode === "forgot" ? "Send reset link" : mode === "reset" ? "Save new password" : "Sign in"} <ArrowRight size={17} />
            </button>
          </form>
          {(mode === "signin" || mode === "register") && <div className="google-signin">
            <div className="google-divider"><span>or continue with</span></div>
            {googleClientId
              ? <div ref={googleButton} className="google-button" />
              : <div className="google-pending">
                <button className="google-pending-button" type="button" disabled>
                  <span className="google-g-mark" aria-hidden="true">G</span>
                  Continue with Google
                </button>
                <p role="status" className="google-unavailable">
                  {googleConfigError || (googleClientId === null
                    ? "Google sign-in needs to be configured by the site owner."
                    : "Loading sign-in options…")}
                </p>
              </div>}
          </div>}
          {mode === "signin" && <div className="auth-secondary-actions">
            <button onClick={() => toggleMode("forgot")}>Forgot password?</button>
            <button onClick={async () => {
              setNotice("");
              setLocalError("");
              setSubmitting(true);
              clearError();
              try {
                setNotice((await api.resendVerification(email)).message);
              } catch (reason) {
                setLocalError(reason instanceof Error ? reason.message : "Unable to send a verification link.");
              } finally {
                setSubmitting(false);
              }
            }} disabled={submitting}>Resend verification email</button>
          </div>}
          {mode === "register" && <p className="mode-toggle">Already have an account? <button onClick={() => toggleMode("signin")}>Sign in</button></p>}
          {mode !== "register" && mode !== "signin" && <p className="mode-toggle"><button onClick={() => toggleMode("signin")}>Back to sign in</button></p>}
          {mode === "signin" && <p className="mode-toggle">New to PetVerse? <button onClick={() => toggleMode("register")}>Create an account</button></p>}
          <div className="security-note"><ShieldCheck size={16} /> Your account is protected with secure, private sign-in.</div>
        </div>
        <footer className="auth-footer">Thoughtful care, for every tail and whisker. <span>© PetVerse</span></footer>
      </section>
    </main>
  );
}
