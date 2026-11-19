import React, { Suspense, useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import {
  BookOpen,
  CalendarDays,
  ChevronLeft,
  ChevronRight,
  Database,
  FolderInput,
  Globe2,
  History,
  LayoutDashboard,
  LogOut,
  Sparkles,
} from "lucide-react";

import siriusLogo from "../assets/sirius-logo.svg";
import { useAuth } from "../auth/useAuth";
import { FeedbackProvider } from "./FeedbackProvider";
import ErrorBoundary from "./ErrorBoundary";

const navItems = [
  { to: "/", icon: FolderInput, label: "Исходные данные", end: true },
  { to: "/editor", icon: BookOpen, label: "Учебные потоки" },
  { to: "/calendar", icon: CalendarDays, label: "Календарь" },
  { to: "/generation", icon: Sparkles, label: "Расчёты" },
  { to: "/history", icon: History, label: "Журнал операций" },
  { to: "/schedule", icon: LayoutDashboard, label: "Расписание" },
  { to: "/reference", icon: Database, label: "Справочники" },
];

export const Layout: React.FC = () => {
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [isLoggingOut, setIsLoggingOut] = useState(false);
  const [logoutError, setLogoutError] = useState(false);
  const { user, logout } = useAuth();
  const userLabel = user?.display_name || user?.username || "Пользователь";
  const userRole = user?.role === "admin" ? "Администратор" : "Оператор";

  const handleLogout = async () => {
    setLogoutError(false);
    setIsLoggingOut(true);
    try {
      await logout();
    } catch {
      setLogoutError(true);
    } finally {
      setIsLoggingOut(false);
    }
  };

  return (
    <div className={`app-shell ${isCollapsed ? "app-shell--compact" : ""}`}>
      <aside className="app-sidebar">
        <div className="app-sidebar__top">
          <div className="app-brand">
            {isCollapsed ? (
              <div className="app-brand__mark" aria-label="Система расписаний">
                SC
              </div>
            ) : (
              <img
                className="app-brand__logo"
                src={siriusLogo}
                alt="Университет Сириус"
              />
            )}
          </div>

          <button
            type="button"
            onClick={() => setIsCollapsed((value) => !value)}
            className="app-sidebar__collapse"
            title={isCollapsed ? "Развернуть меню" : "Свернуть меню"}
            aria-label={isCollapsed ? "Развернуть меню" : "Свернуть меню"}
          >
            {isCollapsed ? (
              <ChevronRight size={16} />
            ) : (
              <ChevronLeft size={16} />
            )}
          </button>

          <nav className="app-navigation" aria-label="Основная навигация">
            {!isCollapsed && (
              <p className="app-navigation__label">ЛИЧНОЕ ПРОСТРАНСТВО</p>
            )}
            {navItems.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                title={isCollapsed ? item.label : undefined}
                aria-label={item.label}
                className={({ isActive }) =>
                  `app-nav-link ${isActive ? "app-nav-link--active" : ""}`
                }
              >
                <item.icon size={18} strokeWidth={1.8} />
                <span>{item.label}</span>
              </NavLink>
            ))}
            {!isCollapsed && <p className="app-navigation__label">ОБЩЕЕ</p>}
            <NavLink
              to="/published"
              title={isCollapsed ? "Общий каталог" : undefined}
              aria-label="Общий каталог"
              className={({ isActive }) =>
                `app-nav-link ${isActive ? "app-nav-link--active" : ""}`
              }
            >
              <Globe2 size={18} strokeWidth={1.8} />
              <span>Общий каталог</span>
            </NavLink>
          </nav>
        </div>

        <div className="app-sidebar__bottom">
          <div className="app-user">
            <div className="app-user__avatar">
              {userLabel.charAt(0).toLocaleUpperCase("ru-RU")}
            </div>
            <div className="app-user__meta">
              <strong>{userLabel}</strong>
              <span>{userRole}</span>
            </div>
          </div>
          <button
            type="button"
            className="app-sidebar__settings"
            title="Выйти"
            aria-label="Выйти"
            onClick={() => void handleLogout()}
            disabled={isLoggingOut}
          >
            <LogOut size={17} />
          </button>
        </div>
      </aside>

      <main className="app-main">
        <div className="app-content">
          {logoutError && (
            <p className="notice notice--danger" role="alert">
              Не удалось выйти
            </p>
          )}
          <ErrorBoundary>
            <FeedbackProvider>
              <Suspense
                fallback={
                  <p role="status" className="loading-state">
                    Загрузка страницы…
                  </p>
                }
              >
                <Outlet />
              </Suspense>
            </FeedbackProvider>
          </ErrorBoundary>
        </div>
      </main>
    </div>
  );
};
