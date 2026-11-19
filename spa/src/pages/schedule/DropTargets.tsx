import type React from "react";
import { useDroppable } from "@dnd-kit/core";

export const DroppableCell: React.FC<{
  dayIdx: number;
  pairNum: number;
  children: React.ReactNode;
  showAvailability: boolean;
  isAvailable: boolean;
}> = ({ dayIdx, pairNum, children, showAvailability, isAvailable }) => {
  const { isOver, setNodeRef } = useDroppable({
    id: `cell-${dayIdx}-${pairNum}`,
    data: { dayIdx, pairNum },
  });

  return (
    <td
      ref={setNodeRef}
      title={
        showAvailability
          ? isAvailable
            ? "Свободно для группы и преподавателя"
            : "Слот занят группой или преподавателем"
          : undefined
      }
      className={`p-1.5 border-l border-border-light align-top min-h-[140px] transition-colors relative ${
        showAvailability
          ? isAvailable
            ? isOver
              ? "bg-amber-200 ring-2 ring-amber-400 ring-inset"
              : "bg-amber-50 ring-1 ring-amber-300 ring-inset"
            : isOver
              ? "bg-red-50 ring-2 ring-red-200 ring-inset"
              : "bg-slate-50/70"
          : isOver
            ? "bg-brand/5"
            : "bg-white hover:bg-gray-50/30"
      }`}
    >
      <div className="flex flex-col gap-2 min-h-[100px]">{children}</div>
    </td>
  );
};

export const SidebarDroppable: React.FC<{ children: React.ReactNode }> = ({
  children,
}) => {
  const { isOver, setNodeRef } = useDroppable({
    id: "sidebar",
    data: { isSidebar: true },
  });

  return (
    <div
      ref={setNodeRef}
      className={`flex-1 overflow-y-auto p-3 transition-colors ${isOver ? "bg-brand/5 ring-2 ring-brand ring-inset" : ""}`}
    >
      <div className="grid grid-cols-1 gap-3">{children}</div>
    </div>
  );
};
