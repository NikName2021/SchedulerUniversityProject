import React from 'react';
import { 
  Users, 
  MapPin, 
  Calendar, 
  Search,
  CheckCircle2,
  Lock,
  ChevronRight
} from 'lucide-react';
import { useAppStore } from '../store/useAppStore';

const DAYS = ['ПН', 'ВТ', 'СР', 'ЧТ', 'ПТ', 'СБ'];
const TIMES = [
  '09:00 - 10:30',
  '10:45 - 12:15',
  '13:00 - 14:30',
  '14:45 - 16:15',
  '16:30 - 18:00',
  '18:15 - 19:45'
];

export const TeachersPage: React.FC = () => {
  const { 
    teachers, 
    selectedTeacherId, 
    setSelectedTeacherId, 
    toggleBlockedSlot,
    isLoading 
  } = useAppStore();

  const selectedTeacher = teachers.find(t => t.id === selectedTeacherId);

  if (isLoading) {
    return <div className="p-20 text-center text-text-secondary">Загрузка данных преподавателей...</div>;
  }

  return (
    <div className="space-y-8" style={{ height: 'calc(100vh - 180px)', display: 'flex', flexDirection: 'column' }}>
      <header className="flex justify-between items-end">
        <div>
          <h1 className="text-3xl font-bold text-brand">Доступность преподавателей</h1>
          <p className="text-text-secondary mt-2">Блокируйте окна, когда преподаватель не может проводить занятия.</p>
        </div>
        
        <div style={{ position: 'relative', width: '300px' }}>
          <Search size={18} style={{ position: 'absolute', left: '1rem', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-tertiary)' }} />
          <input 
            type="text" 
            placeholder="Поиск по ФИО или кафедре" 
            style={{ 
              width: '100%', 
              padding: '0.75rem 1rem 0.75rem 2.75rem', 
              borderRadius: '14px', 
              border: '1px solid var(--border-light)',
              backgroundColor: 'white',
              fontSize: '0.875rem'
            }}
          />
        </div>
      </header>

      <div style={{ display: 'flex', gap: '2rem', flex: 1, overflow: 'hidden' }}>
        {/* Left Sidebar: List */}
        <div style={{ width: '350px', backgroundColor: 'white', borderRadius: '24px', border: '1px solid var(--border-light)', overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
          <div style={{ padding: '1.25rem', borderBottom: '1px solid var(--border-light)', fontWeight: 800, fontSize: '0.875rem' }}>
            ПРЕПОДАВАТЕЛИ ({teachers.length})
          </div>
          <div style={{ flex: 1, overflowY: 'auto' }}>
            {teachers.map(teacher => (
              <button 
                key={teacher.id}
                onClick={() => setSelectedTeacherId(teacher.id)}
                style={{ 
                  width: '100%', 
                  padding: '1.25rem', 
                  textAlign: 'left',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  borderBottom: '1px solid var(--border-light)',
                  backgroundColor: selectedTeacherId === teacher.id ? 'var(--bg-base)' : 'transparent',
                  transition: 'background-color 0.2s',
                  cursor: 'pointer'
                }}
                className="teacher-item"
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                  <div style={{ 
                    width: '40px', 
                    height: '40px', 
                    borderRadius: '50%', 
                    background: selectedTeacherId === teacher.id ? 'var(--brand)' : 'var(--bg-base)',
                    color: selectedTeacherId === teacher.id ? 'white' : 'var(--text-secondary)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontWeight: 900,
                    fontSize: '0.875rem'
                  }}>
                    {teacher.name.split(' ').map(n => n[0]).join('')}
                  </div>
                  <div>
                    <div style={{ fontWeight: 700, fontSize: '0.875rem' }}>{teacher.name}</div>
                    <div style={{ fontSize: '0.625rem', color: 'var(--text-tertiary)', marginTop: '0.125rem', textTransform: 'uppercase', fontWeight: 700 }}>{teacher.dept}</div>
                  </div>
                </div>
                {selectedTeacherId === teacher.id ? (
                  <CheckCircle2 size={18} color="var(--brand)" />
                ) : (
                  <ChevronRight size={18} color="rgba(0,0,0,0.1)" />
                )}
              </button>
            ))}
          </div>
        </div>

        {/* Right Content: Grid */}
        <div style={{ flex: 1, backgroundColor: 'white', borderRadius: '24px', border: '1px solid var(--border-light)', padding: '2rem', display: 'flex', flexDirection: 'column' }}>
          {selectedTeacher ? (
            <>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '2.5rem' }}>
                <div style={{ display: 'flex', gap: '1.5rem', alignItems: 'center' }}>
                  <div style={{ width: '64px', height: '64px', borderRadius: '20px', backgroundColor: 'var(--brand)', color: 'white', display: 'flex', alignItems: 'center', justifySelf: 'center', fontSize: '1.5rem', fontWeight: 900, justifyContent: 'center' }}>
                    {selectedTeacher.name[0]}
                  </div>
                  <div>
                    <h2 style={{ fontSize: '1.5rem', fontWeight: 800 }}>{selectedTeacher.name}</h2>
                    <div className="flex gap-4 mt-1 text-text-secondary" style={{ fontSize: '0.875rem' }}>
                      <span className="flex items-center gap-1"><MapPin size={14} /> {selectedTeacher.dept}</span>
                      <span className="flex items-center gap-1"><Users size={14} /> Кафедральный блок</span>
                    </div>
                  </div>
                </div>
                <div style={{ 
                  backgroundColor: 'var(--bg-base)', 
                  padding: '1rem 1.5rem', 
                  borderRadius: '16px', 
                  textAlign: 'right' 
                }}>
                  <div style={{ fontSize: '0.625rem', color: 'var(--text-tertiary)', fontWeight: 800, textTransform: 'uppercase' }}>Всего заблокировано</div>
                  <div style={{ fontSize: '1.25rem', fontWeight: 900, color: 'var(--brand)' }}>{selectedTeacher.blocked.length} пар</div>
                </div>
              </div>

              <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
                <div style={{ display: 'grid', gridTemplateColumns: '120px repeat(6, 1fr)', gap: '1px', backgroundColor: 'var(--border-light)', border: '1px solid var(--border-light)', borderRadius: '16px', overflow: 'hidden' }}>
                  {/* Header */}
                  <div style={{ backgroundColor: 'var(--bg-base)', padding: '1rem', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                    <Calendar size={18} color="var(--text-tertiary)" />
                  </div>
                  {DAYS.map(day => (
                    <div key={day} style={{ backgroundColor: 'var(--bg-base)', padding: '1rem', textAlign: 'center', fontWeight: 800, fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                      {day}
                    </div>
                  ))}

                  {/* Body */}
                  {TIMES.map((time, slotIdx) => (
                    <React.Fragment key={time}>
                      <div style={{ backgroundColor: 'white', padding: '1rem', textAlign: 'center', borderRight: '1px solid var(--border-light)' }}>
                        <div style={{ fontWeight: 800, fontSize: '0.75rem', color: 'var(--brand)' }}>{slotIdx + 1} пара</div>
                        <div style={{ fontSize: '0.625rem', color: 'var(--text-tertiary)', marginTop: '0.25rem' }}>{time.split(' - ')[0]}</div>
                      </div>
                      {DAYS.map(day => {
                        const slotKey = `${day}-${slotIdx + 1}`;
                        const isBlocked = selectedTeacher.blocked.includes(slotKey);
                        return (
                          <button 
                            key={day}
                            onClick={() => toggleBlockedSlot(selectedTeacher.id, slotKey)}
                            style={{ 
                              backgroundColor: isBlocked ? 'var(--brand)' : 'white',
                              color: isBlocked ? 'white' : 'transparent',
                              border: 'none',
                              cursor: 'pointer',
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'center',
                              transition: 'all 0.2s',
                              height: '80px'
                            }}
                            className="grid-cell"
                          >
                            {isBlocked && <Lock size={20} />}
                          </button>
                        );
                      })}
                    </React.Fragment>
                  ))}
                </div>
              </div>
            </>
          ) : (
            <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-tertiary)', flexDirection: 'column', gap: '1rem' }}>
              <Users size={48} opacity={0.2} />
              <div style={{ fontWeight: 700 }}>Выберите преподавателя для настройки доступности</div>
            </div>
          )}
        </div>
      </div>

      <style dangerouslySetInnerHTML={{ __html: `
        .teacher-item:hover {
          background-color: var(--bg-base);
        }
        .grid-cell:hover {
          background-color: var(--bg-base);
          color: rgba(0,0,0,0.1);
        }
        .grid-cell:hover svg {
          color: var(--brand);
        }
      `}} />
    </div>
  );
};
