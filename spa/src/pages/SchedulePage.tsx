import React, { createContext, useContext, useState } from 'react';
import { 
  Calendar, 
  ChevronLeft, 
  ChevronRight, 
  Filter, 
  Download, 
  AlertTriangle,
  Info,
  Users as UsersIcon
} from 'lucide-react';

const DAYS = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота'];
const TIME_SLOTS = [
  { id: 1, time: '09:00 - 10:30' },
  { id: 2, time: '10:45 - 12:15' },
  { id: 3, time: '13:00 - 14:30' },
  { id: 4, time: '14:45 - 16:15' },
  { id: 5, time: '16:30 - 18:00' },
  { id: 6, time: '18:15 - 19:45' },
];

interface ScheduleEntry {
  day: string;
  slot: number;
  subject: string;
  teacher: string;
  room: string;
  type: 'lec' | 'sem';
  isConflict?: boolean;
}

const MOCK_SCHEDULE: ScheduleEntry[] = [
  { day: 'Понедельник', slot: 1, subject: 'Высшая математика', teacher: 'Иванов А.С.', room: '101', type: 'lec' },
  { day: 'Понедельник', slot: 2, subject: 'Информатика', teacher: 'Петров В.М.', room: '302', type: 'sem' },
  { day: 'Вторник', slot: 3, subject: 'Физика', teacher: 'Сидорова Е.Ю.', room: '204', type: 'lec', isConflict: true },
  { day: 'Среда', slot: 1, subject: 'Иностранный язык', teacher: 'Смит Дж.', room: '501', type: 'sem' },
  { day: 'Четверг', slot: 4, subject: 'Базы данных', teacher: 'Козлов Д.А.', room: '102', type: 'lec' },
];

// --- Compound Components ---

const ScheduleContext = createContext<{ getEntry: (day: string, slot: number) => ScheduleEntry | undefined } | null>(null);

const ScheduleGrid = ({ children, entries }: { children: React.ReactNode, entries: ScheduleEntry[] }) => {
  const getEntry = (day: string, slot: number) => entries.find(e => e.day === day && e.slot === slot);
  
  return (
    <ScheduleContext.Provider value={{ getEntry }}>
      <div style={{
        backgroundColor: 'white',
        borderRadius: '24px',
        boxShadow: 'var(--shadow-md)',
        border: '1px solid var(--border-light)',
        overflow: 'hidden'
      }}>
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            {children}
          </table>
        </div>
      </div>
    </ScheduleContext.Provider>
  );
};

ScheduleGrid.Header = ({ days }: { days: string[] }) => (
  <thead>
    <tr style={{ backgroundColor: 'rgba(15, 76, 129, 0.05)', borderBottom: '1px solid var(--border-light)' }}>
      <th style={{ padding: '1.25rem', textAlign: 'left', fontSize: '0.625rem', fontWeight: 900, textTransform: 'uppercase', color: 'rgba(15, 76, 129, 0.5)', width: '96px' }}>Время</th>
      {days.map(day => (
        <th key={day} style={{ padding: '1.25rem', textAlign: 'center', fontSize: '0.75rem', fontWeight: 900, textTransform: 'uppercase', color: 'var(--brand)', letterSpacing: '0.1em' }}>{day}</th>
      ))}
    </tr>
  </thead>
);

ScheduleGrid.Row = ({ slot, children }: { slot: typeof TIME_SLOTS[0], children: React.ReactNode }) => (
  <tr style={{ borderBottom: '1px solid var(--border-light)' }}>
    <td style={{ padding: '1rem', backgroundColor: 'rgba(244, 245, 248, 0.2)', borderRight: '1px solid rgba(229, 231, 235, 0.5)' }}>
      <div style={{ fontSize: '0.875rem', fontWeight: 900, color: 'var(--brand)' }}>{slot.id} пара</div>
      <div style={{ fontSize: '0.625rem', fontWeight: 700, color: 'var(--text-tertiary)', marginTop: '0.25rem', whiteSpace: 'nowrap' }}>{slot.time}</div>
    </td>
    {children}
  </tr>
);

const ScheduleGridCell = ({ day, slotId }: { day: string, slotId: number }) => {
  const context = useContext(ScheduleContext);
  const entry = context?.getEntry(day, slotId);
  
  return (
    <td style={{ padding: '0.5rem', height: '128px', width: '16.66%', borderRight: '1px solid rgba(229, 231, 235, 0.3)', verticalAlign: 'top' }}>
      {entry ? <ClassCard entry={entry} /> : <div className="empty-slot" style={{ height: '100%', borderRadius: '16px', border: '1px dashed rgba(229, 231, 235, 0.5)' }} />}
    </td>
  );
};
ScheduleGrid.Cell = ScheduleGridCell;

const ClassCard = ({ entry }: { entry: ScheduleEntry }) => (
  <div style={{
    height: '100%',
    borderRadius: '16px',
    padding: '1rem',
    display: 'flex',
    flexDirection: 'column',
    justifyContent: 'space-between',
    transition: 'all var(--transition-fast)',
    cursor: 'grab',
    backgroundColor: entry.isConflict ? '#FFF1F2' : 'rgba(15, 76, 129, 0.05)',
    border: entry.isConflict ? '2px solid #FECDD3' : '1px solid rgba(15, 76, 129, 0.1)',
    color: entry.isConflict ? '#9F1239' : 'inherit'
  }} className="schedule-card">
    <div className="space-y-1">
      <div className="flex justify-between" style={{ alignItems: 'flex-start' }}>
        <span style={{
          fontSize: '0.5625rem',
          fontWeight: 900,
          textTransform: 'uppercase',
          padding: '0.125rem 0.5rem',
          borderRadius: '100px',
          display: 'inline-block',
          backgroundColor: entry.type === 'lec' ? 'rgba(15, 76, 129, 0.1)' : '#E0E7FF',
          color: entry.type === 'lec' ? 'var(--brand)' : '#4338CA'
        }}>{entry.type === 'lec' ? 'Лекция' : 'Семинар'}</span>
        {entry.isConflict && <AlertTriangle size={16} style={{ color: '#F43F5E', animation: 'pulse 2s infinite' }} />}
      </div>
      <div style={{ fontWeight: 700, fontSize: '0.75rem', lineHeight: 1.2 }}>{entry.subject}</div>
    </div>
    
    <div style={{ marginTop: '0.5rem' }} className="space-y-1">
      <div style={{ fontSize: '0.625rem', fontWeight: 700, opacity: 0.7, display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
        <UsersIcon size={12} />
        {entry.teacher}
      </div>
      <div style={{ fontSize: '0.625rem', fontWeight: 900, display: 'flex', alignItems: 'center', gap: '0.25rem', opacity: 0.9 }}>
        <div style={{ width: '6px', height: '6px', borderRadius: '50%', backgroundColor: 'var(--brand)' }}></div>
        Ауд. {entry.room}
      </div>
    </div>
  </div>
);

// --- Page Component ---

export const SchedulePage: React.FC = () => {
  const [selectedGroup, setSelectedGroup] = useState('G-121');

  return (
    <div className="space-y-8">
      <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end' }}>
        <div>
          <h1 className="text-3xl font-bold text-brand">Расписание</h1>
          <p className="text-text-secondary mt-2">Визуализация и ручная корректировка сформированного графика.</p>
        </div>
        
        <div className="flex gap-3">
          <div style={{ display: 'flex', backgroundColor: 'white', padding: '4px', borderRadius: '12px', border: '1px solid var(--border-light)', boxShadow: 'var(--shadow-subtle)' }}>
            <button style={{ padding: '0.5rem 1rem', backgroundColor: 'var(--brand)', color: 'white', borderRadius: '8px', fontSize: '0.875rem', fontWeight: 700 }}>Группы</button>
            <button style={{ padding: '0.5rem 1rem', color: 'var(--text-secondary)', fontSize: '0.875rem', fontWeight: 700 }}>Преподаватели</button>
          </div>
          <button style={{ backgroundColor: 'white', border: '1px solid var(--border-light)', padding: '0.625rem', borderRadius: '12px', color: 'var(--text-secondary)', boxShadow: 'var(--shadow-subtle)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Download size={20} />
          </button>
        </div>
      </header>

      {/* Control Bar */}
      <div className="card" style={{ padding: '1.5rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div className="flex items-center gap-6">
          <div className="flex items-center gap-2">
            <span style={{ fontSize: '0.875rem', fontWeight: 700, color: 'var(--text-secondary)' }}>Группа:</span>
            <select value={selectedGroup} onChange={(e) => setSelectedGroup(e.target.value)} style={{ backgroundColor: 'var(--bg-base)', border: 'none', borderRadius: '12px', padding: '0.5rem 1rem', fontWeight: 700, color: 'var(--brand)', outline: 'none' }}>
              <option>G-121</option>
              <option>G-122</option>
              <option>G-201</option>
            </select>
          </div>
          <div style={{ height: '32px', width: '1px', backgroundColor: 'var(--border-light)' }}></div>
          <div className="flex items-center gap-4">
            <button style={{ padding: '0.5rem', color: 'var(--text-tertiary)' }}><ChevronLeft size={20} /></button>
            <div style={{ fontSize: '0.875rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <Calendar size={16} className="text-brand" />
              01 Сентября — 07 Сентября
            </div>
            <button style={{ padding: '0.5rem', color: 'var(--text-tertiary)' }}><ChevronRight size={20} /></button>
          </div>
        </div>
        <div style={{ fontSize: '0.75rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-tertiary)', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <Filter size={16} />
          Фильтры: Все типы
        </div>
      </div>

      {/* Schedule Table using Compound Components */}
      <ScheduleGrid entries={MOCK_SCHEDULE}>
        <ScheduleGrid.Header days={DAYS} />
        <tbody>
          {TIME_SLOTS.map(slot => (
            <ScheduleGrid.Row key={slot.id} slot={slot}>
              {DAYS.map(day => (
                <ScheduleGrid.Cell key={day} day={day} slotId={slot.id} />
              ))}
            </ScheduleGrid.Row>
          ))}
        </tbody>
      </ScheduleGrid>

      {/* Legend / Info */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-tertiary)', padding: '0 1rem' }}>
        <div className="flex gap-6">
          <div className="flex items-center gap-2">
            <div style={{ width: '12px', height: '12px', borderRadius: '50%', backgroundColor: 'rgba(15, 76, 129, 0.1)', border: '1px solid rgba(15, 76, 129, 0.2)' }}></div>
            Лекционные занятия
          </div>
          <div className="flex items-center gap-2">
            <div style={{ width: '12px', height: '12px', borderRadius: '50%', backgroundColor: '#E0E7FF', border: '1px solid #C7D2FE' }}></div>
            Семинары / Практики
          </div>
          <div className="flex items-center gap-2">
            <div style={{ width: '12px', height: '12px', borderRadius: '50%', backgroundColor: '#FFF1F2', border: '1px solid #FECDD3' }}></div>
            Конфликты
          </div>
        </div>
        <div className="flex items-center gap-2 text-brand">
          <Info size={16} />
          Нажмите на карточку для редактирования
        </div>
      </div>

      <style dangerouslySetInnerHTML={{ __html: `
        .schedule-card:hover { border-color: rgba(15, 76, 129, 0.3) !important; box-shadow: var(--shadow-subtle); }
        .empty-slot:hover { background-color: rgba(244, 245, 248, 0.3); }
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: .5; } }
      `}} />
    </div>
  );
};
