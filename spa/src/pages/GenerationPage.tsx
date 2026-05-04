import React, { useState, useEffect } from 'react';
import { 
  Zap, 
  Users, 
  Calendar, 
  Info,
  CheckCircle2,
  AlertCircle,
  Clock,
  Eye,
  X,
  Search,
  Filter,
  Settings2,
  Download
} from 'lucide-react';

interface Stats {
  total_streams: number;
  active_streams: number;
  ignored_streams: number;
  total_groups: number;
  total_teachers: number;
}

interface StreamPreview {
  id: number;
  event_name: string;
  stream_type: string;
  teacher: string;
}

const ALL_TYPES = [
  'Лекция',
  'Семинар',
  'Лабораторная',
  'Зачет',
  'Внеучебное мероприятие'
];

import { useLocation } from 'react-router-dom';

export const GenerationPage: React.FC = () => {
  const location = useLocation();
  const inheritedData = location.state as any;

  const [groups, setGroups] = useState<string[]>([]);
  const [selectedGroups, setSelectedGroups] = useState<string[]>(inheritedData?.groups || []);
  const [holidays, setHolidays] = useState<string[]>(inheritedData?.holidays || []);
  const [startDate, setStartDate] = useState<string>(inheritedData?.start_date?.split('T')[0] || '2025-09-01');
  const [endDate, setEndDate] = useState<string>(inheritedData?.end_date?.split('T')[0] || '2025-09-07');
  const [newHoliday, setNewHoliday] = useState('');
  const [stats, setStats] = useState<Stats | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [status, setStatus] = useState<{ type: 'success' | 'error', msg: string } | null>(null);
  
  const [searchQuery, setSearchQuery] = useState('');
  const [previewGroup, setPreviewGroup] = useState<string | null>(null);
  const [previewStreams, setPreviewStreams] = useState<StreamPreview[]>([]);
  const [isPreviewLoading, setIsPreviewLoading] = useState(false);

  // Filter types
  const [enabledTypes, setEnabledTypes] = useState<string[]>(inheritedData?.settings?.enabled_types || ['Лекция', 'Семинар', 'Лабораторная']);

  useEffect(() => {
    fetchInitialData();
  }, []);

  const fetchInitialData = async () => {
    setIsLoading(true);
    try {
      const [groupsRes, statsRes] = await Promise.all([
        fetch('http://localhost:8000/api/v1/scheduler/groups'),
        fetch('http://localhost:8000/api/v1/scheduler/stats')
      ]);
      
      const groupsData = await groupsRes.json();
      const statsData = await statsRes.json();
      
      setGroups(groupsData.groups || []);
      // If no inherited groups, don't auto-select all
      if (!inheritedData?.groups) {
          setSelectedGroups([]);
      }
      setStats(statsData);
    } catch (e) {
      console.error('Failed to fetch generation data', e);
    } finally {
      setIsLoading(false);
    }
  };

  const handleToggleGroup = (group: string) => {
    setSelectedGroups(prev => 
      prev.includes(group) ? prev.filter(g => g !== group) : [...prev, group]
    );
  };

  const handleToggleType = (type: string) => {
    setEnabledTypes(prev => 
      prev.includes(type) ? prev.filter(t => t !== type) : [...prev, type]
    );
  };

  const handlePreviewGroup = async (group: string) => {
    setPreviewGroup(group);
    setIsPreviewLoading(true);
    try {
      const res = await fetch(`http://localhost:8000/api/v1/scheduler/streams?group_name=${encodeURIComponent(group)}`);
      const data = await res.json();
      // Only show active (not ignored) streams
      setPreviewStreams(data.filter((s: any) => !s.is_ignored));
    } catch (e) {
      console.error(e);
    } finally {
      setIsPreviewLoading(false);
    }
  };

  const handleAddHoliday = () => {
    if (newHoliday && !holidays.includes(newHoliday)) {
      setHolidays([...holidays, newHoliday]);
      setNewHoliday('');
    }
  };

  const handleRemoveHoliday = (h: string) => {
    setHolidays(holidays.filter(item => item !== h));
  };

  const handleStartGeneration = async () => {
    setIsGenerating(true);
    setStatus(null);
    try {
      const res = await fetch('http://localhost:8000/api/v1/scheduler/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          groups: selectedGroups,
          holidays: holidays,
          start_date: startDate,
          end_date: endDate,
          settings: { 
            enabled_types: enabledTypes,
            created_at: new Date().toISOString() 
          }
        })
      });
      
      if (res.ok) {
        setStatus({ type: 'success', msg: 'Задача на генерацию успешно отправлена!' });
      } else {
        setStatus({ type: 'error', msg: 'Ошибка при отправке задачи.' });
      }
    } catch (e) {
      setStatus({ type: 'error', msg: 'Не удалось связаться с сервером.' });
    } finally {
      setIsGenerating(false);
    }
  };

  const handleExport = () => {
    window.open('http://localhost:8000/api/v1/scheduler/export', '_blank');
  };

  const filteredGroups = groups.filter(g => g.toLowerCase().includes(searchQuery.toLowerCase()));
  
  // Apply type filter to preview
  const displayPreviewStreams = previewStreams.filter(s => enabledTypes.includes(s.stream_type));

  if (isLoading) return <div style={{ padding: '5rem', textAlign: 'center', color: 'var(--text-secondary)' }}>Загрузка параметров генерации...</div>;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem', paddingBottom: '5rem' }} className="animate-fade-in">
      <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end' }}>
        <div>
          <h1 style={{ fontSize: '2rem', fontWeight: 900, color: 'var(--text-primary)', letterSpacing: '-0.02em' }}>Генератор расписания</h1>
          <p style={{ color: 'var(--text-secondary)', marginTop: '0.25rem', fontSize: '0.875rem', fontWeight: 500 }}>Настройка фильтров и запуск алгоритма планирования.</p>
        </div>
        <div style={{ display: 'flex', gap: '0.75rem' }}>
            <div style={{ backgroundColor: 'white', border: '1px solid var(--border-light)', borderRadius: '12px', padding: '0.5rem 1rem', display: 'flex', alignItems: 'center', gap: '0.75rem', boxShadow: 'var(--shadow-subtle)' }}>
                <span style={{ fontSize: '0.625rem', fontWeight: 800, color: 'var(--text-tertiary)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Групп</span>
                <span style={{ fontSize: '1.125rem', fontWeight: 900, color: 'var(--brand)' }}>{selectedGroups.length}</span>
            </div>
            <div style={{ backgroundColor: 'white', border: '1px solid var(--border-light)', borderRadius: '12px', padding: '0.5rem 1rem', display: 'flex', alignItems: 'center', gap: '0.75rem', boxShadow: 'var(--shadow-subtle)' }}>
                <span style={{ fontSize: '0.625rem', fontWeight: 800, color: 'var(--text-tertiary)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Типов</span>
                <span style={{ fontSize: '1.125rem', fontWeight: 900, color: '#f59e0b' }}>{enabledTypes.length}</span>
            </div>
            <button 
                onClick={handleExport}
                style={{ 
                    backgroundColor: 'white', 
                    color: 'var(--text-primary)', 
                    padding: '0.5rem 1rem', 
                    borderRadius: '12px', 
                    fontWeight: 800, 
                    display: 'flex', 
                    alignItems: 'center', 
                    gap: '0.5rem',
                    border: '1px solid var(--border-light)',
                    cursor: 'pointer',
                    transition: 'all 0.2s',
                    boxShadow: 'var(--shadow-sm)',
                    fontSize: '0.875rem'
                }}
            >
                <Download size={18} />
                Excel
            </button>
        </div>
      </header>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(12, 1fr)', gap: '2rem' }}>
        {/* Left Column: Group Selection */}
        <div style={{ gridColumn: 'span 4' }}>
            <div style={{ backgroundColor: 'white', borderRadius: '20px', border: '1px solid var(--border-light)', boxShadow: 'var(--shadow-md)', overflow: 'hidden', display: 'flex', flexDirection: 'column', height: '600px' }}>
                <div style={{ padding: '1.25rem', borderBottom: '1px solid var(--border-light)', backgroundColor: '#fafafa' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
                        <h3 style={{ fontWeight: 800, display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.9375rem' }}>
                            <Users size={18} style={{ color: 'var(--brand)' }} /> Группы
                        </h3>
                        <button 
                            onClick={() => setSelectedGroups(selectedGroups.length === groups.length ? [] : [...groups])}
                            style={{ fontSize: '0.625rem', fontWeight: 900, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--brand)', cursor: 'pointer', border: 'none', background: 'none' }}
                        >
                            {selectedGroups.length === groups.length ? 'Сбросить' : 'Все'}
                        </button>
                    </div>
                    <div style={{ position: 'relative' }}>
                        <Search size={14} style={{ position: 'absolute', left: '0.75rem', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-tertiary)' }} />
                        <input 
                            type="text" 
                            placeholder="Поиск..." 
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                            style={{ width: '100%', backgroundColor: 'white', border: '1px solid var(--border-light)', borderRadius: '10px', padding: '0.625rem 0.75rem 0.625rem 2.25rem', fontSize: '0.875rem', outline: 'none' }}
                        />
                    </div>
                </div>
                
                <div style={{ flex: 1, overflowY: 'auto', padding: '0.5rem' }}>
                    {filteredGroups.map(group => (
                        <div 
                            key={group}
                            style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', padding: '0.75rem', borderRadius: '10px', cursor: 'pointer', backgroundColor: selectedGroups.includes(group) ? 'rgba(79, 70, 229, 0.05)' : 'transparent', transition: 'all 0.2s' }}
                            onClick={() => handleToggleGroup(group)}
                            className="group-item"
                        >
                            <div style={{ width: '20px', height: '20px', borderRadius: '6px', border: `2px solid ${selectedGroups.includes(group) ? 'var(--brand)' : '#d1d5db'}`, backgroundColor: selectedGroups.includes(group) ? 'var(--brand)' : 'white', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                                {selectedGroups.includes(group) && <CheckCircle2 size={12} color="white" />}
                            </div>
                            <span style={{ flex: 1, fontSize: '0.875rem', fontWeight: 700, color: selectedGroups.includes(group) ? 'var(--brand)' : 'var(--text-primary)' }}>{group}</span>
                            <button 
                                onClick={(e) => { e.stopPropagation(); handlePreviewGroup(group); }}
                                style={{ border: 'none', background: 'none', cursor: 'pointer', padding: '0.25rem', color: 'var(--text-tertiary)' }}
                                className="preview-btn"
                            >
                                <Eye size={14} />
                            </button>
                        </div>
                    ))}
                </div>
            </div>
        </div>

        {/* Right Column: Filters & Preview */}
        <div style={{ gridColumn: 'span 8', display: 'flex', flexDirection: 'column', gap: '2rem' }}>
            {/* Global Type Filter */}
            <div style={{ backgroundColor: 'white', borderRadius: '20px', border: '1px solid var(--border-light)', boxShadow: 'var(--shadow-md)', padding: '1.5rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '1.5rem' }}>
                    <div style={{ width: '40px', height: '40px', borderRadius: '10px', backgroundColor: 'rgba(245, 158, 11, 0.1)', color: '#f59e0b', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                        <Settings2 size={20} />
                    </div>
                    <div>
                        <h3 style={{ fontWeight: 800 }}>Типы занятий для генерации</h3>
                        <p style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', fontWeight: 600 }}>Выберите, какие типы пар нужно включить в этот расчет</p>
                    </div>
                </div>
                
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.75rem' }}>
                    {ALL_TYPES.map(type => (
                        <button 
                            key={type}
                            onClick={() => handleToggleType(type)}
                            style={{ 
                                padding: '0.625rem 1rem', 
                                borderRadius: '12px', 
                                border: `2px solid ${enabledTypes.includes(type) ? '#f59e0b' : 'var(--border-light)'}`, 
                                backgroundColor: enabledTypes.includes(type) ? 'rgba(245, 158, 11, 0.05)' : 'white',
                                color: enabledTypes.includes(type) ? '#b45309' : 'var(--text-secondary)',
                                fontSize: '0.75rem',
                                fontWeight: 800,
                                cursor: 'pointer',
                                transition: 'all 0.2s'
                            }}
                        >
                            {type}
                        </button>
                    ))}
                </div>
            </div>

            {/* Preview Section */}
            <div style={{ backgroundColor: 'white', borderRadius: '20px', border: '1px solid var(--border-light)', boxShadow: 'var(--shadow-md)', overflow: 'hidden', opacity: previewGroup ? 1 : 0.6 }}>
                <div style={{ padding: '1.5rem', borderBottom: '1px solid var(--border-light)', backgroundColor: '#fafafa', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                        <div style={{ width: '48px', height: '48px', borderRadius: '12px', backgroundColor: 'white', border: '1px solid var(--border-light)', display: 'flex', alignItems: 'center', justifyContent: 'center', boxShadow: 'var(--shadow-subtle)' }}>
                            <Filter size={24} style={{ color: 'var(--brand)' }} />
                        </div>
                        <div>
                            <h3 style={{ fontWeight: 800, fontSize: '1.125rem' }}>План: {previewGroup || '—'}</h3>
                            <p style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', fontWeight: 600 }}>
                                {displayPreviewStreams.length} пар с учетом фильтров типов
                            </p>
                        </div>
                    </div>
                    {previewGroup && (
                        <button onClick={() => setPreviewGroup(null)} style={{ padding: '0.5rem', border: 'none', background: 'none', cursor: 'pointer', color: 'var(--text-tertiary)' }}>
                            <X size={20} />
                        </button>
                    )}
                </div>
                
                <div style={{ minHeight: '300px', maxHeight: '300px', overflowY: 'auto' }}>
                    {isPreviewLoading ? (
                        <div style={{ padding: '5rem', textAlign: 'center', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '1rem' }}>
                            <Clock size={32} style={{ color: 'var(--brand)', animation: 'spin 1s linear infinite' }} />
                            <span style={{ fontWeight: 700, color: 'var(--text-secondary)' }}>Загрузка...</span>
                        </div>
                    ) : displayPreviewStreams.length > 0 ? (
                        <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
                            <thead style={{ position: 'sticky', top: 0, backgroundColor: 'white', boxShadow: '0 1px 0 var(--border-light)', zIndex: 10 }}>
                                <tr>
                                    <th style={{ padding: '1rem 1.5rem', fontSize: '0.625rem', fontWeight: 900, textTransform: 'uppercase', color: 'var(--text-tertiary)' }}>Дисциплина</th>
                                    <th style={{ padding: '1rem 1.5rem', fontSize: '0.625rem', fontWeight: 900, textTransform: 'uppercase', color: 'var(--text-tertiary)' }}>Тип</th>
                                    <th style={{ padding: '1rem 1.5rem', fontSize: '0.625rem', fontWeight: 900, textTransform: 'uppercase', color: 'var(--text-tertiary)' }}>Преподаватель</th>
                                </tr>
                            </thead>
                            <tbody>
                                {displayPreviewStreams.map(s => (
                                    <tr key={s.id} style={{ borderTop: '1px solid var(--border-light)' }}>
                                        <td style={{ padding: '1rem 1.5rem', fontWeight: 700, fontSize: '0.875rem' }}>{s.event_name}</td>
                                        <td style={{ padding: '1rem 1.5rem' }}>
                                            <span style={{ fontSize: '0.625rem', fontWeight: 900, padding: '0.25rem 0.5rem', borderRadius: '4px', backgroundColor: '#f3f4f6', color: 'var(--text-secondary)', textTransform: 'uppercase' }}>
                                                {s.stream_type}
                                            </span>
                                        </td>
                                        <td style={{ padding: '1rem 1.5rem', fontSize: '0.875rem', color: 'var(--text-secondary)', fontWeight: 600 }}>{s.teacher || '—'}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    ) : (
                        <div style={{ padding: '5rem', textAlign: 'center', color: 'var(--text-tertiary)', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '1rem' }}>
                            <Info size={48} style={{ opacity: 0.1 }} />
                            <span style={{ fontWeight: 700 }}>
                                {previewGroup ? 'Нет пар, соответствующих фильтрам' : 'Выберите группу для проверки состава пар'}
                            </span>
                        </div>
                    )}
                </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '2rem' }}>
                {/* Semester Dates */}
                <div style={{ backgroundColor: 'white', borderRadius: '20px', border: '1px solid var(--border-light)', boxShadow: 'var(--shadow-md)', padding: '1.5rem' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '1.5rem' }}>
                        <div style={{ width: '40px', height: '40px', borderRadius: '10px', backgroundColor: 'rgba(79, 70, 229, 0.1)', color: 'var(--brand)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                            <Clock size={20} />
                        </div>
                        <h3 style={{ fontWeight: 800 }}>Интервал семестра</h3>
                    </div>
                    
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                            <label style={{ fontSize: '0.625rem', fontWeight: 800, color: 'var(--text-tertiary)', textTransform: 'uppercase' }}>Начало</label>
                            <input 
                                type="date" 
                                value={startDate}
                                onChange={(e) => setStartDate(e.target.value)}
                                style={{ backgroundColor: '#f9fafb', border: '1px solid var(--border-light)', borderRadius: '10px', padding: '0.625rem 0.75rem', fontSize: '0.875rem', outline: 'none', fontWeight: 600 }}
                            />
                        </div>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                            <label style={{ fontSize: '0.625rem', fontWeight: 800, color: 'var(--text-tertiary)', textTransform: 'uppercase' }}>Конец</label>
                            <input 
                                type="date" 
                                value={endDate}
                                onChange={(e) => setEndDate(e.target.value)}
                                style={{ backgroundColor: '#f9fafb', border: '1px solid var(--border-light)', borderRadius: '10px', padding: '0.625rem 0.75rem', fontSize: '0.875rem', outline: 'none', fontWeight: 600 }}
                            />
                        </div>
                    </div>
                </div>

                {/* Holidays */}
                <div style={{ backgroundColor: 'white', borderRadius: '20px', border: '1px solid var(--border-light)', boxShadow: 'var(--shadow-md)', padding: '1.5rem' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '1.5rem' }}>
                        <div style={{ width: '40px', height: '40px', borderRadius: '10px', backgroundColor: 'rgba(249, 115, 22, 0.1)', color: '#f97316', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                            <Calendar size={20} />
                        </div>
                        <h3 style={{ fontWeight: 800 }}>Праздники</h3>
                    </div>
                    
                    <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1.5rem' }}>
                        <input 
                            type="date" 
                            value={newHoliday}
                            onChange={(e) => setNewHoliday(e.target.value)}
                            style={{ flex: 1, backgroundColor: '#f9fafb', border: '1px solid var(--border-light)', borderRadius: '10px', padding: '0.5rem 0.75rem', fontSize: '0.875rem', outline: 'none' }}
                        />
                        <button 
                            onClick={handleAddHoliday}
                            style={{ backgroundColor: '#f97316', color: 'white', borderRadius: '10px', padding: '0 1rem', fontWeight: 800, fontSize: '0.75rem', border: 'none', cursor: 'pointer' }}
                        >
                            +
                        </button>
                    </div>

                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', maxHeight: '100px', overflowY: 'auto' }}>
                        {holidays.map(h => (
                            <div key={h} style={{ backgroundColor: 'rgba(249, 115, 22, 0.1)', color: '#ea580c', padding: '0.375rem 0.75rem', borderRadius: '8px', fontSize: '0.75rem', fontWeight: 800, display: 'flex', alignItems: 'center', gap: '0.5rem', border: '1px solid rgba(249, 115, 22, 0.2)' }}>
                                {h}
                                <button onClick={() => handleRemoveHoliday(h)} style={{ border: 'none', background: 'none', color: '#f97316', cursor: 'pointer' }}>×</button>
                            </div>
                        ))}
                    </div>
                </div>

                {/* Action Card */}
                <div style={{ backgroundColor: 'var(--text-primary)', borderRadius: '20px', boxShadow: '0 20px 40px rgba(0,0,0,0.2)', padding: '2rem', color: 'white', position: 'relative', overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
                    <div style={{ position: 'relative', zIndex: 1 }}>
                        <h3 style={{ fontSize: '1.25rem', fontWeight: 900, marginBottom: '0.5rem' }}>Запуск</h3>
                        <p style={{ fontSize: '0.75rem', opacity: 0.6, fontWeight: 500, marginBottom: '2rem', lineHeight: 1.5 }}>
                            Расчет {selectedGroups.length} групп с учетом выбранных типов пар.
                        </p>

                        <button 
                            disabled={selectedGroups.length === 0 || isGenerating || enabledTypes.length === 0}
                            onClick={handleStartGeneration}
                            style={{ 
                                width: '100%', 
                                padding: '1rem', 
                                borderRadius: '12px', 
                                border: 'none', 
                                fontWeight: 900, 
                                fontSize: '0.875rem', 
                                letterSpacing: '0.05em', 
                                textTransform: 'uppercase', 
                                display: 'flex', 
                                alignItems: 'center', 
                                justifyContent: 'center', 
                                gap: '0.75rem',
                                cursor: (selectedGroups.length === 0 || isGenerating || enabledTypes.length === 0) ? 'not-allowed' : 'pointer',
                                backgroundColor: (selectedGroups.length === 0 || isGenerating || enabledTypes.length === 0) ? 'rgba(255,255,255,0.1)' : 'var(--brand)',
                                color: (selectedGroups.length === 0 || isGenerating || enabledTypes.length === 0) ? 'rgba(255,255,255,0.3)' : 'white',
                                boxShadow: isGenerating ? 'none' : '0 8px 24px rgba(79, 70, 229, 0.4)',
                                transition: 'all 0.2s'
                            }}
                        >
                            {isGenerating ? <Clock size={18} style={{ animation: 'spin 1s linear infinite' }} /> : <Zap size={18} />}
                            {isGenerating ? 'Расчет...' : 'Начать расчет'}
                        </button>
                        
                        {status && (
                            <div style={{ marginTop: '1rem', padding: '0.75rem', borderRadius: '10px', fontSize: '0.75rem', fontWeight: 800, backgroundColor: status.type === 'success' ? 'rgba(34, 197, 94, 0.2)' : 'rgba(239, 68, 68, 0.2)', color: status.type === 'success' ? '#4ade80' : '#f87171', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                                {status.type === 'success' ? <CheckCircle2 size={14} /> : <AlertCircle size={14} />}
                                {status.msg}
                            </div>
                        )}
                    </div>
                    <Zap size={120} style={{ position: 'absolute', right: '-20px', bottom: '-20px', opacity: 0.05, transform: 'rotate(15deg)' }} />
                </div>
            </div>
        </div>
      </div>

      <style dangerouslySetInnerHTML={{ __html: `
        @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
        .animate-fade-in { animation: fadeIn 0.4s ease-out forwards; }
        .group-item:hover .preview-btn { opacity: 1 !important; }
        .preview-btn { opacity: 0; transition: opacity 0.2s; }
      `}} />
    </div>
  );
};
