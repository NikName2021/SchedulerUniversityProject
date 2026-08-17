import { useState, type FormEvent } from "react";
import { Eye, EyeOff, LockKeyhole } from "lucide-react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";

import siriusLogo from "../assets/sirius-logo.svg";
import { useAuth } from "../auth/useAuth";

type LoginLocationState = {
  from?: { pathname?: string; search?: string };
};

export const LoginPage = () => {
  const { user, isLoading, login } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  if (!isLoading && user) {
    return <Navigate to="/" replace />;
  }

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      await login(username, password);
      const state = location.state as LoginLocationState | null;
      const pathname = state?.from?.pathname;
      const safePath = pathname?.startsWith("/") && !pathname.startsWith("//");
      navigate(safePath ? `${pathname}${state?.from?.search ?? ""}` : "/", {
        replace: true,
      });
    } catch (loginError) {
      setError(
        loginError instanceof Error
          ? loginError.message
          : "Не удалось выполнить вход",
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <main className="login-page">
      <section className="login-panel" aria-labelledby="login-title">
        <div className="login-panel__brand">
          <img src={siriusLogo} alt="Университет Сириус" />
          <span>Система управления расписанием</span>
        </div>

        <div className="login-panel__icon" aria-hidden="true">
          <LockKeyhole size={22} />
        </div>
        <h1 id="login-title">Вход в систему</h1>
        <p className="login-panel__subtitle">
          Используйте учётную запись оператора или администратора.
        </p>

        <form className="login-form" onSubmit={handleSubmit}>
          <label htmlFor="username">Имя пользователя</label>
          <input
            id="username"
            name="username"
            type="text"
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            autoComplete="username"
            autoCapitalize="none"
            spellCheck={false}
            minLength={3}
            maxLength={64}
            required
            disabled={isSubmitting}
            autoFocus
          />

          <label htmlFor="password">Пароль</label>
          <div className="login-form__password">
            <input
              id="password"
              name="password"
              type={showPassword ? "text" : "password"}
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              autoComplete="current-password"
              maxLength={128}
              required
              disabled={isSubmitting}
            />
            <button
              type="button"
              onClick={() => setShowPassword((current) => !current)}
              aria-label={showPassword ? "Скрыть пароль" : "Показать пароль"}
              title={showPassword ? "Скрыть пароль" : "Показать пароль"}
            >
              {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
            </button>
          </div>

          {error && (
            <div className="login-form__error" role="alert">
              {error === "Invalid username or password"
                ? "Неверное имя пользователя или пароль"
                : error}
            </div>
          )}

          <button
            className="login-form__submit"
            type="submit"
            disabled={isSubmitting || isLoading}
          >
            {isSubmitting ? "Выполняется вход…" : "Войти"}
          </button>
        </form>
      </section>
    </main>
  );
};
