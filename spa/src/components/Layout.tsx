import React, { useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import {
  BookOpen,
  CalendarDays,
  ChevronLeft,
  ChevronRight,
  Database,
  FolderInput,
  History,
  LayoutDashboard,
  LogOut,
  Sparkles,
} from "lucide-react";

import siriusLogo from "../assets/sirius-logo.svg";
import { useAuth } from "../auth/useAuth";
import ErrorBoundary from "./ErrorBoundary";

const pageMeta: Record<string, { title: string; description: string }> = {
  "/": {
    title: "Исходные данные",
    description: "Импорт и контроль учебных данных",
  },
  "/editor": {
    title: "Учебные потоки",
    description: "Состав занятий и учебная нагрузка",
  },
  "/calendar": {
    title: "Календарь",
    description: "Учебные периоды и ограничения",
  },
  "/generation": {
    title: "Расчёты",
    description: "Формирование расписания",
  },
  "/history": {
    title: "Журнал операций",
    description: "Версии, результаты и публикации",
  },
  "/schedule": {
    title: "Расписание",
    description: "Проверка и ручное редактирование",
  },
  "/reference": {
    title: "Справочники",
    description: "Аудитории, преподаватели и параметры",
  },
};

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
  const location = useLocation();
  const currentPage =
    pageMeta[location.pathname] ??
    (location.pathname.startsWith("/schedule/")
      ? pageMeta["/schedule"]
      : pageMeta["/"]);
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
              <p className="app-navigation__label">РАБОЧАЯ ОБЛАСТЬ</p>
            )}
            {navItems.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                title={isCollapsed ? item.label : undefined}
                className={({ isActive }) =>
                  `app-nav-link ${isActive ? "app-nav-link--active" : ""}`
                }
              >
                <item.icon size={18} strokeWidth={1.8} />
                {!isCollapsed && <span>{item.label}</span>}
              </NavLink>
            ))}
          </nav>
        </div>

        <div className="app-sidebar__bottom">
          <div className="app-user">
            <div className="app-user__avatar">
              {userLabel.charAt(0).toLocaleUpperCase("ru-RU")}
            </div>
            {!isCollapsed && (
              <div className="app-user__meta">
                <strong>{userLabel}</strong>
                <span>{userRole}</span>
              </div>
            )}
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
        <header className="app-topbar">
          <div>
            <div className="app-topbar__crumb">Рабочее место оператора</div>
            <h1>{currentPage.title}</h1>
          </div>
          <div className="app-topbar__actions">
            {logoutError && (
              <span className="app-topbar__logout-error" role="alert">
                Не удалось выйти
              </span>
            )}
            <div className="app-topbar__status">
              <span className="app-topbar__status-dot" />
              Система доступна
            </div>
            <button
              type="button"
              className="app-topbar__logout"
              onClick={() => void handleLogout()}
              disabled={isLoggingOut}
              title="Выйти из системы"
            >
              <LogOut size={15} />
              <span>Выйти</span>
            </button>
          </div>
        </header>
        <div className="app-content">
          <div className="app-page-intro">
            <p>{currentPage.description}</p>
          </div>
          <ErrorBoundary>
            <Outlet />
          </ErrorBoundary>
        </div>
      </main>
    </div>
  );
};
