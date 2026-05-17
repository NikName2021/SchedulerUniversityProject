import React from "react";
import { NavLink, Outlet } from "react-router-dom";
import {
  Folder,
  CalendarDays,
  Settings,
  Zap,
  History,
  Layout as LayoutIcon,
} from "lucide-react";

import ErrorBoundary from "./ErrorBoundary";

export const Layout: React.FC = () => {
  const navItems = [
    { to: "/", icon: Folder, label: "Хранилище" },
    { to: "/editor", icon: Settings, label: "Редактор пар" },
    { to: "/calendar", icon: CalendarDays, label: "Календарь" },
    { to: "/generation", icon: Zap, label: "Генерация" },
    { to: "/history", icon: History, label: "История" },
    { to: "/schedule", icon: LayoutIcon, label: "Редактор" },
  ];

  return (
    <div className="min-h-screen flex bg-bg-base/30">
      {/* Sidebar Navigation */}
      <header className="sticky top-0 h-screen w-64 bg-white border-r border-border-light p-6 flex flex-col justify-between z-50 shrink-0">
        <div className="flex flex-col w-full">
          {/* Logo / Header Section */}
          <div className="flex items-center gap-3">
            <div className="bg-brand text-white w-10 h-10 rounded-xl flex items-center justify-center font-black text-lg shadow-sm">
              S
            </div>
            <div>
              <h1 className="text-sm font-extrabold text-text-primary tracking-tight leading-tight">
                Scheduler
              </h1>
              <p className="text-[10px] text-text-secondary font-semibold">
                University MVP
              </p>
            </div>
          </div>

          {/* Navigation Items */}
          <nav className="flex flex-col gap-1 w-full mt-8">
            {navItems.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  `flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-semibold transition-all select-none ${
                    isActive
                      ? "bg-brand text-white shadow-md shadow-brand/10"
                      : "text-text-secondary hover:text-brand hover:bg-bg-base"
                  }`
                }
              >
                <item.icon size={18} className="shrink-0" />
                <span>{item.label}</span>
              </NavLink>
            ))}
          </nav>
        </div>

        {/* Bottom Section with User Profile and Settings Button */}
        <div className="border-t border-border-light pt-4 mt-auto flex items-center justify-between w-full">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-brand/10 text-brand flex items-center justify-center font-bold text-sm">
              А
            </div>
            <div>
              <div className="text-xs font-bold text-text-primary">Админ</div>
              <div className="text-[10px] text-text-tertiary">
                Панель управления
              </div>
            </div>
          </div>
          <button
            className="p-2.5 rounded-xl bg-white border border-border-light text-text-secondary hover:text-brand hover:bg-bg-base transition-all shadow-sm"
            title="Настройки"
          >
            <Settings size={18} />
          </button>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="flex-1 p-10 overflow-y-auto">
        <div className="max-w-6xl animate-fade-in">
          <ErrorBoundary>
            <Outlet />
          </ErrorBoundary>
        </div>
      </main>
    </div>
  );
};
