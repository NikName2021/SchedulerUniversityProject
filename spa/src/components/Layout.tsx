import React, { useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import {
  Folder,
  CalendarDays,
  Settings,
  Zap,
  History,
  Layout as LayoutIcon,
  ChevronLeft,
  ChevronRight,
  Database,
} from "lucide-react";

import ErrorBoundary from "./ErrorBoundary";

export const Layout: React.FC = () => {
  const [isCollapsed, setIsCollapsed] = useState(false);

  const navItems = [
    { to: "/", icon: Folder, label: "Хранилище" },
    { to: "/editor", icon: Settings, label: "Редактор пар" },
    { to: "/calendar", icon: CalendarDays, label: "Календарь" },
    { to: "/generation", icon: Zap, label: "Генерация" },
    { to: "/history", icon: History, label: "История" },
    { to: "/schedule", icon: LayoutIcon, label: "Редактор" },
    { to: "/reference", icon: Database, label: "Базовые данные" },
  ];

  return (
    <div className="min-h-screen flex bg-bg-base/30">
      {/* Sidebar Navigation */}
      <header
        className={`sticky top-0 h-screen bg-white border-r border-border-light p-6 flex flex-col justify-between z-50 shrink-0 transition-all duration-300 relative ${
          isCollapsed ? "w-20 px-4" : "w-64"
        }`}
      >
        {/* Toggle Collapse Button */}
        <button
          onClick={() => setIsCollapsed(!isCollapsed)}
          className="absolute top-8 -right-3 bg-white border border-border-light text-text-secondary hover:text-brand hover:scale-110 w-6 h-6 rounded-full flex items-center justify-center shadow-sm cursor-pointer z-50 transition-all"
          title={isCollapsed ? "Развернуть меню" : "Свернуть меню"}
        >
          {isCollapsed ? <ChevronRight size={12} /> : <ChevronLeft size={12} />}
        </button>

        <div className="flex flex-col w-full items-center">
          {/* Logo / Header Section */}
          <div
            className={`flex items-center gap-3 w-full transition-all duration-300 ${
              isCollapsed ? "justify-center" : ""
            }`}
          >
            <div className="bg-brand text-white w-10 h-10 rounded-xl flex items-center justify-center font-black text-lg shadow-sm shrink-0">
              S
            </div>
            {!isCollapsed && (
              <div className="animate-fade-in whitespace-nowrap overflow-hidden">
                <h1 className="text-sm font-extrabold text-text-primary tracking-tight leading-tight">
                  Scheduler
                </h1>
                <p className="text-[10px] text-text-secondary font-semibold">
                  University MVP
                </p>
              </div>
            )}
          </div>

          {/* Navigation Items */}
          <nav className="flex flex-col gap-1.5 w-full mt-8">
            {navItems.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                title={isCollapsed ? item.label : undefined}
                className={({ isActive }) =>
                  `flex items-center gap-3 py-3 rounded-xl text-sm font-semibold transition-all select-none ${
                    isCollapsed
                      ? "justify-center px-0 w-12 h-12 self-center"
                      : "px-4 w-full"
                  } ${
                    isActive
                      ? "bg-brand text-white shadow-md shadow-brand/10"
                      : "text-text-secondary hover:text-brand hover:bg-bg-base"
                  }`
                }
              >
                <item.icon size={18} className="shrink-0" />
                {!isCollapsed && (
                  <span className="animate-fade-in whitespace-nowrap overflow-hidden">
                    {item.label}
                  </span>
                )}
              </NavLink>
            ))}
          </nav>
        </div>

        {/* Bottom Section with User Profile and Settings Button */}
        <div
          className={`border-t border-border-light pt-4 mt-auto flex items-center w-full transition-all duration-300 ${
            isCollapsed ? "flex-col gap-3 justify-center" : "justify-between"
          }`}
        >
          <div
            className={`flex items-center gap-3 ${
              isCollapsed ? "justify-center" : ""
            }`}
          >
            <div className="w-9 h-9 rounded-xl bg-brand/10 text-brand flex items-center justify-center font-bold text-sm shrink-0">
              А
            </div>
            {!isCollapsed && (
              <div className="animate-fade-in whitespace-nowrap overflow-hidden">
                <div className="text-xs font-bold text-text-primary">Админ</div>
                <div className="text-[10px] text-text-tertiary">
                  Панель управления
                </div>
              </div>
            )}
          </div>
          <button
            className={`rounded-xl bg-white border border-border-light text-text-secondary hover:text-brand hover:bg-bg-base transition-all shadow-sm ${
              isCollapsed ? "p-2" : "p-2.5"
            }`}
            title="Настройки"
          >
            <Settings size={18} />
          </button>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="flex-1 p-10 overflow-y-auto">
        <div
          className={`transition-all duration-300 animate-fade-in ${
            isCollapsed ? "max-w-none w-full" : "max-w-6xl"
          }`}
        >
          <ErrorBoundary>
            <Outlet />
          </ErrorBoundary>
        </div>
      </main>
    </div>
  );
};
