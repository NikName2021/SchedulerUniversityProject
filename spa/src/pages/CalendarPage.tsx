import React, { useState, useEffect } from 'react';
import { 
  Users, 
  MapPin, 
  Search,
  Lock,
  ChevronRight,
  ChevronLeft
} from 'lucide-react';
import { useAppStore } from '../store/useAppStore';

const TIMES = [
  '09:00 - 10:30',
  '10:45 - 12:15',
  '13:00 - 14:30',
  '14:45 - 16:15',
  '16:30 - 18:00',
  '18:15 - 19:45'
];

const WEEK_DAYS = ['ПН', 'ВТ', 'СР', 'ЧТ', 'ПТ', 'СБ'];
const MONTHS = ['Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь', 'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь'];
const MONTHS_SHORT = ['Янв', 'Фев', 'Мар', 'Апр', 'Май', 'Июн', 'Июл', 'Авг', 'Сен', 'Окт', 'Ноя', 'Дек'];

// Helpers
const getStartOfWeek = (date: Date) => {
  const d = new Date(date);
  const day = d.getDay();
  const diff = d.getDate() - day + (day === 0 ? -6 : 1); // Adjust for Sunday (0)
  return new Date(d.setDate(diff));
};

const getDaysOfWeek = (startDate: Date) => {
  const days = [];
  for (let i = 0; i < 6; i++) { // Mon - Sat
    const d = new Date(startDate);
    d.setDate(startDate.getDate() + i);
    days.push(d);
  }
  return days;
};

const formatDateFull = (date: Date) => {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, '0');
  const d = String(date.getDate()).padStart(2, '0');
  return `${y}-${m}-${d}`;
};

export const CalendarPage: React.FC = () => {
  const { 
    teachers, 
    selectedTeacherId, 
    setSelectedTeacherId, 
    setBlockedSlot,
    isLoading 
  } = useAppStore();

  const selectedTeacher = teachers.find(t => t.id === selectedTeacherId);

  // Date State
  const [currentDate, setCurrentDate] = useState(() => {
    const today = new Date();
    // Reset to midnight
    today.setHours(0, 0, 0, 0);
    return today;
  });

  const [dragState, setDragState] = useState<{ isDragging: boolean, mode: 'block' | 'unblock' | null }>({
    isDragging: false,
    mode: null
  });

  const [searchQuery, setSearchQuery] = useState('');

  const filteredTeachers = teachers.filter(t => 
    t.name.toLowerCase().includes(searchQuery.toLowerCase()) || 
    t.dept.toLowerCase().includes(searchQuery.toLowerCase())
  );

  useEffect(() => {
    const handleGlobalMouseUp = () => {
      setDragState({ isDragging: false, mode: null });
    };
    window.addEventListener('mouseup', handleGlobalMouseUp);
    return () => window.removeEventListener('mouseup', handleGlobalMouseUp);
  }, []);

  if (isLoading) {
    return <div className="p-20 text-center text-text-secondary">Загрузка данных преподавателей...</div>;
  }

  const handleMouseDown = (slotKey: string, isCurrentlyBlocked: boolean) => {
    if (!selectedTeacherId) return;
    const newMode = isCurrentlyBlocked ? 'unblock' : 'block';
    setDragState({ isDragging: true, mode: newMode });
    setBlockedSlot(selectedTeacherId, slotKey, newMode === 'block');
  };

  const handleMouseEnter = (slotKey: string) => {
    if (!dragState.isDragging || !dragState.mode || !selectedTeacherId) return;
    setBlockedSlot(selectedTeacherId, slotKey, dragState.mode === 'block');
  };

  // Date Navigation
  const startOfWeek = getStartOfWeek(currentDate);
  const weekDays = getDaysOfWeek(startOfWeek);
  const currentMonthName = MONTHS[startOfWeek.getMonth()];
  const currentYear = startOfWeek.getFullYear();

  const handlePrevWeek = () => {
    const prev = new Date(currentDate);
    prev.setDate(prev.getDate() - 7);
    setCurrentDate(prev);
  };

  const handleNextWeek = () => {
    const next = new Date(currentDate);
    next.setDate(next.getDate() + 7);
    setCurrentDate(next);
  };

  const handleToday = () => {
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    setCurrentDate(today);
  };

  return (
    <div className="space-y-6" style={{ height: 'calc(100vh - 120px)', display: 'flex', flexDirection: 'column' }}>
      <header className="flex justify-between items-end">
        <div>
          <h1 className="text-2xl font-bold text-text-primary">Доступность преподавателей</h1>
          <p className="text-text-secondary mt-1 text-sm">Отметьте окна (красным), когда преподаватель не может проводить занятия.</p>
        </div>
      </header>

      <div style={{ display: 'flex', gap: '1.5rem', flex: 1, overflow: 'hidden' }}>
        {/* Left Sidebar: List */}
        <div style={{ width: '280px', backgroundColor: 'white', borderRadius: '12px', border: '1px solid var(--border-light)', overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
          <div style={{ padding: '1rem', borderBottom: '1px solid var(--border-light)' }}>
            <div style={{ position: 'relative' }}>
              <Search size={16} style={{ position: 'absolute', left: '0.75rem', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-tertiary)' }} />
              <input 
                type="text" 
                placeholder="Поиск..." 
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                style={{ 
                  width: '100%', 
                  padding: '0.5rem 0.75rem 0.5rem 2.25rem', 
                  borderRadius: '8px', 
                  border: '1px solid var(--border-light)',
                  backgroundColor: 'var(--bg-base)',
                  fontSize: '0.875rem'
                }}
              />
            </div>
          </div>
          <div style={{ flex: 1, overflowY: 'auto' }}>
            {filteredTeachers.map(teacher => (
              <button 
                key={teacher.id}
                onClick={() => setSelectedTeacherId(teacher.id)}
                style={{ 
                  width: '100%', 
                  padding: '0.75rem 1rem', 
                  textAlign: 'left',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  borderBottom: '1px solid var(--border-light)',
                  backgroundColor: selectedTeacherId === teacher.id ? '#eef2ff' : 'transparent',
                  color: selectedTeacherId === teacher.id ? 'var(--brand)' : 'var(--text-primary)',
                  transition: 'background-color 0.15s',
                  cursor: 'pointer'
                }}
                className="hover:bg-gray-50"
              >
                <div>
                  <div style={{ fontWeight: 600, fontSize: '0.875rem' }}>{teacher.name}</div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)', marginTop: '0.125rem' }}>{teacher.dept}</div>
                </div>
                {selectedTeacherId === teacher.id && (
                  <ChevronRight size={16} color="var(--brand)" />
                )}
              </button>
            ))}
          </div>
        </div>

        {/* Right Content: Grid */}
        <div style={{ flex: 1, backgroundColor: 'white', borderRadius: '12px', border: '1px solid var(--border-light)', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          {selectedTeacher ? (
            <>
              {/* Toolbar & Date Navigation */}
              <div style={{ padding: '1rem 1.25rem', borderBottom: '1px solid var(--border-light)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', backgroundColor: '#fafafa' }}>
                <div style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
                  <div style={{ width: '40px', height: '40px', borderRadius: '8px', backgroundColor: 'var(--brand)', color: 'white', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '1.25rem', fontWeight: 700 }}>
                    {selectedTeacher.name[0]}
                  </div>
                  <div>
                    <h2 style={{ fontSize: '1.125rem', fontWeight: 700 }}>{selectedTeacher.name}</h2>
                    <div className="flex gap-4 mt-0.5 text-text-secondary" style={{ fontSize: '0.75rem' }}>
                      <span className="flex items-center gap-1"><MapPin size={12} /> {selectedTeacher.dept}</span>
                    </div>
                  </div>
                </div>
                
                <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
                    <button onClick={handlePrevWeek} style={{ padding: '0.5rem', borderRadius: '8px', backgroundColor: 'white', border: '1px solid var(--border-light)' }} className="hover:bg-gray-50">
                      <ChevronLeft size={16} />
                    </button>
                    <button onClick={handleToday} style={{ padding: '0.5rem 1rem', borderRadius: '8px', backgroundColor: 'white', border: '1px solid var(--border-light)', fontSize: '0.875rem', fontWeight: 600 }} className="hover:bg-gray-50">
                      Сегодня
                    </button>
                    <button onClick={handleNextWeek} style={{ padding: '0.5rem', borderRadius: '8px', backgroundColor: 'white', border: '1px solid var(--border-light)' }} className="hover:bg-gray-50">
                      <ChevronRight size={16} />
                    </button>
                  </div>
                  <div style={{ fontWeight: 700, fontSize: '1rem', minWidth: '120px', textAlign: 'right' }}>
                    {currentMonthName} {currentYear}
                  </div>
                </div>
              </div>

              {/* Grid Content */}
              <div style={{ flex: 1, padding: '1.5rem', overflowY: 'auto', backgroundColor: 'white' }}>
                <div style={{ 
                  display: 'grid', 
                  gridTemplateColumns: '80px repeat(6, 1fr)', 
                  border: '1px solid var(--border-light)', 
                  borderRadius: '8px',
                  overflow: 'hidden'
                }}>
                  {/* Empty top-left cell */}
                  <div style={{ backgroundColor: 'var(--bg-base)', borderRight: '1px solid var(--border-light)', borderBottom: '1px solid var(--border-light)' }}></div>
                  
                  {/* Days Header */}
                  {weekDays.map((dateObj, idx) => {
                    const isToday = formatDateFull(dateObj) === formatDateFull(new Date());
                    return (
                      <div key={idx} style={{ 
                        backgroundColor: isToday ? '#eef2ff' : 'var(--bg-base)', 
                        padding: '0.75rem', 
                        textAlign: 'center', 
                        borderBottom: '1px solid var(--border-light)',
                        borderRight: idx !== 5 ? '1px solid var(--border-light)' : 'none'
                      }}>
                        <div style={{ fontWeight: 600, fontSize: '0.75rem', color: isToday ? 'var(--brand)' : 'var(--text-secondary)' }}>
                          {WEEK_DAYS[idx]}
                        </div>
                        <div style={{ fontWeight: 800, fontSize: '1.125rem', color: isToday ? 'var(--brand)' : 'var(--text-primary)', marginTop: '0.125rem' }}>
                          {dateObj.getDate()} {MONTHS_SHORT[dateObj.getMonth()]}
                        </div>
                      </div>
                    );
                  })}

                  {/* Body rows */}
                  {TIMES.map((time, slotIdx) => (
                    <React.Fragment key={time}>
                      {/* Time Label (Y-axis) */}
                      <div style={{ 
                        backgroundColor: '#fafafa', 
                        padding: '0.75rem 0.5rem', 
                        textAlign: 'center', 
                        borderRight: '1px solid var(--border-light)',
                        borderBottom: slotIdx !== TIMES.length - 1 ? '1px solid var(--border-light)' : 'none',
                        display: 'flex',
                        flexDirection: 'column',
                        justifyContent: 'center'
                      }}>
                        <div style={{ fontWeight: 700, fontSize: '0.75rem', color: 'var(--text-primary)' }}>{slotIdx + 1} пара</div>
                        <div style={{ fontSize: '0.625rem', color: 'var(--text-tertiary)', marginTop: '0.125rem' }}>{time}</div>
                      </div>
                      
                      {/* Days Grid Cells */}
                      {weekDays.map((dateObj, idx) => {
                        const dateStr = formatDateFull(dateObj);
                        const slotKey = `${dateStr}-${slotIdx + 1}`;
                        const isBlocked = selectedTeacher.blocked.includes(slotKey);
                        
                        return (
                          <button 
                            key={idx}
                            onMouseDown={() => handleMouseDown(slotKey, isBlocked)}
                            onMouseEnter={() => handleMouseEnter(slotKey)}
                            onDragStart={(e) => e.preventDefault()} 
                            style={{ 
                              backgroundColor: isBlocked ? '#fef2f2' : 'white',
                              color: isBlocked ? 'var(--blocked-text)' : 'transparent',
                              borderBottom: slotIdx !== TIMES.length - 1 ? '1px solid var(--border-light)' : 'none',
                              borderRight: idx !== 5 ? '1px solid var(--border-light)' : 'none',
                              cursor: 'pointer',
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'center',
                              transition: 'background-color 0.1s, border-color 0.1s',
                              height: '64px',
                              padding: 0,
                              position: 'relative'
                            }}
                            className={isBlocked ? "grid-cell-blocked" : "grid-cell"}
                          >
                            {isBlocked && (
                              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '0.25rem' }}>
                                <Lock size={16} />
                                <span style={{ fontSize: '0.625rem', fontWeight: 600 }}>Недоступен</span>
                              </div>
                            )}
                          </button>
                        );
                      })}
                    </React.Fragment>
                  ))}
                </div>
              </div>
            </>
          ) : (
            <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-tertiary)', flexDirection: 'column', gap: '1rem', backgroundColor: '#fafafa' }}>
              <Users size={48} opacity={0.2} />
              <div style={{ fontWeight: 600 }}>Выберите преподавателя слева</div>
            </div>
          )}
        </div>
      </div>

      <style dangerouslySetInnerHTML={{ __html: `
        .grid-cell:hover {
          background-color: #f3f4f6 !important;
        }
        .grid-cell-blocked {
          border: 1px solid #fca5a5 !important;
          z-index: 1;
        }
        .grid-cell-blocked:hover {
          background-color: #fee2e2 !important;
        }
        body {
          user-select: none;
        }
      `}} />
    </div>
  );
};
