import React, { useState } from 'react';
import { 
  FileUp, 
  FileText, 
  CheckCircle2, 
  X, 
  AlertCircle, 
  Trash2,
  Calendar,
  Users
} from 'lucide-react';

// --- Presentational Components ---

const DragDropZone = ({ onDrop, isDragging, setIsDragging }: { 
  onDrop: (files: FileList) => void, 
  isDragging: boolean, 
  setIsDragging: (val: boolean) => void 
}) => (
  <div 
    onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
    onDragLeave={() => setIsDragging(false)}
    onDrop={(e) => {
      e.preventDefault();
      setIsDragging(false);
      if (e.dataTransfer.files) onDrop(e.dataTransfer.files);
    }}
    style={{
      border: `2px dashed ${isDragging ? 'var(--brand)' : 'var(--border-light)'}`,
      borderRadius: '32px',
      padding: '5rem 2rem',
      textAlign: 'center',
      backgroundColor: isDragging ? 'var(--bg-base)' : 'white',
      transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
      cursor: 'pointer',
      transform: isDragging ? 'scale(1.02)' : 'scale(1)'
    }}
    className="group"
  >
    <div style={{
      width: '80px',
      height: '80px',
      backgroundColor: isDragging ? 'var(--brand)' : 'var(--bg-base)',
      color: isDragging ? 'white' : 'var(--brand)',
      borderRadius: '24px',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      margin: '0 auto 2rem',
      transition: 'all 0.3s'
    }}>
      <FileUp size={40} />
    </div>
    <h3 style={{ fontSize: '1.5rem', fontWeight: 800, marginBottom: '1rem' }}>
      Перетащите файлы сюда
    </h3>
    <p className="text-text-secondary" style={{ maxWidth: '400px', margin: '0 auto 2.5rem' }}>
      Загрузите Excel-файлы (.xlsx) с нагрузкой преподавателей, списком аудиторий и учебными планами.
    </p>
    <button className="btn-primary" style={{ margin: '0 auto' }}>
      Выбрать на компьютере
    </button>
  </div>
);

const FileListItem = ({ file, onRemove }: { file: { name: string, size: string, status: string }, onRemove: () => void }) => (
  <div className="card" style={{ padding: '1.25rem', display: 'flex', alignItems: 'center', gap: '1.5rem', transition: 'all 0.2s' }}>
    <div style={{
      width: '48px',
      height: '48px',
      borderRadius: '12px',
      backgroundColor: 'var(--bg-base)',
      color: 'var(--brand)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center'
    }}>
      <FileText size={24} />
    </div>
    
    <div style={{ flex: 1 }}>
      <div className="flex items-center gap-2">
        <span style={{ fontWeight: 700 }}>{file.name}</span>
        <span style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)' }}>{file.size}</span>
      </div>
      <div className="flex items-center gap-4 mt-1.5">
        <div style={{ height: '6px', backgroundColor: 'var(--bg-base)', borderRadius: '100px', flex: 1, overflow: 'hidden' }}>
          <div style={{ height: '100%', width: '100%', backgroundColor: 'var(--brand)', borderRadius: '100px' }} />
        </div>
        <span style={{ fontSize: '0.75rem', fontWeight: 800, color: 'var(--brand)', display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
          <CheckCircle2 size={14} /> Готов
        </span>
      </div>
    </div>

    <button 
      onClick={onRemove}
      style={{
        padding: '0.5rem',
        color: 'var(--text-tertiary)',
        borderRadius: '8px',
        transition: 'all 0.2s'
      }}
      className="hover:bg-rose-50 hover:text-rose-500"
    >
      <Trash2 size={20} />
    </button>
  </div>
);

// --- Container Component ---

export const ImportPage: React.FC = () => {
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  
  const [files, setFiles] = useState([
    { id: -1, name: 'Нагрузка_ИТ_2024.xlsx', size: '2.4 MB', status: 'ready', date: new Date().toISOString() },
    { id: -2, name: 'Аудиторный_фонд.xlsx', size: '1.1 MB', status: 'ready', date: new Date().toISOString() }
  ]);

  React.useEffect(() => {
    fetchHistory();
  }, []);

  const fetchHistory = async () => {
    try {
      const res = await fetch('http://localhost:8000/api/v1/scheduler/import/history');
      if (res.ok) {
        const data = await res.json();
        const mapped = data.map((b: any) => ({
          id: b.id,
          name: b.filename,
          size: b.file_type,
          status: 'ready',
          date: b.created_date
        }));
        setFiles(prev => {
          const locals = prev.filter(p => p.id < 0);
          return [...locals, ...mapped];
        });
      }
    } catch(err) {
      console.error(err);
    }
  };

  const uploadFile = async (file: File) => {
    setIsUploading(true);
    setError(null);
    setSuccessMsg(null);
    const formData = new FormData();
    formData.append('file', file);
    try {
      const res = await fetch('http://localhost:8000/api/v1/scheduler/import/streams', {
        method: 'POST',
        body: formData,
      });
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || 'Upload failed');
      }
      const data = await res.json();
      setSuccessMsg(`Успешно загружено! Добавлено потоков: ${data.streams_added}, групп: ${data.groups_added}`);
      await fetchHistory();
    } catch(err: any) {
      setError(err.message);
    } finally {
      setIsUploading(false);
    }
  };

  const handleDrop = (uploadedFiles: FileList) => {
    if (uploadedFiles.length > 0) {
      uploadFile(uploadedFiles[0]);
    }
  };

  const removeFile = async (index: number) => {
    const file = files[index];
    if (file.id > 0) {
      try {
        const res = await fetch(`http://localhost:8000/api/v1/scheduler/import/history/${file.id}`, { method: 'DELETE' });
        if (res.ok) {
           setSuccessMsg('Файл и связанные данные успешно удалены.');
           await fetchHistory();
        }
      } catch(err) { console.error(err); }
    } else {
      setFiles(files.filter((_, i) => i !== index));
    }
  };

  return (
    <div className="space-y-10">
      <header>
        <h1 className="text-3xl font-bold text-brand">Импорт данных</h1>
        <p className="text-text-secondary mt-2">Загрузите необходимые справочники для работы алгоритма.</p>
        
        {error && <div style={{marginTop: '1rem', padding: '1rem', background: '#fee2e2', color: '#b91c1c', borderRadius: '12px'}}>{error}</div>}
        {successMsg && <div style={{marginTop: '1rem', padding: '1rem', background: '#dcfce7', color: '#15803d', borderRadius: '12px'}}>{successMsg}</div>}
      </header>

      <div style={{ display: 'grid', gridTemplateColumns: '1.5fr 1fr', gap: '2.5rem' }}>
        <div className="space-y-8">
          <DragDropZone 
            onDrop={handleDrop} 
            isDragging={isDragging} 
            setIsDragging={setIsDragging} 
          />

          <div className="space-y-4">
            <h3 style={{ fontSize: '1.125rem', fontWeight: 800, display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              Загруженные файлы
              <span style={{ fontSize: '0.75rem', padding: '0.125rem 0.5rem', backgroundColor: 'var(--bg-base)', borderRadius: '100px', color: 'var(--text-tertiary)' }}>
                {files.length}
              </span>
              {isUploading && <span style={{ fontSize: '0.8rem', color: 'var(--brand)' }}>Загрузка...</span>}
            </h3>
            <div className="space-y-3">
              {files.map((file, idx) => (
                <FileListItem 
                  key={idx} 
                  file={file} 
                  onRemove={() => removeFile(idx)} 
                />
              ))}
              {files.length === 0 && (
                <div style={{ padding: '3rem', textAlign: 'center', color: 'var(--text-tertiary)', border: '1px dashed var(--border-light)', borderRadius: '24px' }}>
                  Нет загруженных файлов
                </div>
              )}
            </div>
          </div>
        </div>

        <div className="space-y-6">
          <div className="card" style={{ padding: '1.75rem', backgroundColor: 'var(--brand)', color: 'white' }}>
            <h4 style={{ fontSize: '1.125rem', fontWeight: 800, marginBottom: '1.25rem', display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
              <AlertCircle size={24} /> Статус конвейера
            </h4>
            <div className="space-y-5">
              <div className="flex items-center gap-3">
                <div style={{ width: '24px', height: '24px', borderRadius: '50%', border: '2px solid white', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '10px', fontWeight: 900 }}>1</div>
                <div style={{ flex: 1, fontSize: '0.875rem' }}>Нагрузка преподавателей</div>
                <CheckCircle2 size={18} fill="white" color="var(--brand)" />
              </div>
              <div className="flex items-center gap-3">
                <div style={{ width: '24px', height: '24px', borderRadius: '50%', border: '2px solid white', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '10px', fontWeight: 900 }}>2</div>
                <div style={{ flex: 1, fontSize: '0.875rem' }}>Аудиторный фонд</div>
                <CheckCircle2 size={18} fill="white" color="var(--brand)" />
              </div>
              <div className="flex items-center gap-3" style={{ opacity: 0.6 }}>
                <div style={{ width: '24px', height: '24px', borderRadius: '50%', border: '2px solid white', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '10px', fontWeight: 900 }}>3</div>
                <div style={{ flex: 1, fontSize: '0.875rem' }}>Учебные планы групп</div>
                <X size={18} color="white" />
              </div>
              <div className="flex items-center gap-3" style={{ opacity: 0.6 }}>
                <div style={{ width: '24px', height: '24px', borderRadius: '50%', border: '2px solid white', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '10px', fontWeight: 900 }}>4</div>
                <div style={{ flex: 1, fontSize: '0.875rem' }}>Потоки обучающихся</div>
                <X size={18} color="white" />
              </div>
            </div>
            <button style={{ 
              width: '100%', 
              backgroundColor: 'white', 
              color: 'var(--brand)', 
              border: 'none', 
              padding: '0.875rem', 
              borderRadius: '12px', 
              marginTop: '1.5rem',
              fontWeight: 800,
              fontSize: '0.875rem'
            }}>
              Настроить блокировки
            </button>
          </div>

          <div className="card" style={{ padding: '1.5rem' }}>
            <h4 style={{ fontWeight: 800, marginBottom: '1rem' }}>Типы данных</h4>
            <div className="space-y-4">
              <div className="flex items-center gap-3 text-sm">
                <Users size={18} color="var(--brand)" />
                <span>Список групп и потоков</span>
              </div>
              <div className="flex items-center gap-3 text-sm">
                <Calendar size={18} color="var(--brand)" />
                <span>Календарный график</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
