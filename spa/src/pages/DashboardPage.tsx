import React from 'react';
import { 
  Users, 
  BookOpen, 
  Calendar, 
  Play, 
  Clock, 
  AlertCircle 
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { useGenerationProgress } from '../hooks/useGenerationProgress';
import { useAppStore } from '../store/useAppStore';

const StatCard = ({ icon: Icon, label, value }: { icon: LucideIcon, label: string, value: string }) => (
  <div className="card" style={{ padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
    <div className="flex items-center gap-2 text-text-secondary" style={{ marginBottom: '0.5rem' }}>
      <Icon size={16} />
      <span style={{ fontSize: '0.75rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>{label}</span>
    </div>
    <div className="font-bold text-3xl">{value}</div>
  </div>
);

export const DashboardPage: React.FC = () => {
  const { progress, isGenerating, logs, start } = useGenerationProgress();
  const { teachers, streams } = useAppStore();

  return (
    <div className="space-y-10">
      <header>
        <h1 className="text-3xl font-bold text-brand">Панель управления</h1>
        <p className="text-text-secondary mt-2">Консоль управления алгоритмом составления расписания.</p>
      </header>

      {/* Stats Grid */}
      <div className="grid grid-cols-3 gap-6">
        <StatCard icon={Users} label="Учебных групп" value={streams.flatMap(s => s.groups).length.toString()} />
        <StatCard icon={BookOpen} label="Преподавателей" value={teachers.length.toString()} />
        <StatCard icon={Calendar} label="Пар к расстановке" value="680" />
      </div>

      {/* Main Orchestrator Card */}
      <div className="card" style={{ padding: '2.5rem', textAlign: 'center', position: 'relative', overflow: 'hidden' }}>
        <div style={{
          position: 'absolute',
          top: 0,
          left: 0,
          width: '100%',
          height: '4px',
          background: 'var(--brand)',
          opacity: 0.1
        }} />
        
        <div style={{ maxWidth: '600px', margin: '0 auto' }} className="space-y-8">
          <div className="space-y-4">
            <h2 style={{ fontSize: '1.5rem', fontWeight: 800 }}>Оркестратор CP-SAT</h2>
            <p className="text-text-secondary">
              Запустите процесс автоматического подбора оптимального времени и аудиторий для всех занятий.
            </p>
          </div>

          <button 
            className="btn-primary" 
            onClick={start}
            disabled={isGenerating}
            style={{ 
              margin: '0 auto', 
              padding: '1.25rem 2.5rem', 
              fontSize: '1.125rem',
              opacity: isGenerating ? 0.7 : 1,
              cursor: isGenerating ? 'not-allowed' : 'pointer'
            }}
          >
            <Play size={24} fill="currentColor" />
            {isGenerating ? 'Расчет в процессе...' : 'Запустить расчет расписания'}
          </button>

          {/* Progress Section */}
          {(isGenerating || progress > 0) && (
            <div style={{ paddingTop: '2.5rem', borderTop: '1px solid var(--border-light)', animation: 'fadeIn 0.5s forwards' }}>
              <div className="flex justify-between" style={{ alignItems: 'flex-end', marginBottom: '1rem' }}>
                <div style={{ textAlign: 'left' }}>
                  <div className="text-brand font-bold flex items-center gap-2" style={{ marginBottom: '0.25rem' }}>
                    <Clock size={20} style={{ animation: isGenerating ? 'pulse 2s infinite' : 'none' }} />
                    {progress < 100 ? 'Алгоритм работает...' : 'Расчет завершен'}
                  </div>
                  <div className="text-sm text-text-tertiary">
                    {progress < 100 ? 'Обработка ограничений' : 'Результаты готовы к просмотру'}
                  </div>
                </div>
                <div className="text-lg font-bold text-brand">{Math.round(progress)}%</div>
              </div>

              <div style={{ height: '12px', background: 'var(--bg-base)', borderRadius: '100px', overflow: 'hidden' }}>
                <div style={{
                  height: '100%',
                  background: 'var(--brand)',
                  width: `${progress}%`,
                  borderRadius: '100px',
                  transition: 'width 0.5s ease-out',
                  position: 'relative'
                }}>
                  {isGenerating && (
                    <div style={{
                      position: 'absolute',
                      inset: 0,
                      background: 'linear-gradient(90deg, transparent, rgba(255,255,255,0.4), transparent)',
                      transform: 'skewX(-20deg)',
                      width: '50px',
                      animation: 'shimmer 2s infinite'
                    }} />
                  )}
                </div>
              </div>

              {/* Logs Area */}
              <div style={{
                marginTop: '2rem',
                background: 'rgba(244, 245, 248, 0.5)',
                borderRadius: '16px',
                padding: '1.5rem',
                textAlign: 'left',
                fontFamily: 'monospace',
                fontSize: '0.875rem',
                color: 'var(--text-secondary)',
                border: '1px solid rgba(229, 231, 235, 0.5)',
              }} className="space-y-4">
                {logs.map((log, index) => (
                  <div key={index} className="flex gap-2">
                    <span className="text-brand font-bold">{'>'}</span>
                    <span>{log}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Warnings Section */}
      <div style={{
        background: 'var(--amber-bg)',
        border: '1px solid var(--amber)',
        borderRadius: '16px',
        padding: '1.5rem',
        display: 'flex',
        gap: '1rem'
      }}>
        <AlertCircle size={24} color="var(--amber-text)" />
        <div>
          <h4 style={{ fontWeight: 800, color: 'var(--amber-text)' }}>Важное замечание</h4>
          <p style={{ color: 'var(--amber-text)', fontSize: '0.875rem', marginTop: '0.25rem' }}>
            Расчет расписания учитывает все заблокированные дни для {teachers.length} преподавателей. 
            Если солвер не сможет найти решение, попробуйте ослабить ограничения в разделе "Преподаватели".
          </p>
        </div>
      </div>

      <style dangerouslySetInnerHTML={{ __html: `
        @keyframes shimmer {
          0% { transform: translateX(-100%) skewX(-20deg); }
          100% { transform: translateX(400%) skewX(-20deg); }
        }
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: .5; }
        }
        @keyframes fadeIn {
          from { opacity: 0; }
          to { opacity: 1; }
        }
      `}} />
    </div>
  );
};
